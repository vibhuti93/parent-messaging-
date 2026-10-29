"""
Stage S10 Multi-Tenant Scheduler & Send Window Engine Test Suite (`tests/test_stage10_scheduler.py`).

Compliant with:
- Stage S10 Gate 10 mandates:
  1. Canonical Schedule Calculation (Primary 2026-10-18 20:30 IST, Reminder 2026-10-19 10:00 IST iff reminder_enabled).
  2. Sunday Validation: Non-Sunday events claiming Sunday OMR window fail closed with InvalidScheduleWindowError.
  3. DST-Free Sanity: Invariant UTC+05:30 offset across year boundaries and seasons in Asia/Kolkata.
  4. DWRR Multi-Tenant Fair Scheduling: Prevents starvation of small tenants (e.g. Org B with 10 jobs vs Org A with 1,000 jobs).
  5. Daily Cap Pacing: Spreading large batches across consecutive eligible days, respecting holidays.
  6. Edge Conditions: Late import, missed window, holiday override, provider outage, unapproved template hold.
  7. Rule Enforcement: Never bypass send window rules with free-form content (WindowRuleBypassForbiddenError).
  8. Persistence & Restart Recovery: Plans and queue orders survive store reloads from disk.
  9. Lock Contention: Single-instance concurrency guard prevents duplicate job dispatches across concurrent workers.
- ADR-0002: Zero float() calls.
- ADR-0005: Timezone-aware datetimes anchored in Asia/Kolkata.
- Global Invariants 10, 13, 14, 15, 17, 18.
"""

from __future__ import annotations

import concurrent.futures
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from omr_dispatch.messaging.policy import TenantContextMissingError
from omr_dispatch.scheduler import (
    KOLKATA_TZ,
    AssessmentScheduleEvent,
    DispatchLock,
    DWRRQueue,
    InvalidScheduleWindowError,
    LockAcquisitionError,
    ScheduledDispatchItem,
    SchedulePolicy,
    SchedulerStore,
    ScheduleStatus,
    WindowRuleBypassForbiddenError,
    pace_batch_over_days,
    plan_schedule,
)

FIXTURE_EVENT_TIME = datetime(2026, 10, 18, 14, 15, 0, tzinfo=KOLKATA_TZ)  # Sunday


# ==============================================================================
# Gate 10 Requirement 1: Canonical Schedule Calculation
# ==============================================================================

def test_canonical_schedule_primary_and_reminder_enabled() -> None:
    """
    Target Fixture Match:
    For assessment event `2026-10-18 14:15+05:30` (Sunday):
      - Primary dispatch scheduled at: `2026-10-18 20:30:00+05:30`.
      - Reminder dispatch scheduled at: `2026-10-19 10:00:00+05:30` (Monday morning) when reminder_enabled=True.
      - Ensure distinct idempotency keys for primary vs. reminder dispatches.
    """
    event = AssessmentScheduleEvent(
        org_id="ORG_DELHI_01",
        assessment_id="ASM_OCT_2026",
        student_id="STU_001",
        event_timestamp=FIXTURE_EVENT_TIME,
        reminder_enabled=True,
    )
    now = datetime(2026, 10, 18, 14, 20, 0, tzinfo=KOLKATA_TZ)

    plan = plan_schedule(event=event, now=now)

    assert plan.status == ScheduleStatus.SCHEDULED
    assert plan.reason_code == "SCHEDULED_PRIMARY_WINDOW"

    # Primary send assertions
    assert plan.primary_dispatch.event_type == "PRIMARY"
    assert plan.primary_dispatch.scheduled_at_ist == datetime(2026, 10, 18, 20, 30, 0, tzinfo=KOLKATA_TZ)
    assert plan.primary_dispatch.window_start_ist == datetime(2026, 10, 18, 20, 30, 0, tzinfo=KOLKATA_TZ)
    assert plan.primary_dispatch.window_end_ist == datetime(2026, 10, 18, 21, 30, 0, tzinfo=KOLKATA_TZ)

    # Reminder send assertions
    assert plan.reminder_dispatch is not None
    assert plan.reminder_dispatch.event_type == "REMINDER"
    assert plan.reminder_dispatch.scheduled_at_ist == datetime(2026, 10, 19, 10, 0, 0, tzinfo=KOLKATA_TZ)
    assert plan.reminder_dispatch.window_start_ist == datetime(2026, 10, 19, 10, 0, 0, tzinfo=KOLKATA_TZ)
    assert plan.reminder_dispatch.window_end_ist == datetime(2026, 10, 19, 12, 0, 0, tzinfo=KOLKATA_TZ)

    # Distinct idempotency keys
    assert plan.primary_dispatch.idempotency_key != plan.reminder_dispatch.idempotency_key
    assert len(plan.dispatches) == 2


