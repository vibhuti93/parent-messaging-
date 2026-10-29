"""
Audit Logging and Compliance Engine (`src/omr_dispatch/messaging/audit.py`).

Compliant with:
- Part B Stage S8 Task 1: Policy decision before every send, recorded in the audit log.
- Global Invariant 10: Never log full phone numbers, tokens, names, scores, QR tokens, or audio payloads; mask them.
- Global Invariant 15: Explicit tenant context (org_id) on all operations. Fails closed if missing.
- Global Invariant 17: Child names (child_display_name) and class/section labels are never logged.
- ADR-0005: Timezone-aware UTC datetimes.
- ADR-0008: Structured JSON logging and typed audit event records.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omr_dispatch.contacts import mask_phone
from omr_dispatch.messaging.policy import TenantContextMissingError
from omr_dispatch.messaging.store import AuditLogRecord, DispatchRepository


class AuditActionType(StrEnum):
    """Authoritative audit action categories."""

    POLICY_EVALUATION = "POLICY_EVALUATION"
    DISPATCH_SCHEDULED = "DISPATCH_SCHEDULED"
    DISPATCH_SUBMITTED = "DISPATCH_SUBMITTED"
    DISPATCH_DELIVERED = "DISPATCH_DELIVERED"
    DISPATCH_BLOCKED = "DISPATCH_BLOCKED"
    DISPATCH_FAILED = "DISPATCH_FAILED"
    KILL_SWITCH_ENGAGED = "KILL_SWITCH_ENGAGED"
    KILL_SWITCH_DISENGAGED = "KILL_SWITCH_DISENGAGED"
    TENANT_ONBOARDED = "TENANT_ONBOARDED"
    SECURITY_ALERT = "SECURITY_ALERT"


# Sensitive key patterns forbidden or requiring masking (Invariants 10 & 17)
PHONE_KEY_PATTERN = re.compile(r"(phone|mobile|recipient|contact)", re.IGNORECASE)
CHILD_NAME_KEY_PATTERN = re.compile(r"(child_display_name|child_name|student_name|name)", re.IGNORECASE)
CLASS_SECTION_KEY_PATTERN = re.compile(r"(class_section|class_name|section)", re.IGNORECASE)
SECRET_KEY_PATTERN = re.compile(r"(token|secret|password|key|payload)", re.IGNORECASE)
SCORE_KEY_PATTERN = re.compile(r"(score|marks|bleed|gross|net)", re.IGNORECASE)


def sanitize_audit_details(details: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize audit details dict before logging or persistence.

    Enforces:
      - Invariant 10: Phone numbers masked via mask_phone; tokens and payloads redacted.
      - Invariant 17: Child display names and class/section labels stripped or redacted.
    """
    sanitized: dict[str, Any] = {}

    for k, v in details.items():
        # Check Invariant 17: Child display names and class labels never logged
        if CHILD_NAME_KEY_PATTERN.search(k):
            sanitized[k] = "[REDACTED_NAME]"
            continue

        if CLASS_SECTION_KEY_PATTERN.search(k):
            sanitized[k] = "[REDACTED_CLASS]"
            continue

        # Check Invariant 10: Secrets / Tokens
        if SECRET_KEY_PATTERN.search(k):
            sanitized[k] = "[REDACTED_SECRET]"
            continue

        # Check Invariant 10: Scores
        if SCORE_KEY_PATTERN.search(k):
            sanitized[k] = "[REDACTED_SCORE]"
            continue

        # Check Invariant 10: Phone numbers
        if PHONE_KEY_PATTERN.search(k):
            if isinstance(v, str):
                sanitized[k] = mask_phone(v)
            else:
                sanitized[k] = "[MASKED_PHONE]"
            continue

        # Recursive sanitization for nested dicts / lists
        if isinstance(v, dict):
            sanitized[k] = sanitize_audit_details(v)
        elif isinstance(v, list):
            sanitized_list: list[Any] = []
            for item in v:
                if isinstance(item, dict):
                    sanitized_list.append(sanitize_audit_details(item))
                elif isinstance(item, str) and (re.search(r"[6-9]\d{9}", item) or item.startswith("+91")):
                    sanitized_list.append(mask_phone(item))
                else:
                    sanitized_list.append(item)
            sanitized[k] = sanitized_list
        else:
            sanitized[k] = v

    return sanitized


class AuditEvent(BaseModel):
    """Domain model for a high-level audit event."""

    model_config = ConfigDict(extra="forbid")

    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str
    actor_id: str = "engine"
    actor_type: str = "SYSTEM"
    action_type: AuditActionType | str
    target_id: str | None = None
    reason_code: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    occurred_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_version: int = 1


class AuditStore:
    """Audit logging repository wrapper guaranteeing tenant isolation and data sanitization."""

    def __init__(self, repository: DispatchRepository) -> None:
        self.repo = repository

    def record_event(self, org_id: str, event: AuditEvent) -> AuditEvent:
        """Record an audit event, sanitizing all details prior to persistence."""
        if not org_id or not str(org_id).strip():
            raise TenantContextMissingError("Explicit org context (org_id) is required for audit operations.")

        if event.org_id != org_id:
            raise TenantContextMissingError("Audit event org_id does not match repository context.")

        sanitized = sanitize_audit_details(event.details)

        record = AuditLogRecord(
            audit_id=event.audit_id,
            org_id=org_id,
            actor_id=event.actor_id,
            actor_type=event.actor_type,
            action_type=(
                event.action_type.value
                if isinstance(event.action_type, AuditActionType)
                else str(event.action_type)
            ),
            target_id=event.target_id,
            reason_code=event.reason_code,
            details_json=json.dumps(sanitized, ensure_ascii=False),
            occurred_at_utc=event.occurred_at_utc,
            schema_version=event.schema_version,
        )
        self.repo.record_audit_log(org_id=org_id, record=record)
        return event

    def list_events(self, org_id: str, limit: int = 100) -> list[AuditEvent]:
        """Query audit events within explicit tenant scope."""
        if not org_id or not str(org_id).strip():
            raise TenantContextMissingError("Explicit org context (org_id) is required for audit operations.")

        records = self.repo.list_audit_logs(org_id=org_id, limit=limit)
        events: list[AuditEvent] = []
        for r in records:
            details_dict = json.loads(r.details_json) if r.details_json else {}
            events.append(
                AuditEvent(
                    audit_id=r.audit_id,
                    org_id=r.org_id,
                    actor_id=r.actor_id,
                    actor_type=r.actor_type,
                    action_type=r.action_type,
                    target_id=r.target_id,
                    reason_code=r.reason_code,
                    details=details_dict,
                    occurred_at_utc=r.occurred_at_utc,
                    schema_version=r.schema_version,
                )
            )
        return events
