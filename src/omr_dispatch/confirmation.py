"""
Parent Confirmation Engine (QR + OTP) (`src/omr_dispatch/confirmation.py`).

Provides:
- Cryptographically random opaque token generation (secrets.token_urlsafe) scoped strictly to
  tenant (org_id), sender (sender_id), student (student_id), assessment (assessment_id), and PTM event.
- Hash-only token storage: persists strictly SHA-256 digests; raw tokens are returned once and never stored.
- Zero-PII QR code payload construction (secure HTTPS URL containing only the opaque token).
- Security controls: configurable TTL expiry, explicit revocation, single-use replay protection.
- Session rate limiting: strict <= 5 failed OTP attempts before lockout (LOCKED_OUT).
- Tenant isolation: cross-tenant token access fails closed with UNAUTHORIZED_TENANT_ACCESS.
- Guardian contact verification & OTP challenge dispatch using org sender's registered authentication template
  only when sender status is READY (ADR-0019).
- Durable SQLite persistence and restart recovery.
- Full compliance with QrTokenProvider protocol from S6 renderer.

Compliant with:
- ADR-0002: Integer-only attempt counters, rate limits, and TTL seconds; zero float() calls.
- ADR-0005: Explicit timezone-aware UTC datetime parameters on all state transitions; zero unanchored clocks.
- ADR-0006: Schema versioning (schema_version = 1) on all serialized result models.
- ADR-0008: Typed exception hierarchy inheriting from OMRDispatchError.
- ADR-0009: Zero direct environment variable reads.
- ADR-0010: Standard Latin digits (0-9) in OTP codes and URLs.
- ADR-0016 & D-04: Strict PTM-linked assessment scoping (is_ptm_linked=True); fails closed otherwise.
- ADR-0019: Sender identity credential isolation and READY status gating.
- Invariant 10: Zero personal data in QR URLs; raw tokens, OTPs, and phone numbers masked in logs/audit records.
- Invariant 15: Mandatory explicit org_id context on all store and manager operations.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from omr_dispatch.contacts import format_e164, mask_phone, normalize_indian_mobile
from omr_dispatch.messaging.policy import TenantContextMissingError
from omr_dispatch.messaging.provider import (
    MessagingProvider,
    SenderIdentity,
    SenderStatus,
    TemplateComponent,
    TemplateParameter,
    TemplateSendRequest,
)
from omr_dispatch.models import Assessment, AssessmentPurpose, OMRDispatchError

# ------------------------------------------------------------------------------
# Constants and Defaults (ADR-0002: Integer-Only Math)
# ------------------------------------------------------------------------------

DEFAULT_BASE_CONFIRMATION_URL: str = "https://confirm.institution.org/verify"
DEFAULT_TOKEN_TTL_SECONDS: int = 7 * 24 * 3600  # 604,800 seconds (7 days)
DEFAULT_OTP_TTL_SECONDS: int = 600  # 600 seconds (10 minutes)
MAX_OTP_ATTEMPTS: int = 5  # Strict lockout threshold (<= 5 attempts)
OTP_LENGTH: int = 6
MIN_TOKEN_ENTROPY_BYTES: int = 32
OTP_TEMPLATE_NAME: str = "guardian_otp_challenge_v1"


# ------------------------------------------------------------------------------
# Exception Hierarchy (ADR-0008)
# ------------------------------------------------------------------------------


class ConfirmationError(OMRDispatchError):
    """Base exception for all parent confirmation operations."""


class NonPtmAssessmentError(ConfirmationError):
    """Raised when confirmation is requested for an assessment not linked to PTM."""


class TokenNotFoundError(ConfirmationError):
    """Raised when an opaque token or token hash is not found in the store."""


class TokenExpiredError(ConfirmationError):
    """Raised when an opaque token or OTP challenge has expired."""


class TokenRevokedError(ConfirmationError):
    """Raised when attempting to access or verify an explicitly revoked token."""


class TokenAlreadyUsedError(ConfirmationError):
    """Raised when attempting to reuse an already confirmed single-use token."""


class SessionLockedOutError(ConfirmationError):
    """Raised when failed verification attempts reach or exceed the maximum limit (5)."""


class UnauthorizedTenantAccessError(ConfirmationError):
    """Raised when an operation attempts to access a token across tenant boundaries."""


class InvalidOtpError(ConfirmationError):
    """Raised when an incorrect OTP is supplied during verification."""


class SenderNotReadyError(ConfirmationError):
    """Raised when the org's sender identity is not in READY status (ADR-0019)."""


class UnverifiedGuardianContactError(ConfirmationError):
    """Raised when guardian contact information is missing, invalid, quarantined, or unconsented."""


# ------------------------------------------------------------------------------
# Enumerations and Statuses
# ------------------------------------------------------------------------------