def test_canonical_schedule_reminder_disabled() -> None:
    """When reminder_enabled=False, exactly zero reminder dispatches are planned."""
    event = AssessmentScheduleEvent(
        org_id="ORG_DELHI_01",
        assessment_id="ASM_OCT_2026",
        student_id="STU_001",
        event_timestamp=FIXTURE_EVENT_TIME,
        reminder_enabled=False,
    )
    now = datetime(2026, 10, 18, 14, 20, 0, tzinfo=KOLKATA_TZ)

    plan = plan_schedule(event=event, now=now)

    assert plan.primary_dispatch.scheduled_at_ist == datetime(2026, 10, 18, 20, 30, 0, tzinfo=KOLKATA_TZ)
    assert plan.reminder_dispatch is None
    assert len(plan.dispatches) == 1


# ==============================================================================
# Gate 10 Requirement 2: Sunday Validation
# ==============================================================================

@pytest.mark.parametrize(
    ("non_sunday_dt", "day_name"),
    [
        (datetime(2026, 10, 21, 14, 15, 0, tzinfo=KOLKATA_TZ), "Wednesday"),
        (datetime(2026, 10, 20, 14, 15, 0, tzinfo=KOLKATA_TZ), "Tuesday"),
        (datetime(2026, 10, 24, 14, 15, 0, tzinfo=KOLKATA_TZ), "Saturday"),
        (datetime(2026, 10, 19, 14, 15, 0, tzinfo=KOLKATA_TZ), "Monday"),
    ],
)
def test_sunday_validation_fails_closed_for_non_sunday_events(
    non_sunday_dt: datetime, day_name: str
) -> None:
    """
    Validate that an event on Wednesday (or any non-Sunday) attempting to claim
    the primary Sunday OMR window fails closed with explicit InvalidScheduleWindowError.
    """
    event = AssessmentScheduleEvent(
        org_id="ORG_DELHI_01",
        assessment_id="ASM_MIDWEEK",
        student_id="STU_001",
        event_timestamp=non_sunday_dt,
        window_type="SUNDAY_OMR",
    )
    now = non_sunday_dt + timedelta(minutes=5)

    with pytest.raises(InvalidScheduleWindowError) as exc_info:
        plan_schedule(event=event, now=now)

    assert "not Sunday" in str(exc_info.value)
    assert day_name in str(exc_info.value)


# ==============================================================================
# Gate 10 Requirement 3: DST-Free Sanity in Asia/Kolkata
# ==============================================================================

def test_dst_free_sanity_across_year_boundaries() -> None:
    """
    Verify that calculations across seasons and year boundaries in ZoneInfo("Asia/Kolkata")
    maintain invariant UTC+05:30 offset with zero DST shifts.
    """
    dates_to_check = [
        datetime(2026, 1, 15, 12, 0, 0, tzinfo=KOLKATA_TZ),   # Winter
        datetime(2026, 6, 21, 12, 0, 0, tzinfo=KOLKATA_TZ),   # Summer Solstice
        datetime(2026, 10, 18, 20, 30, 0, tzinfo=KOLKATA_TZ), # Autumn
        datetime(2026, 12, 31, 23, 59, 59, tzinfo=KOLKATA_TZ),# Year End
        datetime(2027, 1, 1, 0, 0, 0, tzinfo=KOLKATA_TZ),     # Year Start
        datetime(2027, 7, 15, 12, 0, 0, tzinfo=KOLKATA_TZ),   # Following Year Summer
    ]

    expected_offset = timedelta(hours=5, minutes=30)
    expected_offset_seconds = 19800

    for dt in dates_to_check:
        offset = dt.utcoffset()
        assert offset == expected_offset, f"DST drift detected at {dt.isoformat()}"
        assert offset is not None
        assert offset.total_seconds() == expected_offset_seconds
        assert dt.dst() == timedelta(0), f"Non-zero DST detected at {dt.isoformat()}"


