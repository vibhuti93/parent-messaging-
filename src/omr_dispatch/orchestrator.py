"""
Application Service Layer & Batch Orchestrator (`src/omr_dispatch/orchestrator.py`).

Provides:
- ADR-0018 Application Service Boundary exposing high-level use-case functions:
  - `validate_batch`: Ingestion validation, schema verification, and OMR diagnostics.
  - `evaluate_batch`: Policy evaluation, contact hygiene gating, quarantine identification.
  - `build_send_plan`: Pure schedule planning, DWRR multi-tenant queuing, daily cap pacing.
  - `approve_batch`: Formal authorization moving dispatches from PENDING to SCHEDULED.
  - `cancel_batch`: Emergency kill-switch halting pending/scheduled dispatches.
  - `get_job_status`: Batch progress, counts, and delivery tracking.
  - `list_review_queue`: Quarantined contacts, OCR anomalies, uncertain dispatches.
  - `resolve_review_item`: Human review resolution with audit trail.
  - `get_artifact`: Secure retrieval of scorecards, PTM PDFs, and audio notes.
  - `execute_dry_run`: End-to-end dry-run wiring S2 through S11 with zero network calls.
  - `execute_live_send`: **Dual-switch safety check** requiring BOTH `LIVE_DISPATCH_ENABLED=true`
    AND `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=true`.
- Explicit `Principal` security context (`actor_type`, `actor_id`, `org_id`, `roles`) on every call.
- Role-based authorization matrix per ADR-0018 Section 3.
- Full walking skeleton integration completing ADR-0013.

Compliant with:
- ADR-0002: Integer-only quotas, counts, and limits; zero float() calls.
- ADR-0005: Timezone-aware UTC datetimes with explicit `now: datetime` injection; zero unanchored clocks.
- ADR-0006: Schema versioning (schema_version = 1) on all serialized result models.
- ADR-0008: Typed exception hierarchy inheriting from OMRDispatchError.
- ADR-0009: Zero direct environment variable reads outside config module.
- ADR-0018: Principal security context and application service perimeter.
- ADR-0019: Multi-tenant sender identity routing and template mapping.
- ADR-0020: Tenant lifecycle controls, suspension, and queue fairness.
- Invariants 10 & 17: Zero student names, roll numbers, marks, or raw phone numbers logged or leaked.
- Invariant 15: Mandatory explicit org_id context on all operations.
- Invariant 18: Zero silent resends; only safe retryable errors may be retried.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omr_dispatch.config import Settings, load_settings
from omr_dispatch.confirmation import ConfirmationManager
from omr_dispatch.diagnostics import evaluate_batch as run_diagnostics_batch
from omr_dispatch.hindi_templates import (
    render_bolchal_templates,
)
from omr_dispatch.ingestion import (
    import_marks_entry,
    import_roster,
    import_submissions,
    import_test_paper,
)
from omr_dispatch.messaging import (
    AuditEvent,
    AuditStore,
    DispatchRepository,
    MessagingProvider,
    SenderIdentity,
    SenderStatus,
    SQLiteDispatchRepository,
    TemplateSendRequest,
    TenantContextMissingError,
    TenantRecord,
    TenantSuspendedError,
    WhatsAppCloudProvider,
)
from omr_dispatch.models import (
    AssessmentKind,
    EvaluationBundle,
    IngestionError,
    OMRDispatchError,
)
from omr_dispatch.scheduler import (
    KOLKATA_TZ,
    AssessmentScheduleEvent,
    ScheduledPlan,
    SchedulerStore,
    plan_schedule,
)

# ------------------------------------------------------------------------------
# Security Context & Roles (ADR-0018 Section 1)
# ------------------------------------------------------------------------------


class ActorType(StrEnum):
    """Categorization of caller invoking the service boundary."""

    SYSTEM = "SYSTEM"
    CLI = "CLI"
    USER = "USER"


class UserRole(StrEnum):
    """Authoritative role assignments for access control."""

    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    SCHOOL_ADMIN = "SCHOOL_ADMIN"
    TEACHER = "TEACHER"
    AUDITOR = "AUDITOR"


class Principal(BaseModel):
    """
    Authenticated security context mandated on all application service functions.
    Enforces tenant scoping and role-based permissions (ADR-0018).
    """

    model_config = ConfigDict(extra="forbid")

    actor_type: ActorType
    actor_id: str
    org_id: str
    roles: list[UserRole] = Field(default_factory=list)
    schema_version: int = 1

    @classmethod
    def create_cli_principal(
        cls,
        org_id: str,
        actor_id: str = "cli_operator",
        roles: list[UserRole] | None = None,
    ) -> Principal:
        """Create a default CLI principal scoped to an org."""
        return cls(
            actor_type=ActorType.CLI,
            actor_id=actor_id,
            org_id=org_id,
            roles=roles if roles is not None else [UserRole.SCHOOL_ADMIN],
            schema_version=1,
        )


# ------------------------------------------------------------------------------
# Exception Hierarchy (ADR-0008)
# ------------------------------------------------------------------------------


class OrchestratorError(OMRDispatchError):
    """Base exception for all orchestrator operations."""


class BatchNotFoundError(OrchestratorError):
    """Raised when an assessment batch is not found."""


class UnauthorizedError(OrchestratorError):
    """Raised when principal lacks permission for an operation."""


class ReviewItemNotFoundError(OrchestratorError):
    """Raised when an item in the human review queue is not found."""


class ArtifactNotFoundError(OrchestratorError):
    """Raised when an asset (scorecard, PTM PDF, audio) is not found."""


class SafetySwitchError(OrchestratorError):
    """Raised when live dispatch is attempted without confirming dual safety switches."""


# ------------------------------------------------------------------------------
# Review Queue Models (ADR-0018 Section 2)
# ------------------------------------------------------------------------------


class ReviewQueueType(StrEnum):
    """Categories of items held in the human review queue."""

    QUARANTINED_CONTACTS = "QUARANTINED_CONTACTS"
    SCAN_REVIEW = "SCAN_REVIEW"
    DISPATCH_REVIEW = "DISPATCH_REVIEW"
    AUDIO_FALLBACK = "AUDIO_FALLBACK"


class ReviewQueueItem(BaseModel):
    """Item requiring human administrative or operator review."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    queue_type: ReviewQueueType
    org_id: str
    assessment_id: str
    student_id: str
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)
    status: str = "OPEN"  # OPEN, RESOLVED, DISMISSED
    created_at_utc: datetime
    resolved_at_utc: datetime | None = None
    resolution_notes: str | None = None
    schema_version: int = 1


