"""
Contact Hygiene, Phone Normalization, and Admission Quarantine Engine (`src/omr_dispatch/contacts.py`).

Compliant with:
- Global Invariant 9: Never infer consent, guardian identity, or sibling status from surname/spreadsheet.
- Global Invariant 10: Never log full phone numbers; mask them.
- Global Invariant 13: Fail closed on uncertain input.
- Global Invariant 15: Explicit tenant context (org_id).
- ADR-0008: Typed reason codes and structured rejection tracking.
- ADR-0010: Unicode NFC normalization.
- ADR-0016: Assessment purpose and consent scope alignment.
"""

from __future__ import annotations

import re
from collections import Counter
from enum import StrEnum
from typing import Any

from omr_dispatch.models import (
    AssessmentPurpose,
    ContactEvaluation,
    ContactQuarantineFlag,
    StudentAdmissionRow,
    StudentRoster,
)

# Strict Indian mobile national number format: exactly 10 digits starting with 6, 7, 8, or 9
INDIAN_NATIONAL_MOBILE_REGEX = re.compile(r"^[6-9]\d{9}$")

# Characters stripped during phone normalization
ALLOWED_STRIP_CHARS = set(" -+() \t\r\n")


class PhoneNormalizationReason(StrEnum):
    """Reason codes for phone normalization and format validation (S3 Task 1)."""

    VALID = "VALID"
    EMPTY = "EMPTY"
    MALFORMED_CHARACTERS = "MALFORMED_CHARACTERS"
    INVALID_LENGTH = "INVALID_LENGTH"
    INVALID_STARTING_DIGIT = "INVALID_STARTING_DIGIT"


def normalize_indian_mobile_with_reason(
    raw: str | None,
) -> tuple[str | None, PhoneNormalizationReason]:
    """
    Normalize and validate an Indian mobile phone number, recording the reason code.

    Rules (S3 Task 1):
      - Strip spaces, hyphens, parentheses, and '+'.
      - Reject alphabetic and unexpected symbols with MALFORMED_CHARACTERS.
      - 12 digits starting with '91' -> drop country code prefix '91'.
      - 11 digits starting with '0' -> drop trunk prefix '0'.
      - Valid iff exactly 10 digits matching ^[6-9]\\d{9}$.
      - Format check only; does not guarantee active WhatsApp capability.
    """
    if raw is None:
        return None, PhoneNormalizationReason.EMPTY

    # Remove standard punctuation/whitespace
    cleaned_chars = [c for c in raw if c not in ALLOWED_STRIP_CHARS]
    if not cleaned_chars:
        return None, PhoneNormalizationReason.EMPTY

    # Check for alphabetic or disallowed characters
    if not all(c.isascii() and c.isdigit() for c in cleaned_chars):
        return None, PhoneNormalizationReason.MALFORMED_CHARACTERS

    digits = "".join(cleaned_chars)

    # Prefix stripping rules
    if len(digits) == 12 and digits.startswith("91"):
        national = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        national = digits[1:]
    else:
        national = digits

    if len(national) != 10:
        return None, PhoneNormalizationReason.INVALID_LENGTH

    if not INDIAN_NATIONAL_MOBILE_REGEX.match(national):
        return None, PhoneNormalizationReason.INVALID_STARTING_DIGIT

    return national, PhoneNormalizationReason.VALID


def normalize_indian_mobile(raw: str | None) -> str | None:
    """
    Normalize and validate Indian mobile phone number (S3 Task 1).
    Returns 10-digit national number string (e.g. '9811122201') or None if invalid.
    """
    normalized, _ = normalize_indian_mobile_with_reason(raw)
    return normalized


def format_e164(national_number: str | None) -> str | None:
    """Format a 10-digit Indian national number into international E.164 string (+91XXXXXXXXXX)."""
    if not national_number or len(national_number) != 10:
        return None
    return f"+91{national_number}"


