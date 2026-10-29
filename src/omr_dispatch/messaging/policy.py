"""
Messaging Policy Engine (`src/omr_dispatch/messaging/policy.py`).

Enforces pre-dispatch gating rules before any provider network invocation:
- Global Invariant 8: Live messaging disabled by default.
- Global Invariant 9: Never infer consent, guardian identity, or sibling status from spreadsheet value or surname.
- Global Invariant 10: Never log full phone numbers; mask them.
- Global Invariant 13: Fail closed: uncertain input -> REVIEW_REQUIRED / block / defer, never a guess.
- Global Invariant 15: Explicit tenant context (org_id) on all operations.
- ADR-0005: Timezone-aware UTC datetimes.
- ADR-0008: Typed reason codes and structured rejection tracking.
- ADR-0010: Unicode NFC normalization.
- ADR-0016: Assessment purpose and consent scope alignment.
- ADR-0019: Per-school sender identity and template prerequisites.
- ADR-0020: Global and tenant-specific kill switches.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from omr_dispatch.contacts import mask_phone, normalize_indian_mobile
from omr_dispatch.models import (
    AssessmentPurpose,
    ContactEvaluation,
    ContactQuarantineFlag,
    OMRDispatchError,
    StudentAdmissionRow,
)


class TenantContextMissingError(OMRDispatchError):
    """Raised when an operation is attempted without an explicit org_id (Invariant 15)."""


class PolicyReasonCode(StrEnum):
    """Authoritative reason codes for policy gating decisions (S8 Task 1)."""

    ALLOWED = "ALLOWED"

    # Contact & Phone hygiene quarantine flags
    INTERCEPTION_RISK_SAME_NUMBER = "INTERCEPTION_RISK_SAME_NUMBER"
    DUPLICATE_PARENT_UNVERIFIED = "DUPLICATE_PARENT_UNVERIFIED"
    INVALID_PHONE_NUMBER = "INVALID_PHONE_NUMBER"
    INVALID_STUDENT_PHONE_NUMBER = "INVALID_STUDENT_PHONE_NUMBER"

    # Consent and Guardian Verification flags
    CONSENT_UNKNOWN = "CONSENT_UNKNOWN"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    CONSENT_MISSING = "CONSENT_MISSING"
    CONSENT_PURPOSE_MISMATCH = "CONSENT_PURPOSE_MISMATCH"
    GUARDIAN_UNVERIFIED = "GUARDIAN_UNVERIFIED"

    # Administrative and Kill Switch flags
    GLOBAL_KILL_SWITCH_ENGAGED = "GLOBAL_KILL_SWITCH_ENGAGED"
    TENANT_KILL_SWITCH_ENGAGED = "TENANT_KILL_SWITCH_ENGAGED"
    TENANT_SUSPENDED = "TENANT_SUSPENDED"

    # Sender prerequisites and Account/Billing flags
    SENDER_NOT_READY = "SENDER_NOT_READY"
    SENDER_NOT_CONFIGURED = "SENDER_NOT_CONFIGURED"
    CREDENTIALS_MISSING = "CREDENTIALS_MISSING"
    DAILY_QUOTA_EXCEEDED = "DAILY_QUOTA_EXCEEDED"
    BILLING_INACTIVE = "BILLING_INACTIVE"

    # Template and Service Window flags
    TEMPLATE_NOT_APPROVED = "TEMPLATE_NOT_APPROVED"
    TEMPLATE_CONTENT_MISMATCH = "TEMPLATE_CONTENT_MISMATCH"
    SERVICE_WINDOW_CLOSED_FOR_FREEFORM = "SERVICE_WINDOW_CLOSED_FOR_FREEFORM"

    # API contract and Safety switches
    LIVE_DISPATCH_DISABLED = "LIVE_DISPATCH_DISABLED"
    UNKNOWN_NEEDS_REVIEW = "UNKNOWN_NEEDS_REVIEW"


class ServiceWindowState(BaseModel):
    """Tracks WhatsApp 24-hour customer service window status."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool = False
    last_incoming_at_utc: datetime | None = None
    window_closes_at_utc: datetime | None = None


