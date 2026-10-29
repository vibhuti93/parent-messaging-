"""
Messaging Provider Interface and Common Data Contracts (`src/omr_dispatch/messaging/provider.py`).

Compliant with:
- Part B Stage S9 Task 1 & ADR-0019 (Per-school sender identity and credential segregation).
- Global Invariant 10: Never log or persist full phone numbers or secrets; mask them.
- Global Invariant 15: Every call requires explicit tenant context (org_id).
- Global Invariant 16: No global credentials or shared phone-number IDs; resolve from SenderIdentity.
- ADR-0002: Zero float() calls.
- ADR-0008: Typed exception hierarchy.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from omr_dispatch.messaging.retry import ClassifiedError
from omr_dispatch.models import OMRDispatchError


class ProviderError(OMRDispatchError):
    """Base exception for messaging provider interactions."""

    def __init__(self, message: str, classification: ClassifiedError | None = None) -> None:
        super().__init__(message)
        self.classification = classification


class RetryableProviderError(ProviderError):
    """Raised for ephemeral failures classified as RETRY_SAFE (e.g. 429 rate limit)."""


class OutcomeUnknownError(ProviderError):
    """Raised when request acceptance is uncertain (e.g. 5xx, timeouts). Never auto-retry."""


class OperatorActionRequiredError(ProviderError):
    """Raised when authentication, billing, or account restrictions require human intervention."""


class PermanentProviderError(ProviderError):
    """Raised when a request is unrecoverable (e.g. invalid payload, non-WhatsApp recipient)."""


class TenantCredentialsMissingError(ProviderError):
    """Raised when an org context lacks configured credentials or SenderIdentity (Invariant 16)."""


class ServiceWindowClosedError(ProviderError):
    """Raised when attempting freeform or audio transmission outside the 24h customer window."""


class SenderStatus(StrEnum):
    """Operational lifecycle status of a per-school sender identity (ADR-0019)."""

    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONNECTED = "CONNECTED"
    TEMPLATES_PENDING = "TEMPLATES_PENDING"
    READY = "READY"
    SUSPENDED = "SUSPENDED"
    FLAGGED = "FLAGGED"


class QualityRating(StrEnum):
    """Meta WhatsApp Business phone number quality rating (R-04)."""

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    UNKNOWN = "UNKNOWN"


class TemplateRegistrationStatus(StrEnum):
    """Registration status of a message template in Meta Business Manager (R-06)."""

    APPROVED = "APPROVED"
    IN_REVIEW = "IN_REVIEW"
    PAUSED = "PAUSED"
    REJECTED = "REJECTED"


class SenderIdentity(BaseModel):
    """First-class sender identity scoped to a specific school org_id (ADR-0019)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    sender_id: str
    org_id: str
    waba_id: str
    phone_number_id: str
    display_phone_number: str
    verified_display_name: str
    status: SenderStatus = SenderStatus.NOT_CONFIGURED
    quality_rating: QualityRating = QualityRating.UNKNOWN
    daily_message_limit: int = 250
    credential_secret_ref: str
    app_secret_ref: str
    template_registry: dict[str, TemplateRegistrationStatus] = Field(default_factory=dict)
    is_primary: bool = True


class TemplateParameter(BaseModel):
    """Individual template variable parameter (R-09)."""

    model_config = ConfigDict(extra="forbid")

    type: str = "text"  # text, image, document
    text: str | None = None
    media_id: str | None = None


class TemplateComponent(BaseModel):
    """Component block within a template send request (header, body, button)."""

    model_config = ConfigDict(extra="forbid")

    type: str  # header, body, button
    parameters: list[TemplateParameter] = Field(default_factory=list)


class TemplateSendRequest(BaseModel):
    """Request payload for sending an approved WhatsApp Message Template."""

    model_config = ConfigDict(extra="forbid")

    recipient_phone_e164: str
    template_name: str
    language_code: str = "hi"
    components: list[TemplateComponent] = Field(default_factory=list)


class FreeformSendRequest(BaseModel):
    """Request payload for sending in-window free-form text."""

    model_config = ConfigDict(extra="forbid")

    recipient_phone_e164: str
    body_text: str


class MediaSendRequest(BaseModel):
    """Request payload for sending standalone media messages."""

    model_config = ConfigDict(extra="forbid")

    recipient_phone_e164: str
    media_type: str  # image, audio, document
    media_id: str
    caption: str | None = None
    is_voice: bool = False


class ProviderSendResponse(BaseModel):
    """Structured response from a successful provider send operation."""

    model_config = ConfigDict(extra="forbid")

    wamid: str
    recipient_phone_e164: str
    status: str = "sent"
    raw_response_json: str | None = None


class ProviderHealthStatus(BaseModel):
    """Status check report for a sender identity."""

    model_config = ConfigDict(extra="forbid")

    is_healthy: bool
    phone_number_id: str
    quality_rating: QualityRating
    details: dict[str, Any] = Field(default_factory=dict)


class MessagingProvider(Protocol):
    """
    Protocol defining the authoritative messaging provider interface.
    Every call requires an explicit org_id and SenderIdentity.
    """

    def send_template(
        self, org_id: str, sender: SenderIdentity, request: TemplateSendRequest
    ) -> ProviderSendResponse:
        """Send an approved WhatsApp template message."""
        ...

    def send_freeform_text(
        self, org_id: str, sender: SenderIdentity, request: FreeformSendRequest
    ) -> ProviderSendResponse:
        """Send freeform text strictly inside an active 24h customer service window."""
        ...

    def send_media(
        self, org_id: str, sender: SenderIdentity, request: MediaSendRequest
    ) -> ProviderSendResponse:
        """Send standalone media (scorecard image, audio voice note, PTM PDF)."""
        ...

    def upload_media(
        self,
        org_id: str,
        sender: SenderIdentity,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
    ) -> str:
        """Upload media to provider storage; returns durable media_id."""
        ...

    def check_health(self, org_id: str, sender: SenderIdentity) -> ProviderHealthStatus:
        """Query provider health and quality status for the sender identity."""
        ...