class ConfirmationStatus(StrEnum):
    """Lifecycle status of a parent confirmation token."""

    PENDING = "PENDING"
    CHALLENGED = "CHALLENGED"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    LOCKED_OUT = "LOCKED_OUT"


class VerificationMethod(StrEnum):
    """Verification mechanism recorded in the confirmation assurance log."""

    DIGITAL_OTP = "DIGITAL_OTP"
    PAPER_SIGNATURE_UNVERIFIED = "PAPER_SIGNATURE_UNVERIFIED"


# ------------------------------------------------------------------------------
# Models (Pydantic v2 with extra="forbid" and schema_version)
# ------------------------------------------------------------------------------


class ConfirmationTokenInfo(BaseModel):
    """
    Ephemeral issuance information returned strictly once upon token creation.
    The `raw_token` field is NEVER stored in the database.
    """

    model_config = ConfigDict(extra="forbid")

    raw_token: str
    token_hash: str
    qr_payload_url: str
    org_id: str
    sender_id: str
    student_id: str
    assessment_id: str
    ptm_event_id: str
    status: ConfirmationStatus
    expires_at_utc: datetime
    created_at_utc: datetime
    schema_version: int = 1


class ConfirmationRecord(BaseModel):
    """
    Persisted confirmation record containing strictly hashed credentials and security counters.
    """

    model_config = ConfigDict(extra="forbid")

    token_hash: str
    org_id: str
    sender_id: str
    student_id: str
    assessment_id: str
    ptm_event_id: str
    status: ConfirmationStatus
    failed_attempts: int = 0
    max_attempts: int = MAX_OTP_ATTEMPTS
    otp_hash: str | None = None
    otp_created_at_utc: datetime | None = None
    otp_expires_at_utc: datetime | None = None
    verified_at_utc: datetime | None = None
    verification_method: VerificationMethod | None = None
    guardian_phone_masked: str | None = None
    created_at_utc: datetime
    expires_at_utc: datetime
    schema_version: int = 1


class OtpChallengeResult(BaseModel):
    """Result of dispatching an OTP challenge to a verified guardian."""

    model_config = ConfigDict(extra="forbid")

    token_hash: str
    org_id: str
    recipient_phone_masked: str
    template_name: str
    dispatched: bool
    expires_at_utc: datetime
    schema_version: int = 1


class ConfirmationResult(BaseModel):
    """Immutable proof record of successful guardian confirmation."""

    model_config = ConfigDict(extra="forbid")

    token_hash: str
    org_id: str
    student_id: str
    assessment_id: str
    ptm_event_id: str
    status: ConfirmationStatus
    verified_at_utc: datetime
    verification_method: VerificationMethod
    assurance_statement: str = (
        "Mechanism provides verification of WhatsApp OTP receipt by registered guardian contact; "
        "paper signature line remains optional and unverified."
    )
    schema_version: int = 1


# ------------------------------------------------------------------------------
# Pure Core Cryptographic and URL Helpers
# ------------------------------------------------------------------------------


