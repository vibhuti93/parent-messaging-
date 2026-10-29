"""
Stage S8 Messaging Policy Engine, Durable State & Repository Contract Test Suite.

Compliant with:
- Gate 8 in S8.md:
  - STU_02 -> zero sends, exact block reason (INTERCEPTION_RISK_SAME_NUMBER);
  - STU_03/04, 07, 08, 09, 10 blocked;
  - STU_01 and STU_05/06 allowed to proceed to policy-permitted mode;
  - STU_17 eligible only with verified consent;
  - STU_19 blocked;
  - duplicate job invocation yields one logical delivery;
  - state-transition table tests (illegal transitions rejected);
  - restart recovery reloads state.
  - Dual-engine repository contract test suite passes against both SQLite and PostgreSQL.
- Global Invariant 8: Live messaging disabled by default.
- Global Invariant 9: Never infer consent, guardian identity, or sibling status.
- Global Invariant 10: Never log full phone numbers; mask them.
- Global Invariant 13: Fail closed: uncertain input -> REVIEW_REQUIRED / block / defer.
- Global Invariant 15: Explicit tenant context (org_id) on all operations.
- Global Invariant 17: Child names and class labels never logged.
- ADR-0005, ADR-0007, ADR-0017, ADR-0018, ADR-0019, ADR-0020.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from omr_dispatch.contacts import validate_admission_batch
from omr_dispatch.messaging.audit import (
    AuditActionType,
    AuditEvent,
    AuditStore,
)
from omr_dispatch.messaging.policy import (
    MessageIntent,
    PolicyReasonCode,
    SenderPrerequisites,
    ServiceWindowState,
    TenantContextMissingError,
    compute_idempotency_key,
    evaluate_dispatch_policy,
)
from omr_dispatch.messaging.store import (
    DispatchEventRecord,
    DispatchRecord,
    DispatchRepository,
    DispatchState,
    DuplicateWamidEventError,
    IdempotencyCollisionError,
    IllegalStateTransitionError,
    PostgresDispatchRepository,
    SQLiteDispatchRepository,
    TenantRecord,
    create_repository,
)
from omr_dispatch.models import StudentAdmissionRow


@pytest.fixture
def golden_admissions() -> list[StudentAdmissionRow]:
    """Load the approved 20-student golden admissions fixture."""
    fixture_path = Path("fixtures/golden/admissions_300.json")
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)
    return [StudentAdmissionRow.model_validate(s) for s in data["students"]]


@pytest.fixture
def sample_sender() -> SenderPrerequisites:
    """Standard verified sender prerequisites for testing."""
    return SenderPrerequisites(
        org_id="ORG_TEST",
        sender_id="sender_001",
        status="READY",
        waba_id="waba_12345",
        phone_number_id="phone_id_67890",
        has_valid_credentials=True,
        billing_active=True,
        daily_quota=1000,
        messages_sent_today=10,
        approved_templates=["parent_scorecard_v1", "absent_notification_v1"],
    )


@pytest.fixture(params=["sqlite", "postgresql"])
def dual_engine_repo(request: pytest.FixtureRequest, tmp_path: Path) -> Generator[DispatchRepository, None, None]:
    """
    Dual-engine repository fixture:
    Executes repository contract suite against both SQLite and PostgreSQL.
    """
    engine_name = request.param
    if engine_name == "sqlite":
        db_file = tmp_path / f"test_{uuid.uuid4().hex[:8]}.db"
        repo = create_repository(engine="sqlite", db_path=db_file)
    else:
        # PostgreSQL engine: connects to live PostgreSQL if configured,
        # or runs against Postgres DDL contract simulator enforcing RLS policies.
        repo = create_repository(engine="postgresql")

    yield repo
    repo.close()


# ==============================================================================
# Gate 8 Golden Student Policy Tests
# ==============================================================================

class TestGate8GoldenStudentPolicy:
    """Test policy gating against the approved 20-student admissions fixture."""

    def test_gate8_golden_roster_decisions(
        self, golden_admissions: list[StudentAdmissionRow], sample_sender: SenderPrerequisites
    ) -> None:
        """
        Verify exact Gate 8 gating requirements:
          - STU_02: zero sends, exact block reason INTERCEPTION_RISK_SAME_NUMBER
          - STU_03, 04: blocked (DUPLICATE_PARENT_UNVERIFIED)
          - STU_07: blocked (INVALID_PHONE_NUMBER)
          - STU_08: blocked (CONSENT_UNKNOWN)
          - STU_09: blocked (CONSENT_REVOKED)
          - STU_10: blocked (GUARDIAN_UNVERIFIED)
          - STU_01: allowed to proceed to policy-permitted mode
          - STU_05, 06: allowed to proceed (verified siblings sharing guardian phone)
          - STU_17: absent student, eligible with verified consent
          - STU_19: absent student with revoked consent, blocked (CONSENT_REVOKED)
        """
        org_id = "ORG_TEST"
        # Pre-validate contact hygiene
        contact_evals = validate_admission_batch(golden_admissions, org_id=org_id)
        eval_map = {e.student_id: e for e in contact_evals}
        admission_map = {s.student_id: s for s in golden_admissions}

        # 1. STU_02 -> zero sends, exact block reason INTERCEPTION_RISK_SAME_NUMBER
        stu_02_intent = MessageIntent(
            org_id=org_id,
            student_id="STU_02",
            assessment_id="TEST_300",
            template_name="parent_scorecard_v1",
        )
        dec_02 = evaluate_dispatch_policy(
            org_id=org_id,
            admission=admission_map["STU_02"],
            assessment_id="TEST_300",
            contact_eval=eval_map["STU_02"],
            intent=stu_02_intent,
            sender=sample_sender,
        )
        assert dec_02.allowed is False
        assert dec_02.reason_code == PolicyReasonCode.INTERCEPTION_RISK_SAME_NUMBER
        assert dec_02.target_state == "BLOCKED_HYGIENE"

        # 2. STU_03 & STU_04 -> blocked with DUPLICATE_PARENT_UNVERIFIED
        for sid in ("STU_03", "STU_04"):
            intent = MessageIntent(
                org_id=org_id,
                student_id=sid,
                assessment_id="TEST_300",
                template_name="parent_scorecard_v1",
            )
            dec = evaluate_dispatch_policy(
                org_id=org_id,
                admission=admission_map[sid],
                assessment_id="TEST_300",
                contact_eval=eval_map[sid],
                intent=intent,
                sender=sample_sender,
            )
            assert dec.allowed is False
            assert dec.reason_code == PolicyReasonCode.DUPLICATE_PARENT_UNVERIFIED
            assert dec.target_state == "BLOCKED_HYGIENE"

        # 3. STU_07 -> blocked with INVALID_PHONE_NUMBER
        intent_07 = MessageIntent(
            org_id=org_id,
            student_id="STU_07",
            assessment_id="TEST_300",
            template_name="parent_scorecard_v1",
        )
        dec_07 = evaluate_dispatch_policy(
            org_id=org_id,
            admission=admission_map["STU_07"],
            assessment_id="TEST_300",
            contact_eval=eval_map["STU_07"],
            intent=intent_07,
            sender=sample_sender,
        )
        assert dec_07.allowed is False
        assert dec_07.reason_code == PolicyReasonCode.INVALID_PHONE_NUMBER
        assert dec_07.target_state == "BLOCKED_HYGIENE"

        # 4. STU_08 -> blocked with CONSENT_UNKNOWN
        intent_08 = MessageIntent(
            org_id=org_id,
            student_id="STU_08",
            assessment_id="TEST_300",
            template_name="parent_scorecard_v1",
        )
        dec_08 = evaluate_dispatch_policy(
            org_id=org_id,
            admission=admission_map["STU_08"],
            assessment_id="TEST_300",
            contact_eval=eval_map["STU_08"],
            intent=intent_08,
            sender=sample_sender,
        )
        assert dec_08.allowed is False
        assert dec_08.reason_code == PolicyReasonCode.CONSENT_UNKNOWN
        assert dec_08.target_state == "BLOCKED_CONSENT"

        # 5. STU_09 -> blocked with CONSENT_REVOKED
        intent_09 = MessageIntent(
            org_id=org_id,
            student_id="STU_09",
            assessment_id="TEST_300",
            template_name="parent_scorecard_v1",
        )
        dec_09 = evaluate_dispatch_policy(
            org_id=org_id,
            admission=admission_map["STU_09"],
            assessment_id="TEST_300",
            contact_eval=eval_map["STU_09"],
            intent=intent_09,
            sender=sample_sender,
        )
        assert dec_09.allowed is False
        assert dec_09.reason_code == PolicyReasonCode.CONSENT_REVOKED
        assert dec_09.target_state == "BLOCKED_CONSENT"

        # 6. STU_10 -> blocked with GUARDIAN_UNVERIFIED
        intent_10 = MessageIntent(
            org_id=org_id,
            student_id="STU_10",
            assessment_id="TEST_300",
            template_name="parent_scorecard_v1",
        )
        dec_10 = evaluate_dispatch_policy(
            org_id=org_id,
            admission=admission_map["STU_10"],
            assessment_id="TEST_300",
            contact_eval=eval_map["STU_10"],
            intent=intent_10,
            sender=sample_sender,
        )
        assert dec_10.allowed is False
        assert dec_10.reason_code == PolicyReasonCode.GUARDIAN_UNVERIFIED
        assert dec_10.target_state == "BLOCKED_CONSENT"

        # 7. STU_01 -> allowed to proceed to policy-permitted mode
        intent_01 = MessageIntent(
            org_id=org_id,
            student_id="STU_01",
            assessment_id="TEST_300",
            template_name="parent_scorecard_v1",
        )
        dec_01 = evaluate_dispatch_policy(
            org_id=org_id,
            admission=admission_map["STU_01"],
            assessment_id="TEST_300",
            contact_eval=eval_map["STU_01"],
            intent=intent_01,
            sender=sample_sender,
        )
        assert dec_01.allowed is True
        assert dec_01.reason_code == PolicyReasonCode.ALLOWED
        assert dec_01.target_state == "SCHEDULED"

        # 8. STU_05 & STU_06 -> verified siblings, both allowed to proceed
        for sid in ("STU_05", "STU_06"):
            intent = MessageIntent(
                org_id=org_id,
                student_id=sid,
                assessment_id="TEST_300",
                template_name="parent_scorecard_v1",
            )
            dec = evaluate_dispatch_policy(
                org_id=org_id,
                admission=admission_map[sid],
                assessment_id="TEST_300",
                contact_eval=eval_map[sid],
                intent=intent,
                sender=sample_sender,
            )
            assert dec.allowed is True
            assert dec.reason_code == PolicyReasonCode.ALLOWED
            assert dec.target_state == "SCHEDULED"

        # 9. STU_17 -> absent student, eligible with verified consent
        intent_17 = MessageIntent(
            org_id=org_id,
            student_id="STU_17",
            assessment_id="TEST_300",
            template_name="absent_notification_v1",
        )
        dec_17 = evaluate_dispatch_policy(
            org_id=org_id,
            admission=admission_map["STU_17"],
            assessment_id="TEST_300",
            contact_eval=eval_map["STU_17"],
            intent=intent_17,
            sender=sample_sender,
        )
        assert dec_17.allowed is True
        assert dec_17.reason_code == PolicyReasonCode.ALLOWED
        assert dec_17.target_state == "SCHEDULED"

        # 10. STU_19 -> absent student with revoked consent, blocked
        intent_19 = MessageIntent(
            org_id=org_id,
            student_id="STU_19",
            assessment_id="TEST_300",
            template_name="absent_notification_v1",
        )
        dec_19 = evaluate_dispatch_policy(
            org_id=org_id,
            admission=admission_map["STU_19"],
            assessment_id="TEST_300",
            contact_eval=eval_map["STU_19"],
            intent=intent_19,
            sender=sample_sender,
        )
        assert dec_19.allowed is False
        assert dec_19.reason_code == PolicyReasonCode.CONSENT_REVOKED
        assert dec_19.target_state == "BLOCKED_CONSENT"


# ==============================================================================
# Additional Policy Engine Unit Tests
# ==============================================================================

class TestPolicyEngineEdgeCases:
    """Test policy gating boundary conditions."""

    def test_missing_org_id_raises_tenant_context_missing(
        self, golden_admissions: list[StudentAdmissionRow]
    ) -> None:
        """Every policy evaluation must fail closed if org_id is missing (Invariant 15)."""
        adm = golden_admissions[0]
        with pytest.raises(TenantContextMissingError):
            evaluate_dispatch_policy(
                org_id="",
                admission=adm,
                assessment_id="TEST_300",
            )

    def test_global_and_tenant_kill_switches(
        self, golden_admissions: list[StudentAdmissionRow], sample_sender: SenderPrerequisites
    ) -> None:
        """Kill switch halts dispatch immediately with BLOCKED_POLICY."""
        adm = golden_admissions[0]  # STU_01 is normally allowed
        org_id = "ORG_TEST"
        intent = MessageIntent(org_id=org_id, student_id=adm.student_id, assessment_id="TEST_300", template_name="parent_scorecard_v1")

        # Global kill switch
        dec_global = evaluate_dispatch_policy(
            org_id=org_id,
            admission=adm,
            assessment_id="TEST_300",
            intent=intent,
            sender=sample_sender,
            global_kill_switch=True,
        )
        assert dec_global.allowed is False
        assert dec_global.reason_code == PolicyReasonCode.GLOBAL_KILL_SWITCH_ENGAGED
        assert dec_global.target_state == "BLOCKED_POLICY"

        # Tenant kill switch
        dec_tenant = evaluate_dispatch_policy(
            org_id=org_id,
            admission=adm,
            assessment_id="TEST_300",
            intent=intent,
            sender=sample_sender,
            tenant_kill_switch=True,
        )
        assert dec_tenant.allowed is False
        assert dec_tenant.reason_code == PolicyReasonCode.TENANT_KILL_SWITCH_ENGAGED
        assert dec_tenant.target_state == "BLOCKED_POLICY"

    def test_service_window_and_freeform_policy(
        self, golden_admissions: list[StudentAdmissionRow], sample_sender: SenderPrerequisites
    ) -> None:
        """Free-form messages are permitted ONLY when 24h service window is active."""
        adm = golden_admissions[0]
        org_id = "ORG_TEST"
        freeform_intent = MessageIntent(
            org_id=org_id,
            student_id=adm.student_id,
            assessment_id="TEST_300",
            is_freeform=True,
        )

        # Inactive window -> BLOCKED_POLICY
        dec_closed = evaluate_dispatch_policy(
            org_id=org_id,
            admission=adm,
            assessment_id="TEST_300",
            intent=freeform_intent,
            sender=sample_sender,
            service_window=ServiceWindowState(is_active=False),
        )
        assert dec_closed.allowed is False
        assert dec_closed.reason_code == PolicyReasonCode.SERVICE_WINDOW_CLOSED_FOR_FREEFORM
        assert dec_closed.target_state == "BLOCKED_POLICY"

        # Active window -> ALLOWED
        dec_open = evaluate_dispatch_policy(
            org_id=org_id,
            admission=adm,
            assessment_id="TEST_300",
            intent=freeform_intent,
            sender=sample_sender,
            service_window=ServiceWindowState(is_active=True),
        )
        assert dec_open.allowed is True
        assert dec_open.target_state == "SCHEDULED"

    def test_template_approval_and_content_constraints(
        self, golden_admissions: list[StudentAdmissionRow], sample_sender: SenderPrerequisites
    ) -> None:
        """Template must be registered, approved, and satisfy content constraints."""
        adm = golden_admissions[0]
        org_id = "ORG_TEST"

        # Missing template on non-freeform
        intent_missing = MessageIntent(
            org_id=org_id,
            student_id=adm.student_id,
            assessment_id="TEST_300",
            template_name=None,
        )
        dec_missing = evaluate_dispatch_policy(
            org_id=org_id,
            admission=adm,
            assessment_id="TEST_300",
            intent=intent_missing,
            sender=sample_sender,
        )
        assert dec_missing.allowed is False
        assert dec_missing.reason_code == PolicyReasonCode.TEMPLATE_NOT_APPROVED

        # Unapproved template
        intent_unapproved = MessageIntent(
            org_id=org_id,
            student_id=adm.student_id,
            assessment_id="TEST_300",
            template_name="unapproved_template_xyz",
        )
        dec_unapproved = evaluate_dispatch_policy(
            org_id=org_id,
            admission=adm,
            assessment_id="TEST_300",
            intent=intent_unapproved,
            sender=sample_sender,
        )
        assert dec_unapproved.allowed is False
        assert dec_unapproved.reason_code == PolicyReasonCode.TEMPLATE_NOT_APPROVED

        # Content constraint violation
        intent_content_invalid = MessageIntent(
            org_id=org_id,
            student_id=adm.student_id,
            assessment_id="TEST_300",
            template_name="parent_scorecard_v1",
            template_content_valid=False,
        )
        dec_invalid_content = evaluate_dispatch_policy(
            org_id=org_id,
            admission=adm,
            assessment_id="TEST_300",
            intent=intent_content_invalid,
            sender=sample_sender,
        )
        assert dec_invalid_content.allowed is False
        assert dec_invalid_content.reason_code == PolicyReasonCode.TEMPLATE_CONTENT_MISMATCH

    def test_daily_quota_and_sender_readiness(
        self, golden_admissions: list[StudentAdmissionRow], sample_sender: SenderPrerequisites
    ) -> None:
        """Sender not ready or exceeding daily quota is blocked."""
        adm = golden_admissions[0]
        org_id = "ORG_TEST"
        intent = MessageIntent(
            org_id=org_id,
            student_id=adm.student_id,
            assessment_id="TEST_300",
            template_name="parent_scorecard_v1",
        )

        # Quota exceeded
        exhausted_sender = sample_sender.model_copy(update={"messages_sent_today": 1000, "daily_quota": 1000})
        dec_quota = evaluate_dispatch_policy(
            org_id=org_id,
            admission=adm,
            assessment_id="TEST_300",
            intent=intent,
            sender=exhausted_sender,
        )
        assert dec_quota.allowed is False
        assert dec_quota.reason_code == PolicyReasonCode.DAILY_QUOTA_EXCEEDED

        # Sender suspended
        suspended_sender = sample_sender.model_copy(update={"status": "SUSPENDED"})
        dec_suspended = evaluate_dispatch_policy(
            org_id=org_id,
            admission=adm,
            assessment_id="TEST_300",
            intent=intent,
            sender=suspended_sender,
        )
        assert dec_suspended.allowed is False
        assert dec_suspended.reason_code == PolicyReasonCode.SENDER_NOT_READY


# ==============================================================================
# Idempotency and Deduplication Tests
# ==============================================================================

class TestIdempotencyAndKeys:
    """Verify Task 3 per-org idempotency key construction and duplicate delivery prevention."""

    def test_idempotency_key_composition_has_no_phone_numbers(self) -> None:
        """Idempotency key formula must contain zero raw phone numbers (Task 3)."""
        key = compute_idempotency_key(
            org_id="ORG_A",
            student_id="STU_01",
            assessment_id="ASSESS_01",
            purpose="EXAM_RESULTS",
            channel="WHATSAPP",
            event_type="PRIMARY",
        )
        assert len(key) == 64
        # Assert exact frozen literal matching sha256("ORG_A:STU_01:ASSESS_01:EXAM_RESULTS:WHATSAPP:PRIMARY")
        assert key == "97135106d51f51ae74887e88c4654f1a2605b1dd9b7ae7b4f85391f9ec6da214"
        # Verify deterministic
        key2 = compute_idempotency_key(
            org_id="ORG_A",
            student_id="STU_01",
            assessment_id="ASSESS_01",
            purpose="EXAM_RESULTS",
            channel="WHATSAPP",
            event_type="PRIMARY",
        )
        assert key == key2

        # Distinct reminder event yields distinct key
        key_reminder = compute_idempotency_key(
            org_id="ORG_A",
            student_id="STU_01",
            assessment_id="ASSESS_01",
            purpose="EXAM_RESULTS",
            channel="WHATSAPP",
            event_type="REMINDER",
        )
        assert key != key_reminder

        # Distinct org yields distinct key
        key_org_b = compute_idempotency_key(
            org_id="ORG_B",
            student_id="STU_01",
            assessment_id="ASSESS_01",
            purpose="EXAM_RESULTS",
            channel="WHATSAPP",
            event_type="PRIMARY",
        )
        assert key != key_org_b

    def test_duplicate_job_invocation_yields_one_logical_delivery(
        self, dual_engine_repo: DispatchRepository
    ) -> None:
        """
        Gate 8: duplicate job invocation yields one logical delivery.
        Second creation attempt with the same idempotency key raises IdempotencyCollisionError.
        """
        repo = dual_engine_repo
        org_id = "ORG_ALPHA"
        now = datetime.now(UTC)
        idem_key = compute_idempotency_key(org_id, "STU_01", "TEST_1")

        # 1. First job invocation
        dispatch = DispatchRecord(
            dispatch_id=str(uuid.uuid4()),
            org_id=org_id,
            assessment_id="TEST_1",
            student_id="STU_01",
            recipient_phone_masked="98*** **02",
            idempotency_key=idem_key,
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        initial_event = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch.dispatch_id,
            org_id=org_id,
            event_type=DispatchState.SCHEDULED,
            occurred_at_utc=now,
        )
        created = repo.create_dispatch(org_id, dispatch, initial_event)
        assert created.dispatch_id == dispatch.dispatch_id

        # 2. Second job invocation: lookup detects existing delivery
        existing = repo.get_dispatch_by_idempotency_key(org_id, idem_key)
        assert existing is not None
        assert existing.dispatch_id == dispatch.dispatch_id

        # 3. Direct duplicate insertion fails closed via DB constraint
        duplicate_dispatch = DispatchRecord(
            dispatch_id=str(uuid.uuid4()),
            org_id=org_id,
            assessment_id="TEST_1",
            student_id="STU_01",
            recipient_phone_masked="98*** **02",
            idempotency_key=idem_key,
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        with pytest.raises(IdempotencyCollisionError):
            repo.create_dispatch(org_id, duplicate_dispatch, initial_event)

        # 4. Total dispatches in org remains exactly 1
        all_dispatches = repo.list_dispatches(org_id)
        assert len(all_dispatches) == 1


# ==============================================================================
# State Transition Table Tests
# ==============================================================================

class TestStateTransitionTable:
    """Exhaustive tests of the 13 dispatch states and state-transition table."""

    def test_valid_lifecycle_transitions(self, dual_engine_repo: DispatchRepository) -> None:
        """
        Verify happy-path transition sequence:
        PENDING -> SCHEDULED -> UPLOADING_MEDIA -> SUBMITTED -> DELIVERED -> READ.
        """
        repo = dual_engine_repo
        org_id = "ORG_BETA"
        now = datetime.now(UTC)
        dispatch_id = str(uuid.uuid4())
        idem_key = compute_idempotency_key(org_id, "STU_01", "TEST_2")

        # 1. PENDING
        dispatch = DispatchRecord(
            dispatch_id=dispatch_id,
            org_id=org_id,
            assessment_id="TEST_2",
            student_id="STU_01",
            recipient_phone_masked="98*** **02",
            idempotency_key=idem_key,
            current_status=DispatchState.PENDING,
            created_at_utc=now,
            updated_at_utc=now,
        )
        init_event = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.PENDING,
            occurred_at_utc=now,
        )
        repo.create_dispatch(org_id, dispatch, init_event)

        # 2. PENDING -> SCHEDULED
        ev_sched = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.SCHEDULED,
            occurred_at_utc=now,
        )
        rec = repo.record_event(org_id, ev_sched)
        assert rec.current_status == DispatchState.SCHEDULED

        # 3. SCHEDULED -> UPLOADING_MEDIA
        ev_upload = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.UPLOADING_MEDIA,
            occurred_at_utc=now,
        )
        rec = repo.record_event(org_id, ev_upload)
        assert rec.current_status == DispatchState.UPLOADING_MEDIA

        # 4. UPLOADING_MEDIA -> SUBMITTED
        ev_submit = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.SUBMITTED,
            provider_wamid="wamid.HBgLMTE=",
            occurred_at_utc=now,
        )
        rec = repo.record_event(org_id, ev_submit)
        assert rec.current_status == DispatchState.SUBMITTED

        # 5. SUBMITTED -> DELIVERED
        ev_delivered = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.DELIVERED,
            provider_wamid="wamid.HBgLMTE=",
            occurred_at_utc=now,
        )
        rec = repo.record_event(org_id, ev_delivered)
        assert rec.current_status == DispatchState.DELIVERED

        # 6. DELIVERED -> READ
        ev_read = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.READ,
            provider_wamid="wamid.HBgLMTE=",
            occurred_at_utc=now,
        )
        rec = repo.record_event(org_id, ev_read)
        assert rec.current_status == DispatchState.READ

        # Verify historical event count
        history = repo.list_events_for_dispatch(org_id, dispatch_id)
        assert len(history) == 6

    def test_illegal_state_transitions_rejected(self, dual_engine_repo: DispatchRepository) -> None:
        """Gate 8: state-transition table tests (illegal transitions rejected)."""
        repo = dual_engine_repo
        org_id = "ORG_GAMMA"
        now = datetime.now(UTC)
        dispatch_id = str(uuid.uuid4())
        idem_key = compute_idempotency_key(org_id, "STU_02", "TEST_3")

        # Start with BLOCKED_CONSENT (terminal state)
        dispatch = DispatchRecord(
            dispatch_id=dispatch_id,
            org_id=org_id,
            assessment_id="TEST_3",
            student_id="STU_02",
            recipient_phone_masked="98*** **03",
            idempotency_key=idem_key,
            current_status=DispatchState.BLOCKED_CONSENT,
            created_at_utc=now,
            updated_at_utc=now,
        )
        init_event = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.BLOCKED_CONSENT,
            occurred_at_utc=now,
        )
        repo.create_dispatch(org_id, dispatch, init_event)

        # Illegal transition 1: BLOCKED_CONSENT -> DELIVERED
        illegal_ev1 = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.DELIVERED,
            occurred_at_utc=now,
        )
        with pytest.raises(IllegalStateTransitionError):
            repo.record_event(org_id, illegal_ev1)

        # Illegal transition 2: BLOCKED_CONSENT -> SCHEDULED
        illegal_ev2 = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.SCHEDULED,
            occurred_at_utc=now,
        )
        with pytest.raises(IllegalStateTransitionError):
            repo.record_event(org_id, illegal_ev2)

        # Illegal transition 3: DELIVERED -> PENDING
        # Create a delivered dispatch
        disp_deliv_id = str(uuid.uuid4())
        disp_deliv = DispatchRecord(
            dispatch_id=disp_deliv_id,
            org_id=org_id,
            assessment_id="TEST_3",
            student_id="STU_03",
            recipient_phone_masked="98*** **03",
            idempotency_key="key_delivered_test",
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        repo.create_dispatch(
            org_id,
            disp_deliv,
            DispatchEventRecord(
                event_id=str(uuid.uuid4()),
                dispatch_id=disp_deliv_id,
                org_id=org_id,
                event_type=DispatchState.SCHEDULED,
                occurred_at_utc=now,
            ),
        )
        repo.record_event(
            org_id,
            DispatchEventRecord(
                event_id=str(uuid.uuid4()),
                dispatch_id=disp_deliv_id,
                org_id=org_id,
                event_type=DispatchState.SUBMITTED,
                occurred_at_utc=now,
            ),
        )
        repo.record_event(
            org_id,
            DispatchEventRecord(
                event_id=str(uuid.uuid4()),
                dispatch_id=disp_deliv_id,
                org_id=org_id,
                event_type=DispatchState.DELIVERED,
                occurred_at_utc=now,
            ),
        )
        # Attempt illegal transition DELIVERED -> PENDING
        illegal_deliv_to_pending = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=disp_deliv_id,
            org_id=org_id,
            event_type=DispatchState.PENDING,
            occurred_at_utc=now,
        )
        with pytest.raises(IllegalStateTransitionError):
            repo.record_event(org_id, illegal_deliv_to_pending)

    def test_duplicate_wamid_deduplication(self, dual_engine_repo: DispatchRepository) -> None:
        """DB unique constraint on (org_id, provider_wamid, event_type) rejects duplicate events."""
        repo = dual_engine_repo
        org_id = "ORG_DELTA"
        now = datetime.now(UTC)
        dispatch_id = str(uuid.uuid4())
        idem_key = compute_idempotency_key(org_id, "STU_03", "TEST_4")

        dispatch = DispatchRecord(
            dispatch_id=dispatch_id,
            org_id=org_id,
            assessment_id="TEST_4",
            student_id="STU_03",
            recipient_phone_masked="98*** **04",
            idempotency_key=idem_key,
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        init_event = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.SCHEDULED,
            occurred_at_utc=now,
        )
        repo.create_dispatch(org_id, dispatch, init_event)

        # Transition to SUBMITTED
        sub_event = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.SUBMITTED,
            provider_wamid="wamid.TEST_DEDUP_123",
            occurred_at_utc=now,
        )
        repo.record_event(org_id, sub_event)

        # Record DELIVERED event
        deliv_event = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.DELIVERED,
            provider_wamid="wamid.TEST_DEDUP_123",
            occurred_at_utc=now,
        )
        repo.record_event(org_id, deliv_event)

        # Attempt duplicate DELIVERED event with same wamid -> DuplicateWamidEventError
        deliv_dup = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.DELIVERED,
            provider_wamid="wamid.TEST_DEDUP_123",
            occurred_at_utc=now,
        )
        with pytest.raises(DuplicateWamidEventError):
            repo.record_event(org_id, deliv_dup)


# ==============================================================================
# Restart Recovery Tests
# ==============================================================================

class TestRestartRecovery:
    """Gate 8: restart recovery reloads state."""

    def test_sqlite_restart_recovery_reloads_state(self, tmp_path: Path) -> None:
        """Verify that opening an existing SQLite database reloads state and event logs."""
        db_file = tmp_path / "persistent_dispatches.db"
        org_id = "ORG_RESTART"
        now = datetime.now(UTC)
        dispatch_id = str(uuid.uuid4())
        idem_key = compute_idempotency_key(org_id, "STU_RESTART", "TEST_R")

        # Session 1: Create repository, insert dispatch, transition to SUBMITTED
        repo1 = SQLiteDispatchRepository(db_path=db_file)
        dispatch = DispatchRecord(
            dispatch_id=dispatch_id,
            org_id=org_id,
            assessment_id="TEST_R",
            student_id="STU_RESTART",
            recipient_phone_masked="98*** **99",
            idempotency_key=idem_key,
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        init_event = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.SCHEDULED,
            occurred_at_utc=now,
        )
        repo1.create_dispatch(org_id, dispatch, init_event)

        submit_event = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_id,
            org_id=org_id,
            event_type=DispatchState.SUBMITTED,
            provider_wamid="wamid.RESTART_OK",
            occurred_at_utc=now,
        )
        repo1.record_event(org_id, submit_event)
        repo1.close()

        # Session 2: Crash / Restart recovery -> Re-open repository from same file
        repo2 = SQLiteDispatchRepository(db_path=db_file)
        recovered = repo2.get_dispatch_by_id(org_id, dispatch_id)
        assert recovered is not None
        assert recovered.current_status == DispatchState.SUBMITTED
        assert recovered.idempotency_key == idem_key

        events = repo2.list_events_for_dispatch(org_id, dispatch_id)
        assert len(events) == 2
        assert events[0].event_type == DispatchState.SCHEDULED
        assert events[1].event_type == DispatchState.SUBMITTED
        repo2.close()


# ==============================================================================
# Multi-Tenant Isolation & Repository Contract Tests
# ==============================================================================

class TestMultiTenantIsolation:
    """Verify ADR-0017 and Invariant 15 tenant isolation gates."""

    def test_missing_tenant_context_gate(self, dual_engine_repo: DispatchRepository) -> None:
        """Repository operations without org context must fail closed (Invariant 15)."""
        repo = dual_engine_repo
        now = datetime.now(UTC)
        dispatch = DispatchRecord(
            dispatch_id=str(uuid.uuid4()),
            org_id="ORG_TEST",
            assessment_id="TEST_1",
            student_id="STU_01",
            recipient_phone_masked="98*** **01",
            idempotency_key="key_test",
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        event = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch.dispatch_id,
            org_id="ORG_TEST",
            event_type=DispatchState.SCHEDULED,
            occurred_at_utc=now,
        )

        # Empty or whitespace org_id raises TenantContextMissingError
        with pytest.raises(TenantContextMissingError):
            repo.create_dispatch("", dispatch, event)

        with pytest.raises(TenantContextMissingError):
            repo.get_dispatch_by_id("", "dispatch_123")

        with pytest.raises(TenantContextMissingError):
            repo.list_dispatches("")

        with pytest.raises(TenantContextMissingError):
            repo.cancel_pending_for_org("   ")

    def test_cross_tenant_data_isolation(self, dual_engine_repo: DispatchRepository) -> None:
        """Dispatches in ORG_A must never be visible or mutable from ORG_B (ADR-0017)."""
        repo = dual_engine_repo
        now = datetime.now(UTC)

        # Ingest STU_01 in ORG_A
        dispatch_a = DispatchRecord(
            dispatch_id=str(uuid.uuid4()),
            org_id="ORG_A",
            assessment_id="TEST_ISO",
            student_id="STU_01",
            recipient_phone_masked="98*** **01",
            idempotency_key=compute_idempotency_key("ORG_A", "STU_01", "TEST_ISO"),
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        event_a = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_a.dispatch_id,
            org_id="ORG_A",
            event_type=DispatchState.SCHEDULED,
            occurred_at_utc=now,
        )
        repo.create_dispatch("ORG_A", dispatch_a, event_a)

        # Ingest STU_01 in ORG_B with identical student ID
        dispatch_b = DispatchRecord(
            dispatch_id=str(uuid.uuid4()),
            org_id="ORG_B",
            assessment_id="TEST_ISO",
            student_id="STU_01",
            recipient_phone_masked="98*** **02",
            idempotency_key=compute_idempotency_key("ORG_B", "STU_01", "TEST_ISO"),
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        event_b = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_b.dispatch_id,
            org_id="ORG_B",
            event_type=DispatchState.SCHEDULED,
            occurred_at_utc=now,
        )
        repo.create_dispatch("ORG_B", dispatch_b, event_b)

        # Querying ORG_A returns strictly ORG_A dispatch
        list_a = repo.list_dispatches("ORG_A")
        assert len(list_a) == 1
        assert list_a[0].dispatch_id == dispatch_a.dispatch_id

        # Querying ORG_B returns strictly ORG_B dispatch
        list_b = repo.list_dispatches("ORG_B")
        assert len(list_b) == 1
        assert list_b[0].dispatch_id == dispatch_b.dispatch_id

        # ORG_B cannot retrieve ORG_A dispatch by ID
        cross_fetch = repo.get_dispatch_by_id("ORG_B", dispatch_a.dispatch_id)
        assert cross_fetch is None

    def test_postgres_rls_raw_query_defence_in_depth(self) -> None:
        """
        ADR-0017 Section 6: Set session app.current_org_id = 'ORG_A';
        Raw query targeting ORG_B returns 0 rows under Postgres RLS enforcement.
        """
        pg_repo = PostgresDispatchRepository()
        now = datetime.now(UTC)

        # Insert dispatch for ORG_B
        dispatch_b = DispatchRecord(
            dispatch_id=str(uuid.uuid4()),
            org_id="ORG_B",
            assessment_id="TEST_RLS",
            student_id="STU_RLS",
            recipient_phone_masked="98*** **99",
            idempotency_key="key_rls_b",
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        event_b = DispatchEventRecord(
            event_id=str(uuid.uuid4()),
            dispatch_id=dispatch_b.dispatch_id,
            org_id="ORG_B",
            event_type=DispatchState.SCHEDULED,
            occurred_at_utc=now,
        )
        pg_repo.create_dispatch("ORG_B", dispatch_b, event_b)

        # Execute raw query under session context ORG_A attempting to select ORG_B
        results = pg_repo.execute_raw_rls_query(
            session_org_id="ORG_A",
            query="SELECT * FROM dispatches WHERE org_id = 'ORG_B'",
        )
        # Under RLS defence in depth, cross-tenant rows are blocked (returns 0 rows)
        assert len(results) == 0
        pg_repo.close()

    def test_tenant_kill_switch_cancels_pending_dispatches(
        self, dual_engine_repo: DispatchRepository
    ) -> None:
        """Emergency kill-switch cancels pending and scheduled dispatches for that org only (Task 4)."""
        repo = dual_engine_repo
        now = datetime.now(UTC)

        # Register tenants
        tenant_a = TenantRecord(
            org_id="ORG_KS_A",
            school_name="School A",
            created_at_utc=now,
            updated_at_utc=now,
        )
        tenant_b = TenantRecord(
            org_id="ORG_KS_B",
            school_name="School B",
            created_at_utc=now,
            updated_at_utc=now,
        )
        repo.register_tenant(tenant_a)
        repo.register_tenant(tenant_b)

        # Create scheduled dispatches for both tenants
        disp_a = DispatchRecord(
            dispatch_id=str(uuid.uuid4()),
            org_id="ORG_KS_A",
            assessment_id="TEST_KS",
            student_id="STU_A",
            recipient_phone_masked="98*** **01",
            idempotency_key="key_ks_a",
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        repo.create_dispatch(
            "ORG_KS_A",
            disp_a,
            DispatchEventRecord(
                event_id=str(uuid.uuid4()),
                dispatch_id=disp_a.dispatch_id,
                org_id="ORG_KS_A",
                event_type=DispatchState.SCHEDULED,
                occurred_at_utc=now,
            ),
        )

        disp_b = DispatchRecord(
            dispatch_id=str(uuid.uuid4()),
            org_id="ORG_KS_B",
            assessment_id="TEST_KS",
            student_id="STU_B",
            recipient_phone_masked="98*** **02",
            idempotency_key="key_ks_b",
            current_status=DispatchState.SCHEDULED,
            created_at_utc=now,
            updated_at_utc=now,
        )
        repo.create_dispatch(
            "ORG_KS_B",
            disp_b,
            DispatchEventRecord(
                event_id=str(uuid.uuid4()),
                dispatch_id=disp_b.dispatch_id,
                org_id="ORG_KS_B",
                event_type=DispatchState.SCHEDULED,
                occurred_at_utc=now,
            ),
        )

        # Activate kill-switch on ORG_KS_A
        repo.set_tenant_kill_switch("ORG_KS_A", active=True)

        # ORG_KS_A dispatch transitions to CANCELLED
        reloaded_a = repo.get_dispatch_by_id("ORG_KS_A", disp_a.dispatch_id)
        assert reloaded_a is not None
        assert reloaded_a.current_status == DispatchState.CANCELLED

        # ORG_KS_B dispatch remains untouched (SCHEDULED)
        reloaded_b = repo.get_dispatch_by_id("ORG_KS_B", disp_b.dispatch_id)
        assert reloaded_b is not None
        assert reloaded_b.current_status == DispatchState.SCHEDULED


# ==============================================================================
# Audit Log & Privacy Invariant Tests
# ==============================================================================

class TestAuditLogHygiene:
    """Verify Invariant 10 and Invariant 17 privacy sanitization in audit trails."""

    def test_audit_log_scrubs_names_and_masks_phones(
        self, dual_engine_repo: DispatchRepository
    ) -> None:
        """
        Audit logging must:
          - Mask Indian phone numbers (Invariant 10)
          - Redact child names (child_display_name) and class labels (Invariant 17)
          - Redact tokens and scores (Invariant 10)
        """
        repo = dual_engine_repo
        audit_store = AuditStore(repo)
        org_id = "ORG_AUDIT"
        now = datetime.now(UTC)

        raw_details = {
            "child_display_name": "आरव",
            "student_name": "Aarav Sharma",
            "class_section": "कक्षा 10-A",
            "guardian_phone": "+91 98111-22202",
            "access_token": "EAAB1234567890abcdef",
            "total_score": 55,
            "decision": "BLOCKED_CONSENT",
        }

        event = AuditEvent(
            audit_id=str(uuid.uuid4()),
            org_id=org_id,
            actor_type="CLI",
            actor_id="operator_1",
            action_type=AuditActionType.POLICY_EVALUATION,
            target_id="STU_01",
            reason_code="CONSENT_REVOKED",
            details=raw_details,
            occurred_at_utc=now,
        )

        audit_store.record_event(org_id=org_id, event=event)

        # Query back and verify sanitized contents
        stored_events = audit_store.list_events(org_id=org_id)
        assert len(stored_events) == 1
        d = stored_events[0].details

        # Invariant 17: Zero child names or class sections
        assert d["child_display_name"] == "[REDACTED_NAME]"
        assert d["student_name"] == "[REDACTED_NAME]"
        assert d["class_section"] == "[REDACTED_CLASS]"

        # Invariant 10: Masked phone numbers and redacted secrets/scores
        assert d["guardian_phone"] == "98*** **02"
        assert d["access_token"] == "[REDACTED_SECRET]"
        assert d["total_score"] == "[REDACTED_SCORE]"
        assert d["decision"] == "BLOCKED_CONSENT"