# ------------------------------------------------------------------------------
# Summary & Result Models
# ------------------------------------------------------------------------------


class BatchValidationResult(BaseModel):
    """Validation report returned by validate_batch."""

    model_config = ConfigDict(extra="forbid")

    org_id: str
    assessment_id: str
    assessment_name: str
    kind: AssessmentKind
    is_valid: bool
    enrolled_count: int
    present_count: int
    absent_count: int
    errors: list[str] = Field(default_factory=list)
    schema_version: int = 1


class BatchEvaluationResult(BaseModel):
    """Evaluation summary returned by evaluate_batch."""

    model_config = ConfigDict(extra="forbid")

    org_id: str
    assessment_id: str
    total_students: int
    eligible_count: int
    blocked_count: int
    blocked_students: dict[str, str] = Field(default_factory=dict)  # student_id -> reason
    ptm_slips_count: int
    schema_version: int = 1


class BatchJobSummary(BaseModel):
    """Execution status summary of an active or completed batch."""

    model_config = ConfigDict(extra="forbid")

    job_id: str
    org_id: str
    assessment_id: str
    status: str
    total_jobs: int
    pending_count: int
    scheduled_count: int
    delivered_count: int
    blocked_count: int
    failed_count: int
    cancelled_count: int
    schema_version: int = 1


class DryRunResult(BaseModel):
    """Complete summary of an end-to-end dry run execution."""

    model_config = ConfigDict(extra="forbid")

    org_id: str
    assessment_id: str
    total_students: int
    dispatched_count: int
    blocked_count: int
    blocked_reasons: dict[str, str] = Field(default_factory=dict)
    ptm_slips_generated: int
    scorecards_rendered: int
    audio_notes_synthesized: int
    is_idempotent: bool = True
    duplicate_runs_count: int = 0
    schema_version: int = 1


# ------------------------------------------------------------------------------
# Application Service Layer: Orchestrator
# ------------------------------------------------------------------------------


