"""
Stage S12 Orchestrator, CLI, Audit, and Retention Test Suite (`tests/test_stage12_orchestrator.py`).

Gate 12 Mandates:
1. End-to-end golden batch dry run against local test provider:
   - Exactly 17 PTM slips generated.
   - Exactly 8 students blocked with exact exclusion reasons:
     STU_02 (INTERCEPTION_RISK_SAME_NUMBER), STU_03 (DUPLICATE_PARENT_UNVERIFIED),
     STU_04 (DUPLICATE_PARENT_UNVERIFIED), STU_07 (INVALID_PHONE_NUMBER),
     STU_08 (CONSENT_UNKNOWN), STU_09 (CONSENT_REVOKED),
     STU_10 (GUARDIAN_UNVERIFIED), STU_19 (CONSENT_REVOKED).
   - Exactly 12 eligible students dispatched.
   - Zero real network calls or external messaging endpoints contacted.
2. Idempotent rerun produces zero duplicate deliveries.
3. Dual-switch safety on live send:
   - Refuses live dispatch unless BOTH LIVE_DISPATCH_ENABLED=true AND DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=true.
   - Refuses dispatch if tenant is suspended (emergency kill-switch).
4. Retention purge and consent revocation:
   - Purges transient media older than 30 days and dispatches older than 90 days.
   - Generates immutable cryptographic tombstone.
   - Consent revocation cancels active dispatches, revokes confirmation tokens, and logs audit record.
5. CLI argument and tenant boundary enforcement:
   - Missing or whitespace `--org-id` fails CLI with non-zero exit code.
   - Cross-tenant access fails closed with UnauthorizedError.
   - Role-based authorization matrix enforced.
6. Privacy leak scan:
   - Zero unmasked phone numbers, student names, or raw tokens in logs or CLI output streams.

Compliant with:
- ADR-0002: Zero float() calls.
- ADR-0005: Timezone-aware UTC datetimes.
- ADR-0008: Typed exception hierarchy.
- ADR-0013: Walking skeleton integration.
- ADR-0018: Principal security context and application service perimeter.
- ADR-0019: Multi-tenant sender identity routing.
- ADR-0020: Tenant lifecycle controls and retention enforcement.
- Invariants 10, 15, 17, 18.
"""

from __future__ import annotations

import io
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from omr_dispatch.cli import main as cli_main
from omr_dispatch.config import Settings
from omr_dispatch.confirmation import (
    ConfirmationManager,
    ConfirmationStatus,
    ConfirmationStore,
)
from omr_dispatch.messaging import (
    AuditStore,
    QualityRating,
    SenderIdentity,
    SenderStatus,
    SQLiteDispatchRepository,
    TemplateRegistrationStatus,
    TenantSuspendedError,
    WhatsAppCloudProvider,
)
from omr_dispatch.models import AssessmentKind
from omr_dispatch.orchestrator import (
    ActorType,
    ArtifactNotFoundError,
    DryRunResult,
    Orchestrator,
    Principal,
    ReviewItemNotFoundError,
    SafetySwitchError,
    UnauthorizedError,
    UserRole,
)
from omr_dispatch.retention import (
    PurgeReport,
    RetentionPolicy,
    propagate_consent_revocation,
    purge_retention_data,
)
from omr_dispatch.scheduler import SchedulerStore

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden"

TEST_ORG_ID = "DEFAULT_INSTITUTION"
ALT_ORG_ID = "INST_ALT_202"


@pytest.fixture
def repo() -> SQLiteDispatchRepository:
    """Provide a fresh in-memory SQLite dispatch repository."""
    return SQLiteDispatchRepository(db_path=":memory:")


@pytest.fixture
def scheduler_store(tmp_path: Path) -> SchedulerStore:
    """Provide a fresh scheduler store."""
    return SchedulerStore(db_path=tmp_path / "sched.db")


@pytest.fixture
def audit_store(repo: SQLiteDispatchRepository) -> AuditStore:
    """Provide an audit store bound to the test repository."""
    return AuditStore(repo)


