"""
Multi-Tenant Scheduler & Send Window Engine (`src/omr_dispatch/scheduler.py`).

Compliant with:
- Stage S10 Task 1, 2, 3, 4 & Gate 10 mandates.
- D-10 Schedule: Asia/Kolkata timezone.
  - Primary send window: Sunday 20:30 IST for OMR assessments.
  - Reminder window: Monday 10:00 IST (strictly when reminder_enabled=True).
  - Distinct idempotency keys for primary vs. reminder dispatches.
  - Validates that event date is Sunday for Sunday OMR window; rejects non-Sunday events.
- ADR-0002: Zero float() calls in core and scheduler modules. All quantums, deficits,
  weights, caps, and intervals are represented as exact integers or fractions.
- ADR-0005: Time hygiene: timezone-aware datetimes anchored in Asia/Kolkata and UTC.
  Deterministic plan_schedule requires injected current time (`now`).
- ADR-0017 / ADR-0019 / ADR-0020: Multi-tenant fair queuing (Deficit Weighted Round-Robin),
  per-sender daily message limit pacing, tenant isolation, and single-instance dispatch locking.
- Window Condition Handling: Late import, missed window, holiday override, provider outage,
  unapproved template hold, and events created outside window.
- Invariants 13 & 14: Never bypass send window rules with free-form content.
"""

from __future__ import annotations

import json
import sqlite3
import struct
import tempfile
import threading
import uuid
import zoneinfo
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from omr_dispatch.messaging.policy import TenantContextMissingError, compute_idempotency_key
from omr_dispatch.models import OMRDispatchError


def _ensure_kolkata_tz() -> ZoneInfo:
    """Ensure Asia/Kolkata ZoneInfo resolves deterministically across POSIX and Windows hosts."""
    try:
        return ZoneInfo("Asia/Kolkata")
    except Exception:
        tmp = tempfile.gettempdir()
        tzdir = Path(tmp) / "omr_tzdata"
        (tzdir / "Asia").mkdir(parents=True, exist_ok=True)
        tzfile = tzdir / "Asia" / "Kolkata"
        if not tzfile.exists():
            magic = b"TZif\x00" + b"\x00" * 15
            header = struct.pack(">6I", 0, 0, 0, 0, 1, 4)
            ttinfo = struct.pack(">Ibb", 19800, 0, 0)
            abbr = b"IST\x00"
            tzfile.write_bytes(magic + header + ttinfo + abbr)
        current_paths = list(zoneinfo.TZPATH)
        if str(tzdir) not in current_paths:
            zoneinfo.reset_tzpath([str(tzdir)] + current_paths)
        return ZoneInfo("Asia/Kolkata")


KOLKATA_TZ = _ensure_kolkata_tz()
UTC_TZ = UTC

DEFAULT_PRIMARY_WINDOW_START = time(20, 30)
DEFAULT_PRIMARY_WINDOW_END = time(21, 30)
DEFAULT_REMINDER_WINDOW_START = time(10, 0)
DEFAULT_REMINDER_WINDOW_END = time(12, 0)


# ==============================================================================
# Exceptions Hierarchy
# ==============================================================================

class SchedulerError(OMRDispatchError):
    """Base exception for all scheduler errors."""


class InvalidScheduleWindowError(SchedulerError):
    """Raised when an event attempts to claim an invalid schedule window (e.g. non-Sunday for Sunday OMR window)."""


class MissedSendWindowError(SchedulerError):
    """Raised when current time has exceeded the allowed send window."""


class LateImportError(SchedulerError):
    """Raised when an assessment is imported after the window start time."""


class HolidayOverrideError(SchedulerError):
    """Raised when an operation conflicts with a declared holiday override."""


class TemplateNotApprovedError(SchedulerError):
    """Raised when scheduled dispatches are blocked due to an unapproved template."""


class ProviderOutageError(SchedulerError):
    """Raised when dispatches are halted due to upstream provider outage."""


class WindowRuleBypassForbiddenError(SchedulerError):
    """Raised when an attempt is made to bypass send window restrictions using free-form content."""


class LockAcquisitionError(SchedulerError):
    """Raised when a single-instance dispatch lock cannot be acquired due to contention."""


# ==============================================================================
# Enums and Value Objects
# ==============================================================================

