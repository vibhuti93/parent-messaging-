"""
Stage S11 Parent Confirmation (QR + OTP) Test Suite (`tests/test_stage11_confirmation.py`).

Compliant with:
- Stage S11 Gate 11 mandates:
  1. Token Randomness & Hash Persistence: >= 32 bytes entropy, store contains strictly SHA-256 hash.
  2. Zero PII in QR Payload: HTTPS URL containing strictly opaque token; student name, roll number,
     marks, and parent phone are completely absent.
  3. Success Path: Valid token + correct OTP within TTL transitions state to CONFIRMED and logs audit record.
  4. Failure & Lockout Paths:
     - Expired token rejected (TOKEN_EXPIRED).
     - Revoked token rejected (TOKEN_REVOKED).
     - Token reuse rejected (TOKEN_ALREADY_USED).
     - Wrong token rejected (TOKEN_NOT_FOUND).
     - Rate limit enforcement: 5 incorrect OTP attempts triggers LOCKED_OUT; 6th attempt blocked.
     - Cross-org unauthorized access rejected (UNAUTHORIZED_TENANT_ACCESS).
  5. PTM-Linked Guard: Attempting confirmation on is_ptm_linked=False assessment fails closed.
  6. Persistence & Restart Recovery: Confirmations and attempt counters persist across repository re-initialization.
- ADR-0002: Zero float() calls; all counters, limits, and timestamps use integer math.
- ADR-0005: Timezone-aware UTC datetimes.
- ADR-0008: Typed exception hierarchy.
- ADR-0019: Per-school sender identity isolation and READY status gating.
- Invariants 10, 15, 17.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from omr_dispatch.confirmation import (
    DEFAULT_OTP_TTL_SECONDS,
    DEFAULT_TOKEN_TTL_SECONDS,
    OTP_TEMPLATE_NAME,
    ConfirmationManager,
    ConfirmationResult,
    ConfirmationStatus,
    ConfirmationStore,
    InvalidOtpError,
    NonPtmAssessmentError,
    SenderNotReadyError,
    SessionLockedOutError,
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenNotFoundError,
    TokenRevokedError,
    UnauthorizedTenantAccessError,
    UnverifiedGuardianContactError,
    VerificationMethod,
    construct_qr_payload_url,
    generate_opaque_token,
)
from omr_dispatch.contacts import mask_phone
from omr_dispatch.messaging.policy import TenantContextMissingError
from omr_dispatch.messaging.provider import (
    FreeformSendRequest,
    MediaSendRequest,
    ProviderHealthStatus,
    ProviderSendResponse,
    QualityRating,
    SenderIdentity,
    SenderStatus,
    TemplateRegistrationStatus,
    TemplateSendRequest,
)
from omr_dispatch.models import Assessment, AssessmentKind, AssessmentPurpose
from omr_dispatch.renderer import QrTokenProvider

# ------------------------------------------------------------------------------
# Test Fixtures & Mock Provider
# ------------------------------------------------------------------------------

TEST_NOW = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
ORG_A = "SCH_DELHI_001"
ORG_B = "SCH_MUMBAI_002"
SENDER_ID_A = "snd_delhi_001"
STUDENT_ID = "STU_2026_042"
ASSESSMENT_ID = "ASM_TERM1_2026"
PTM_EVENT_ID = "PTM_OCT_2026"
VALID_GUARDIAN_PHONE = "9876543210"


class MockMessagingProvider:
    """Zero-network mock messaging provider capturing template send requests."""

    def __init__(self) -> None:
        self.sent_requests: list[tuple[str, SenderIdentity, TemplateSendRequest]] = []

    def send_template(
        self,
        org_id: str,
        sender: SenderIdentity,
        request: TemplateSendRequest,
    ) -> ProviderSendResponse:
        self.sent_requests.append((org_id, sender, request))
        return ProviderSendResponse(
            wamid=f"wamid.{secrets.token_hex(8)}",
            recipient_phone_e164=request.recipient_phone_e164,
            status="sent",
        )

    def send_freeform_text(
        self,
        org_id: str,
        sender: SenderIdentity,
        request: FreeformSendRequest,
    ) -> ProviderSendResponse:
        return ProviderSendResponse(
            wamid=f"wamid.{secrets.token_hex(8)}",
            recipient_phone_e164=request.recipient_phone_e164,
            status="sent",
        )

    def send_media(
        self,
        org_id: str,
        sender: SenderIdentity,
        request: MediaSendRequest,
    ) -> ProviderSendResponse:
        return ProviderSendResponse(
            wamid=f"wamid.{secrets.token_hex(8)}",
            recipient_phone_e164=request.recipient_phone_e164,
            status="sent",
        )

    def upload_media(
        self,
        org_id: str,
        sender: SenderIdentity,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
    ) -> str:
        return f"media_{secrets.token_hex(8)}"

    def check_health(self, org_id: str, sender: SenderIdentity) -> ProviderHealthStatus:
        return ProviderHealthStatus.HEALTHY


def make_sender(
    org_id: str = ORG_A,
    sender_id: str = SENDER_ID_A,
    status: SenderStatus = SenderStatus.READY,
) -> SenderIdentity:
    return SenderIdentity(
        sender_id=sender_id,
        org_id=org_id,
        waba_id="waba_12345",
        phone_number_id="phone_id_999",
        display_phone_number="+91 98765 43210",
        verified_display_name="Delhi Public School",
        status=status,
        quality_rating=QualityRating.GREEN,
        daily_message_limit=250,
        credential_secret_ref="ENV:WHATSAPP_TOKEN_DELHI",
        app_secret_ref="ENV:WHATSAPP_SECRET_DELHI",
        template_registry={OTP_TEMPLATE_NAME: TemplateRegistrationStatus.APPROVED},
        is_primary=True,
    )


# ------------------------------------------------------------------------------
# Gate 11 Requirement 1: Token Randomness & Hash-Only Persistence
# ------------------------------------------------------------------------------


def test_token_randomness_and_hash_only_storage() -> None:
    """
    Assert token entropy >= 32 bytes and store contains strictly SHA-256 hash.
    Raw plaintext token is NEVER written to the database.
    """
    store = ConfirmationStore()
    manager = ConfirmationManager(store=store)

    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
        is_ptm_linked=True,
    )

    # 1. Assert token randomness and length >= 32 bytes entropy
    assert len(token_info.raw_token) >= 43  # 32 bytes url-safe base64 = 43 chars
    decoded = base64.urlsafe_b64decode(token_info.raw_token + "==")
    assert len(decoded) >= 32

    # 2. Assert token hash matches SHA-256 digest
    expected_hash = hashlib.sha256(token_info.raw_token.encode("utf-8")).hexdigest()
    assert token_info.token_hash == expected_hash

    # 3. Formally inspect SQLite database: raw token must NOT exist anywhere in tables
    cur = store.conn.execute("SELECT * FROM parent_confirmations WHERE token_hash = ?", (token_info.token_hash,))
    row = cur.fetchone()
    assert row is not None

    # Verify columns
    assert row["token_hash"] == expected_hash
    assert row["org_id"] == ORG_A
    assert row["student_id"] == STUDENT_ID

    # Assert raw token does NOT appear in any column of the row
    for col_val in row:
        if col_val is not None:
            assert token_info.raw_token not in str(col_val), (
                f"CRITICAL PRIVACY VIOLATION: raw token found persisted in database column: {col_val}"
            )

    # Assert raw token is NOT in confirmation_audit_log
    audit_cur = store.conn.execute("SELECT * FROM confirmation_audit_log WHERE token_hash = ?", (token_info.token_hash,))
    for a_row in audit_cur.fetchall():
        for a_val in a_row:
            if a_val is not None:
                assert token_info.raw_token not in str(a_val), (
                    "CRITICAL PRIVACY VIOLATION: raw token found persisted in audit log!"
                )


# ------------------------------------------------------------------------------
# Gate 11 Requirement 2: Zero PII in QR Payload
# ------------------------------------------------------------------------------


def test_zero_pii_in_qr_payload() -> None:
    """
    Formally inspect QR payload URL:
      - Protocol must be HTTPS.
      - URL parameter must contain strictly 'token'.
      - Student name, roll number, student ID, marks, and parent phone must be completely absent.
    """
    manager = ConfirmationManager()
    token_info = manager.issue_token(
        student_id="STU_9999",
        assessment_id="ASM_2026",
        ptm_event_id="PTM_2026",
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
        is_ptm_linked=True,
    )

    url = token_info.qr_payload_url

    # 1. Scheme assertion
    assert url.startswith("https://")
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "confirm.institution.org"
    assert parsed.path == "/verify"

    # 2. Query parameter assertion: exactly one parameter named 'token'
    params = parse_qs(parsed.query)
    assert list(params.keys()) == ["token"]
    assert params["token"] == [token_info.raw_token]

    # 3. Absence of sensitive student/parent identifiers
    forbidden_tokens = [
        "STU_9999",
        "Aarav",
        "आरव",
        "Sharma",
        "शर्मा",
        "9876543210",
        "+919876543210",
        "101",  # Roll number
        "95.5",  # Marks
        "marks",
        "score",
        "roll",
        "phone",
        "guardian",
    ]

    for item in forbidden_tokens:
        assert item.lower() not in url.lower(), (
            f"PRIVACY VIOLATION: QR payload URL leaks personal or academic identifier: '{item}' in {url}"
        )


# ------------------------------------------------------------------------------
# Gate 11 Requirement 3: Success Path Full Lifecycle
# ------------------------------------------------------------------------------


def test_success_path_full_lifecycle() -> None:
    """
    Verify complete happy path:
      1. Issue token for PTM assessment.
      2. Request OTP challenge using READY sender and verified guardian contact.
      3. Provider dispatches OTP template with Latin digits.
      4. Submit valid OTP within TTL.
      5. State transitions to CONFIRMED.
      6. Audit records created with masked phone and zero raw secrets.
    """
    store = ConfirmationStore()
    manager = ConfirmationManager(store=store)
    provider = MockMessagingProvider()
    sender = make_sender()

    # Step 1: Issue token
    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
        is_ptm_linked=True,
    )
    assert token_info.status == ConfirmationStatus.PENDING

    # Step 2: Request OTP challenge
    t_challenge = TEST_NOW + timedelta(minutes=5)
    challenge_res = manager.request_otp_challenge(
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        sender=sender,
        guardian_phone=VALID_GUARDIAN_PHONE,
        has_consent=True,
        is_quarantined=False,
        provider=provider,
        now=t_challenge,
    )

    assert challenge_res.dispatched is True
    assert challenge_res.recipient_phone_masked == mask_phone(VALID_GUARDIAN_PHONE)
    assert challenge_res.template_name == OTP_TEMPLATE_NAME
    assert len(provider.sent_requests) == 1

    # Extract OTP passed to provider template parameters
    _, _, send_req = provider.sent_requests[0]
    assert send_req.template_name == OTP_TEMPLATE_NAME
    body_param = send_req.components[0].parameters[0].text
    assert body_param is not None
    otp_code = body_param
    assert len(otp_code) == 6
    assert otp_code.isdigit()

    # Step 3: Verify OTP within TTL (e.g. 2 minutes later)
    t_verify = t_challenge + timedelta(minutes=2)
    confirm_res = manager.verify_otp(
        otp_code=otp_code,
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        now=t_verify,
    )

    assert isinstance(confirm_res, ConfirmationResult)
    assert confirm_res.status == ConfirmationStatus.CONFIRMED
    assert confirm_res.verified_at_utc == t_verify
    assert confirm_res.verification_method == VerificationMethod.DIGITAL_OTP
    assert "paper signature line remains optional and unverified" in confirm_res.assurance_statement

    # Step 4: Verify audit trail
    audit_entries = store.get_audit_trail(token_info.token_hash, org_id=ORG_A)
    actions = [e["action"] for e in audit_entries]
    assert "TOKEN_ISSUED" in actions
    assert "OTP_CHALLENGED" in actions
    assert "CONFIRMATION_VERIFIED" in actions


# ------------------------------------------------------------------------------
# Gate 11 Requirement 4: Failure & Lockout Paths
# ------------------------------------------------------------------------------


def test_token_expired_rejection() -> None:
    """Tokens past TTL (7 days) fail closed with TokenExpiredError."""
    manager = ConfirmationManager()
    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
        ttl_seconds=DEFAULT_TOKEN_TTL_SECONDS,  # 7 days
    )

    # Advance time to 8 days later
    past_expiry = TEST_NOW + timedelta(days=8)

    # Attempting OTP challenge on expired token fails
    with pytest.raises(TokenExpiredError):
        manager.request_otp_challenge(
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            sender=make_sender(),
            guardian_phone=VALID_GUARDIAN_PHONE,
            has_consent=True,
            now=past_expiry,
        )

    # Attempting OTP verification on expired token fails
    with pytest.raises(TokenExpiredError):
        manager.verify_otp(
            otp_code="123456",
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            now=past_expiry,
        )


def test_token_revocation_rejection() -> None:
    """Explicitly revoked tokens fail closed with TokenRevokedError."""
    manager = ConfirmationManager()
    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )

    # Explicitly revoke token
    manager.revoke_token(
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        now=TEST_NOW + timedelta(minutes=10),
        reason="Parent requested cancellation",
    )

    # Subsequent challenge fails
    with pytest.raises(TokenRevokedError):
        manager.request_otp_challenge(
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            sender=make_sender(),
            guardian_phone=VALID_GUARDIAN_PHONE,
            has_consent=True,
            now=TEST_NOW + timedelta(minutes=15),
        )

    # Subsequent verify fails
    with pytest.raises(TokenRevokedError):
        manager.verify_otp(
            otp_code="123456",
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            now=TEST_NOW + timedelta(minutes=15),
        )


def test_token_reuse_replay_protection() -> None:
    """Confirmed tokens cannot be reused; fail closed with TokenAlreadyUsedError."""
    manager = ConfirmationManager()
    provider = MockMessagingProvider()
    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )

    manager.request_otp_challenge(
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        sender=make_sender(),
        guardian_phone=VALID_GUARDIAN_PHONE,
        has_consent=True,
        provider=provider,
        now=TEST_NOW,
    )
    otp = provider.sent_requests[0][2].components[0].parameters[0].text
    assert otp is not None

    # First verification succeeds
    res1 = manager.verify_otp(
        otp_code=otp,
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        now=TEST_NOW + timedelta(minutes=1),
    )
    assert res1.status == ConfirmationStatus.CONFIRMED

    # Replay attempt 1: verify again
    with pytest.raises(TokenAlreadyUsedError):
        manager.verify_otp(
            otp_code=otp,
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            now=TEST_NOW + timedelta(minutes=2),
        )

    # Replay attempt 2: request new challenge on confirmed token
    with pytest.raises(TokenAlreadyUsedError):
        manager.request_otp_challenge(
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            sender=make_sender(),
            guardian_phone=VALID_GUARDIAN_PHONE,
            has_consent=True,
            now=TEST_NOW + timedelta(minutes=3),
        )


def test_wrong_token_rejection() -> None:
    """Nonexistent or altered tokens fail closed with TokenNotFoundError."""
    manager = ConfirmationManager()
    fake_token = secrets.token_urlsafe(32)

    with pytest.raises(TokenNotFoundError):
        manager.request_otp_challenge(
            raw_token=fake_token,
            org_id=ORG_A,
            sender=make_sender(),
            guardian_phone=VALID_GUARDIAN_PHONE,
            has_consent=True,
            now=TEST_NOW,
        )

    with pytest.raises(TokenNotFoundError):
        manager.verify_otp(
            otp_code="123456",
            raw_token=fake_token,
            org_id=ORG_A,
            now=TEST_NOW,
        )

    with pytest.raises(TokenNotFoundError):
        manager.revoke_token(
            raw_token=fake_token,
            org_id=ORG_A,
            now=TEST_NOW,
        )


def test_rate_limit_lockout_after_5_failed_attempts() -> None:
    """
    Session rate limiting:
      - 1st to 4th incorrect attempts raise InvalidOtpError with remaining attempt count.
      - 5th incorrect attempt locks out the session (SessionLockedOutError).
      - 6th attempt is blocked immediately with SessionLockedOutError, even with correct OTP.
    """
    store = ConfirmationStore()
    manager = ConfirmationManager(store=store)
    provider = MockMessagingProvider()
    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )

    manager.request_otp_challenge(
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        sender=make_sender(),
        guardian_phone=VALID_GUARDIAN_PHONE,
        has_consent=True,
        provider=provider,
        now=TEST_NOW,
    )
    correct_otp = provider.sent_requests[0][2].components[0].parameters[0].text
    assert correct_otp is not None
    wrong_otp = "000000" if correct_otp != "000000" else "111111"

    # Attempts 1 to 4: InvalidOtpError with remaining attempts
    for i in range(1, 5):
        with pytest.raises(InvalidOtpError) as exc_info:
            manager.verify_otp(
                otp_code=wrong_otp,
                raw_token=token_info.raw_token,
                org_id=ORG_A,
                now=TEST_NOW + timedelta(seconds=10 * i),
            )
        assert f"{5 - i} attempt(s) remaining" in str(exc_info.value)
        rec = store.get_record(token_info.token_hash, org_id=ORG_A)
        assert rec is not None
        assert rec.failed_attempts == i
        assert rec.status == ConfirmationStatus.CHALLENGED

    # 5th attempt: Triggers lockout
    with pytest.raises(SessionLockedOutError) as exc_info:
        manager.verify_otp(
            otp_code=wrong_otp,
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            now=TEST_NOW + timedelta(seconds=50),
        )
    assert "Maximum failed attempts" in str(exc_info.value)

    # Verify database status is LOCKED_OUT
    rec_locked = store.get_record(token_info.token_hash, org_id=ORG_A)
    assert rec_locked is not None
    assert rec_locked.status == ConfirmationStatus.LOCKED_OUT
    assert rec_locked.failed_attempts == 5

    # 6th attempt: Even with the CORRECT OTP, session is locked out!
    with pytest.raises(SessionLockedOutError) as exc_info6:
        manager.verify_otp(
            otp_code=correct_otp,
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            now=TEST_NOW + timedelta(seconds=60),
        )
    assert "locked out" in str(exc_info6.value).lower()


def test_cross_tenant_unauthorized_access_rejection() -> None:
    """Valid token presented under mismatched org_id fails closed with UnauthorizedTenantAccessError."""
    store = ConfirmationStore()
    manager = ConfirmationManager(store=store)

    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )

    # 1. Direct store lookup across tenant boundary
    with pytest.raises(UnauthorizedTenantAccessError):
        store.get_record(token_info.token_hash, org_id=ORG_B)

    # 2. OTP challenge request presenting ORG_B
    sender_b = make_sender(org_id=ORG_B, sender_id="snd_mumbai_002")
    with pytest.raises(UnauthorizedTenantAccessError):
        manager.request_otp_challenge(
            raw_token=token_info.raw_token,
            org_id=ORG_B,
            sender=sender_b,
            guardian_phone=VALID_GUARDIAN_PHONE,
            has_consent=True,
            now=TEST_NOW,
        )

    # 3. Presenting ORG_B sender while claiming ORG_A request
    with pytest.raises(UnauthorizedTenantAccessError):
        manager.request_otp_challenge(
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            sender=sender_b,  # Belongs to ORG_B!
            guardian_phone=VALID_GUARDIAN_PHONE,
            has_consent=True,
            now=TEST_NOW,
        )

    # 4. OTP verification presenting ORG_B
    with pytest.raises(UnauthorizedTenantAccessError):
        manager.verify_otp(
            otp_code="123456",
            raw_token=token_info.raw_token,
            org_id=ORG_B,
            now=TEST_NOW,
        )

    # 5. Revocation presenting ORG_B
    with pytest.raises(UnauthorizedTenantAccessError):
        manager.revoke_token(
            raw_token=token_info.raw_token,
            org_id=ORG_B,
            now=TEST_NOW,
        )


# ------------------------------------------------------------------------------
# Gate 11 Requirement 5: PTM-Linked Assessment Guard
# ------------------------------------------------------------------------------


def test_ptm_linked_guard_rejection() -> None:
    """Confirmation tokens apply strictly to PTM-linked assessments; non-PTM fails closed."""
    manager = ConfirmationManager()

    # 1. Non-PTM flag: is_ptm_linked=False fails closed
    with pytest.raises(NonPtmAssessmentError) as exc_info1:
        manager.issue_token(
            student_id=STUDENT_ID,
            assessment_id="ASM_UNIT_TEST",
            ptm_event_id=PTM_EVENT_ID,
            org_id=ORG_A,
            sender_id=SENDER_ID_A,
            now=TEST_NOW,
            is_ptm_linked=False,
        )
    assert "not PTM-linked" in str(exc_info1.value)

    # 2. Non-PTM assessment model (e.g. MIDTERM without PTM_LINKED flag)
    non_ptm_assessment = Assessment(
        assessment_id="ASM_MIDTERM_01",
        kind=AssessmentKind.OMR_MCQ,
        name="Half Yearly Exam",
        total_max_marks=300,
        purpose_flags=[AssessmentPurpose.MIDTERM],
        org_id=ORG_A,
    )
    with pytest.raises(NonPtmAssessmentError):
        manager.issue_token(
            student_id=STUDENT_ID,
            assessment_id=non_ptm_assessment.assessment_id,
            ptm_event_id=PTM_EVENT_ID,
            org_id=ORG_A,
            sender_id=SENDER_ID_A,
            now=TEST_NOW,
            assessment=non_ptm_assessment,
            is_ptm_linked=None,  # Derived from assessment
        )

    # 3. PTM-linked assessment model succeeds
    ptm_assessment = Assessment(
        assessment_id="ASM_PTM_01",
        kind=AssessmentKind.OMR_MCQ,
        name="Term Diagnostic Test",
        total_max_marks=300,
        purpose_flags=[AssessmentPurpose.PTM_LINKED],
        org_id=ORG_A,
    )
    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ptm_assessment.assessment_id,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
        assessment=ptm_assessment,
        is_ptm_linked=None,
    )
    assert token_info.status == ConfirmationStatus.PENDING


# ------------------------------------------------------------------------------
# Gate 11 Requirement 6: Persistence & Restart Recovery
# ------------------------------------------------------------------------------


def test_persistence_and_restart_recovery(tmp_path: Path) -> None:
    """Confirmations, attempt counters, and state transitions persist across store restarts."""
    db_file = tmp_path / "confirmations_restart.db"

    # Instance 1: Setup and record 2 failed attempts
    store1 = ConfirmationStore(db_path=db_file)
    manager1 = ConfirmationManager(store=store1)
    provider = MockMessagingProvider()

    token_info = manager1.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )

    manager1.request_otp_challenge(
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        sender=make_sender(),
        guardian_phone=VALID_GUARDIAN_PHONE,
        has_consent=True,
        provider=provider,
        now=TEST_NOW,
    )
    otp = provider.sent_requests[0][2].components[0].parameters[0].text
    assert otp is not None
    wrong_otp = "999999" if otp != "999999" else "888888"

    # 2 failed attempts
    with pytest.raises(InvalidOtpError):
        manager1.verify_otp(wrong_otp, raw_token=token_info.raw_token, org_id=ORG_A, now=TEST_NOW + timedelta(seconds=10))
    with pytest.raises(InvalidOtpError):
        manager1.verify_otp(wrong_otp, raw_token=token_info.raw_token, org_id=ORG_A, now=TEST_NOW + timedelta(seconds=20))

    # Close store1 before re-opening
    store1.close()
    del manager1
    del store1

    store2 = ConfirmationStore(db_path=db_file)
    manager2 = ConfirmationManager(store=store2)

    # Verify persisted state
    rec_reloaded = store2.get_record(token_info.token_hash, org_id=ORG_A)
    assert rec_reloaded is not None
    assert rec_reloaded.failed_attempts == 2
    assert rec_reloaded.status == ConfirmationStatus.CHALLENGED

    # Attempts 3 and 4
    with pytest.raises(InvalidOtpError):
        manager2.verify_otp(wrong_otp, raw_token=token_info.raw_token, org_id=ORG_A, now=TEST_NOW + timedelta(seconds=30))
    with pytest.raises(InvalidOtpError):
        manager2.verify_otp(wrong_otp, raw_token=token_info.raw_token, org_id=ORG_A, now=TEST_NOW + timedelta(seconds=40))

    # 5th attempt locks out
    with pytest.raises(SessionLockedOutError):
        manager2.verify_otp(wrong_otp, raw_token=token_info.raw_token, org_id=ORG_A, now=TEST_NOW + timedelta(seconds=50))

    rec_locked = store2.get_record(token_info.token_hash, org_id=ORG_A)
    assert rec_locked is not None
    assert rec_locked.status == ConfirmationStatus.LOCKED_OUT
    assert rec_locked.failed_attempts == 5
    store2.close()


# ------------------------------------------------------------------------------
# Additional Protocol, Security, and Precondition Tests
# ------------------------------------------------------------------------------


def test_qr_token_provider_protocol_conformance() -> None:
    """ConfirmationManager conforms to QrTokenProvider protocol from S6 renderer."""
    manager = ConfirmationManager()
    assert isinstance(manager, QrTokenProvider)

    # Before issuing token: returns None
    assert manager.get_token(STUDENT_ID, org_id=ORG_A, assessment_id=ASSESSMENT_ID) is None

    # After issuing token: returns raw token
    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )
    retrieved = manager.get_token(STUDENT_ID, org_id=ORG_A, assessment_id=ASSESSMENT_ID)
    assert retrieved == token_info.raw_token

    # After confirming token: returns None
    provider = MockMessagingProvider()
    manager.request_otp_challenge(
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        sender=make_sender(),
        guardian_phone=VALID_GUARDIAN_PHONE,
        has_consent=True,
        provider=provider,
        now=TEST_NOW,
    )
    otp = provider.sent_requests[0][2].components[0].parameters[0].text
    assert otp is not None
    manager.verify_otp(otp, raw_token=token_info.raw_token, org_id=ORG_A, now=TEST_NOW + timedelta(minutes=1))

    # Confirmed token evicted from active provider
    assert manager.get_token(STUDENT_ID, org_id=ORG_A, assessment_id=ASSESSMENT_ID) is None


def test_sender_not_ready_rejections() -> None:
    """Non-READY sender identities fail closed with SenderNotReadyError (ADR-0019)."""
    manager = ConfirmationManager()
    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )

    unready_statuses = [
        SenderStatus.NOT_CONFIGURED,
        SenderStatus.CONNECTED,
        SenderStatus.TEMPLATES_PENDING,
        SenderStatus.SUSPENDED,
        SenderStatus.FLAGGED,
    ]

    for st in unready_statuses:
        sender = make_sender(status=st)
        with pytest.raises(SenderNotReadyError):
            manager.request_otp_challenge(
                raw_token=token_info.raw_token,
                org_id=ORG_A,
                sender=sender,
                guardian_phone=VALID_GUARDIAN_PHONE,
                has_consent=True,
                now=TEST_NOW,
            )


def test_unverified_guardian_contact_rejections() -> None:
    """Invalid phone, unconsented, or quarantined contacts fail closed."""
    manager = ConfirmationManager()
    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )
    sender = make_sender()

    # 1. Invalid phone number
    with pytest.raises(UnverifiedGuardianContactError):
        manager.request_otp_challenge(
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            sender=sender,
            guardian_phone="12345",  # Invalid
            has_consent=True,
            now=TEST_NOW,
        )

    # 2. Missing consent
    with pytest.raises(UnverifiedGuardianContactError):
        manager.request_otp_challenge(
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            sender=sender,
            guardian_phone=VALID_GUARDIAN_PHONE,
            has_consent=False,  # No consent
            now=TEST_NOW,
        )

    # 3. Quarantined contact
    with pytest.raises(UnverifiedGuardianContactError):
        manager.request_otp_challenge(
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            sender=sender,
            guardian_phone=VALID_GUARDIAN_PHONE,
            has_consent=True,
            is_quarantined=True,  # Quarantined
            now=TEST_NOW,
        )


def test_otp_challenge_ttl_expiry() -> None:
    """An OTP past its challenge TTL (10 minutes) cannot be verified."""
    manager = ConfirmationManager()
    provider = MockMessagingProvider()
    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )

    manager.request_otp_challenge(
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        sender=make_sender(),
        guardian_phone=VALID_GUARDIAN_PHONE,
        has_consent=True,
        provider=provider,
        otp_ttl_seconds=DEFAULT_OTP_TTL_SECONDS,  # 10 minutes
        now=TEST_NOW,
    )
    otp = provider.sent_requests[0][2].components[0].parameters[0].text
    assert otp is not None

    # Advance time by 11 minutes (past 10 min TTL)
    t_expired = TEST_NOW + timedelta(minutes=11)
    with pytest.raises(TokenExpiredError):
        manager.verify_otp(
            otp_code=otp,
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            now=t_expired,
        )


def test_tenant_context_missing_fails_closed() -> None:
    """Calls without explicit org context fail closed (Invariant 15)."""
    store = ConfirmationStore()
    manager = ConfirmationManager(store=store)

    with pytest.raises(TenantContextMissingError):
        manager.issue_token(
            student_id=STUDENT_ID,
            assessment_id=ASSESSMENT_ID,
            ptm_event_id=PTM_EVENT_ID,
            org_id="",  # Empty
            sender_id=SENDER_ID_A,
            now=TEST_NOW,
        )

    with pytest.raises(TenantContextMissingError):
        store.get_record("hash123", org_id="   ")  # Whitespace


def test_audit_privacy_hygiene() -> None:
    """Audit log records sanitize phone numbers and redact tokens/secrets (Invariant 10)."""
    store = ConfirmationStore()
    manager = ConfirmationManager(store=store)
    provider = MockMessagingProvider()

    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )

    manager.request_otp_challenge(
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        sender=make_sender(),
        guardian_phone=VALID_GUARDIAN_PHONE,
        has_consent=True,
        provider=provider,
        now=TEST_NOW,
    )

    audit_entries = store.get_audit_trail(token_info.token_hash, org_id=ORG_A)
    assert len(audit_entries) >= 2

    # Check raw database rows in confirmation_audit_log
    cur = store.conn.execute("SELECT * FROM confirmation_audit_log WHERE token_hash = ?", (token_info.token_hash,))
    rows = cur.fetchall()
    assert len(rows) >= 2
    for row in rows:
        details_str = row["details_json"]
        # Raw 10-digit mobile number must NEVER appear unmasked
        assert VALID_GUARDIAN_PHONE not in details_str
        # Raw token must NEVER appear
        assert token_info.raw_token not in details_str
        # Masked phone must appear in challenge audit
        if row["action"] == "OTP_CHALLENGED":
            assert mask_phone(VALID_GUARDIAN_PHONE) in details_str


def test_https_enforcement_on_custom_base_url() -> None:
    """Confirmation QR URL must strictly enforce HTTPS protocol."""
    raw_token = generate_opaque_token()
    # Non-HTTPS fails
    with pytest.raises(ValueError, match="HTTPS"):
        construct_qr_payload_url(raw_token, base_url="http://insecure.institution.org/verify")

    # Valid HTTPS succeeds
    secure_url = construct_qr_payload_url(raw_token, base_url="https://portal.dps.edu.in/confirm")
    assert secure_url == f"https://portal.dps.edu.in/confirm?token={raw_token}"


def test_timezone_naive_datetime_fails_closed() -> None:
    """Time hygiene: naive datetimes without timezone fail closed (ADR-0005)."""
    manager = ConfirmationManager()
    naive_dt = datetime(2026, 10, 24, 10, 0, 0)  # No tzinfo

    with pytest.raises(ValueError, match="timezone-aware"):
        manager.issue_token(
            student_id=STUDENT_ID,
            assessment_id=ASSESSMENT_ID,
            ptm_event_id=PTM_EVENT_ID,
            org_id=ORG_A,
            sender_id=SENDER_ID_A,
            now=naive_dt,
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        manager.request_otp_challenge(
            raw_token="some_token",
            org_id=ORG_A,
            sender=make_sender(),
            guardian_phone=VALID_GUARDIAN_PHONE,
            has_consent=True,
            now=naive_dt,
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        manager.verify_otp(
            otp_code="123456",
            raw_token="some_token",
            org_id=ORG_A,
            now=naive_dt,
        )


def test_locked_out_session_blocks_new_otp_challenges() -> None:
    """Once a token session is LOCKED_OUT, requesting new OTP challenges is blocked."""
    store = ConfirmationStore()
    manager = ConfirmationManager(store=store)
    provider = MockMessagingProvider()

    token_info = manager.issue_token(
        student_id=STUDENT_ID,
        assessment_id=ASSESSMENT_ID,
        ptm_event_id=PTM_EVENT_ID,
        org_id=ORG_A,
        sender_id=SENDER_ID_A,
        now=TEST_NOW,
    )

    manager.request_otp_challenge(
        raw_token=token_info.raw_token,
        org_id=ORG_A,
        sender=make_sender(),
        guardian_phone=VALID_GUARDIAN_PHONE,
        has_consent=True,
        provider=provider,
        now=TEST_NOW,
    )

    # Exhaust 5 attempts
    for i in range(1, 5):
        with pytest.raises(InvalidOtpError):
            manager.verify_otp("000000", raw_token=token_info.raw_token, org_id=ORG_A, now=TEST_NOW + timedelta(seconds=i))

    with pytest.raises(SessionLockedOutError):
        manager.verify_otp("000000", raw_token=token_info.raw_token, org_id=ORG_A, now=TEST_NOW + timedelta(seconds=5))

    # Token is now LOCKED_OUT. Attempting to request another challenge fails closed
    with pytest.raises(SessionLockedOutError):
        manager.request_otp_challenge(
            raw_token=token_info.raw_token,
            org_id=ORG_A,
            sender=make_sender(),
            guardian_phone=VALID_GUARDIAN_PHONE,
            has_consent=True,
            provider=provider,
            now=TEST_NOW + timedelta(seconds=10),
        )