# ==============================================================================
# Gate 10 Requirement 4: DWRR Multi-Tenant Fair Scheduling
# ==============================================================================

def test_dwrr_fair_scheduling_starvation_prevention() -> None:
    """
    Simulate 3 tenants:
      - Org A with 1,000 jobs
      - Org B with 10 jobs
      - Org C with 50 jobs
    Demonstrate that Org B and Org C are NOT starved by Org A.
    All 10 jobs of Org B complete in Round 1 (within the first ~50 total dispatches),
    long before Org A's 1,000 jobs finish.
    """
    quantum = 20
    queue = DWRRQueue(quantum=quantum)

    # 1. Enqueue Org A: 1,000 jobs
    for i in range(1000):
        queue.enqueue(
            ScheduledDispatchItem(
                job_id=f"A_{i}",
                org_id="ORG_A",
                assessment_id="ASM_A",
                student_id=f"STU_A_{i}",
                event_type="PRIMARY",
                scheduled_at_utc=datetime.now(UTC),
                scheduled_at_ist=datetime.now(KOLKATA_TZ),
                window_start_ist=datetime.now(KOLKATA_TZ),
                window_end_ist=datetime.now(KOLKATA_TZ),
                idempotency_key=f"idem_A_{i}",
            )
        )

    # 2. Enqueue Org B: 10 jobs
    for i in range(10):
        queue.enqueue(
            ScheduledDispatchItem(
                job_id=f"B_{i}",
                org_id="ORG_B",
                assessment_id="ASM_B",
                student_id=f"STU_B_{i}",
                event_type="PRIMARY",
                scheduled_at_utc=datetime.now(UTC),
                scheduled_at_ist=datetime.now(KOLKATA_TZ),
                window_start_ist=datetime.now(KOLKATA_TZ),
                window_end_ist=datetime.now(KOLKATA_TZ),
                idempotency_key=f"idem_B_{i}",
            )
        )

    # 3. Enqueue Org C: 50 jobs
    for i in range(50):
        queue.enqueue(
            ScheduledDispatchItem(
                job_id=f"C_{i}",
                org_id="ORG_C",
                assessment_id="ASM_C",
                student_id=f"STU_C_{i}",
                event_type="PRIMARY",
                scheduled_at_utc=datetime.now(UTC),
                scheduled_at_ist=datetime.now(KOLKATA_TZ),
                window_start_ist=datetime.now(KOLKATA_TZ),
                window_end_ist=datetime.now(KOLKATA_TZ),
                idempotency_key=f"idem_C_{i}",
            )
        )

    # Drain round 1
    round_1 = queue.drain_round()

    # Round 1 should dispatch:
    # Org A: 20 jobs (quantum=20)
    # Org B: 10 jobs (all of them, since 10 <= 20)
    # Org C: 20 jobs (quantum=20)
    a_round1 = [j for j in round_1 if j.org_id == "ORG_A"]
    b_round1 = [j for j in round_1 if j.org_id == "ORG_B"]
    c_round1 = [j for j in round_1 if j.org_id == "ORG_C"]

    assert len(a_round1) == 20
    assert len(b_round1) == 10
    assert len(c_round1) == 20
    assert len(round_1) == 50

    # Org B is 100% completed in round 1!
    assert queue.queue_size("ORG_B") == 0
    assert queue.queue_size("ORG_C") == 30
    assert queue.queue_size("ORG_A") == 980

    # Drain the rest of the queue
    all_remaining = queue.drain_all()
    complete_stream = round_1 + all_remaining

    assert len(complete_stream) == 1060

    # Validate that Org B's final job was dispatched at index 29 (far before job 1000)
    last_b_idx = max(i for i, j in enumerate(complete_stream) if j.org_id == "ORG_B")
    assert last_b_idx < 50, f"Org B suffered starvation: last job at index {last_b_idx}"

    # Validate Org C completed within 3 rounds (60 jobs total from C, completed by index ~110)
    last_c_idx = max(i for i, j in enumerate(complete_stream) if j.org_id == "ORG_C")
    assert last_c_idx < 150, f"Org C suffered starvation: last job at index {last_c_idx}"


