"""
Messaging Policy Engine, Tenant Repositories, Providers, and Webhooks Subpackage (`src/omr_dispatch/messaging`).
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
from omr_dispatch.messaging.provider import (
    FreeformSendRequest,
    MediaSendRequest,
    MessagingProvider,
    OperatorActionRequiredError,
    OutcomeUnknownError,
    PermanentProviderError,
    ProviderError,
    ProviderHealthStatus,
    ProviderSendResponse,
    QualityRating,
    RetryableProviderError,
    SenderIdentity,
    SenderStatus,
    ServiceWindowClosedError,
    TemplateComponent,
    TemplateParameter,
    TemplateRegistrationStatus,
    TemplateSendRequest,
    TenantCredentialsMissingError,
)
from omr_dispatch.messaging.retry import (
    ClassifiedError,
    ErrorClass,
    classify_provider_error,
    compute_backoff_delay_ms,
    should_auto_retry,
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
from omr_dispatch.messaging.webhooks import (
    WebhookDemultiplexer,
    extract_phone_number_id,
    verify_webhook_signature,
)
from omr_dispatch.messaging.whatsapp_cloud import (
    DEFAULT_GRAPH_BASE_URL,
    WhatsAppCloudProvider,
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
    # Provider Contracts & Error Hierarchy
    "MessagingProvider",
    "SenderIdentity",
    "SenderStatus",
    "QualityRating",
    "TemplateRegistrationStatus",
    "TemplateParameter",
    "TemplateComponent",
    "TemplateSendRequest",
    "FreeformSendRequest",
    "MediaSendRequest",
    "ProviderSendResponse",
    "ProviderHealthStatus",
    "ProviderError",
    "RetryableProviderError",
    "OutcomeUnknownError",
    "OperatorActionRequiredError",
    "PermanentProviderError",
    "TenantCredentialsMissingError",
    "ServiceWindowClosedError",
    # Retry & Error Classification
    "ErrorClass",
    "ClassifiedError",
    "classify_provider_error",
    "compute_backoff_delay_ms",
    "should_auto_retry",
    # WhatsApp Cloud Implementation
    "DEFAULT_GRAPH_BASE_URL",
    "WhatsAppCloudProvider",
    # Webhooks & Demultiplexing
    "verify_webhook_signature",
    "extract_phone_number_id",
    "WebhookDemultiplexer",
]