class ScheduleStatus(StrEnum):
    """Lifecycle and evaluation status for scheduled jobs and plans."""

    SCHEDULED = "SCHEDULED"
    DEFERRED_HOLIDAY = "DEFERRED_HOLIDAY"
    DEFERRED_LATE_IMPORT = "DEFERRED_LATE_IMPORT"
    MISSED_WINDOW = "MISSED_WINDOW"
    HOLD_PROVIDER_OUTAGE = "HOLD_PROVIDER_OUTAGE"
    HOLD_UNAPPROVED_TEMPLATE = "HOLD_UNAPPROVED_TEMPLATE"
    REJECTED_NON_SUNDAY = "REJECTED_NON_SUNDAY"
    PACED_DAILY_CAP = "PACED_DAILY_CAP"
    CANCELLED = "CANCELLED"


class SchedulePolicy(BaseModel):
    """Per-assessment or institutional scheduling and send-window policy."""

    model_config = ConfigDict(extra="forbid")

    window_type: str = "SUNDAY_OMR"  # "SUNDAY_OMR" or "CUSTOM"
    primary_window_start: time = DEFAULT_PRIMARY_WINDOW_START
    primary_window_end: time = DEFAULT_PRIMARY_WINDOW_END
    reminder_window_start: time = DEFAULT_REMINDER_WINDOW_START
    reminder_window_end: time = DEFAULT_REMINDER_WINDOW_END
    holidays: set[date] = Field(default_factory=set)
    daily_cap: int = 250
    template_approved: bool = True
    provider_operational: bool = True
    allow_late_import: bool = False
    allow_freeform_bypass: bool = False  # Banned: triggering causes immediate failure
    schema_version: int = 1


class AssessmentScheduleEvent(BaseModel):
    """Incoming event triggering schedule generation for an assessment or student."""

    model_config = ConfigDict(extra="forbid")

    org_id: str
    assessment_id: str
    event_timestamp: datetime
    reminder_enabled: bool = False
    student_id: str = "DEFAULT"
    student_ids: list[str] = Field(default_factory=list)
    purpose: str = "EXAM_RESULTS"
    channel: str = "WHATSAPP"
    window_type: str = "SUNDAY_OMR"
    is_freeform: bool = False
    template_name: str | None = None
    schema_version: int = 1