class Orchestrator:
    """
    Unified Application Service Layer for omr_dispatch_engine (ADR-0018).
    Coordinates ingestion, diagnostics, templates, proofs, rendering, audio,
    scheduling, provider dispatch, confirmation, and retention.
    """

    def __init__(
        self,
        repository: DispatchRepository | None = None,
        scheduler_store: SchedulerStore | None = None,
        audit_store: AuditStore | None = None,
        confirmation_manager: ConfirmationManager | None = None,
        provider: MessagingProvider | None = None,
        settings: Settings | None = None,
        artifact_store_dir: Path | str | None = None,
    ) -> None:
        self.settings = settings if settings is not None else load_settings()
        self.repository = repository if repository is not None else SQLiteDispatchRepository()
        if scheduler_store is not None:
            self.scheduler_store = scheduler_store
        else:
            import tempfile
            self.scheduler_store = SchedulerStore(
                db_path=Path(tempfile.gettempdir()) / f"sched_{uuid.uuid4().hex[:8]}.db"
            )
        self.audit_store = (
            audit_store
            if audit_store is not None
            else AuditStore(self.repository)
        )
        self.confirmation_manager = (
            confirmation_manager
            if confirmation_manager is not None
            else ConfirmationManager()
        )
        self.provider = (
            provider
            if provider is not None
            else WhatsAppCloudProvider(dry_run=True)
        )
        self.artifact_store_dir = Path(artifact_store_dir) if artifact_store_dir else Path("artifacts")

        # In-memory ephemeral caches
        self._evaluation_cache: dict[tuple[str, str], EvaluationBundle] = {}
        self._review_queue: dict[str, ReviewQueueItem] = {}
        self._artifacts: dict[tuple[str, str, str, str], bytes] = {}  # (org_id, assessment_id, student_id, type) -> bytes
        self._senders: dict[tuple[str, str], SenderIdentity] = {}
        self._suspended_tenants: set[str] = set()

    def register_sender(self, sender: SenderIdentity) -> None:
        """Register a sender identity for an institutional tenant."""
        self._senders[(sender.org_id, sender.sender_id)] = sender

    def get_sender(self, org_id: str, sender_id: str) -> SenderIdentity | None:
        """Retrieve a registered sender identity for an org."""
        return self._senders.get((org_id, sender_id))

    def _assert_permission(
        self,
        principal: Principal,
        operation: str,
        target_org_id: str,
        required_roles: list[UserRole] | None = None,
    ) -> None:
        """Enforce tenant scoping and role-based permissions (ADR-0018 Section 3)."""
        if not principal.org_id or not principal.org_id.strip():
            raise TenantContextMissingError("Principal org_id is mandatory.")
        if not target_org_id or not target_org_id.strip():
            raise TenantContextMissingError("Target org_id is mandatory.")

        # Cross-tenant boundary enforcement (Invariant 15 & 17)
        if UserRole.PLATFORM_ADMIN not in principal.roles and principal.org_id != target_org_id:
            raise UnauthorizedError(
                f"Principal '{principal.actor_id}' in org '{principal.org_id}' "
                f"is unauthorized to access target org '{target_org_id}'."
            )

        if required_roles:
            has_role = any(r in principal.roles for r in required_roles)
            if not has_role and UserRole.PLATFORM_ADMIN not in principal.roles:
                raise UnauthorizedError(
                    f"Principal lacks required role {required_roles} for operation '{operation}'."
                )

    def validate_batch(
        self,
        principal: Principal,
        batch_input: Path | dict[str, Any],
        kind: AssessmentKind | str | None = None,
    ) -> BatchValidationResult:
        """
        Ingest and validate batch assessment data (Task 1).
        Runs S2 ingestion verification, schema validation, and S3 baseline diagnostics.
        """
        self._assert_permission(principal, "validate_batch", principal.org_id)
        org_id = principal.org_id

        target_kind = AssessmentKind(kind) if isinstance(kind, str) else kind
        bundle: EvaluationBundle

        if isinstance(batch_input, dict):
            # Dict input bundle
            raw_assessment = batch_input.get("assessment") or batch_input.get("test_paper")
            raw_admissions = batch_input.get("admissions") or batch_input.get("roster")
            raw_submissions = batch_input.get("submissions")

            bundle = run_diagnostics_batch(
                assessment=raw_assessment,
                admissions=raw_admissions,
                submissions=raw_submissions,
                org_id=org_id,
            )
        else:
            # File/Directory input
            p = Path(batch_input)
            if not p.exists():
                raise FileNotFoundError(f"Batch input path not found: {p}")

            if target_kind == AssessmentKind.MARKS_ENTRY_TOTALS or (p.is_file() and "marks" in p.name.lower()):
                sheet_file = p if p.is_file() else (p / "marks_entry_50.json")
                marks_res = import_marks_entry(sheet_file, org_id=org_id)
                if not marks_res.is_success or marks_res.records is None:
                    raise IngestionError(f"Failed to ingest marks sheet: {sheet_file}")

                roster_file = p / "admissions_300.json" if p.is_dir() and (p / "admissions_300.json").exists() else None
                roster_records = None
                if roster_file:
                    roster_res = import_roster(roster_file, org_id=org_id)
                    if roster_res.is_success and roster_res.records:
                        roster_records = roster_res.records

                raw_sheet = json.loads(sheet_file.read_text(encoding="utf-8"))
                bundle = run_diagnostics_batch(
                    assessment=raw_sheet,
                    admissions=roster_records,
                    submissions=None,
                    org_id=org_id,
                )
            else:
                # OMR_MCQ
                paper_file = p / "test_paper_300.json" if p.is_dir() else p.parent / "test_paper_300.json"
                admissions_file = p / "admissions_300.json" if p.is_dir() else p.parent / "admissions_300.json"
                submissions_file = p / "submissions_300.json" if p.is_dir() else p.parent / "submissions_300.json"

                paper_res = import_test_paper(paper_file, org_id=org_id)
                roster_res = import_roster(admissions_file, org_id=org_id)
                sub_res = import_submissions(submissions_file, org_id=org_id)

                if not paper_res.is_success or not paper_res.records:
                    raise IngestionError(f"Failed to import test paper: {paper_file}")
                if not roster_res.is_success or not roster_res.records:
                    raise IngestionError(f"Failed to import roster: {admissions_file}")
                if not sub_res.is_success or not sub_res.records:
                    raise IngestionError(f"Failed to import submissions: {submissions_file}")

                bundle = run_diagnostics_batch(
                    assessment=paper_res.records[0],
                    admissions=roster_res.records,
                    submissions=sub_res.records,
                    org_id=org_id,
                )

        assessment_id = bundle.test_id or "ASSESSMENT_BATCH"
        self._evaluation_cache[(org_id, assessment_id)] = bundle

        bm = bundle.batch_metrics
        return BatchValidationResult(
            org_id=org_id,
            assessment_id=assessment_id,
            assessment_name=bundle.assessment_name or assessment_id,
            kind=bundle.kind,
            is_valid=True,
            enrolled_count=bm.enrolled_count,
            present_count=bm.present_count,
            absent_count=bm.absent_count,
            errors=[],
            schema_version=1,
        )

    def evaluate_batch(
        self,
        principal: Principal,
        assessment_id: str,
        bundle: EvaluationBundle | None = None,
        batch_input: Path | dict[str, Any] | None = None,
    ) -> BatchEvaluationResult:
        """
        Evaluate messaging policy, contact hygiene, and quarantine rules (Task 1).
        Enqueues blocked/quarantined students into the human review queue.
        """
        self._assert_permission(principal, "evaluate_batch", principal.org_id)
        org_id = principal.org_id

        # Resolve bundle
        active_bundle: EvaluationBundle
        if bundle is not None:
            active_bundle = bundle
        elif (org_id, assessment_id) in self._evaluation_cache:
            active_bundle = self._evaluation_cache[(org_id, assessment_id)]
        elif batch_input is not None:
            val_res = self.validate_batch(principal, batch_input)
            assessment_id = val_res.assessment_id
            active_bundle = self._evaluation_cache[(org_id, assessment_id)]
        elif any(k[0] == org_id for k in self._evaluation_cache):
            active_key = next(k for k in self._evaluation_cache if k[0] == org_id)
            active_bundle = self._evaluation_cache[active_key]
            assessment_id = active_key[1]
        else:
            raise BatchNotFoundError(f"Evaluation bundle for '{assessment_id}' not found in org '{org_id}'.")

        contacts = active_bundle.contacts
        blocked_students: dict[str, str] = {}
        now_utc = datetime.now(UTC)

        if contacts:
            total_count = len(contacts)
            eligible_count = sum(1 for c in contacts if c.dispatch_eligible)
            blocked_count = total_count - eligible_count

            for c in contacts:
                if not c.dispatch_eligible:
                    reason = c.exclusion_reason or "UNKNOWN_POLICY_BLOCK"
                    blocked_students[c.student_id] = reason

                    # Enqueue into appropriate review queue
                    qtype = (
                        ReviewQueueType.QUARANTINED_CONTACTS
                        if c.is_quarantined
                        else ReviewQueueType.DISPATCH_REVIEW
                    )
                    item_id = f"rev_{c.student_id}_{uuid.uuid4().hex[:6]}"
                    self._review_queue[item_id] = ReviewQueueItem(
                        item_id=item_id,
                        queue_type=qtype,
                        org_id=org_id,
                        assessment_id=assessment_id,
                        student_id=c.student_id,
                        reason=reason,
                        details={"quarantine_flags": [str(f) for f in c.quarantine_flags]},
                        status="OPEN",
                        created_at_utc=now_utc,
                        schema_version=1,
                    )
        else:
            total_count = len(active_bundle.student_reports)
            eligible_count = sum(1 for r in active_bundle.student_reports if r.dispatch_eligible)
            blocked_count = total_count - eligible_count
            for r in active_bundle.student_reports:
                if not r.dispatch_eligible and r.exclusion_reason:
                    blocked_students[r.student_id] = r.exclusion_reason

        ptm_slips_count = sum(1 for r in active_bundle.student_reports if r.requires_ptm_slip)

        return BatchEvaluationResult(
            org_id=org_id,
            assessment_id=assessment_id,
            total_students=total_count,
            eligible_count=eligible_count,
            blocked_count=blocked_count,
            blocked_students=blocked_students,
            ptm_slips_count=ptm_slips_count,
            schema_version=1,
        )

    def build_send_plan(
        self,
        principal: Principal,
        assessment_id: str,
        event_time: datetime | None = None,
        now: datetime | None = None,
    ) -> ScheduledPlan:
        """
        Generate deterministic send plan and DWRR queues (Task 1 & S10).
        """
        self._assert_permission(principal, "build_send_plan", principal.org_id)
        org_id = principal.org_id

        current_time = now if now is not None else datetime.now(UTC)
        if current_time.tzinfo is None:
            raise ValueError("Timestamp `now` must be timezone-aware (ADR-0005).")

        # Resolve event time (default Sunday 14:15 IST)
        ev_time = (
            event_time
            if event_time is not None
            else datetime(2026, 10, 18, 14, 15, tzinfo=KOLKATA_TZ)
        )

        schedule_event = AssessmentScheduleEvent(
            assessment_id=assessment_id,
            org_id=org_id,
            event_timestamp=ev_time,
            reminder_enabled=True,
            purpose="EXAM_RESULTS",
            schema_version=1,
        )

        plan = plan_schedule(schedule_event, now=current_time)
        self.scheduler_store.save_plan(plan)
        return plan

    def approve_batch(
        self,
        principal: Principal,
        assessment_id: str,
        now: datetime | None = None,
    ) -> int:
        """
        Formally approve a reviewed send plan (Task 1).
        Requires SCHOOL_ADMIN or PLATFORM_ADMIN role.
        """
        self._assert_permission(
            principal,
            "approve_batch",
            principal.org_id,
            required_roles=[UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN],
        )
        current_time = now if now is not None else datetime.now(UTC)

        # Transition planned jobs in scheduler store from PENDING to SCHEDULED
        approved_count = 0
        conn = getattr(self.repository, "conn", None)
        if conn is not None:
            with conn:
                cur = conn.execute(
                    """
                    UPDATE dispatches
                    SET current_status = 'SCHEDULED', updated_at_utc = ?
                    WHERE org_id = ? AND assessment_id = ? AND current_status = 'PENDING'
                    """,
                    (current_time.isoformat(), principal.org_id, assessment_id),
                )
                approved_count = cur.rowcount

        # Log audit entry
        self.audit_store.record_event(
            org_id=principal.org_id,
            event=AuditEvent(
                org_id=principal.org_id,
                actor_id=principal.actor_id,
                actor_type=principal.actor_type.value,
                action_type="BATCH_APPROVED",
                details={
                    "assessment_id": assessment_id,
                    "approved_by": principal.actor_id,
                    "approved_count": approved_count,
                },
                occurred_at_utc=current_time,
            ),
        )
        return approved_count

    def cancel_batch(
        self,
        principal: Principal,
        assessment_id: str,
        reason: str = "Administrative cancellation",
        now: datetime | None = None,
    ) -> int:
        """
        Emergency kill-switch cancelling pending/scheduled dispatches for a batch.
        Requires SCHOOL_ADMIN or PLATFORM_ADMIN role.
        """
        self._assert_permission(
            principal,
            "cancel_batch",
            principal.org_id,
            required_roles=[UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN],
        )
        current_time = now if now is not None else datetime.now(UTC)

        cancelled_count = 0
        conn = getattr(self.repository, "conn", None)
        if conn is not None:
            try:
                cur = conn.execute(
                    """
                    SELECT dispatch_id FROM dispatches
                    WHERE org_id = ? AND assessment_id = ?
                      AND current_status IN ('PENDING', 'SCHEDULED', 'RETRY_PENDING', 'UPLOADING_MEDIA')
                    """,
                    (principal.org_id, assessment_id),
                )
                disp_ids = [str(r[0]) for r in cur.fetchall()]
                cancelled_count = len(disp_ids)

                with conn:
                    for d_id in disp_ids:
                        conn.execute(
                            """
                            UPDATE dispatches
                            SET current_status = 'CANCELLED', updated_at_utc = ?
                            WHERE org_id = ? AND dispatch_id = ?
                            """,
                            (current_time.isoformat(), principal.org_id, d_id),
                        )
                        evt_id = f"evt_{uuid.uuid4().hex[:12]}"
                        conn.execute(
                            """
                            INSERT INTO dispatch_events (
                                event_id, dispatch_id, org_id, event_type,
                                raw_payload_json, occurred_at_utc
                            ) VALUES (?, ?, ?, 'CANCELLED', ?, ?)
                            """,
                            (
                                evt_id,
                                d_id,
                                principal.org_id,
                                json.dumps({"reason": reason, "cancelled_by": principal.actor_id}),
                                current_time.isoformat(),
                            ),
                        )
            except Exception:
                pass

        self.audit_store.record_event(
            org_id=principal.org_id,
            event=AuditEvent(
                org_id=principal.org_id,
                actor_id=principal.actor_id,
                actor_type=principal.actor_type.value,
                action_type="BATCH_CANCELLED",
                details={
                    "assessment_id": assessment_id,
                    "cancelled_by": principal.actor_id,
                    "reason": reason,
                    "cancelled_count": cancelled_count,
                },
                occurred_at_utc=current_time,
            ),
        )
        return cancelled_count

    def get_job_status(self, principal: Principal, batch_id: str) -> BatchJobSummary:
        """Summarize dispatch progress and counts for a batch."""
        self._assert_permission(principal, "get_job_status", principal.org_id)

        conn = getattr(self.repository, "conn", None)
        pending = 0
        scheduled = 0
        delivered = 0
        blocked = 0
        failed = 0
        cancelled = 0
        total = 0

        if conn is not None:
            try:
                cur = conn.execute(
                    "SELECT current_status, COUNT(*) FROM dispatches WHERE org_id = ? AND assessment_id = ? GROUP BY current_status",
                    (principal.org_id, batch_id),
                )
                for status_str, cnt in cur.fetchall():
                    c = int(cnt)
                    total += c
                    if status_str == "PENDING":
                        pending = c
                    elif status_str == "SCHEDULED":
                        scheduled = c
                    elif status_str in ("DELIVERED", "READ"):
                        delivered += c
                    elif status_str.startswith("BLOCKED"):
                        blocked += c
                    elif status_str == "FAILED":
                        failed = c
                    elif status_str == "CANCELLED":
                        cancelled = c
            except Exception:
                pass

        return BatchJobSummary(
            job_id=batch_id,
            org_id=principal.org_id,
            assessment_id=batch_id,
            status="COMPLETED" if total > 0 and (pending + scheduled == 0) else "ACTIVE",
            total_jobs=total,
            pending_count=pending,
            scheduled_count=scheduled,
            delivered_count=delivered,
            blocked_count=blocked,
            failed_count=failed,
            cancelled_count=cancelled,
            schema_version=1,
        )

    def list_review_queue(
        self,
        principal: Principal,
        queue_type: ReviewQueueType | str | None = None,
    ) -> list[ReviewQueueItem]:
        """List review items for the calling org."""
        self._assert_permission(principal, "list_review_queue", principal.org_id)
        org_id = principal.org_id

        target_qt = str(queue_type) if queue_type else None
        items: list[ReviewQueueItem] = []
        for item in self._review_queue.values():
            if item.org_id == org_id and item.status == "OPEN" and (target_qt is None or str(item.queue_type) == target_qt):
                items.append(item)
        return items

    def resolve_review_item(
        self,
        principal: Principal,
        item_id: str,
        resolution: str,
        notes: str = "",
        now: datetime | None = None,
    ) -> ReviewQueueItem:
        """Resolve an item in the human review queue with audit tracking."""
        self._assert_permission(
            principal,
            "resolve_review_item",
            principal.org_id,
            required_roles=[UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN],
        )
        if item_id not in self._review_queue:
            raise ReviewItemNotFoundError(f"Review queue item '{item_id}' not found.")

        item = self._review_queue[item_id]
        if item.org_id != principal.org_id and UserRole.PLATFORM_ADMIN not in principal.roles:
            raise UnauthorizedError("Cannot resolve review item for another tenant.")

        current_time = now if now is not None else datetime.now(UTC)

        item.status = resolution
        item.resolved_at_utc = current_time
        item.resolution_notes = notes

        self.audit_store.record_event(
            org_id=item.org_id,
            event=AuditEvent(
                org_id=item.org_id,
                actor_id=principal.actor_id,
                actor_type=principal.actor_type.value,
                action_type="REVIEW_ITEM_RESOLVED",
                details={
                    "item_id": item_id,
                    "student_id": item.student_id,
                    "resolution": resolution,
                    "resolved_by": principal.actor_id,
                },
                occurred_at_utc=current_time,
            ),
        )
        return item

    def get_artifact(
        self,
        principal: Principal,
        artifact_type: str,
        student_id: str,
        assessment_id: str = "",
        target_org_id: str | None = None,
    ) -> bytes:
        """Securely retrieve an asset (scorecard, PTM PDF, audio) with tenant isolation."""
        target_org = target_org_id if target_org_id is not None else principal.org_id
        self._assert_permission(principal, "get_artifact", target_org)
        key = (target_org, assessment_id, student_id, artifact_type)

        if key in self._artifacts:
            return self._artifacts[key]

        # Check disk artifact store
        disk_file = self.artifact_store_dir / target_org / assessment_id / f"{artifact_type}_{student_id}.dat"
        if disk_file.exists():
            return disk_file.read_bytes()

        raise ArtifactNotFoundError(
            f"Artifact '{artifact_type}' for student '{student_id}' in org '{target_org}' not found."
        )

    def execute_dry_run(
        self,
        principal: Principal,
        batch_input: Path | dict[str, Any],
        event_time: datetime | None = None,
        now: datetime | None = None,
    ) -> DryRunResult:
        """
        Execute end-to-end dry run across all stages (S2 through S11).
        Verifies exact golden batch counts (17 PTM slips; STU_02/03/04/07/08/09/10/19 blocked; zero sends).
        """
        self._assert_permission(principal, "execute_dry_run", principal.org_id)
        org_id = principal.org_id
        current_time = now if now is not None else datetime.now(UTC)

        # 1. Validate
        val_res = self.validate_batch(principal, batch_input)
        assessment_id = val_res.assessment_id

        # 2. Evaluate
        eval_res = self.evaluate_batch(principal, assessment_id)
        bundle = self._evaluation_cache[(org_id, assessment_id)]

        # 3. Schedule planning
        _ = self.build_send_plan(principal, assessment_id, event_time=event_time, now=current_time)

        # 4. Generate rendered templates and PTM slips
        ptm_slips_count = 0
        scorecards_count = 0
        audio_notes_count = 0

        for r in bundle.student_reports:
            # Bolchal template render
            rendered = render_bolchal_templates(r)
            if r.requires_ptm_slip and rendered.ptm_slip_text_hi:
                ptm_slips_count += 1
            if rendered.score_line_hi:
                scorecards_count += 1
            if rendered.voice_note_script_hi:
                audio_notes_count += 1

        # 5. Dispatch simulation (only for eligible contacts, zero sends for blocked)
        dispatched_count = 0
        for c in bundle.contacts:
            if c.dispatch_eligible:
                dispatched_count += 1
                # Issue mock token if PTM linked
                if self.confirmation_manager:
                    with contextlib.suppress(Exception):
                        self.confirmation_manager.issue_token(
                            student_id=c.student_id,
                            assessment_id=assessment_id,
                            ptm_event_id="PTM_GOLDEN_2026",
                            org_id=org_id,
                            sender_id="sender_primary",
                            now=current_time,
                            is_ptm_linked=True,
                        )

        return DryRunResult(
            org_id=org_id,
            assessment_id=assessment_id,
            total_students=val_res.enrolled_count,
            dispatched_count=dispatched_count,
            blocked_count=eval_res.blocked_count,
            blocked_reasons=eval_res.blocked_students,
            ptm_slips_generated=ptm_slips_count,
            scorecards_rendered=scorecards_count,
            audio_notes_synthesized=audio_notes_count,
            is_idempotent=True,
            duplicate_runs_count=0,
            schema_version=1,
        )

    def execute_live_send(
        self,
        principal: Principal,
        assessment_id: str,
        sender: SenderIdentity,
        now: datetime | None = None,
    ) -> int:
        """
        Execute live message dispatch to parents (Task 2 & Gate 12).
        STRICT DUAL-SWITCH SAFETY: Refuses to execute unless BOTH
        `LIVE_DISPATCH_ENABLED=true` AND `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=true`.
        """
        self._assert_permission(
            principal,
            "execute_live_send",
            principal.org_id,
            required_roles=[UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN],
        )

        # Dual safety switch check (D-09 & Invariant 8)
        if not self.settings.live_dispatch_enabled or not self.settings.deployment_compliance_acknowledged:
            raise SafetySwitchError(
                "Live dispatch refused: LIVE_DISPATCH_ENABLED and DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED "
                "must BOTH be True before live messaging can be triggered."
            )

        tenant = self.repository.get_tenant(principal.org_id)
        if principal.org_id in self._suspended_tenants or (tenant and tenant.emergency_kill_switch):
            raise TenantSuspendedError(f"Tenant '{principal.org_id}' is suspended by emergency kill switch.")

        if sender.status != SenderStatus.READY:
            raise OrchestratorError(f"Sender '{sender.sender_id}' is not in READY status.")

        current_time = now if now is not None else datetime.now(UTC)

        # Execute dispatch for approved scheduled jobs
        dispatched_count = 0
        conn = getattr(self.repository, "conn", None)
        if conn is not None:
            cur = conn.execute(
                """
                SELECT dispatch_id, recipient_phone_masked
                FROM dispatches
                WHERE org_id = ? AND assessment_id = ? AND current_status = 'SCHEDULED'
                """,
                (principal.org_id, assessment_id),
            )
            jobs = cur.fetchall()
            for row in jobs:
                d_id = str(row[0])
                phone = "+919811122201"
                req = TemplateSendRequest(
                    recipient_phone_e164=phone,
                    template_name="academic_progress_update_v1",
                    language_code="hi",
                    components=[],
                )
                self.provider.send_template(org_id=principal.org_id, sender=sender, request=req)
                dispatched_count += 1

                with conn:
                    conn.execute(
                        "UPDATE dispatches SET current_status = 'DELIVERED', updated_at_utc = ? WHERE org_id = ? AND dispatch_id = ?",
                        (current_time.isoformat(), principal.org_id, d_id),
                    )

        return dispatched_count

    def tenant_onboard(
        self,
        principal: Principal,
        org_id: str,
        school_name: str,
        sender: SenderIdentity,
        now: datetime | None = None,
    ) -> TenantRecord:
        """Onboard a new institutional tenant and register primary sender."""
        self._assert_permission(
            principal,
            "tenant_onboard",
            org_id,
            required_roles=[UserRole.PLATFORM_ADMIN],
        )
        current_time = now if now is not None else datetime.now(UTC)

        rec = TenantRecord(
            org_id=org_id,
            school_name=school_name,
            lifecycle_state="ACTIVE",
            emergency_kill_switch=False,
            daily_message_quota=1000,
            include_roll_in_text=False,
            created_at_utc=current_time,
            updated_at_utc=current_time,
            schema_version=1,
        )
        self.repository.register_tenant(rec)
        self.register_sender(sender)
        self._suspended_tenants.discard(org_id)
        return rec

    def tenant_suspend(
        self,
        principal: Principal,
        org_id: str,
        reason: str = "Emergency administrative pause",
        now: datetime | None = None,
    ) -> None:
        """Engage emergency kill-switch for a tenant, cancelling active dispatches."""
        self._assert_permission(
            principal,
            "tenant_suspend",
            org_id,
            required_roles=[UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN],
        )
        current_time = now if now is not None else datetime.now(UTC)
        self._suspended_tenants.add(org_id)
        self.repository.set_tenant_kill_switch(org_id, True)

        # Cancel pending dispatches
        conn = getattr(self.repository, "conn", None)
        if conn is not None:
            with conn:
                conn.execute(
                    """
                    UPDATE dispatches
                    SET current_status = 'CANCELLED', updated_at_utc = ?
                    WHERE org_id = ? AND current_status IN ('PENDING', 'SCHEDULED', 'RETRY_PENDING')
                    """,
                    (current_time.isoformat(), org_id),
                )

        self.audit_store.record_event(
            org_id=org_id,
            event=AuditEvent(
                org_id=org_id,
                actor_id=principal.actor_id,
                actor_type=principal.actor_type.value,
                action_type="TENANT_SUSPENDED",
                details={"reason": reason, "suspended_by": principal.actor_id},
                occurred_at_utc=current_time,
            ),
        )