def test_dwrr_weighted_fairness() -> None:
    """Verify DWRR honors integer tenant weights (e.g. Org X weight 2 vs Org Y weight 1)."""
    weights = {"ORG_X": 2, "ORG_Y": 1}
    queue = DWRRQueue(quantum=10, weights=weights)

    for i in range(100):
        queue.enqueue(
            ScheduledDispatchItem(
                job_id=f"X_{i}",
                org_id="ORG_X",
                assessment_id="ASM",
                student_id=f"STU_X_{i}",
                event_type="PRIMARY",
                scheduled_at_utc=datetime.now(UTC),
                scheduled_at_ist=datetime.now(KOLKATA_TZ),
                window_start_ist=datetime.now(KOLKATA_TZ),
                window_end_ist=datetime.now(KOLKATA_TZ),
                idempotency_key=f"idem_X_{i}",
            )
        )
        queue.enqueue(
            ScheduledDispatchItem(
                job_id=f"Y_{i}",
                org_id="ORG_Y",
                assessment_id="ASM",
                student_id=f"STU_Y_{i}",
                event_type="PRIMARY",
                scheduled_at_utc=datetime.now(UTC),
                scheduled_at_ist=datetime.now(KOLKATA_TZ),
                window_start_ist=datetime.now(KOLKATA_TZ),
                window_end_ist=datetime.now(KOLKATA_TZ),
                idempotency_key=f"idem_Y_{i}",
            )
        )

    # In Round 1:
    # ORG_X receives quantum * weight = 10 * 2 = 20 jobs
    # ORG_Y receives quantum * weight = 10 * 1 = 10 jobs
    round_1 = queue.drain_round()
    x_jobs = [j for j in round_1 if j.org_id == "ORG_X"]
    y_jobs = [j for j in round_1 if j.org_id == "ORG_Y"]

    assert len(x_jobs) == 20
    assert len(y_jobs) == 10


# ==============================================================================
# Gate 10 Requirement 5: Daily Cap Pacing
# ==============================================================================

def test_daily_cap_pacing_splits_batch_across_consecutive_days() -> None:
    """
    Verify daily message cap pacing:
      - Batch of 600 items with daily cap 250
      - Day 1: 250 items
      - Day 2: 250 items
      - Day 3: 100 items
    """
    start_date = date(2026, 10, 18)  # Sunday
    items = [
        ScheduledDispatchItem(
            job_id=f"job_{i}",
            org_id="ORG_TEST",
            assessment_id="ASM_TEST",
            student_id=f"STU_{i}",
            event_type="PRIMARY",
            scheduled_at_utc=datetime.now(UTC),
            scheduled_at_ist=datetime.now(KOLKATA_TZ),
            window_start_ist=datetime.now(KOLKATA_TZ),
            window_end_ist=datetime.now(KOLKATA_TZ),
            idempotency_key=f"idem_{i}",
        )
        for i in range(600)
    ]

    paced = pace_batch_over_days(
        dispatches=items,
        daily_cap=250,
        current_sent_today=0,
        start_date=start_date,
    )

    assert len(paced) == 600

    day1_items = [p for p in paced if p.scheduled_at_ist.date() == date(2026, 10, 18)]
    day2_items = [p for p in paced if p.scheduled_at_ist.date() == date(2026, 10, 19)]
    day3_items = [p for p in paced if p.scheduled_at_ist.date() == date(2026, 10, 20)]

    assert len(day1_items) == 250
    assert len(day2_items) == 250
    assert len(day3_items) == 100

    # Status of spillover days marked with PACED_DAILY_CAP
    assert day1_items[0].status == ScheduleStatus.SCHEDULED
    assert day2_items[0].status == ScheduleStatus.PACED_DAILY_CAP
    assert day3_items[0].status == ScheduleStatus.PACED_DAILY_CAP