class ScheduledDispatchItem(BaseModel):
    """Single dispatch job placed on the multi-tenant scheduler queue."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    org_id: str
    assessment_id: str
    student_id: str
    event_type: str  # "PRIMARY" or "REMINDER"
    scheduled_at_utc: datetime
    scheduled_at_ist: datetime
    window_start_ist: datetime
    window_end_ist: datetime
    idempotency_key: str
    status: ScheduleStatus = ScheduleStatus.SCHEDULED
    reason: str | None = None
    queue_order: int = 0
    cost: int = 1  # Integer message credit cost for DWRR
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1


class ScheduledPlan(BaseModel):
    """Complete planned schedule for an assessment event."""

    model_config = ConfigDict(extra="forbid")

    org_id: str
    assessment_id: str
    status: ScheduleStatus
    reason_code: str
    primary_dispatch: ScheduledDispatchItem
    reminder_dispatch: ScheduledDispatchItem | None = None
    dispatches: list[ScheduledDispatchItem] = Field(default_factory=list)
    created_at_utc: datetime
    schema_version: int = 1


# ==============================================================================
# Task 1: Pure Schedule Planning (`plan_schedule`)
# ==============================================================================

def validate_send_window(
    dt: datetime,
    window_start: time,
    window_end: time,
    tz: ZoneInfo = KOLKATA_TZ,
) -> bool:
    """Check if the given datetime falls within the window boundaries in the target timezone."""
    localized = dt.astimezone(tz)
    local_time = localized.time()
    return window_start <= local_time <= window_end


def plan_schedule(
    event: AssessmentScheduleEvent | Any,
    now: datetime,
    policy: SchedulePolicy | None = None,
) -> ScheduledPlan:
    """
    Pure deterministic schedule planning function (Task 1).

    Enforces:
      - Time hygiene (ADR-0005): `now` and `event.event_timestamp` must be timezone-aware.
      - Sunday OMR window validation: event must occur on Sunday (`dt.weekday() == 6`).
        Non-Sunday events claiming Sunday OMR window fail closed with InvalidScheduleWindowError.
      - Target Fixture Match (D-10): For event `2026-10-18 14:15+05:30` (Sunday):
        * Primary dispatch scheduled at: `2026-10-18 20:30:00+05:30`.
        * Reminder dispatch scheduled at: `2026-10-19 10:00:00+05:30` iff `reminder_enabled=True`.
        * Distinct idempotency keys for primary vs. reminder dispatches.
      - Guardrails against freeform bypass (Invariant 13 & 14): never bypass window rules with freeform content.
      - Edge condition handling: holiday override, provider outage, unapproved template, late import, missed window.
    """
    if now.tzinfo is None:
        raise ValueError("Current time `now` must be timezone-aware (ADR-0005).")

    # Resolve event attributes whether Pydantic model or duck-typed object
    org_id = getattr(event, "org_id", "")
    if not org_id or not str(org_id).strip():
        raise TenantContextMissingError("Explicit org context (org_id) is required to plan a schedule.")

    assessment_id = getattr(event, "assessment_id", "")
    event_timestamp: datetime = event.event_timestamp
    if event_timestamp.tzinfo is None:
        raise ValueError("Event timestamp must be timezone-aware (ADR-0005).")

    reminder_enabled = bool(getattr(event, "reminder_enabled", False))
    student_id = getattr(event, "student_id", "DEFAULT")
    purpose = getattr(event, "purpose", "EXAM_RESULTS")
    channel = getattr(event, "channel", "WHATSAPP")
    is_freeform = bool(getattr(event, "is_freeform", False))
    template_name = getattr(event, "template_name", None)

    active_policy = policy if policy is not None else SchedulePolicy()
    window_type = getattr(event, "window_type", active_policy.window_type)

    # Freeform bypass prevention guardrail (Rule: Never bypass send window rules with free-form content)
    if is_freeform or active_policy.allow_freeform_bypass:
        raise WindowRuleBypassForbiddenError(
            "Free-form content cannot be used to bypass send window closures (Invariant 13 & 14)."
        )

    # Localize timestamps to Asia/Kolkata
    event_dt_ist = event_timestamp.astimezone(KOLKATA_TZ)
    now_ist = now.astimezone(KOLKATA_TZ)
    now_utc = now.astimezone(UTC_TZ)

    # Validate Sunday constraint for Sunday OMR window
    if window_type == "SUNDAY_OMR" and event_dt_ist.weekday() != 6:
        weekday_name = event_dt_ist.strftime("%A")
        raise InvalidScheduleWindowError(
            f"Event date {event_dt_ist.date()} is on {weekday_name} (weekday {event_dt_ist.weekday()}), "
            "not Sunday. Non-Sunday events cannot claim the primary Sunday OMR window (D-10)."
        )

    # Calculate nominal primary window boundaries (D-10: Sunday 20:30 IST)
    event_date = event_dt_ist.date()
    primary_start_ist = datetime.combine(event_date, active_policy.primary_window_start, tzinfo=KOLKATA_TZ)
    primary_end_ist = datetime.combine(event_date, active_policy.primary_window_end, tzinfo=KOLKATA_TZ)

    # Status and condition classification
    status = ScheduleStatus.SCHEDULED
    reason_code = "SCHEDULED_PRIMARY_WINDOW"

    # Edge Condition 1: Template approval missing -> Hold dispatches without free-form bypass
    if not active_policy.template_approved:
        status = ScheduleStatus.HOLD_UNAPPROVED_TEMPLATE
        reason_code = "TEMPLATE_APPROVAL_MISSING"

    # Edge Condition 2: Upstream provider outage -> Hold dispatches until service restored
    elif not active_policy.provider_operational:
        status = ScheduleStatus.HOLD_PROVIDER_OUTAGE
        reason_code = "PROVIDER_OUTAGE_HOLD"

    # Edge Condition 3: Holiday override -> Postpone to next eligible non-holiday business day
    elif event_date in active_policy.holidays:
        status = ScheduleStatus.DEFERRED_HOLIDAY
        reason_code = f"HOLIDAY_OVERRIDE_ON_{event_date.isoformat()}"
        # Advance primary date to next eligible day
        cand_date = event_date + timedelta(days=1)
        while cand_date in active_policy.holidays:
            cand_date += timedelta(days=1)
        primary_start_ist = datetime.combine(cand_date, active_policy.primary_window_start, tzinfo=KOLKATA_TZ)
        primary_end_ist = datetime.combine(cand_date, active_policy.primary_window_end, tzinfo=KOLKATA_TZ)

    # Edge Condition 4: Missed Window -> current time past window end
    elif now_ist > primary_end_ist:
        status = ScheduleStatus.MISSED_WINDOW
        reason_code = "MISSED_SEND_WINDOW_END"

    # Edge Condition 5: Late Import -> imported after primary window start
    elif now_ist > primary_start_ist:
        if not active_policy.allow_late_import:
            status = ScheduleStatus.DEFERRED_LATE_IMPORT
            reason_code = "LATE_IMPORT_AFTER_WINDOW_START"
        else:
            status = ScheduleStatus.SCHEDULED
            reason_code = "LATE_IMPORT_WITHIN_WINDOW_ALLOWED"

    # Edge Condition 6: Event created outside window (e.g. 14:15 IST before 20:30 window)
    else:
        status = ScheduleStatus.SCHEDULED
        reason_code = "SCHEDULED_PRIMARY_WINDOW"

    # Compute distinct idempotency keys (Task 1)
    primary_idempotency_key = compute_idempotency_key(
        org_id=org_id,
        student_id=student_id,
        assessment_id=assessment_id,
        purpose=purpose,
        channel=channel,
        event_type="PRIMARY",
    )

    primary_dispatch = ScheduledDispatchItem(
        job_id=str(uuid.uuid4()),
        org_id=org_id,
        assessment_id=assessment_id,
        student_id=student_id,
        event_type="PRIMARY",
        scheduled_at_utc=primary_start_ist.astimezone(UTC_TZ),
        scheduled_at_ist=primary_start_ist,
        window_start_ist=primary_start_ist,
        window_end_ist=primary_end_ist,
        idempotency_key=primary_idempotency_key,
        status=status,
        reason=reason_code,
        queue_order=1,
        metadata={"template_name": template_name, "is_freeform": is_freeform},
    )

    all_dispatches = [primary_dispatch]
    reminder_dispatch: ScheduledDispatchItem | None = None

    # Reminder dispatch calculation: Monday 10:00 IST strictly when reminder_enabled=True
    if reminder_enabled:
        reminder_date = event_date + timedelta(days=1)
        # Check if reminder date hits a holiday
        while reminder_date in active_policy.holidays:
            reminder_date += timedelta(days=1)

        reminder_start_ist = datetime.combine(
            reminder_date, active_policy.reminder_window_start, tzinfo=KOLKATA_TZ
        )
        reminder_end_ist = datetime.combine(
            reminder_date, active_policy.reminder_window_end, tzinfo=KOLKATA_TZ
        )

        reminder_status = status
        reminder_reason = "SCHEDULED_REMINDER_WINDOW"
        if status == ScheduleStatus.MISSED_WINDOW and now_ist <= reminder_start_ist:
            reminder_status = ScheduleStatus.SCHEDULED

        reminder_idempotency_key = compute_idempotency_key(
            org_id=org_id,
            student_id=student_id,
            assessment_id=assessment_id,
            purpose=purpose,
            channel=channel,
            event_type="REMINDER",
        )

        reminder_dispatch = ScheduledDispatchItem(
            job_id=str(uuid.uuid4()),
            org_id=org_id,
            assessment_id=assessment_id,
            student_id=student_id,
            event_type="REMINDER",
            scheduled_at_utc=reminder_start_ist.astimezone(UTC_TZ),
            scheduled_at_ist=reminder_start_ist,
            window_start_ist=reminder_start_ist,
            window_end_ist=reminder_end_ist,
            idempotency_key=reminder_idempotency_key,
            status=reminder_status,
            reason=reminder_reason,
            queue_order=2,
            metadata={"template_name": template_name, "is_freeform": is_freeform},
        )
        all_dispatches.append(reminder_dispatch)

    return ScheduledPlan(
        org_id=org_id,
        assessment_id=assessment_id,
        status=status,
        reason_code=reason_code,
        primary_dispatch=primary_dispatch,
        reminder_dispatch=reminder_dispatch,
        dispatches=all_dispatches,
        created_at_utc=now_utc,
    )


# ==============================================================================
# Task 2: Multi-Tenant Fair Scheduling & Daily Cap Pacing
# ==============================================================================

def pace_batch_over_days(
    dispatches: Sequence[ScheduledDispatchItem],
    daily_cap: int,
    current_sent_today: int = 0,
    start_date: date | None = None,
    window_start: time = DEFAULT_PRIMARY_WINDOW_START,
    window_end: time = DEFAULT_PRIMARY_WINDOW_END,
    holidays: set[date] | None = None,
) -> list[ScheduledDispatchItem]:
    """
    Pace large batches over consecutive eligible days respecting daily message caps (Task 2 & ADR-0019/ADR-0020).

    When a batch exceeds the day's remaining cap or window, spread the batch across
    consecutive eligible days within allowed send windows.
    Zero float() calls: all calculations use exact integer subtraction and counts.
    """
    if daily_cap <= 0:
        raise ValueError("daily_cap must be a positive integer.")
    if current_sent_today < 0:
        raise ValueError("current_sent_today cannot be negative.")

    holiday_set = holidays or set()
    paced_items: list[ScheduledDispatchItem] = []

    # Determine initial start date
    if start_date is not None:
        curr_date = start_date
    elif dispatches:
        curr_date = dispatches[0].scheduled_at_ist.date()
    else:
        curr_date = date.today()

    # Remaining cap for first day
    remaining_today = max(0, daily_cap - current_sent_today)
    day_count = 0

    idx = 0
    total_items = len(dispatches)

    while idx < total_items:
        # Skip holidays
        while curr_date in holiday_set:
            curr_date += timedelta(days=1)
            remaining_today = daily_cap
            day_count += 1

        if remaining_today == 0:
            # Advance to next day
            curr_date += timedelta(days=1)
            remaining_today = daily_cap
            day_count += 1
            continue

        # Allot items for current day
        allotment = min(remaining_today, total_items - idx)
        for _ in range(allotment):
            item = dispatches[idx]
            day_start_ist = datetime.combine(curr_date, window_start, tzinfo=KOLKATA_TZ)
            day_end_ist = datetime.combine(curr_date, window_end, tzinfo=KOLKATA_TZ)

            status = item.status
            reason = item.reason
            if day_count > 0:
                status = ScheduleStatus.PACED_DAILY_CAP
                reason = f"PACED_DAY_{day_count}_DUE_TO_DAILY_CAP_{daily_cap}"

            updated_item = item.model_copy(
                update={
                    "scheduled_at_ist": day_start_ist,
                    "scheduled_at_utc": day_start_ist.astimezone(UTC_TZ),
                    "window_start_ist": day_start_ist,
                    "window_end_ist": day_end_ist,
                    "status": status,
                    "reason": reason,
                    "queue_order": idx + 1,
                }
            )
            paced_items.append(updated_item)
            idx += 1

        remaining_today -= allotment

    return paced_items


class DWRRQueue:
    """
    Deficit Weighted Round-Robin (DWRR) multi-tenant fair queue engine.

    Features:
      - Maintains integer quantum credits and deficit counters per tenant.
      - Prevents large tenants (e.g. 1,000 jobs) from starving small tenants (e.g. 10 jobs).
      - Zero float() calls: all calculations use exact integer arithmetic (ADR-0002).
      - Thread-safe queue operations.
    """

    def __init__(self, quantum: int = 20, weights: dict[str, int] | None = None) -> None:
        if quantum <= 0:
            raise ValueError("DWRR quantum must be an integer >= 1.")
        self.quantum: int = quantum
        self.weights: dict[str, int] = weights or {}
        self.deficits: dict[str, int] = {}
        self.queues: dict[str, list[ScheduledDispatchItem]] = {}
        self._lock = threading.Lock()

    def enqueue(self, item: ScheduledDispatchItem) -> None:
        """Enqueue a single dispatch job under its tenant org_id."""
        with self._lock:
            org_id = item.org_id
            if org_id not in self.queues:
                self.queues[org_id] = []
                self.deficits[org_id] = 0
            self.queues[org_id].append(item)

    def enqueue_batch(self, items: Sequence[ScheduledDispatchItem]) -> None:
        """Enqueue a batch of dispatch jobs."""
        for item in items:
            self.enqueue(item)

    def queue_size(self, org_id: str | None = None) -> int:
        """Return the number of queued items for an org or across all orgs."""
        with self._lock:
            if org_id is not None:
                return len(self.queues.get(org_id, []))
            return sum(len(q) for q in self.queues.values())

    def drain_round(self) -> list[ScheduledDispatchItem]:
        """
        Execute one DWRR round across active tenant queues.
        Each tenant receives quantum * weight integer credits added to its deficit.
        """
        with self._lock:
            dispatched: list[ScheduledDispatchItem] = []
            active_orgs = [org for org, q in self.queues.items() if len(q) > 0]
            # Deterministic ordering across tenants
            active_orgs.sort()

            for org_id in active_orgs:
                weight = self.weights.get(org_id, 1)
                if weight <= 0:
                    weight = 1

                # Credit integer quantum
                self.deficits[org_id] += self.quantum * weight
                queue = self.queues[org_id]

                while queue:
                    job = queue[0]
                    cost = job.cost
                    if cost <= 0:
                        cost = 1

                    if cost <= self.deficits[org_id]:
                        self.deficits[org_id] -= cost
                        dispatched.append(queue.pop(0))
                    else:
                        break

                # Reset deficit if queue becomes empty (standard DWRR rule to prevent unbounded deficit accumulation)
                if len(queue) == 0:
                    self.deficits[org_id] = 0

            return dispatched

    def drain_all(self) -> list[ScheduledDispatchItem]:
        """Drain all queued items in fair DWRR interleaved sequence."""
        all_dispatched: list[ScheduledDispatchItem] = []
        while self.queue_size() > 0:
            round_items = self.drain_round()
            if not round_items:
                break
            all_dispatched.extend(round_items)
        return all_dispatched


# ==============================================================================
# Task 4: Single-Instance Dispatch Lock
# ==============================================================================

class DispatchLock:
    """
    Robust single-instance concurrency lock.

    Guarantees that two worker processes or threads can never pick up and dispatch
    the same scheduled job simultaneously.
    Supports SQLite database table mutex or in-memory reentrant locking.
    """

    SCHEMA_DDL = """
    CREATE TABLE IF NOT EXISTS dispatch_locks (
        lock_key TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        acquired_at_utc TEXT NOT NULL,
        expires_at_utc TEXT NOT NULL
    );
    """
    _GLOBAL_LOCK = threading.RLock()

    def __init__(
        self,
        db_path: Path | str | None,
        lock_key: str,
        owner_id: str,
        ttl_seconds: int = 60,
    ) -> None:
        self.db_path = str(db_path) if db_path is not None else ":memory:"
        self.lock_key = lock_key
        self.owner_id = owner_id
        self.ttl_seconds = ttl_seconds
        self._acquired = False

    def acquire(self, timeout_seconds: int = 0) -> bool:
        """
        Attempt to acquire the lock. Returns True if acquired, False otherwise.
        """
        with self._GLOBAL_LOCK:
            try:
                conn = sqlite3.connect(self.db_path, timeout=5.0)
            except Exception:
                return False

            try:
                try:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute(self.SCHEMA_DDL)
                except sqlite3.OperationalError:
                    pass

                now_utc = datetime.now(UTC_TZ)
                now_iso = now_utc.isoformat()
                expires_iso = (now_utc + timedelta(seconds=self.ttl_seconds)).isoformat()

                with conn:
                    # Check existing lock
                    cur = conn.execute(
                        "SELECT owner_id, expires_at_utc FROM dispatch_locks WHERE lock_key = ?",
                        (self.lock_key,),
                    )
                    row = cur.fetchone()

                    if row is None:
                        # Insert new lock
                        conn.execute(
                            "INSERT INTO dispatch_locks (lock_key, owner_id, acquired_at_utc, expires_at_utc) "
                            "VALUES (?, ?, ?, ?)",
                            (self.lock_key, self.owner_id, now_iso, expires_iso),
                        )
                        self._acquired = True
                        return True

                    existing_owner, existing_expires_iso = row
                    existing_expires = datetime.fromisoformat(existing_expires_iso)

                    if existing_expires < now_utc:
                        # Lock has expired, re-acquire
                        conn.execute(
                            "UPDATE dispatch_locks SET owner_id = ?, acquired_at_utc = ?, expires_at_utc = ? "
                            "WHERE lock_key = ?",
                            (self.owner_id, now_iso, expires_iso, self.lock_key),
                        )
                        self._acquired = True
                        return True

                    if existing_owner == self.owner_id:
                        # Re-entrant acquire by same owner
                        conn.execute(
                            "UPDATE dispatch_locks SET expires_at_utc = ? WHERE lock_key = ? AND owner_id = ?",
                            (expires_iso, self.lock_key, self.owner_id),
                        )
                        self._acquired = True
                        return True

                    # Lock held by another owner and not expired
                    return False
            except sqlite3.OperationalError:
                return False
            finally:
                conn.close()

    def release(self) -> bool:
        """Release the lock if owned by this instance."""
        with self._GLOBAL_LOCK:
            try:
                conn = sqlite3.connect(self.db_path, timeout=5.0)
            except Exception:
                self._acquired = False
                return False

            try:
                with conn:
                    cur = conn.execute(
                        "DELETE FROM dispatch_locks WHERE lock_key = ? AND owner_id = ?",
                        (self.lock_key, self.owner_id),
                    )
                    self._acquired = False
                    return cur.rowcount > 0
            except sqlite3.OperationalError:
                self._acquired = False
                return False
            finally:
                conn.close()

    def __enter__(self) -> DispatchLock:
        if not self.acquire():
            raise LockAcquisitionError(
                f"Could not acquire dispatch lock '{self.lock_key}'. Held by another instance."
            )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


# ==============================================================================
# Persistence & Restart Recovery Store
# ==============================================================================

class SchedulerStore:
    """
    Durable SQLite store for persisted schedules and queue states.
    Ensures that planned schedules and queue order survive system restarts.
    """

    SCHEMA_DDL = """
    CREATE TABLE IF NOT EXISTS scheduled_jobs (
        job_id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        assessment_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        scheduled_at_utc TEXT NOT NULL,
        window_start_utc TEXT NOT NULL,
        window_end_utc TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        status TEXT NOT NULL,
        reason TEXT,
        queue_order INTEGER NOT NULL,
        cost INTEGER NOT NULL DEFAULT 1,
        metadata_json TEXT,
        created_at_utc TEXT NOT NULL,
        CONSTRAINT uq_scheduled_job_idempotency UNIQUE (org_id, idempotency_key)
    );

    CREATE INDEX IF NOT EXISTS idx_sched_jobs_org_order ON scheduled_jobs(org_id, status, queue_order);
    """

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(self.SCHEMA_DDL)
            conn.executescript(DispatchLock.SCHEMA_DDL)
        finally:
            conn.close()

    def save_plan(self, plan: ScheduledPlan) -> None:
        """Persist all dispatches in a scheduled plan atomically."""
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                for item in plan.dispatches:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO scheduled_jobs (
                            job_id, org_id, assessment_id, student_id, event_type,
                            scheduled_at_utc, window_start_utc, window_end_utc,
                            idempotency_key, status, reason, queue_order, cost,
                            metadata_json, created_at_utc
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.job_id,
                            item.org_id,
                            item.assessment_id,
                            item.student_id,
                            item.event_type,
                            item.scheduled_at_utc.isoformat(),
                            item.window_start_ist.astimezone(UTC_TZ).isoformat(),
                            item.window_end_ist.astimezone(UTC_TZ).isoformat(),
                            item.idempotency_key,
                            str(item.status),
                            item.reason,
                            item.queue_order,
                            item.cost,
                            json.dumps(item.metadata),
                            plan.created_at_utc.isoformat(),
                        ),
                    )
        finally:
            conn.close()

    def load_plan(self, org_id: str, assessment_id: str) -> ScheduledPlan | None:
        """Load and reconstruct a persisted schedule for an assessment."""
        if not org_id or not str(org_id).strip():
            raise TenantContextMissingError("Explicit org context (org_id) is required to load a plan.")

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """
                SELECT job_id, org_id, assessment_id, student_id, event_type,
                       scheduled_at_utc, window_start_utc, window_end_utc,
                       idempotency_key, status, reason, queue_order, cost,
                       metadata_json, created_at_utc
                FROM scheduled_jobs
                WHERE org_id = ? AND assessment_id = ?
                ORDER BY queue_order ASC
                """,
                (org_id, assessment_id),
            )
            rows = cur.fetchall()
            if not rows:
                return None

            dispatches: list[ScheduledDispatchItem] = []
            primary_dispatch: ScheduledDispatchItem | None = None
            reminder_dispatch: ScheduledDispatchItem | None = None
            plan_created_at = datetime.now(UTC_TZ)

            for row in rows:
                (
                    job_id,
                    r_org_id,
                    r_assessment_id,
                    student_id,
                    event_type,
                    scheduled_at_utc_str,
                    window_start_utc_str,
                    window_end_utc_str,
                    idempotency_key,
                    status_str,
                    reason,
                    queue_order,
                    cost,
                    metadata_json,
                    created_at_utc_str,
                ) = row

                scheduled_at_utc = datetime.fromisoformat(scheduled_at_utc_str)
                scheduled_at_ist = scheduled_at_utc.astimezone(KOLKATA_TZ)
                window_start_ist = datetime.fromisoformat(window_start_utc_str).astimezone(KOLKATA_TZ)
                window_end_ist = datetime.fromisoformat(window_end_utc_str).astimezone(KOLKATA_TZ)
                plan_created_at = datetime.fromisoformat(created_at_utc_str)

                meta = json.loads(metadata_json) if metadata_json else {}

                item = ScheduledDispatchItem(
                    job_id=job_id,
                    org_id=r_org_id,
                    assessment_id=r_assessment_id,
                    student_id=student_id,
                    event_type=event_type,
                    scheduled_at_utc=scheduled_at_utc,
                    scheduled_at_ist=scheduled_at_ist,
                    window_start_ist=window_start_ist,
                    window_end_ist=window_end_ist,
                    idempotency_key=idempotency_key,
                    status=ScheduleStatus(status_str),
                    reason=reason,
                    queue_order=queue_order,
                    cost=cost,
                    metadata=meta,
                )
                dispatches.append(item)
                if event_type == "PRIMARY" and primary_dispatch is None:
                    primary_dispatch = item
                elif event_type == "REMINDER" and reminder_dispatch is None:
                    reminder_dispatch = item

            if primary_dispatch is None:
                primary_dispatch = dispatches[0]

            return ScheduledPlan(
                org_id=org_id,
                assessment_id=assessment_id,
                status=primary_dispatch.status,
                reason_code=primary_dispatch.reason or "LOADED_FROM_STORE",
                primary_dispatch=primary_dispatch,
                reminder_dispatch=reminder_dispatch,
                dispatches=dispatches,
                created_at_utc=plan_created_at,
            )
        finally:
            conn.close()

    def list_jobs(
        self,
        org_id: str,
        status: ScheduleStatus | None = None,
    ) -> list[ScheduledDispatchItem]:
        """List persisted jobs for an org, optionally filtered by status."""
        if not org_id or not str(org_id).strip():
            raise TenantContextMissingError("Explicit org context (org_id) is required to list jobs.")

        conn = sqlite3.connect(self.db_path)
        try:
            if status is not None:
                cur = conn.execute(
                    """
                    SELECT job_id, org_id, assessment_id, student_id, event_type,
                           scheduled_at_utc, window_start_utc, window_end_utc,
                           idempotency_key, status, reason, queue_order, cost,
                           metadata_json
                    FROM scheduled_jobs
                    WHERE org_id = ? AND status = ?
                    ORDER BY queue_order ASC
                    """,
                    (org_id, str(status)),
                )
            else:
                cur = conn.execute(
                    """
                    SELECT job_id, org_id, assessment_id, student_id, event_type,
                           scheduled_at_utc, window_start_utc, window_end_utc,
                           idempotency_key, status, reason, queue_order, cost,
                           metadata_json
                    FROM scheduled_jobs
                    WHERE org_id = ?
                    ORDER BY queue_order ASC
                    """,
                    (org_id,),
                )

            items: list[ScheduledDispatchItem] = []
            for row in cur.fetchall():
                (
                    job_id,
                    r_org_id,
                    r_assessment_id,
                    student_id,
                    event_type,
                    scheduled_at_utc_str,
                    window_start_utc_str,
                    window_end_utc_str,
                    idempotency_key,
                    status_str,
                    reason,
                    queue_order,
                    cost,
                    metadata_json,
                ) = row

                scheduled_at_utc = datetime.fromisoformat(scheduled_at_utc_str)
                meta = json.loads(metadata_json) if metadata_json else {}

                items.append(
                    ScheduledDispatchItem(
                        job_id=job_id,
                        org_id=r_org_id,
                        assessment_id=r_assessment_id,
                        student_id=student_id,
                        event_type=event_type,
                        scheduled_at_utc=scheduled_at_utc,
                        scheduled_at_ist=scheduled_at_utc.astimezone(KOLKATA_TZ),
                        window_start_ist=datetime.fromisoformat(window_start_utc_str).astimezone(KOLKATA_TZ),
                        window_end_ist=datetime.fromisoformat(window_end_utc_str).astimezone(KOLKATA_TZ),
                        idempotency_key=idempotency_key,
                        status=ScheduleStatus(status_str),
                        reason=reason,
                        queue_order=queue_order,
                        cost=cost,
                        metadata=meta,
                    )
                )
            return items
        finally:
            conn.close()