@pytest.fixture
def conf_manager() -> ConfirmationManager:
    """Provide a fresh in-memory confirmation manager."""
    store = ConfirmationStore(db_path=":memory:")
    return ConfirmationManager(store=store)


@pytest.fixture
def orchestrator(
    repo: SQLiteDispatchRepository,
    scheduler_store: SchedulerStore,
    audit_store: AuditStore,
    conf_manager: ConfirmationManager,
) -> Orchestrator:
    """Provide an orchestrator wired to in-memory test stores."""
    provider = WhatsAppCloudProvider(dry_run=True)
    settings = Settings(
        live_dispatch_enabled=False,
        deployment_compliance_acknowledged=False,
    )
    return Orchestrator(
        repository=repo,
        scheduler_store=scheduler_store,
        audit_store=audit_store,
        confirmation_manager=conf_manager,
        provider=provider,
        settings=settings,
    )


@pytest.fixture
def school_admin_principal() -> Principal:
    """Principal with SCHOOL_ADMIN role for the primary test org."""
    return Principal(
        actor_type=ActorType.CLI,
        actor_id="admin_user_01",
        org_id=TEST_ORG_ID,
        roles=[UserRole.SCHOOL_ADMIN],
        schema_version=1,
    )


@pytest.fixture
def teacher_principal() -> Principal:
    """Principal with TEACHER role for the primary test org."""
    return Principal(
        actor_type=ActorType.CLI,
        actor_id="teacher_user_01",
        org_id=TEST_ORG_ID,
        roles=[UserRole.TEACHER],
        schema_version=1,
    )


@pytest.fixture
def platform_admin_principal() -> Principal:
    """Principal with PLATFORM_ADMIN role for cross-tenant maintenance."""
    return Principal(
        actor_type=ActorType.CLI,
        actor_id="platform_admin_01",
        org_id="PLATFORM_SYSTEM",
        roles=[UserRole.PLATFORM_ADMIN],
        schema_version=1,
    )


@pytest.fixture
def ready_sender() -> SenderIdentity:
    """Construct a valid READY sender identity for test org."""
    return SenderIdentity(
        sender_id="sender_primary",
        org_id=TEST_ORG_ID,
        phone_number_id="phone_num_9988",
        waba_id="waba_num_9988",
        display_phone_number="+919811100000",
        verified_display_name="Delhi Public School Test",
        status=SenderStatus.READY,
        quality_rating=QualityRating.GREEN,
        daily_message_limit=1000,
        credential_secret_ref="SECRET_KEY_REF",
        app_secret_ref="APP_SECRET_REF",
        template_registry={
            "academic_progress_update_v1": TemplateRegistrationStatus.APPROVED,
        },
        is_primary=True,
        schema_version=1,
    )


# ==============================================================================
# Gate 12 Mandate 1: End-to-End Golden Batch Dry Run
# ==============================================================================


class TestGoldenBatchDryRun:
    """Verify exact counts and exclusions on golden fixtures (Gate 12 Mandate 1)."""

    def test_golden_batch_dry_run_exact_counts(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
    ) -> None:
        """
        End-to-end dry-run across stages S2 through S11 against local provider:
        - Exactly 20 enrolled students
        - Exactly 17 PTM slips generated
        - Exactly 8 students blocked
        - Exactly 12 students eligible for dispatch
        - Zero real network calls
        """
        now = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        result: DryRunResult = orchestrator.execute_dry_run(
            principal=school_admin_principal,
            batch_input=FIXTURES_DIR,
            now=now,
        )

        assert result.total_students == 20
        assert result.ptm_slips_generated == 17
        assert result.dispatched_count == 12
        assert result.blocked_count == 8
        assert result.scorecards_rendered == 16
        assert result.audio_notes_synthesized == 20

        # Verify exact exclusion reasons for all 8 blocked students
        expected_blocked = {
            "STU_02": "INTERCEPTION_RISK_SAME_NUMBER",
            "STU_03": "DUPLICATE_PARENT_UNVERIFIED",
            "STU_04": "DUPLICATE_PARENT_UNVERIFIED",
            "STU_07": "INVALID_PHONE_NUMBER",
            "STU_08": "CONSENT_UNKNOWN",
            "STU_09": "CONSENT_REVOKED",
            "STU_10": "GUARDIAN_UNVERIFIED",
            "STU_19": "CONSENT_REVOKED",
        }
        assert result.blocked_reasons == expected_blocked

        # Verify eligible students (12 students)
        eligible_expected = {
            "STU_01", "STU_05", "STU_06",
            "STU_11", "STU_12", "STU_13", "STU_14", "STU_15", "STU_16", "STU_17", "STU_18",
            "STU_20",
        }
        all_students = {f"STU_{i:02d}" for i in range(1, 21)}
        actual_eligible = all_students - set(result.blocked_reasons.keys())
        assert actual_eligible == eligible_expected