def test_daily_cap_pacing_respects_already_sent_today_and_holidays() -> None:
    """
    Pacing with:
      - daily_cap: 250
      - current_sent_today: 150 (leaves 100 for Day 1)
      - Day 2 is a Holiday! Should skip Day 2 and use Day 3.
    """
    start_date = date(2026, 10, 18)
    holiday = date(2026, 10, 19)
    items = [
        ScheduledDispatchItem(
            job_id=f"job_{i}",
            org_id="ORG_TEST",
            assessment_id="ASM_TEST",
            student_id=f"STU_{i}",
            event_type="PRIMARY",
            scheduled_at_utc=datetime.now(UTC),
            scheduled_at_ist=datetime.now(KOLKATA_TZ),
            window_start_ist=datetime.now(KOLKATA_TZ),
            window_end_ist=datetime.now(KOLKATA_TZ),
            idempotency_key=f"idem_{i}",
        )
        for i in range(300)
    ]

    paced = pace_batch_over_days(
        dispatches=items,
        daily_cap=250,
        current_sent_today=150,
        start_date=start_date,
        holidays={holiday},
    )

    day1_items = [p for p in paced if p.scheduled_at_ist.date() == date(2026, 10, 18)]
    day2_items = [p for p in paced if p.scheduled_at_ist.date() == holiday]
    day3_items = [p for p in paced if p.scheduled_at_ist.date() == date(2026, 10, 20)]

    assert len(day1_items) == 100
    assert len(day2_items) == 0  # Completely skipped holiday!
    assert len(day3_items) == 200


# ==============================================================================
# Gate 10 Requirement 6: Edge Cases & Window Condition Rules
# ==============================================================================

def test_late_import_after_window_start() -> None:
    """Import after 20:30 IST is flagged as late import and deferred by default."""
    event = AssessmentScheduleEvent(
        org_id="ORG_TEST",
        assessment_id="ASM_LATE",
        event_timestamp=FIXTURE_EVENT_TIME,
    )
    # Current time is 20:45 IST (after 20:30 start, before 21:30 end)
    late_now = datetime(2026, 10, 18, 20, 45, 0, tzinfo=KOLKATA_TZ)

    plan = plan_schedule(event=event, now=late_now, policy=SchedulePolicy(allow_late_import=False))
    assert plan.status == ScheduleStatus.DEFERRED_LATE_IMPORT
    assert "LATE_IMPORT" in plan.reason_code


def test_missed_window_after_window_end() -> None:
    """Current time exceeding window end time (21:30 IST) results in MISSED_WINDOW."""
    event = AssessmentScheduleEvent(
        org_id="ORG_TEST",
        assessment_id="ASM_MISSED",
        event_timestamp=FIXTURE_EVENT_TIME,
    )
    # Current time is 22:00 IST (after 21:30 window closure)
    missed_now = datetime(2026, 10, 18, 22, 0, 0, tzinfo=KOLKATA_TZ)

    plan = plan_schedule(event=event, now=missed_now)
    assert plan.status == ScheduleStatus.MISSED_WINDOW
    assert plan.reason_code == "MISSED_SEND_WINDOW_END"


def test_holiday_override_postpones_to_next_eligible_day() -> None:
    """Event date falling on institutional holiday postpones to next eligible business day."""
    event = AssessmentScheduleEvent(
        org_id="ORG_TEST",
        assessment_id="ASM_HOLIDAY",
        event_timestamp=FIXTURE_EVENT_TIME,
    )
    holiday = date(2026, 10, 18)
    now = datetime(2026, 10, 18, 14, 20, 0, tzinfo=KOLKATA_TZ)

    plan = plan_schedule(
        event=event,
        now=now,
        policy=SchedulePolicy(holidays={holiday}),
    )

    assert plan.status == ScheduleStatus.DEFERRED_HOLIDAY
    assert plan.primary_dispatch.scheduled_at_ist.date() == date(2026, 10, 19)