class SenderPrerequisites(BaseModel):
    """Sender identity prerequisites evaluated prior to dispatch."""

    model_config = ConfigDict(extra="forbid")

    org_id: str
    sender_id: str = "default_sender"
    status: str = "READY"  # READY, NOT_CONFIGURED, SUSPENDED, FLAGGED
    waba_id: str = ""
    phone_number_id: str = ""
    has_valid_credentials: bool = True
    billing_active: bool = True
    daily_quota: int = 1000
    messages_sent_today: int = 0
    approved_templates: list[str] = Field(default_factory=list)


class MessageIntent(BaseModel):
    """Structured representation of intended message dispatch."""

    model_config = ConfigDict(extra="forbid")

    org_id: str
    student_id: str
    assessment_id: str
    purpose: str = "EXAM_RESULTS"
    channel: str = "WHATSAPP"
    is_freeform: bool = False
    template_name: str | None = None
    template_content_valid: bool = True
    recipient_phone_raw: str | None = None
    event_type: str = "PRIMARY"  # PRIMARY or REMINDER


class PolicyDecision(BaseModel):
    """Deterministic policy evaluation result before dispatch."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    reason_code: PolicyReasonCode | str
    target_state: str  # SCHEDULED, BLOCKED_CONSENT, BLOCKED_HYGIENE, BLOCKED_POLICY
    idempotency_key: str
    checks: dict[str, bool | str | None]
    evaluated_at_utc: datetime
    recipient_phone_masked: str = ""


def compute_idempotency_key(
    org_id: str,
    student_id: str,
    assessment_id: str,
    purpose: str = "EXAM_RESULTS",
    channel: str = "WHATSAPP",
    event_type: str = "PRIMARY",
) -> str:
    """
    Compute deterministic per-org idempotency key (S8 Task 3).
    Formula: sha256(f"{org_id}:{student_id}:{assessment_id}:{purpose}:{channel}:{event_type}")
    Guaranteed: Contains zero raw phone numbers or personal data.
    """
    if not org_id or not str(org_id).strip():
        raise TenantContextMissingError("Explicit org context (org_id) is required to compute idempotency key.")
    raw_str = f"{org_id}:{student_id}:{assessment_id}:{purpose}:{channel}:{event_type}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


def evaluate_dispatch_policy(
    org_id: str,
    admission: StudentAdmissionRow,
    assessment_id: str,
    contact_eval: ContactEvaluation | None = None,
    intent: MessageIntent | None = None,
    sender: SenderPrerequisites | None = None,
    service_window: ServiceWindowState | None = None,
    global_kill_switch: bool = False,
    tenant_kill_switch: bool = False,
    tenant_suspended: bool = False,
    require_live_enabled: bool = False,
    live_dispatch_enabled: bool = False,
    clock_now_utc: datetime | None = None,
) -> PolicyDecision:
    """
    Evaluate policy decisions before every message send (S8 Task 1).

    Enforces:
      1. Explicit org context (org_id) - raises TenantContextMissingError if absent.
      2. Global & per-tenant emergency kill-switches / pause.
      3. Contact hygiene quarantine flags (interception risk, unverified duplicate, invalid number).
      4. Guardian verification status (must be VERIFIED).
      5. Consent status (must be OPT_IN, non-revoked, and scope-aligned).
      6. Sender readiness, credentials, and billing prerequisites.
      7. Service window (free-form allowed only in active 24h window; template required otherwise).
      8. Template approval status and content compatibility.
      9. Live dispatch safety switch (when require_live_enabled is True).

    Returns a typed PolicyDecision with exact reason code and target state:
      - SCHEDULED if allowed
      - BLOCKED_CONSENT if consent or guardian verification fails
      - BLOCKED_HYGIENE if contact quarantine flags are present
      - BLOCKED_POLICY if administrative, sender, template, or window checks fail
    """
    if not org_id or not str(org_id).strip():
        raise TenantContextMissingError("Explicit org context (org_id) is required for policy evaluation.")

    now = clock_now_utc or datetime.now(UTC)

    # Resolve message parameters
    purpose = intent.purpose if intent else "EXAM_RESULTS"
    channel = intent.channel if intent else "WHATSAPP"
    event_type = intent.event_type if intent else "PRIMARY"
    is_freeform = intent.is_freeform if intent else False
    template_name = intent.template_name if intent else None
    template_content_valid = intent.template_content_valid if intent else True

    # Compute idempotency key with zero personal data
    idempotency_key = compute_idempotency_key(
        org_id=org_id,
        student_id=admission.student_id,
        assessment_id=assessment_id,
        purpose=purpose,
        channel=channel,
        event_type=event_type,
    )

    # Mask phone for safe reporting
    recipient_phone_raw = (
        intent.recipient_phone_raw
        if (intent and intent.recipient_phone_raw)
        else admission.raw_guardian_phone
    )
    masked_phone = mask_phone(recipient_phone_raw)

    checks_evaluated: dict[str, bool | str | None] = {}

    # Check 1: Global and Tenant Kill-Switch / Suspension
    if global_kill_switch:
        checks_evaluated["global_kill_switch"] = "ENGAGED"
        return PolicyDecision(
            allowed=False,
            reason_code=PolicyReasonCode.GLOBAL_KILL_SWITCH_ENGAGED,
            target_state="BLOCKED_POLICY",
            idempotency_key=idempotency_key,
            checks=checks_evaluated,
            evaluated_at_utc=now,
            recipient_phone_masked=masked_phone,
        )

    if tenant_suspended:
        checks_evaluated["tenant_suspended"] = "SUSPENDED"
        return PolicyDecision(
            allowed=False,
            reason_code=PolicyReasonCode.TENANT_SUSPENDED,
            target_state="BLOCKED_POLICY",
            idempotency_key=idempotency_key,
            checks=checks_evaluated,
            evaluated_at_utc=now,
            recipient_phone_masked=masked_phone,
        )

    if tenant_kill_switch:
        checks_evaluated["tenant_kill_switch"] = "ENGAGED"
        return PolicyDecision(
            allowed=False,
            reason_code=PolicyReasonCode.TENANT_KILL_SWITCH_ENGAGED,
            target_state="BLOCKED_POLICY",
            idempotency_key=idempotency_key,
            checks=checks_evaluated,
            evaluated_at_utc=now,
            recipient_phone_masked=masked_phone,
        )

    # Check 2: Live Dispatch Enforcement (if requested)
    if require_live_enabled and not live_dispatch_enabled:
        checks_evaluated["live_dispatch_enabled"] = False
        return PolicyDecision(
            allowed=False,
            reason_code=PolicyReasonCode.LIVE_DISPATCH_DISABLED,
            target_state="BLOCKED_POLICY",
            idempotency_key=idempotency_key,
            checks=checks_evaluated,
            evaluated_at_utc=now,
            recipient_phone_masked=masked_phone,
        )

    # Check 3: Contact Hygiene and Quarantine Flags
    if contact_eval is not None and (contact_eval.is_quarantined or contact_eval.quarantine_flags):
        # Order of precedence for quarantine exclusion reasons
        precedence = [
            ContactQuarantineFlag.INVALID_PHONE_NUMBER.value,
            ContactQuarantineFlag.INVALID_STUDENT_PHONE_NUMBER.value,
            ContactQuarantineFlag.INTERCEPTION_RISK_SAME_NUMBER.value,
            ContactQuarantineFlag.DUPLICATE_PARENT_UNVERIFIED.value,
        ]
        chosen_reason = None
        for candidate in precedence:
            if candidate in contact_eval.quarantine_flags:
                chosen_reason = candidate
                break
        if chosen_reason is None:
            chosen_reason = contact_eval.quarantine_flags[0]

        checks_evaluated["quarantine"] = chosen_reason
        return PolicyDecision(
            allowed=False,
            reason_code=chosen_reason,
            target_state="BLOCKED_HYGIENE",
            idempotency_key=idempotency_key,
            checks=checks_evaluated,
            evaluated_at_utc=now,
            recipient_phone_masked=masked_phone,
        )

    # Direct phone format check if contact_eval not provided
    norm_guardian = normalize_indian_mobile(recipient_phone_raw)
    if norm_guardian is None:
        checks_evaluated["phone_format"] = "INVALID"
        return PolicyDecision(
            allowed=False,
            reason_code=PolicyReasonCode.INVALID_PHONE_NUMBER,
            target_state="BLOCKED_HYGIENE",
            idempotency_key=idempotency_key,
            checks=checks_evaluated,
            evaluated_at_utc=now,
            recipient_phone_masked=masked_phone,
        )

    # Direct interception risk check if student phone present
    if admission.raw_student_phone and str(admission.raw_student_phone).strip():
        norm_student = normalize_indian_mobile(admission.raw_student_phone)
        if norm_student and norm_student == norm_guardian:
            checks_evaluated["interception_risk"] = "SAME_NUMBER"
            return PolicyDecision(
                allowed=False,
                reason_code=PolicyReasonCode.INTERCEPTION_RISK_SAME_NUMBER,
                target_state="BLOCKED_HYGIENE",
                idempotency_key=idempotency_key,
                checks=checks_evaluated,
                evaluated_at_utc=now,
                recipient_phone_masked=masked_phone,
            )

    # Check 4: Guardian Verification Status (Invariant 9)
    if admission.guardian_verification != "VERIFIED":
        checks_evaluated["guardian_verification"] = admission.guardian_verification
        return PolicyDecision(
            allowed=False,
            reason_code=PolicyReasonCode.GUARDIAN_UNVERIFIED,
            target_state="BLOCKED_CONSENT",
            idempotency_key=idempotency_key,
            checks=checks_evaluated,
            evaluated_at_utc=now,
            recipient_phone_masked=masked_phone,
        )

    # Check 5: Consent Status (Invariant 9: Non-empty phone number is NOT consent)
    if admission.consent_status == "REVOKED":
        checks_evaluated["consent_status"] = "REVOKED"
        return PolicyDecision(
            allowed=False,
            reason_code=PolicyReasonCode.CONSENT_REVOKED,
            target_state="BLOCKED_CONSENT",
            idempotency_key=idempotency_key,
            checks=checks_evaluated,
            evaluated_at_utc=now,
            recipient_phone_masked=masked_phone,
        )

    if admission.consent_status != "OPT_IN":
        checks_evaluated["consent_status"] = admission.consent_status or "MISSING"
        reason = (
            PolicyReasonCode.CONSENT_UNKNOWN
            if admission.consent_status == "UNKNOWN"
            else PolicyReasonCode.CONSENT_MISSING
        )
        return PolicyDecision(
            allowed=False,
            reason_code=reason,
            target_state="BLOCKED_CONSENT",
            idempotency_key=idempotency_key,
            checks=checks_evaluated,
            evaluated_at_utc=now,
            recipient_phone_masked=masked_phone,
        )

    # Consent purpose alignment (ADR-0016)
    if admission.consent_scope and admission.consent_scope != "EXAM_RESULTS_ALL":
        scope = admission.consent_scope
        allowed_scope = (
            (purpose == AssessmentPurpose.PTM_LINKED.value and scope == "EXAM_RESULTS_PTM")
            or (purpose == AssessmentPurpose.WEEKLY_TEST.value and scope == "EXAM_RESULTS_WEEKLY")
        )
        if not allowed_scope:
            checks_evaluated["consent_scope"] = f"MISMATCH_{scope}_FOR_{purpose}"
            return PolicyDecision(
                allowed=False,
                reason_code=PolicyReasonCode.CONSENT_PURPOSE_MISMATCH,
                target_state="BLOCKED_CONSENT",
                idempotency_key=idempotency_key,
                checks=checks_evaluated,
                evaluated_at_utc=now,
                recipient_phone_masked=masked_phone,
            )

    # Check 6: Sender Identity and Account Prerequisites (ADR-0019)
    if sender is not None:
        if sender.status != "READY":
            checks_evaluated["sender_status"] = sender.status
            return PolicyDecision(
                allowed=False,
                reason_code=PolicyReasonCode.SENDER_NOT_READY,
                target_state="BLOCKED_POLICY",
                idempotency_key=idempotency_key,
                checks=checks_evaluated,
                evaluated_at_utc=now,
                recipient_phone_masked=masked_phone,
            )

        if not sender.has_valid_credentials:
            checks_evaluated["credentials"] = "MISSING"
            return PolicyDecision(
                allowed=False,
                reason_code=PolicyReasonCode.CREDENTIALS_MISSING,
                target_state="BLOCKED_POLICY",
                idempotency_key=idempotency_key,
                checks=checks_evaluated,
                evaluated_at_utc=now,
                recipient_phone_masked=masked_phone,
            )

        if not sender.billing_active:
            checks_evaluated["billing"] = "INACTIVE"
            return PolicyDecision(
                allowed=False,
                reason_code=PolicyReasonCode.BILLING_INACTIVE,
                target_state="BLOCKED_POLICY",
                idempotency_key=idempotency_key,
                checks=checks_evaluated,
                evaluated_at_utc=now,
                recipient_phone_masked=masked_phone,
            )

        if sender.messages_sent_today >= sender.daily_quota:
            checks_evaluated["daily_quota"] = f"{sender.messages_sent_today}/{sender.daily_quota}"
            return PolicyDecision(
                allowed=False,
                reason_code=PolicyReasonCode.DAILY_QUOTA_EXCEEDED,
                target_state="BLOCKED_POLICY",
                idempotency_key=idempotency_key,
                checks=checks_evaluated,
                evaluated_at_utc=now,
                recipient_phone_masked=masked_phone,
            )

    # Check 7: Service Window & Free-form vs Template
    if is_freeform:
        window_active = service_window is not None and service_window.is_active
        if not window_active:
            checks_evaluated["service_window"] = "CLOSED_FOR_FREEFORM"
            return PolicyDecision(
                allowed=False,
                reason_code=PolicyReasonCode.SERVICE_WINDOW_CLOSED_FOR_FREEFORM,
                target_state="BLOCKED_POLICY",
                idempotency_key=idempotency_key,
                checks=checks_evaluated,
                evaluated_at_utc=now,
                recipient_phone_masked=masked_phone,
            )
    else:
        # Template message requirement
        if not template_name:
            checks_evaluated["template"] = "MISSING"
            return PolicyDecision(
                allowed=False,
                reason_code=PolicyReasonCode.TEMPLATE_NOT_APPROVED,
                target_state="BLOCKED_POLICY",
                idempotency_key=idempotency_key,
                checks=checks_evaluated,
                evaluated_at_utc=now,
                recipient_phone_masked=masked_phone,
            )

        if sender is not None and sender.approved_templates and template_name not in sender.approved_templates:
            checks_evaluated["template"] = f"NOT_APPROVED_{template_name}"
            return PolicyDecision(
                allowed=False,
                reason_code=PolicyReasonCode.TEMPLATE_NOT_APPROVED,
                target_state="BLOCKED_POLICY",
                idempotency_key=idempotency_key,
                checks=checks_evaluated,
                evaluated_at_utc=now,
                recipient_phone_masked=masked_phone,
            )

        if not template_content_valid:
            checks_evaluated["template_content"] = "INVALID_CONSTRAINTS"
            return PolicyDecision(
                allowed=False,
                reason_code=PolicyReasonCode.TEMPLATE_CONTENT_MISMATCH,
                target_state="BLOCKED_POLICY",
                idempotency_key=idempotency_key,
                checks=checks_evaluated,
                evaluated_at_utc=now,
                recipient_phone_masked=masked_phone,
            )

    # All policy gates passed successfully
    checks_evaluated["all_passed"] = True
    return PolicyDecision(
        allowed=True,
        reason_code=PolicyReasonCode.ALLOWED,
        target_state="SCHEDULED",
        idempotency_key=idempotency_key,
        checks=checks_evaluated,
        evaluated_at_utc=now,
        recipient_phone_masked=masked_phone,
    )