def mask_phone(phone: str | None) -> str:
    """
    Mask phone number for safe logging and diagnostics display (Invariant 10).
    Preserves prefix and trailing digits, masking middle digits.
    Example: '+919811122201' -> '+91 98*** **01', '9811122201' -> '98*** **01'.
    """
    if not phone:
        return "[EMPTY]"
    norm = normalize_indian_mobile(phone)
    if norm is None:
        # Fallback masking for malformed input
        s = str(phone).strip()
        if len(s) <= 4:
            return "***"
        return f"{s[:2]}***{s[-2:]}"

    return f"{norm[:2]}*** **{norm[-2:]}"


def validate_admission_batch(
    rows: list[StudentAdmissionRow] | StudentRoster | list[dict[str, Any]],
    assessment_purpose: AssessmentPurpose | str | None = None,
    org_id: str | None = None,
) -> list[ContactEvaluation]:
    """
    Validate contact hygiene and safety quarantine across an admission cohort (S3 Task 2).

    Rules:
      1. Detect invalid guardian phone numbers -> INVALID_PHONE_NUMBER.
      2. Detect invalid student phone numbers (when provided) -> INVALID_STUDENT_PHONE_NUMBER.
      3. Detect identical normalized student and guardian numbers -> INTERCEPTION_RISK_SAME_NUMBER.
      4. Detect repeated guardian phone numbers across different students without verified sibling status
         -> DUPLICATE_PARENT_UNVERIFIED on all colliding records.
      5. Sibling exception: Verified siblings (verified_sibling=True) sharing a guardian number are not flagged.
      6. Quarantine flags are deduplicated and deterministically sorted (alphabetical).
      7. Quarantine gate: If any quarantine flag is present, is_quarantined=True and dispatch is blocked.
      8. Dispatch eligibility: Requires valid + verified guardian contact, non-revoked OPT_IN for the
         purpose, and zero unresolved quarantine flags.
      9. Fail-closed: Never bypass quarantine to reach an expected send count.
    """
    # Normalize input into list of StudentAdmissionRow
    admissions: list[StudentAdmissionRow]
    active_org_id = org_id or "DEFAULT_INSTITUTION"

    if isinstance(rows, StudentRoster):
        admissions = rows.students
        if rows.org_id:
            active_org_id = rows.org_id
    elif isinstance(rows, list):
        parsed: list[StudentAdmissionRow] = []
        for item in rows:
            if isinstance(item, StudentAdmissionRow):
                parsed.append(item)
            elif isinstance(item, dict):
                d = dict(item)
                if "org_id" not in d:
                    d["org_id"] = active_org_id
                parsed.append(StudentAdmissionRow.model_validate(d))
            else:
                raise TypeError(f"Unsupported admission item type: {type(item).__name__}")
        admissions = parsed
    else:
        raise TypeError(f"Unsupported admission rows type: {type(rows).__name__}")

    # Phase 1: Pre-normalize all phone numbers across the batch
    norm_guard_map: dict[str, tuple[str | None, PhoneNormalizationReason]] = {}
    norm_stu_map: dict[str, tuple[str | None, PhoneNormalizationReason]] = {}

    for s in admissions:
        sid = s.student_id
        norm_guard_map[sid] = normalize_indian_mobile_with_reason(s.raw_guardian_phone)
        norm_stu_map[sid] = normalize_indian_mobile_with_reason(s.raw_student_phone)

    # Phase 2: Frequency analysis of guardian numbers to detect unverified duplicates
    valid_guard_numbers = [
        norm_g for norm_g, reason in norm_guard_map.values() if norm_g is not None
    ]
    guard_counts = Counter(valid_guard_numbers)

    # Phase 3: Evaluate safety flags and eligibility per student
    results: list[ContactEvaluation] = []

    for s in admissions:
        sid = s.student_id
        norm_g, _ = norm_guard_map[sid]
        norm_s, _ = norm_stu_map[sid]

        flags: list[str] = []

        # 1. Guardian phone format check
        if norm_g is None:
            flags.append(ContactQuarantineFlag.INVALID_PHONE_NUMBER.value)

        # 2. Student phone format check (if student phone was provided)
        has_raw_student_phone = bool(
            s.raw_student_phone and str(s.raw_student_phone).strip()
        )
        if has_raw_student_phone and norm_s is None:
            flags.append(ContactQuarantineFlag.INVALID_STUDENT_PHONE_NUMBER.value)

        # 3. Interception risk: identical normalized student and guardian numbers
        if norm_g is not None and norm_s is not None and norm_g == norm_s:
            flags.append(ContactQuarantineFlag.INTERCEPTION_RISK_SAME_NUMBER.value)

        # 4. Duplicate guardian phone collision without verified sibling status
        if norm_g is not None and guard_counts[norm_g] > 1 and not s.verified_sibling:
            flags.append(ContactQuarantineFlag.DUPLICATE_PARENT_UNVERIFIED.value)

        # Deduplicate and sort flags deterministically
        quarantine_flags = sorted(set(flags))
        is_quarantined = len(quarantine_flags) > 0

        # Phase 4: Dispatch eligibility and exclusion reason determination
        dispatch_eligible = True
        exclusion_reason: str | None = None

        if is_quarantined:
            dispatch_eligible = False
            # Ratified exclusion precedence (2026-10-23):
            # 1. INVALID_PHONE_NUMBER
            # 2. INVALID_STUDENT_PHONE_NUMBER
            # 3. INTERCEPTION_RISK_SAME_NUMBER
            # 4. DUPLICATE_PARENT_UNVERIFIED
            precedence = [
                ContactQuarantineFlag.INVALID_PHONE_NUMBER.value,
                ContactQuarantineFlag.INVALID_STUDENT_PHONE_NUMBER.value,
                ContactQuarantineFlag.INTERCEPTION_RISK_SAME_NUMBER.value,
                ContactQuarantineFlag.DUPLICATE_PARENT_UNVERIFIED.value,
            ]
            for candidate in precedence:
                if candidate in quarantine_flags:
                    exclusion_reason = candidate
                    break
            if exclusion_reason is None:
                exclusion_reason = quarantine_flags[0]

        elif s.consent_status != "OPT_IN":
            dispatch_eligible = False
            exclusion_reason = f"CONSENT_{s.consent_status}"

        elif s.guardian_verification != "VERIFIED":
            dispatch_eligible = False
            exclusion_reason = f"GUARDIAN_{s.guardian_verification}"

        elif assessment_purpose is not None and s.consent_scope:
            # Assessment purpose and consent scope alignment (ADR-0016)
            purp_str = (
                assessment_purpose.value
                if isinstance(assessment_purpose, AssessmentPurpose)
                else str(assessment_purpose)
            )
            scope = s.consent_scope
            if scope != "EXAM_RESULTS_ALL":
                allowed = (
                    (purp_str == AssessmentPurpose.PTM_LINKED.value and scope == "EXAM_RESULTS_PTM")
                    or (purp_str == AssessmentPurpose.WEEKLY_TEST.value and scope == "EXAM_RESULTS_WEEKLY")
                )

                if not allowed:
                    dispatch_eligible = False
                    exclusion_reason = "BLOCKED_CONSENT"

        manual_status = "PENDING_OPERATOR_REVIEW" if is_quarantined else "NOT_REQUIRED"

        results.append(
            ContactEvaluation(
                student_id=sid,
                is_quarantined=is_quarantined,
                quarantine_flags=quarantine_flags,
                dispatch_eligible=dispatch_eligible,
                exclusion_reason=exclusion_reason,
                normalized_guardian_phone=norm_g,
                normalized_student_phone=norm_s,
                manual_resolution_status=manual_status,
                org_id=s.org_id or active_org_id,
                schema_version=s.schema_version,
            )
        )

    return results