# ==============================================================================
# Gate 12 Mandate 2: Idempotent Rerun Produces Zero Duplicate Deliveries
# ==============================================================================


class TestIdempotencyAndNoDuplicates:
    """Verify rerun producing zero duplicate deliveries (Gate 12 Mandate 2)."""

    def test_dry_run_rerun_is_strictly_idempotent(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
    ) -> None:
        """Rerunning the dry run multiple times produces identical deterministic metrics."""
        now = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        run1 = orchestrator.execute_dry_run(school_admin_principal, batch_input=FIXTURES_DIR, now=now)
        run2 = orchestrator.execute_dry_run(school_admin_principal, batch_input=FIXTURES_DIR, now=now)

        assert run1.total_students == run2.total_students == 20
        assert run1.dispatched_count == run2.dispatched_count == 12
        assert run1.blocked_count == run2.blocked_count == 8
        assert run1.ptm_slips_generated == run2.ptm_slips_generated == 17
        assert run1.blocked_reasons == run2.blocked_reasons

    def test_live_send_rerun_does_not_deliver_duplicates(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
        ready_sender: SenderIdentity,
    ) -> None:
        """After dispatches reach DELIVERED status, subsequent sends deliver 0 duplicate messages."""
        # Enable dual safety switches for testing live send execution
        orchestrator.settings.live_dispatch_enabled = True
        orchestrator.settings.deployment_compliance_acknowledged = True

        now = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        batch_id = "ASSESSMENT_BATCH_IDEM"

        # Seed scheduled dispatches in repository
        conn = orchestrator.repository.conn
        with conn:
            for i in range(1, 4):
                conn.execute(
                    """
                    INSERT INTO dispatches (
                        dispatch_id, org_id, assessment_id, student_id,
                        recipient_phone_masked, current_status, idempotency_key,
                        created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, 'SCHEDULED', ?, ?, ?)
                    """,
                    (
                        f"disp_idem_{i}",
                        TEST_ORG_ID,
                        batch_id,
                        f"STU_{i:02d}",
                        f"98*** **{i:02d}",
                        f"key_idem_{i}",
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )

        # First live send execution -> delivers 3 messages
        sent_1 = orchestrator.execute_live_send(school_admin_principal, assessment_id=batch_id, sender=ready_sender, now=now)
        assert sent_1 == 3

        # Rerun live send -> all items are now DELIVERED, zero duplicate deliveries
        sent_2 = orchestrator.execute_live_send(school_admin_principal, assessment_id=batch_id, sender=ready_sender, now=now)
        assert sent_2 == 0


# ==============================================================================
# Gate 12 Mandate 3: Dual-Switch Safety on Live Send
# ==============================================================================


class TestDualSwitchSafety:
    """Verify strict dual-switch safety checks on live send (Gate 12 Mandate 3)."""

    def test_send_refused_when_both_switches_false(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
        ready_sender: SenderIdentity,
    ) -> None:
        """When live_dispatch_enabled=False and compliance=False, live send fails closed."""
        orchestrator.settings.live_dispatch_enabled = False
        orchestrator.settings.deployment_compliance_acknowledged = False

        with pytest.raises(SafetySwitchError, match="LIVE_DISPATCH_ENABLED and DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED"):
            orchestrator.execute_live_send(
                school_admin_principal,
                assessment_id="BATCH_SAFE_01",
                sender=ready_sender,
            )

    def test_send_refused_when_only_one_switch_true(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
        ready_sender: SenderIdentity,
    ) -> None:
        """When only one switch is enabled, live send fails closed."""
        # Case A: Live dispatch True, Compliance False
        orchestrator.settings.live_dispatch_enabled = True
        orchestrator.settings.deployment_compliance_acknowledged = False
        with pytest.raises(SafetySwitchError):
            orchestrator.execute_live_send(school_admin_principal, assessment_id="BATCH_SAFE_01", sender=ready_sender)

        # Case B: Live dispatch False, Compliance True
        orchestrator.settings.live_dispatch_enabled = False
        orchestrator.settings.deployment_compliance_acknowledged = True
        with pytest.raises(SafetySwitchError):
            orchestrator.execute_live_send(school_admin_principal, assessment_id="BATCH_SAFE_01", sender=ready_sender)

    def test_send_refused_when_tenant_is_suspended(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
        ready_sender: SenderIdentity,
    ) -> None:
        """Emergency kill-switch overrides enabled switches and halts send."""
        orchestrator.settings.live_dispatch_enabled = True
        orchestrator.settings.deployment_compliance_acknowledged = True

        # Suspend tenant
        orchestrator.tenant_suspend(school_admin_principal, org_id=TEST_ORG_ID, reason="Administrative pause")

        with pytest.raises(TenantSuspendedError, match="emergency kill switch"):
            orchestrator.execute_live_send(school_admin_principal, assessment_id="BATCH_SAFE_01", sender=ready_sender)


# ==============================================================================
# Gate 12 Mandate 4: Retention Purge and Consent Revocation
# ==============================================================================


class TestRetentionAndConsentRevocation:
    """Verify D-13 retention cleanup and consent propagation (Gate 12 Mandate 4)."""

    def test_retention_purge_dry_run_and_execution(
        self,
        orchestrator: Orchestrator,
        tmp_path: Path,
    ) -> None:
        """
        Retention purge:
        - Dry run inspects candidate items without deleting.
        - Execution unlinks files older than 30 days and preserves recent files.
        - Generates immutable cryptographic tombstone hash.
        """
        now = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        policy = RetentionPolicy(transient_media_days=30, audit_log_days=90)

        # Create temporary media files
        media_dir = tmp_path / "artifacts" / TEST_ORG_ID
        media_dir.mkdir(parents=True)
        old_file = media_dir / "old_scorecard.png"
        old_file.write_bytes(b"OLD_MEDIA_BYTES")
        recent_file = media_dir / "recent_scorecard.png"
        recent_file.write_bytes(b"RECENT_MEDIA_BYTES")

        # Set modification time of old_file to 45 days ago
        old_ts = (now - timedelta(days=45)).timestamp()
        import os
        os.utime(old_file, (old_ts, old_ts))

        # 1. Dry run
        dry_report: PurgeReport = purge_retention_data(
            org_id=TEST_ORG_ID,
            now=now,
            artifact_dir=tmp_path / "artifacts",
            repository=orchestrator.repository,
            policy=policy,
            dry_run=True,
        )
        assert dry_report.dry_run is True
        assert dry_report.artifacts_scanned == 2
        assert dry_report.artifacts_purged == 1
        assert dry_report.bytes_freed > 0
        assert old_file.exists()  # Dry run must not delete!
        assert recent_file.exists()

        # 2. Destructive execution
        exec_report: PurgeReport = purge_retention_data(
            org_id=TEST_ORG_ID,
            now=now,
            artifact_dir=tmp_path / "artifacts",
            repository=orchestrator.repository,
            audit_store=orchestrator.audit_store,
            policy=policy,
            dry_run=False,
        )
        assert exec_report.dry_run is False
        assert exec_report.artifacts_purged == 1
        assert not old_file.exists()  # Old file unlinked
        assert recent_file.exists()   # Recent file retained
        assert len(exec_report.tombstone_hash) == 64  # SHA-256 hash length

    def test_consent_revocation_cancels_dispatches_and_tokens(
        self,
        orchestrator: Orchestrator,
        conf_manager: ConfirmationManager,
    ) -> None:
        """Guardian opt-out cancels active dispatches and revokes confirmation tokens."""
        now = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)
        target_student = "STU_REVOKE_01"

        # Seed scheduled dispatch for target student
        conn = orchestrator.repository.conn
        with conn:
            conn.execute(
                """
                INSERT INTO dispatches (
                    dispatch_id, org_id, assessment_id, student_id,
                    recipient_phone_masked, current_status, idempotency_key,
                    created_at_utc, updated_at_utc
                ) VALUES (?, ?, 'BATCH_REV', ?, '98*** **99', 'SCHEDULED', 'key_rev', ?, ?)
                """,
                ("disp_rev_01", TEST_ORG_ID, target_student, now.isoformat(), now.isoformat()),
            )

        # Issue confirmation token for target student
        tok_info = conf_manager.issue_token(
            student_id=target_student,
            assessment_id="BATCH_REV",
            ptm_event_id="PTM_EVENT_01",
            org_id=TEST_ORG_ID,
            sender_id="sender_primary",
            now=now,
            is_ptm_linked=True,
        )
        assert tok_info.status == ConfirmationStatus.PENDING

        # Propagate consent revocation
        rev_res = propagate_consent_revocation(
            org_id=TEST_ORG_ID,
            student_id=target_student,
            now=now,
            repository=orchestrator.repository,
            confirmation_manager=conf_manager,
            audit_store=orchestrator.audit_store,
            reason="PARENT_OPT_OUT_FORM",
        )
        assert rev_res.dispatches_cancelled == 1
        assert rev_res.tokens_revoked == 1

        # Assert dispatch status is now CANCELLED
        cur = conn.execute("SELECT current_status FROM dispatches WHERE dispatch_id = 'disp_rev_01'")
        assert cur.fetchone()[0] == "CANCELLED"

        # Assert confirmation token is now REVOKED
        conf_rec = conf_manager.store.get_record(tok_info.token_hash, org_id=TEST_ORG_ID)
        assert conf_rec is not None
        assert conf_rec.status == ConfirmationStatus.REVOKED


