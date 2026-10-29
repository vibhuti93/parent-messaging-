"""
Messaging Policy Engine, Tenant Repositories, and Audit Subpackage (`src/omr_dispatch/messaging`).
"""

from __future__ import annotations

from omr_dispatch.messaging.audit import (
    AuditActionType,
    AuditEvent,
    AuditStore,
    sanitize_audit_details,
)
from omr_dispatch.messaging.policy import (
    MessageIntent,
    PolicyDecision,
    PolicyReasonCode,
    SenderPrerequisites,
    ServiceWindowState,
    TenantContextMissingError,
    compute_idempotency_key,
    evaluate_dispatch_policy,
)
from omr_dispatch.messaging.store import (
    VALID_STATE_TRANSITIONS,
    AuditLogRecord,
    DispatchEventRecord,
    DispatchNotFoundError,
    DispatchRecord,
    DispatchRepository,
    DispatchState,
    DuplicateWamidEventError,
    IdempotencyCollisionError,
    IllegalStateTransitionError,
    PostgresDispatchRepository,
    SQLiteDispatchRepository,
    TenantNotFoundError,
    TenantRecord,
    TenantSuspendedError,
    create_repository,
)

__all__ = [
    # Policy Engine
    "PolicyReasonCode",
    "ServiceWindowState",
    "SenderPrerequisites",
    "MessageIntent",
    "PolicyDecision",
    "TenantContextMissingError",
    "compute_idempotency_key",
    "evaluate_dispatch_policy",
    # Durable Storage
    "DispatchState",
    "VALID_STATE_TRANSITIONS",
    "DispatchRecord",
    "DispatchEventRecord",
    "TenantRecord",
    "AuditLogRecord",
    "IdempotencyCollisionError",
    "IllegalStateTransitionError",
    "DuplicateWamidEventError",
    "DispatchNotFoundError",
    "TenantNotFoundError",
    "TenantSuspendedError",
    "DispatchRepository",
    "SQLiteDispatchRepository",
    "PostgresDispatchRepository",
    "create_repository",
    # Audit Logging
    "AuditActionType",
    "AuditEvent",
    "AuditStore",
    "sanitize_audit_details",
]