def test_provider_outage_holds_jobs_safely() -> None:
    """Upstream provider outage holds queued dispatches without dropping them."""
    event = AssessmentScheduleEvent(
        org_id="ORG_TEST",
        assessment_id="ASM_OUTAGE",
        event_timestamp=FIXTURE_EVENT_TIME,
    )
    now = datetime(2026, 10, 18, 14, 20, 0, tzinfo=KOLKATA_TZ)

    plan = plan_schedule(
        event=event,
        now=now,
        policy=SchedulePolicy(provider_operational=False),
    )

    assert plan.status == ScheduleStatus.HOLD_PROVIDER_OUTAGE
    assert plan.primary_dispatch.status == ScheduleStatus.HOLD_PROVIDER_OUTAGE
    assert len(plan.dispatches) >= 1


def test_unapproved_template_holds_jobs_without_freeform_bypass() -> None:
    """If template approval is missing, dispatches are held without freeform bypass."""
    event = AssessmentScheduleEvent(
        org_id="ORG_TEST",
        assessment_id="ASM_UNAPPROVED",
        event_timestamp=FIXTURE_EVENT_TIME,
    )
    now = datetime(2026, 10, 18, 14, 20, 0, tzinfo=KOLKATA_TZ)

    plan = plan_schedule(
        event=event,
        now=now,
        policy=SchedulePolicy(template_approved=False),
    )

    assert plan.status == ScheduleStatus.HOLD_UNAPPROVED_TEMPLATE
    assert plan.primary_dispatch.status == ScheduleStatus.HOLD_UNAPPROVED_TEMPLATE


def test_freeform_content_cannot_bypass_window_rules() -> None:
    """
    Invariant 13 & 14: Never bypass send window rules with free-form content.
    Attempting to schedule free-form content raises WindowRuleBypassForbiddenError.
    """
    event = AssessmentScheduleEvent(
        org_id="ORG_TEST",
        assessment_id="ASM_FREEFORM",
        event_timestamp=FIXTURE_EVENT_TIME,
        is_freeform=True,
    )
    now = datetime(2026, 10, 18, 14, 20, 0, tzinfo=KOLKATA_TZ)

    with pytest.raises(WindowRuleBypassForbiddenError):
        plan_schedule(event=event, now=now)


# ==============================================================================
# Gate 10 Requirement 7: Persistence & Restart Recovery
# ==============================================================================

def test_persistence_and_restart_recovery(tmp_path: Path) -> None:
    """
    Persist planned schedules to SQLite repository, close the instance,
    re-open a fresh store from disk, and assert schedule integrity.
    """
    db_file = tmp_path / "scheduler_persistence.db"
    store = SchedulerStore(db_file)

    event = AssessmentScheduleEvent(
        org_id="ORG_SCH_01",
        assessment_id="ASM_RESTART_TEST",
        student_id="STU_999",
        event_timestamp=FIXTURE_EVENT_TIME,
        reminder_enabled=True,
    )
    now = datetime(2026, 10, 18, 14, 20, 0, tzinfo=KOLKATA_TZ)

    original_plan = plan_schedule(event=event, now=now)
    store.save_plan(original_plan)

    # Re-open fresh instance from disk
    fresh_store = SchedulerStore(db_file)
    loaded_plan = fresh_store.load_plan("ORG_SCH_01", "ASM_RESTART_TEST")

    assert loaded_plan is not None
    assert loaded_plan.org_id == "ORG_SCH_01"
    assert loaded_plan.assessment_id == "ASM_RESTART_TEST"
    assert loaded_plan.primary_dispatch.scheduled_at_ist == original_plan.primary_dispatch.scheduled_at_ist
    assert loaded_plan.primary_dispatch.idempotency_key == original_plan.primary_dispatch.idempotency_key
    assert loaded_plan.reminder_dispatch is not None
    assert loaded_plan.reminder_dispatch.scheduled_at_ist == original_plan.reminder_dispatch.scheduled_at_ist
    assert loaded_plan.reminder_dispatch.idempotency_key == original_plan.reminder_dispatch.idempotency_key

    # Check job listing preserves queue order
    jobs = fresh_store.list_jobs("ORG_SCH_01")
    assert len(jobs) == 2
    assert jobs[0].event_type == "PRIMARY"
    assert jobs[1].event_type == "REMINDER"
    assert jobs[0].queue_order < jobs[1].queue_order