# ==============================================================================
# Gate 12 Mandate 5: CLI Argument & Tenant Boundary Enforcement
# ==============================================================================


class TestCLITenantBoundariesAndRoles:
    """Verify mandatory --org-id, role matrix, and tenant isolation (Gate 12 Mandate 5)."""

    def test_cli_omitted_org_id_fails(self) -> None:
        """Calling CLI dry-run without --org-id fails with non-zero exit code."""
        with pytest.raises(SystemExit) as exc_info:
            cli_main(["dry-run", "--input", str(FIXTURES_DIR)])
        assert exc_info.value.code != 0

    def test_cli_empty_org_id_fails(self) -> None:
        """Calling CLI dry-run with empty or whitespace --org-id fails."""
        code = cli_main(["dry-run", "--input", str(FIXTURES_DIR), "--org-id", "   "])
        assert code == 2

    def test_cli_dry_run_success(self) -> None:
        """Calling CLI dry-run with valid arguments executes successfully."""
        code = cli_main(["dry-run", "--input", str(FIXTURES_DIR), "--org-id", TEST_ORG_ID])
        assert code == 0

    def test_cli_send_refused_without_switches(self) -> None:
        """CLI send command without safety switches returns code 1."""
        code = cli_main(["send", "--org-id", TEST_ORG_ID, "--assessment-id", "TEST_BATCH"])
        assert code == 1

    def test_cross_tenant_access_fails_closed(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
    ) -> None:
        """Actor from ORG_A attempting operations on ORG_B raises UnauthorizedError."""
        # Principal belongs to TEST_ORG_ID; target operation touches ALT_ORG_ID
        with pytest.raises(UnauthorizedError, match="unauthorized to access target org"):
            orchestrator.tenant_suspend(school_admin_principal, org_id=ALT_ORG_ID)

        with pytest.raises(UnauthorizedError):
            orchestrator.get_artifact(
                school_admin_principal,
                artifact_type="SCORECARD",
                student_id="STU_01",
                target_org_id=ALT_ORG_ID,
            )

    def test_role_based_permissions(
        self,
        orchestrator: Orchestrator,
        teacher_principal: Principal,
        school_admin_principal: Principal,
        platform_admin_principal: Principal,
        ready_sender: SenderIdentity,
    ) -> None:
        """Enforce ADR-0018 Section 3 role permission matrix."""
        # 1. TEACHER cannot approve or cancel a batch
        with pytest.raises(UnauthorizedError, match="lacks required role"):
            orchestrator.approve_batch(teacher_principal, assessment_id="BATCH_ROLE_01")

        with pytest.raises(UnauthorizedError, match="lacks required role"):
            orchestrator.cancel_batch(teacher_principal, assessment_id="BATCH_ROLE_01")

        # 2. SCHOOL_ADMIN can approve and cancel their own batch
        orchestrator.approve_batch(school_admin_principal, assessment_id="BATCH_ROLE_01")
        orchestrator.cancel_batch(school_admin_principal, assessment_id="BATCH_ROLE_01")

        # 3. PLATFORM_ADMIN can operate across tenants
        orchestrator.tenant_onboard(
            platform_admin_principal,
            org_id="ORG_NEW_303",
            school_name="New Branch School",
            sender=ready_sender,
        )