def compute_token_hash(raw_token: str) -> str:
    """Compute deterministic SHA-256 hex digest of an opaque token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def compute_otp_hash(otp_code: str, token_hash: str) -> str:
    """
    Compute keyed HMAC-SHA256 digest of an OTP code using token_hash as secret key.
    Provides constant-time verifiable one-way storage.
    """
    return hmac.new(token_hash.encode("utf-8"), otp_code.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_opaque_token(nbytes: int = MIN_TOKEN_ENTROPY_BYTES) -> str:
    """
    Generate a cryptographically random, URL-safe opaque token with >= 32 bytes entropy.
    """
    if nbytes < MIN_TOKEN_ENTROPY_BYTES:
        raise ValueError(f"Token entropy must be at least {MIN_TOKEN_ENTROPY_BYTES} bytes.")
    return secrets.token_urlsafe(nbytes)


def construct_qr_payload_url(raw_token: str, base_url: str = DEFAULT_BASE_CONFIRMATION_URL) -> str:
    """
    Construct the zero-PII HTTPS URL for embedding into the PTM slip QR code.
    Contains strictly the opaque token and zero personal data.
    """
    if not base_url.startswith("https://"):
        raise ValueError("Confirmation URL must use secure HTTPS protocol.")
    return f"{base_url}?token={raw_token}"


def check_is_ptm_linked(
    assessment: Assessment | Any = None,
    *,
    is_ptm_linked: bool | None = None,
) -> bool:
    """Check whether an assessment is linked to PTM consultation meetings."""
    if is_ptm_linked is not None:
        return bool(is_ptm_linked)
    if assessment is not None:
        if hasattr(assessment, "is_ptm_linked"):
            return bool(assessment.is_ptm_linked)
        if hasattr(assessment, "purpose_flags"):
            return (
                AssessmentPurpose.PTM_LINKED in assessment.purpose_flags
                or "PTM_LINKED" in assessment.purpose_flags
            )
    return False


# ------------------------------------------------------------------------------
# Persistent SQLite Confirmation Store
# ------------------------------------------------------------------------------


class ConfirmationStore:
    """
    Durable SQLite store for parent confirmations, attempts, and audit trail.
    Enforces tenant context (org_id) on every operation (Invariant 15).
    """

    SCHEMA_DDL = """
    CREATE TABLE IF NOT EXISTS parent_confirmations (
        token_hash TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        sender_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        assessment_id TEXT NOT NULL,
        ptm_event_id TEXT NOT NULL,
        status TEXT NOT NULL,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 5,
        otp_hash TEXT,
        otp_created_at_utc TEXT,
        otp_expires_at_utc TEXT,
        verified_at_utc TEXT,
        verification_method TEXT,
        guardian_phone_masked TEXT,
        created_at_utc TEXT NOT NULL,
        expires_at_utc TEXT NOT NULL,
        metadata_json TEXT,
        schema_version INTEGER NOT NULL DEFAULT 1
    );

    CREATE INDEX IF NOT EXISTS idx_parent_confirmations_org ON parent_confirmations(org_id, student_id, assessment_id);
    CREATE INDEX IF NOT EXISTS idx_parent_confirmations_status ON parent_confirmations(org_id, status);

    CREATE TABLE IF NOT EXISTS confirmation_audit_log (
        event_id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        token_hash TEXT NOT NULL,
        action TEXT NOT NULL,
        timestamp_utc TEXT NOT NULL,
        details_json TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_conf_audit_token ON confirmation_audit_log(org_id, token_hash);
    """

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        if self.db_path != ":memory:":
            with contextlib.suppress(sqlite3.OperationalError):
                self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")
        self._init_schema()

    def close(self) -> None:
        """Close the underlying database connection."""
        with contextlib.suppress(Exception):
            self.conn.close()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(self.SCHEMA_DDL)

    def _assert_org_context(self, org_id: str) -> None:
        if not org_id or not org_id.strip():
            raise TenantContextMissingError("Tenant context (org_id) is mandatory on all operations.")

    def save_record(self, record: ConfirmationRecord, *, org_id: str) -> None:
        """Persist a new confirmation record."""
        self._assert_org_context(org_id)
        if record.org_id != org_id:
            raise UnauthorizedTenantAccessError("Mismatched org_id in confirmation record.")

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO parent_confirmations (
                    token_hash, org_id, sender_id, student_id, assessment_id,
                    ptm_event_id, status, failed_attempts, max_attempts,
                    otp_hash, otp_created_at_utc, otp_expires_at_utc,
                    verified_at_utc, verification_method, guardian_phone_masked,
                    created_at_utc, expires_at_utc, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.token_hash,
                    record.org_id,
                    record.sender_id,
                    record.student_id,
                    record.assessment_id,
                    record.ptm_event_id,
                    str(record.status),
                    record.failed_attempts,
                    record.max_attempts,
                    record.otp_hash,
                    record.otp_created_at_utc.isoformat() if record.otp_created_at_utc else None,
                    record.otp_expires_at_utc.isoformat() if record.otp_expires_at_utc else None,
                    record.verified_at_utc.isoformat() if record.verified_at_utc else None,
                    str(record.verification_method) if record.verification_method else None,
                    record.guardian_phone_masked,
                    record.created_at_utc.isoformat(),
                    record.expires_at_utc.isoformat(),
                    record.schema_version,
                ),
            )

    def get_record(self, token_hash: str, *, org_id: str) -> ConfirmationRecord | None:
        """
        Fetch a confirmation record by token hash, enforcing tenant isolation.
        If a record exists under a different org_id, raises UnauthorizedTenantAccessError.
        """
        self._assert_org_context(org_id)

        cur = self.conn.execute(
            "SELECT * FROM parent_confirmations WHERE token_hash = ?",
            (token_hash,),
        )
        row = cur.fetchone()
        if row is None:
            return None

        row_org_id = str(row["org_id"])
        if row_org_id != org_id:
            raise UnauthorizedTenantAccessError(
                f"Cross-tenant access forbidden: record belongs to {row_org_id}, caller is {org_id}."
            )

        return self._row_to_record(row)

    def get_by_student(
        self,
        student_id: str,
        *,
        org_id: str,
        assessment_id: str | None = None,
    ) -> ConfirmationRecord | None:
        """Fetch confirmation record for a student within an org."""
        self._assert_org_context(org_id)

        if assessment_id is not None:
            cur = self.conn.execute(
                """
                SELECT * FROM parent_confirmations
                WHERE org_id = ? AND student_id = ? AND assessment_id = ?
                ORDER BY created_at_utc DESC LIMIT 1
                """,
                (org_id, student_id, assessment_id),
            )
        else:
            cur = self.conn.execute(
                """
                SELECT * FROM parent_confirmations
                WHERE org_id = ? AND student_id = ?
                ORDER BY created_at_utc DESC LIMIT 1
                """,
                (org_id, student_id),
            )
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def update_status(self, token_hash: str, status: ConfirmationStatus, *, org_id: str) -> None:
        """Update token lifecycle status."""
        self._assert_org_context(org_id)
        # Verify tenant ownership first
        rec = self.get_record(token_hash, org_id=org_id)
        if rec is None:
            raise TokenNotFoundError(f"Token hash {token_hash} not found for org {org_id}.")

        with self.conn:
            self.conn.execute(
                "UPDATE parent_confirmations SET status = ? WHERE token_hash = ? AND org_id = ?",
                (str(status), token_hash, org_id),
            )

    def set_otp(
        self,
        token_hash: str,
        *,
        otp_hash: str,
        otp_created_at_utc: datetime,
        otp_expires_at_utc: datetime,
        guardian_phone_masked: str,
        org_id: str,
    ) -> None:
        """Attach an OTP challenge to a confirmation record."""
        self._assert_org_context(org_id)
        rec = self.get_record(token_hash, org_id=org_id)
        if rec is None:
            raise TokenNotFoundError(f"Token hash {token_hash} not found for org {org_id}.")

        with self.conn:
            self.conn.execute(
                """
                UPDATE parent_confirmations
                SET otp_hash = ?, otp_created_at_utc = ?, otp_expires_at_utc = ?,
                    guardian_phone_masked = ?, status = ?
                WHERE token_hash = ? AND org_id = ?
                """,
                (
                    otp_hash,
                    otp_created_at_utc.isoformat(),
                    otp_expires_at_utc.isoformat(),
                    guardian_phone_masked,
                    str(ConfirmationStatus.CHALLENGED),
                    token_hash,
                    org_id,
                ),
            )

    def record_failed_attempt(
        self,
        token_hash: str,
        *,
        org_id: str,
        max_attempts: int = MAX_OTP_ATTEMPTS,
    ) -> int:
        """
        Increment the failed attempt counter in integer math.
        If the new count reaches max_attempts, automatically transitions status to LOCKED_OUT.
        Returns the updated failed attempt count.
        """
        self._assert_org_context(org_id)
        rec = self.get_record(token_hash, org_id=org_id)
        if rec is None:
            raise TokenNotFoundError(f"Token hash {token_hash} not found for org {org_id}.")

        with self.conn:
            new_attempts = rec.failed_attempts + 1
            new_status = str(ConfirmationStatus.LOCKED_OUT) if new_attempts >= max_attempts else str(rec.status)

            self.conn.execute(
                """
                UPDATE parent_confirmations
                SET failed_attempts = ?, status = ?
                WHERE token_hash = ? AND org_id = ?
                """,
                (new_attempts, new_status, token_hash, org_id),
            )
            return new_attempts

    def confirm_token(
        self,
        token_hash: str,
        *,
        verified_at_utc: datetime,
        method: VerificationMethod,
        org_id: str,
    ) -> None:
        """Transition token to CONFIRMED with verification timestamp and method."""
        self._assert_org_context(org_id)
        rec = self.get_record(token_hash, org_id=org_id)
        if rec is None:
            raise TokenNotFoundError(f"Token hash {token_hash} not found for org {org_id}.")

        with self.conn:
            self.conn.execute(
                """
                UPDATE parent_confirmations
                SET status = ?, verified_at_utc = ?, verification_method = ?
                WHERE token_hash = ? AND org_id = ?
                """,
                (
                    str(ConfirmationStatus.CONFIRMED),
                    verified_at_utc.isoformat(),
                    str(method),
                    token_hash,
                    org_id,
                ),
            )

    def record_audit(
        self,
        token_hash: str,
        action: str,
        details: dict[str, Any],
        timestamp_utc: datetime,
        *,
        org_id: str,
    ) -> None:
        """
        Record a tenant-scoped audit entry.
        Never logs raw tokens, raw OTP secrets, or full phone numbers (Invariant 10).
        """
        self._assert_org_context(org_id)

        # Sanitize details to guarantee zero unmasked PII
        sanitized: dict[str, Any] = {}
        for k, v in details.items():
            if "phone" in k.lower() or "mobile" in k.lower() or "contact" in k.lower():
                if isinstance(v, str):
                    sanitized[k] = v if "*" in v else mask_phone(v)
                else:
                    sanitized[k] = "[MASKED_PHONE]"
            elif "token" in k.lower() or "otp" in k.lower() or "secret" in k.lower():
                sanitized[k] = "[REDACTED_SECRET]"
            else:
                sanitized[k] = v

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO confirmation_audit_log (
                    event_id, org_id, token_hash, action, timestamp_utc, details_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    org_id,
                    token_hash,
                    action,
                    timestamp_utc.isoformat(),
                    json.dumps(sanitized),
                ),
            )

    def get_audit_trail(self, token_hash: str, *, org_id: str) -> list[dict[str, Any]]:
        """Retrieve audit log history for a token within an org."""
        self._assert_org_context(org_id)

        cur = self.conn.execute(
            """
            SELECT event_id, org_id, token_hash, action, timestamp_utc, details_json
            FROM confirmation_audit_log
            WHERE org_id = ? AND token_hash = ?
            ORDER BY timestamp_utc ASC
            """,
            (org_id, token_hash),
        )
        entries: list[dict[str, Any]] = []
        for row in cur.fetchall():
            entries.append(
                {
                    "event_id": row["event_id"],
                    "org_id": row["org_id"],
                    "token_hash": row["token_hash"],
                    "action": row["action"],
                    "timestamp_utc": row["timestamp_utc"],
                    "details": json.loads(row["details_json"]),
                }
            )
        return entries

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ConfirmationRecord:
        otp_created = (
            datetime.fromisoformat(row["otp_created_at_utc"])
            if row["otp_created_at_utc"]
            else None
        )
        otp_expires = (
            datetime.fromisoformat(row["otp_expires_at_utc"])
            if row["otp_expires_at_utc"]
            else None
        )
        verified_at = (
            datetime.fromisoformat(row["verified_at_utc"])
            if row["verified_at_utc"]
            else None
        )
        ver_method = (
            VerificationMethod(row["verification_method"])
            if row["verification_method"]
            else None
        )

        return ConfirmationRecord(
            token_hash=row["token_hash"],
            org_id=row["org_id"],
            sender_id=row["sender_id"],
            student_id=row["student_id"],
            assessment_id=row["assessment_id"],
            ptm_event_id=row["ptm_event_id"],
            status=ConfirmationStatus(row["status"]),
            failed_attempts=int(row["failed_attempts"]),
            max_attempts=int(row["max_attempts"]),
            otp_hash=row["otp_hash"],
            otp_created_at_utc=otp_created,
            otp_expires_at_utc=otp_expires,
            verified_at_utc=verified_at,
            verification_method=ver_method,
            guardian_phone_masked=row["guardian_phone_masked"],
            created_at_utc=datetime.fromisoformat(row["created_at_utc"]),
            expires_at_utc=datetime.fromisoformat(row["expires_at_utc"]),
            schema_version=int(row["schema_version"]),
        )


# ------------------------------------------------------------------------------
# High-Level Confirmation Manager & QrTokenProvider
# ------------------------------------------------------------------------------


class ConfirmationManager:
    """
    High-level parent confirmation coordinator.
    Manages opaque tokens, OTP challenge generation, rate limiting, and verification.
    Implements QrTokenProvider protocol for seamless integration with PlaywrightRenderer.
    """

    def __init__(self, store: ConfirmationStore | None = None) -> None:
        self.store = store if store is not None else ConfirmationStore()
        # In-memory ephemeral cache of raw tokens for PTM slip generation session only
        # Key: (org_id, student_id, assessment_id) -> raw_token
        self._ephemeral_tokens: dict[tuple[str, str, str], str] = {}

    def get_token(
        self,
        student_id: str,
        *,
        org_id: str = "DEFAULT_INSTITUTION",
        assessment_id: str | None = None,
    ) -> str | None:
        """
        Implementation of QrTokenProvider protocol (S6 Task 9 / S11).
        Returns the raw opaque token string for embedding into PTM slips,
        or None if no active token exists.
        Never encodes personal data.
        """
        if not org_id or not org_id.strip():
            return None

        # Check ephemeral cache first
        key = (org_id, student_id, assessment_id or "")
        if key in self._ephemeral_tokens:
            return self._ephemeral_tokens[key]

        # Check store for active record
        rec = self.store.get_by_student(student_id, org_id=org_id, assessment_id=assessment_id)
        if rec is None or rec.status in (
            ConfirmationStatus.EXPIRED,
            ConfirmationStatus.REVOKED,
            ConfirmationStatus.CONFIRMED,
            ConfirmationStatus.LOCKED_OUT,
        ):
            return None

        # Store holds only hash; return None if raw token has expired from ephemeral cache
        return None

    def issue_token(
        self,
        student_id: str,
        assessment_id: str,
        ptm_event_id: str,
        *,
        org_id: str,
        sender_id: str,
        now: datetime,
        is_ptm_linked: bool = True,
        assessment: Assessment | None = None,
        ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
        base_url: str = DEFAULT_BASE_CONFIRMATION_URL,
    ) -> ConfirmationTokenInfo:
        """
        Issue a new opaque confirmation token.

        Enforces:
          - Mandatory tenant context (org_id).
          - Strict PTM-linked assessment scoping: fails closed if not PTM linked.
          - Cryptographically secure 32-byte entropy token generation.
          - Hash-only storage: database receives strictly SHA-256 digest.
          - Zero-PII QR code payload construction.
        """
        if not org_id or not org_id.strip():
            raise TenantContextMissingError("Tenant context (org_id) is mandatory.")

        if now.tzinfo is None:
            raise ValueError("Timestamp `now` must be timezone-aware (ADR-0005).")

        # PTM-linked guardrail
        ptm_linked = check_is_ptm_linked(assessment, is_ptm_linked=is_ptm_linked)
        if not ptm_linked:
            raise NonPtmAssessmentError(
                f"Assessment '{assessment_id}' is not PTM-linked. Confirmation tokens apply only to PTM events."
            )

        # Generate cryptographically secure token and its hash
        raw_token = generate_opaque_token(MIN_TOKEN_ENTROPY_BYTES)
        token_hash = compute_token_hash(raw_token)
        qr_url = construct_qr_payload_url(raw_token, base_url=base_url)

        expires_at = now + timedelta(seconds=ttl_seconds)

        record = ConfirmationRecord(
            token_hash=token_hash,
            org_id=org_id,
            sender_id=sender_id,
            student_id=student_id,
            assessment_id=assessment_id,
            ptm_event_id=ptm_event_id,
            status=ConfirmationStatus.PENDING,
            failed_attempts=0,
            max_attempts=MAX_OTP_ATTEMPTS,
            created_at_utc=now,
            expires_at_utc=expires_at,
            schema_version=1,
        )

        self.store.save_record(record, org_id=org_id)
        self.store.record_audit(
            token_hash,
            "TOKEN_ISSUED",
            {
                "student_id": student_id,
                "assessment_id": assessment_id,
                "ptm_event_id": ptm_event_id,
                "ttl_seconds": ttl_seconds,
            },
            now,
            org_id=org_id,
        )

        # Cache raw token ephemerally for QrTokenProvider
        self._ephemeral_tokens[(org_id, student_id, assessment_id)] = raw_token

        return ConfirmationTokenInfo(
            raw_token=raw_token,
            token_hash=token_hash,
            qr_payload_url=qr_url,
            org_id=org_id,
            sender_id=sender_id,
            student_id=student_id,
            assessment_id=assessment_id,
            ptm_event_id=ptm_event_id,
            status=ConfirmationStatus.PENDING,
            expires_at_utc=expires_at,
            created_at_utc=now,
            schema_version=1,
        )

    def revoke_token(
        self,
        *,
        org_id: str,
        now: datetime,
        raw_token: str | None = None,
        token_hash: str | None = None,
        reason: str = "Administrative revocation",
    ) -> None:
        """Explicitly revoke a token, preventing any further challenges or verification."""
        if not org_id or not org_id.strip():
            raise TenantContextMissingError("Tenant context (org_id) is mandatory.")

        if now.tzinfo is None:
            raise ValueError("Timestamp `now` must be timezone-aware (ADR-0005).")

        thash = token_hash or (compute_token_hash(raw_token) if raw_token else None)
        if not thash:
            raise ValueError("Either raw_token or token_hash must be provided.")

        rec = self.store.get_record(thash, org_id=org_id)
        if rec is None:
            raise TokenNotFoundError(f"Token hash {thash} not found for org {org_id}.")

        self.store.update_status(thash, ConfirmationStatus.REVOKED, org_id=org_id)
        self.store.record_audit(
            thash,
            "TOKEN_REVOKED",
            {"reason": reason},
            now,
            org_id=org_id,
        )

    def request_otp_challenge(
        self,
        *,
        org_id: str,
        sender: SenderIdentity,
        guardian_phone: str,
        has_consent: bool,
        now: datetime,
        raw_token: str | None = None,
        token_hash: str | None = None,
        is_quarantined: bool = False,
        provider: MessagingProvider | None = None,
        otp_ttl_seconds: int = DEFAULT_OTP_TTL_SECONDS,
    ) -> OtpChallengeResult:
        """
        Request and dispatch an OTP challenge to a verified guardian.

        Enforces:
          - Mandatory tenant context (org_id) and tenant boundary check.
          - Sender readiness: sender status must be READY (ADR-0019).
          - Verified guardian contact: valid phone number, explicit consent, not quarantined.
          - Token validity: not expired, not revoked, not already used, not locked out.
          - Cryptographically secure 6-digit OTP generation and keyed hash storage.
          - Dispatches challenge via registered authentication template.
        """
        if not org_id or not org_id.strip():
            raise TenantContextMissingError("Tenant context (org_id) is mandatory.")

        if now.tzinfo is None:
            raise ValueError("Timestamp `now` must be timezone-aware (ADR-0005).")

        # Sender tenant boundary check
        if sender.org_id != org_id:
            raise UnauthorizedTenantAccessError(
                f"Sender {sender.sender_id} org ({sender.org_id}) does not match request org ({org_id})."
            )

        # Sender readiness check (ADR-0019)
        if sender.status != SenderStatus.READY:
            raise SenderNotReadyError(
                f"Sender '{sender.sender_id}' is in status '{sender.status}'; must be READY to send OTP challenges."
            )

        thash = token_hash or (compute_token_hash(raw_token) if raw_token else None)
        if not thash:
            raise ValueError("Either raw_token or token_hash must be provided.")

        rec = self.store.get_record(thash, org_id=org_id)
        if rec is None:
            raise TokenNotFoundError(f"Token hash {thash} not found for org {org_id}.")

        # Security control checks
        if rec.status == ConfirmationStatus.REVOKED:
            raise TokenRevokedError(f"Token {thash} has been revoked.")

        if rec.status == ConfirmationStatus.CONFIRMED:
            raise TokenAlreadyUsedError(f"Token {thash} has already been confirmed and cannot be reused.")

        if rec.status == ConfirmationStatus.LOCKED_OUT or rec.failed_attempts >= rec.max_attempts:
            raise SessionLockedOutError(f"Token {thash} session is locked out due to excessive failed attempts.")

        if rec.expires_at_utc <= now:
            self.store.update_status(thash, ConfirmationStatus.EXPIRED, org_id=org_id)
            raise TokenExpiredError(f"Token {thash} expired at {rec.expires_at_utc.isoformat()}.")

        # Guardian contact verification
        normalized_phone = normalize_indian_mobile(guardian_phone)
        if normalized_phone is None:
            raise UnverifiedGuardianContactError(
                "Guardian phone number is invalid or cannot be normalized to Indian national format."
            )

        e164_phone = format_e164(normalized_phone)
        if e164_phone is None:
            raise UnverifiedGuardianContactError(
                "Guardian phone number cannot be formatted to standard E.164."
            )

        if not has_consent:
            raise UnverifiedGuardianContactError(
                "Guardian contact lacks verified explicit consent for automated messaging."
            )

        if is_quarantined:
            raise UnverifiedGuardianContactError(
                "Guardian contact is currently quarantined due to safety or collision flags."
            )

        # Generate 6-digit numeric OTP and compute HMAC hash
        otp_code = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = compute_otp_hash(otp_code, rec.token_hash)
        otp_expires_at = now + timedelta(seconds=otp_ttl_seconds)
        masked_phone = mask_phone(normalized_phone)

        # Persist challenge state
        self.store.set_otp(
            thash,
            otp_hash=otp_hash,
            otp_created_at_utc=now,
            otp_expires_at_utc=otp_expires_at,
            guardian_phone_masked=masked_phone,
            org_id=org_id,
        )

        dispatched = False
        if provider is not None:
            # Build Meta WhatsApp Authentication Template request
            req = TemplateSendRequest(
                recipient_phone_e164=e164_phone,
                template_name=OTP_TEMPLATE_NAME,
                language_code="hi",
                components=[
                    TemplateComponent(
                        type="body",
                        parameters=[TemplateParameter(type="text", text=otp_code)],
                    ),
                    TemplateComponent(
                        type="button",
                        parameters=[TemplateParameter(type="text", text=otp_code)],
                    ),
                ],
            )
            provider.send_template(org_id=org_id, sender=sender, request=req)
            dispatched = True

        self.store.record_audit(
            thash,
            "OTP_CHALLENGED",
            {
                "recipient_phone": masked_phone,
                "template_name": OTP_TEMPLATE_NAME,
                "dispatched": dispatched,
                "expires_at_utc": otp_expires_at.isoformat(),
            },
            now,
            org_id=org_id,
        )

        return OtpChallengeResult(
            token_hash=thash,
            org_id=org_id,
            recipient_phone_masked=masked_phone,
            template_name=OTP_TEMPLATE_NAME,
            dispatched=dispatched,
            expires_at_utc=otp_expires_at,
            schema_version=1,
        )

    def verify_otp(
        self,
        otp_code: str,
        *,
        org_id: str,
        now: datetime,
        raw_token: str | None = None,
        token_hash: str | None = None,
    ) -> ConfirmationResult:
        """
        Verify an OTP submitted by a guardian and transition token to CONFIRMED.

        Enforces:
          - Mandatory tenant context (org_id) and isolation check.
          - Strict <= 5 failed attempts rate limiting: 5th failure locks out session.
          - Once locked out, all subsequent attempts fail closed immediately.
          - Replay protection: cannot confirm an already confirmed token.
          - Constant-time HMAC comparison (hmac.compare_digest).
          - Accurate assurance statement (paper signature line remains unverified).
        """
        if not org_id or not org_id.strip():
            raise TenantContextMissingError("Tenant context (org_id) is mandatory.")

        if now.tzinfo is None:
            raise ValueError("Timestamp `now` must be timezone-aware (ADR-0005).")

        thash = token_hash or (compute_token_hash(raw_token) if raw_token else None)
        if not thash:
            raise ValueError("Either raw_token or token_hash must be provided.")

        rec = self.store.get_record(thash, org_id=org_id)
        if rec is None:
            raise TokenNotFoundError(f"Token hash {thash} not found for org {org_id}.")

        # Lifecycle and security checks
        if rec.status == ConfirmationStatus.REVOKED:
            raise TokenRevokedError(f"Token {thash} has been revoked.")

        if rec.status == ConfirmationStatus.CONFIRMED:
            raise TokenAlreadyUsedError(f"Token {thash} has already been confirmed and cannot be reused.")

        if rec.status == ConfirmationStatus.LOCKED_OUT or rec.failed_attempts >= rec.max_attempts:
            raise SessionLockedOutError(
                f"Session is locked out after reaching maximum failed attempts ({rec.max_attempts})."
            )

        if rec.expires_at_utc <= now:
            self.store.update_status(thash, ConfirmationStatus.EXPIRED, org_id=org_id)
            raise TokenExpiredError(f"Token {thash} expired at {rec.expires_at_utc.isoformat()}.")

        # OTP challenge existence & TTL checks
        if rec.otp_hash is None or rec.otp_expires_at_utc is None:
            raise InvalidOtpError("No active OTP challenge exists for this confirmation session.")

        if rec.otp_expires_at_utc <= now:
            new_attempts = self.store.record_failed_attempt(thash, org_id=org_id, max_attempts=rec.max_attempts)
            if new_attempts >= rec.max_attempts:
                self.store.record_audit(
                    thash,
                    "SESSION_LOCKED_OUT",
                    {"reason": "OTP expired and attempts exhausted", "failed_attempts": new_attempts},
                    now,
                    org_id=org_id,
                )
                raise SessionLockedOutError(f"Session locked out after {new_attempts} failed attempts.")
            raise TokenExpiredError("The OTP challenge has expired. Please request a new OTP.")

        # Constant-time comparison
        candidate_hash = compute_otp_hash(otp_code.strip(), rec.token_hash)
        if hmac.compare_digest(candidate_hash, rec.otp_hash):
            # Verification SUCCESS
            self.store.confirm_token(
                thash,
                verified_at_utc=now,
                method=VerificationMethod.DIGITAL_OTP,
                org_id=org_id,
            )
            self.store.record_audit(
                thash,
                "CONFIRMATION_VERIFIED",
                {
                    "verification_method": str(VerificationMethod.DIGITAL_OTP),
                    "student_id": rec.student_id,
                    "assessment_id": rec.assessment_id,
                },
                now,
                org_id=org_id,
            )

            # Evict from ephemeral cache to free memory
            self._ephemeral_tokens.pop((org_id, rec.student_id, rec.assessment_id), None)

            return ConfirmationResult(
                token_hash=thash,
                org_id=org_id,
                student_id=rec.student_id,
                assessment_id=rec.assessment_id,
                ptm_event_id=rec.ptm_event_id,
                status=ConfirmationStatus.CONFIRMED,
                verified_at_utc=now,
                verification_method=VerificationMethod.DIGITAL_OTP,
                schema_version=1,
            )

        # Verification FAILURE
        new_attempts = self.store.record_failed_attempt(thash, org_id=org_id, max_attempts=rec.max_attempts)
        if new_attempts >= rec.max_attempts:
            self.store.record_audit(
                thash,
                "SESSION_LOCKED_OUT",
                {"failed_attempts": new_attempts, "max_attempts": rec.max_attempts},
                now,
                org_id=org_id,
            )
            raise SessionLockedOutError(
                f"Maximum failed attempts ({rec.max_attempts}) reached. Session is locked out."
            )

        remaining = rec.max_attempts - new_attempts
        self.store.record_audit(
            thash,
            "OTP_ATTEMPT_FAILED",
            {"failed_attempts": new_attempts, "remaining_attempts": remaining},
            now,
            org_id=org_id,
        )
        raise InvalidOtpError(f"Invalid OTP entered. {remaining} attempt(s) remaining.")