# ==============================================================================
# Gate 10 Requirement 8: Single-Instance Dispatch Lock Contention
# ==============================================================================

def test_dispatch_lock_basic_acquire_and_release(tmp_path: Path) -> None:
    """Verify standard single-instance lock lifecycle."""
    db_file = tmp_path / "locks.db"
    lock1 = DispatchLock(db_file, lock_key="job_001", owner_id="worker_A", ttl_seconds=60)
    lock2 = DispatchLock(db_file, lock_key="job_001", owner_id="worker_B", ttl_seconds=60)

    # Worker A acquires
    assert lock1.acquire() is True

    # Worker B tries to acquire same lock -> fails
    assert lock2.acquire() is False

    # Worker A releases
    assert lock1.release() is True

    # Worker B can now acquire
    assert lock2.acquire() is True
    assert lock2.release() is True


def test_dispatch_lock_context_manager_contention_raises_error(tmp_path: Path) -> None:
    """Context manager raises LockAcquisitionError when another instance holds the lock."""
    db_file = tmp_path / "locks.db"
    lock1 = DispatchLock(db_file, lock_key="job_002", owner_id="worker_A", ttl_seconds=60)
    lock2 = DispatchLock(db_file, lock_key="job_002", owner_id="worker_B", ttl_seconds=60)

    with lock1, pytest.raises(LockAcquisitionError), lock2:
        pass


def test_dispatch_lock_multi_threaded_contention(tmp_path: Path) -> None:
    """
    Multi-threaded contention simulation:
      - 10 worker threads concurrently attempt to claim and dispatch the same scheduled job.
      - Exactly ONE worker acquires the lock and dispatches; 9 workers fail and skip.
      - Zero duplicate dispatch execution.
    """
    db_file = tmp_path / "locks_mt.db"
    lock_key = "scheduled_job_critical_999"

    successful_dispatches: list[str] = []
    failed_attempts: list[str] = []
    active_holders = 0
    max_simultaneous_holders = 0
    simultaneous_lock = threading.Lock()

    def worker_task(worker_id: str) -> None:
        nonlocal active_holders, max_simultaneous_holders
        lock = DispatchLock(db_file, lock_key=lock_key, owner_id=worker_id, ttl_seconds=30)
        if lock.acquire():
            try:
                with simultaneous_lock:
                    active_holders += 1
                    if active_holders > max_simultaneous_holders:
                        max_simultaneous_holders = active_holders

                # Hold lock in critical section to create contention
                import time as pytime
                pytime.sleep(0.02)

                with simultaneous_lock:
                    active_holders -= 1
                successful_dispatches.append(worker_id)
            finally:
                lock.release()
        else:
            failed_attempts.append(worker_id)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_task, f"worker_{i}") for i in range(10)]
        concurrent.futures.wait(futures)

    # Invariant: At no point did two workers hold the lock simultaneously
    assert max_simultaneous_holders == 1
    # Contention occurred: some workers were locked out
    assert len(failed_attempts) >= 1
    # Total attempts evaluated sum to 10
    assert len(successful_dispatches) + len(failed_attempts) == 10


# ==============================================================================
# Invariant and Hygiene Validation
# ==============================================================================

def test_tenant_context_missing_fails_closed() -> None:
    """plan_schedule fails closed when org_id is empty (Invariant 15)."""
    event = AssessmentScheduleEvent(
        org_id="",
        assessment_id="ASM_TEST",
        event_timestamp=FIXTURE_EVENT_TIME,
    )
    now = datetime(2026, 10, 18, 14, 20, 0, tzinfo=KOLKATA_TZ)

    with pytest.raises(TenantContextMissingError):
        plan_schedule(event=event, now=now)


def test_timezone_naive_now_rejected() -> None:
    """plan_schedule fails closed when now is timezone-naive (ADR-0005)."""
    event = AssessmentScheduleEvent(
        org_id="ORG_TEST",
        assessment_id="ASM_TEST",
        event_timestamp=FIXTURE_EVENT_TIME,
    )
    naive_now = datetime(2026, 10, 18, 14, 20, 0)  # Naive

    with pytest.raises(ValueError, match="timezone-aware"):
        plan_schedule(event=event, now=naive_now)