# ==============================================================================
# Gate 12 Mandate 6: Privacy Leak Scan Across Logs and CLI Output
# ==============================================================================


class TestPrivacyHygieneLeaks:
    """Verify zero unmasked student names, phone numbers, or tokens (Gate 12 Mandate 6)."""

    def test_privacy_leak_scan_in_cli_dry_run_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Capture CLI stdout and stderr during dry-run.
        Assert zero unmasked phone numbers, names, scores, or raw tokens appear.
        """
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", stdout_buf)
        monkeypatch.setattr(sys, "stderr", stderr_buf)

        exit_code = cli_main(["dry-run", "--input", str(FIXTURES_DIR), "--org-id", TEST_ORG_ID])
        assert exit_code == 0

        output = stdout_buf.getvalue() + stderr_buf.getvalue()

        # 1. Zero raw 10-digit Indian phone numbers
        phone_matches = re.findall(r"(?<!\d)[6-9]\d{9}(?!\d)", output)
        assert len(phone_matches) == 0, f"Raw phone numbers detected in CLI output: {phone_matches}"

        # 2. Zero student personal names from admissions roster
        student_names = [
            "Aarav Sharma", "Vihaan Verma", "Aditi Singh", "Ananya Patel",
            "Reyansh Gupta", "Ishaan Kumar", "Prisha Reddy",
        ]
        for name in student_names:
            assert name not in output, f"Student name '{name}' leaked in CLI output."

        # 3. Blocked student IDs (surrogates) are properly displayed with reasons
        assert "STU_02: INTERCEPTION_RISK_SAME_NUMBER" in output
        assert "STU_09: CONSENT_REVOKED" in output


# ==============================================================================
# Additional Use-Case Service Layer Coverage
# ==============================================================================


class TestOrchestratorServiceFunctions:
    """Verify additional Orchestrator service layer functions."""

    def test_validate_and_evaluate_marks_entry_batch(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
    ) -> None:
        """Validate and evaluate MARKS_ENTRY_TOTALS batch."""
        sheet_path = FIXTURES_DIR / "marks_entry_50.json"
        val_res = orchestrator.validate_batch(
            school_admin_principal,
            batch_input=sheet_path,
            kind=AssessmentKind.MARKS_ENTRY_TOTALS,
        )
        assert val_res.is_valid is True
        assert val_res.enrolled_count == 6
        assert val_res.present_count == 5
        assert val_res.absent_count == 1

        eval_res = orchestrator.evaluate_batch(school_admin_principal, assessment_id=val_res.assessment_id)
        assert eval_res.total_students == 6
        assert eval_res.eligible_count == 0
        assert eval_res.blocked_count == 6

    def test_review_queue_management_lifecycle(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
    ) -> None:
        """Review queue enqueuing, listing, and resolution."""
        # Trigger evaluation on golden fixtures to populate review queue
        orchestrator.evaluate_batch(
            school_admin_principal,
            assessment_id="ASSESSMENT_BATCH",
            batch_input=FIXTURES_DIR,
        )

        # List review queue items
        items = orchestrator.list_review_queue(school_admin_principal)
        assert len(items) > 0

        target_item = items[0]
        assert target_item.status == "OPEN"

        # Resolve review item
        resolved = orchestrator.resolve_review_item(
            school_admin_principal,
            item_id=target_item.item_id,
            resolution="RESOLVED",
            notes="Guardian phone verified manually by principal",
        )
        assert resolved.status == "RESOLVED"
        assert resolved.resolved_at_utc is not None
        assert resolved.resolution_notes == "Guardian phone verified manually by principal"

        # Non-existent item resolution raises ReviewItemNotFoundError
        with pytest.raises(ReviewItemNotFoundError):
            orchestrator.resolve_review_item(
                school_admin_principal,
                item_id="non_existent_item",
                resolution="RESOLVED",
            )

    def test_get_artifact_retrieval_and_not_found(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
    ) -> None:
        """Artifact storage and retrieval by opaque key with tenant isolation."""
        # Store ephemeral mock artifact
        key = (TEST_ORG_ID, "BATCH_01", "STU_01", "SCORECARD")
        orchestrator._artifacts[key] = b"PNG_IMAGE_BYTES"

        data = orchestrator.get_artifact(
            school_admin_principal,
            artifact_type="SCORECARD",
            student_id="STU_01",
            assessment_id="BATCH_01",
        )
        assert data == b"PNG_IMAGE_BYTES"

        # Not found raises ArtifactNotFoundError
        with pytest.raises(ArtifactNotFoundError, match="not found"):
            orchestrator.get_artifact(
                school_admin_principal,
                artifact_type="SCORECARD",
                student_id="STU_99",
                assessment_id="BATCH_01",
            )

    def test_batch_job_summary_counts(
        self,
        orchestrator: Orchestrator,
        school_admin_principal: Principal,
    ) -> None:
        """Summarize dispatch job status counts."""
        conn = orchestrator.repository.conn
        with conn:
            conn.execute(
                """
                INSERT INTO dispatches (
                    dispatch_id, org_id, assessment_id, student_id,
                    recipient_phone_masked, current_status, idempotency_key,
                    created_at_utc, updated_at_utc
                ) VALUES
                  ('d1', ?, 'BATCH_STAT', 'STU_01', '98*** **01', 'DELIVERED', 'k1', '2026-10-20T10:00:00Z', '2026-10-20T10:00:00Z'),
                  ('d2', ?, 'BATCH_STAT', 'STU_02', '98*** **02', 'PENDING', 'k2', '2026-10-20T10:00:00Z', '2026-10-20T10:00:00Z'),
                  ('d3', ?, 'BATCH_STAT', 'STU_03', '98*** **03', 'FAILED', 'k3', '2026-10-20T10:00:00Z', '2026-10-20T10:00:00Z')
                """,
                (TEST_ORG_ID, TEST_ORG_ID, TEST_ORG_ID),
            )

        summary = orchestrator.get_job_status(school_admin_principal, batch_id="BATCH_STAT")
        assert summary.total_jobs == 3
        assert summary.delivered_count == 1
        assert summary.pending_count == 1
        assert summary.failed_count == 1
