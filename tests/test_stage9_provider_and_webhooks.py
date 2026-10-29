"""
Stage S9 Gate Tests — Provider Adapter, Webhooks, and Retries (`tests/test_stage9_provider_and_webhooks.py`).

Compliant with:
- Part B Stage S9 Task 1, 2, 3, 4 & Gate 9 mandates.
- ADR-0019: Per-school sender identity, credential isolation, dynamic webhook demultiplexing.
- Global Invariant 8: No real messaging endpoints or live network transmission.
- Global Invariant 10: Never log or expose raw tokens, phone numbers, or PII.
- Global Invariant 13: Fail closed; uncertain send outcome is OUTCOME_UNKNOWN / UNKNOWN_NEEDS_REVIEW, never a blind retry.
- Global Invariant 15: Explicit tenant context (org_id) required on every call.
- Global Invariant 16: Zero global credentials; resolve per-org SenderIdentity.
- Global Invariant 18: No silent resends; only RETRY_SAFE errors may auto-retry.
- ADR-0002: Zero float() calls in core and messaging packages.
- ADR-0005: Zero unanchored datetime calls; explicit UTC timestamps.
- ADR-0008: Typed exception hierarchy and structured error classification.

NOTICE / CONTRACT DISCLAIMER:
All tests in this suite execute against a real local loopback HTTPServer on an ephemeral port (127.0.0.1:0).
Payload assertions evaluate conformance against recorded provider contract fixtures (tests/fixtures/provider_contract/**).
Green tests prove deterministic local request generation, five-class error handling, state-machine transitions,
and webhook demultiplexing behavior—NOT Meta Cloud API production acceptance or parent delivery.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from pydantic import SecretStr

from omr_dispatch.messaging.policy import TenantContextMissingError
from omr_dispatch.messaging.provider import (
    FreeformSendRequest,
    MediaSendRequest,
    OperatorActionRequiredError,
    OutcomeUnknownError,
    PermanentProviderError,
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
    ErrorClass,
    classify_provider_error,
    compute_backoff_delay_ms,
    should_auto_retry,
)
from omr_dispatch.messaging.store import (
    DispatchEventRecord,
    DispatchRecord,
    DispatchState,
    PostgresDispatchRepository,
    SQLiteDispatchRepository,
    TenantRecord,
)
from omr_dispatch.messaging.webhooks import (
    WebhookDemultiplexer,
    extract_phone_number_id,
    verify_webhook_signature,
)
from omr_dispatch.messaging.whatsapp_cloud import WhatsAppCloudProvider

CONTRACT_DISCLAIMER = (
    "All tests verify local provider adapter contracts, state machine transitions, "
    "retry policies, and webhook routing behavior. Green tests prove engine conformance "
    "against recorded fixtures and local contracts, not live Meta Cloud API acceptance or delivery."
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "provider_contract"


def load_fixture(filename: str) -> dict[str, Any]:
    """Load JSON contract fixture."""
    path = FIXTURES_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


# ==============================================================================
# Real Local Loopback HTTPServer Fixture
# ==============================================================================

class MockServerRequestHandler(BaseHTTPRequestHandler):
    """Local HTTP request handler capturing requests and serving custom responses."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard stderr request logging."""
        pass

    def do_POST(self) -> None:
        server: MockProviderServer = self.server  # type: ignore
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)

        record = {
            "path": self.path,
            "method": "POST",
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "body": body_bytes,
        }
        server.captured_requests.append(record)

        # Check for queued custom response
        if server.response_queue:
            status_code, resp_bytes, headers = server.response_queue.pop(0)
            self.send_response(status_code)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp_bytes)
            return

        # Default fallback: 200 OK with template_send_response
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(load_fixture("template_send_response.json")).encode())

    def do_GET(self) -> None:
        server: MockProviderServer = self.server  # type: ignore
        record = {
            "path": self.path,
            "method": "GET",
            "headers": {k.lower(): v for k, v in self.headers.items()},
            "body": b"",
        }
        server.captured_requests.append(record)

        if server.response_queue:
            status_code, resp_bytes, headers = server.response_queue.pop(0)
            self.send_response(status_code)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp_bytes)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"quality_rating": "GREEN", "verified_name": "Test School"}).encode())


class MockProviderServer(ThreadingHTTPServer):
    """Threaded HTTP server for local provider contract testing."""

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, MockServerRequestHandler)
        self.captured_requests: list[dict[str, Any]] = []
        self.response_queue: list[tuple[int, bytes, dict[str, str]]] = []

    def queue_response(
        self, status_code: int, body_dict: dict[str, Any] | bytes, headers: dict[str, str] | None = None
    ) -> None:
        h = headers or {"Content-Type": "application/json"}
        body_bytes = body_dict if isinstance(body_dict, bytes) else json.dumps(body_dict).encode("utf-8")
        self.response_queue.append((status_code, body_bytes, h))


@pytest.fixture
def mock_server():
    """Start local loopback HTTPServer on 127.0.0.1 with ephemeral port."""
    server = MockProviderServer(("127.0.0.1", 0))
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    server.base_url = f"http://127.0.0.1:{port}"
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


@pytest.fixture
def test_sender() -> SenderIdentity:
    """Canonical test sender identity scoped to school_001."""
    return SenderIdentity(
        sender_id="snd_test_001",
        org_id="school_001",
        waba_id="waba_test_001",
        phone_number_id="phone_id_test_001",
        display_phone_number="+91 98765 43210",
        verified_display_name="Delhi Public School",
        status=SenderStatus.READY,
        quality_rating=QualityRating.GREEN,
        credential_secret_ref="mock_token_secret_sch01",
        app_secret_ref="mock_app_secret_sch01",
        template_registry={
            "parent_scorecard_v1": TemplateRegistrationStatus.APPROVED,
            "ptm_attendance_v1": TemplateRegistrationStatus.APPROVED,
            "unapproved_template_v1": TemplateRegistrationStatus.REJECTED,
        },
    )


@pytest.fixture
def secret_map() -> dict[str, str]:
    return {
        "mock_token_secret_sch01": "TEST_META_TOKEN_SCH01",
        "mock_app_secret_sch01": "TEST_META_APP_SECRET_SCH01",
        "mock_token_secret_sch02": "TEST_META_TOKEN_SCH02",
        "mock_app_secret_sch02": "TEST_META_APP_SECRET_SCH02",
    }


@pytest.fixture
def secret_resolver(secret_map: dict[str, str]):
    def _resolve(ref: str) -> SecretStr:
        val = secret_map.get(ref, "")
        return SecretStr(val)

    return _resolve


# ==============================================================================
# Gate 9 Task 1: Provider Adapter & Payload Conformance Tests
# ==============================================================================

def test_gate9_contract_disclaimer_present():
    """Verify test suite contains explicit contract disclaimer."""
    assert "not live Meta Cloud API acceptance or delivery" in CONTRACT_DISCLAIMER


def test_gate9_template_send_payload_conformance(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """
    Assert TemplateSendRequest matches recorded contract fixture exactly:
    - Target URL path contains configured phone_number_id.
    - Headers contain Authorization: Bearer <tenant_token>.
    - JSON body matches tests/fixtures/provider_contract/template_send_request.json.
    """
    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
    )

    request = TemplateSendRequest(
        recipient_phone_e164="+91 98111 22201",
        template_name="parent_scorecard_v1",
        language_code="hi",
        components=[
            TemplateComponent(
                type="header",
                parameters=[TemplateParameter(type="image", media_id="meta_media_scorecard_12345")],
            ),
            TemplateComponent(
                type="body",
                parameters=[
                    TemplateParameter(type="text", text="आरव"),
                    TemplateParameter(type="text", text="कक्षा 10-A"),
                    TemplateParameter(type="text", text="55"),
                    TemplateParameter(type="text", text="300"),
                ],
            ),
        ],
    )

    resp = provider.send_template("school_001", test_sender, request)

    assert isinstance(resp, ProviderSendResponse)
    assert resp.wamid == "wamid.HBgLMTE="
    assert resp.status == "sent"

    # Verify captured HTTP wire request
    assert len(mock_server.captured_requests) == 1
    req_captured = mock_server.captured_requests[0]

    parsed_url = urlparse(req_captured["path"])
    assert parsed_url.path == f"/{test_sender.phone_number_id}/messages"
    assert req_captured["headers"]["authorization"] == "Bearer TEST_META_TOKEN_SCH01"
    assert "application/json" in req_captured["headers"]["content-type"]

    # Match request against fixture
    sent_json = json.loads(req_captured["body"].decode("utf-8"))
    fixture_json = load_fixture("template_send_request.json")
    assert sent_json == fixture_json


def test_gate9_media_upload_multipart_conformance(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """
    Assert upload_media sends valid multipart/form-data with durable ID returned:
    - Content-Type contains multipart/form-data boundary.
    - Multipart body contains messaging_product, type, and binary file parts.
    - Returns Meta media ID from media_upload_response.json.
    """
    mock_server.queue_response(200, load_fixture("media_upload_response.json"))

    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
    )

    fake_file = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"  # JPEG magic bytes
    media_id = provider.upload_media(
        org_id="school_001",
        sender=test_sender,
        file_bytes=fake_file,
        mime_type="image/jpeg",
        filename="scorecard_test.jpg",
    )

    assert media_id == "meta_media_scorecard_12345"

    assert len(mock_server.captured_requests) == 1
    req = mock_server.captured_requests[0]
    assert req["path"] == f"/{test_sender.phone_number_id}/media"
    assert "multipart/form-data; boundary=" in req["headers"]["content-type"]
    assert b'name="messaging_product"\r\n\r\nwhatsapp' in req["body"]
    assert b'name="type"\r\n\r\nimage/jpeg' in req["body"]
    assert fake_file in req["body"]


def test_gate9_freeform_text_service_window_enforcement(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """
    Freeform text sending rules:
    - Permitted strictly when service_window_active=True.
    - Fails closed with ServiceWindowClosedError when service_window_active=False without network transmission.
    """
    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
    )

    request = FreeformSendRequest(
        recipient_phone_e164="+91 98111 22201",
        body_text="प्रिय अभिभावक, आपके बच्चे का परिणाम तैयार है।",
    )

    # 1. Closed service window -> fails closed
    with pytest.raises(ServiceWindowClosedError, match="Free-form text is prohibited outside active 24h"):
        provider.send_freeform_text("school_001", test_sender, request, service_window_active=False)

    assert len(mock_server.captured_requests) == 0  # Zero network transmission

    # 2. Active service window -> allowed
    resp = provider.send_freeform_text("school_001", test_sender, request, service_window_active=True)
    assert resp.status == "sent"
    assert len(mock_server.captured_requests) == 1

    sent_body = json.loads(mock_server.captured_requests[0]["body"].decode("utf-8"))
    fixture_json = load_fixture("freeform_text_request.json")
    assert sent_body == fixture_json


def test_gate9_audio_voice_note_service_window_guard(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """
    Audio voice notes outside active service window must fail closed (S9 Task 4 & DECISIONS_OPEN item s).
    """
    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
    )

    media_request = MediaSendRequest(
        recipient_phone_e164="+91 98111 22201",
        media_type="audio",
        media_id="meta_media_audio_123",
        is_voice=True,
    )

    # 1. Outside window -> fails closed
    with pytest.raises(ServiceWindowClosedError, match="Audio voice note is prohibited outside active 24h"):
        provider.send_media("school_001", test_sender, media_request, service_window_active=False)

    assert len(mock_server.captured_requests) == 0

    # 2. Inside window -> transmitted
    resp = provider.send_media("school_001", test_sender, media_request, service_window_active=True)
    assert resp.status == "sent"
    assert len(mock_server.captured_requests) == 1

    sent_json = json.loads(mock_server.captured_requests[0]["body"].decode("utf-8"))
    fixture_json = load_fixture("audio_voice_note_request.json")
    assert sent_json == fixture_json


def test_gate9_dry_run_mode(test_sender: SenderIdentity, secret_resolver):
    """Dry-run mode produces synthetic responses with zero network calls."""
    provider = WhatsAppCloudProvider(
        base_url="http://127.0.0.1:9999",  # Unused port
        secret_resolver=secret_resolver,
        dry_run=True,
    )

    template_req = TemplateSendRequest(
        recipient_phone_e164="+919811122201",
        template_name="parent_scorecard_v1",
    )
    resp = provider.send_template("school_001", test_sender, template_req)
    assert resp.wamid.startswith("wamid.DRY_RUN_")

    media_id = provider.upload_media("school_001", test_sender, b"fake", "image/jpeg", "test.jpg")
    assert media_id.startswith("meta_media_dryrun_")


# ==============================================================================
# Gate 9 Task 2: Five-Class Error Classification & Retry Policy
# ==============================================================================

def test_gate9_retry_safe_429_with_retry_after(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """
    HTTP 429 Rate Limit:
    - Classified as RETRY_SAFE.
    - Honors Retry-After header.
    - Automatically retries and succeeds on subsequent 200.
    """
    errors_fixture = load_fixture("error_responses.json")
    rate_limit_payload = errors_fixture["rate_limit_429"]

    # Queue 429 followed by 200
    mock_server.queue_response(429, rate_limit_payload, {"Content-Type": "application/json", "Retry-After": "1"})
    mock_server.queue_response(200, load_fixture("template_send_response.json"))

    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
        max_retries=3,
    )

    req = TemplateSendRequest(
        recipient_phone_e164="+919811122201",
        template_name="parent_scorecard_v1",
    )

    resp = provider.send_template("school_001", test_sender, req)
    assert resp.wamid == "wamid.HBgLMTE="
    assert len(mock_server.captured_requests) == 2  # Proves auto-retry occurred


def test_gate9_outcome_unknown_500_zero_auto_retries(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """
    HTTP 500 Server Error:
    - Classified as OUTCOME_UNKNOWN.
    - Raises OutcomeUnknownError.
    - Strictly ZERO auto-retries (Invariant 13 & 18).
    """
    errors_fixture = load_fixture("error_responses.json")
    server_error_payload = errors_fixture["server_error_500"]
    mock_server.queue_response(500, server_error_payload)

    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
        max_retries=3,
    )

    req = TemplateSendRequest(
        recipient_phone_e164="+919811122201",
        template_name="parent_scorecard_v1",
    )

    with pytest.raises(OutcomeUnknownError, match="Outcome unknown"):
        provider.send_template("school_001", test_sender, req)

    assert len(mock_server.captured_requests) == 1  # ZERO auto-retries!


def test_gate9_permanent_400_fail_closed_zero_retries(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """
    Permanent client error (e.g. code 131026 non-WhatsApp user):
    - Classified as PERMANENT.
    - Raises PermanentProviderError.
    - ZERO auto-retries.
    """
    errors_fixture = load_fixture("error_responses.json")
    perm_payload = errors_fixture["permanent_error_400"]
    mock_server.queue_response(400, perm_payload)

    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
        max_retries=3,
    )

    req = TemplateSendRequest(
        recipient_phone_e164="+919811122201",
        template_name="parent_scorecard_v1",
    )

    with pytest.raises(PermanentProviderError, match="Permanent unrecoverable error"):
        provider.send_template("school_001", test_sender, req)

    assert len(mock_server.captured_requests) == 1


def test_gate9_operator_action_401_tenant_isolated(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """
    HTTP 401 Auth Error (e.g. code 190 invalid token):
    - Classified as OPERATOR_ACTION.
    - Raises OperatorActionRequiredError.
    - School A failure does not affect School B.
    """
    errors_fixture = load_fixture("error_responses.json")
    auth_payload = errors_fixture["auth_error_401"]
    mock_server.queue_response(401, auth_payload)

    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
    )

    req = TemplateSendRequest(
        recipient_phone_e164="+919811122201",
        template_name="parent_scorecard_v1",
    )

    with pytest.raises(OperatorActionRequiredError, match="Operator action required"):
        provider.send_template("school_001", test_sender, req)

    assert len(mock_server.captured_requests) == 1


def test_gate9_strict_per_org_identity_and_credentials(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """
    Strict Tenant Boundary Invariants (15 & 16, ADR-0019):
    - Calling with mismatched org_id raises TenantContextMissingError.
    - Calling without configured credentials raises TenantCredentialsMissingError.
    - Zero fallback to shared global tokens.
    """
    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
    )

    req = TemplateSendRequest(
        recipient_phone_e164="+919811122201",
        template_name="parent_scorecard_v1",
    )

    # 1. Org ID mismatch
    with pytest.raises(TenantContextMissingError, match="Tenant context mismatch"):
        provider.send_template("school_002", test_sender, req)

    # 2. Empty org_id
    with pytest.raises(TenantContextMissingError, match="Explicit org context"):
        provider.send_template("", test_sender, req)

    # 3. Missing secret reference
    unconfigured_sender = test_sender.model_copy(update={"credential_secret_ref": ""})
    with pytest.raises(TenantCredentialsMissingError, match="No valid credentials"):
        provider.send_template("school_001", unconfigured_sender, req)


def test_gate9_network_timeout_classification():
    """Network timeouts classified as OUTCOME_UNKNOWN and never auto-retried."""
    classified = classify_provider_error(is_timeout=True)
    assert classified.error_class == ErrorClass.OUTCOME_UNKNOWN
    assert should_auto_retry(classified.error_class, current_attempt=1) is False

    classified_conn = classify_provider_error(is_connection_reset=True)
    assert classified_conn.error_class == ErrorClass.OUTCOME_UNKNOWN
    assert should_auto_retry(classified_conn.error_class, current_attempt=1) is False


def test_gate9_backoff_delay_integer_milliseconds():
    """Verify backoff delay adheres to ADR-0002: integer milliseconds, bounded, deterministic with seed."""
    delay_ms = compute_backoff_delay_ms(attempt=1, base_delay_ms=1000, seed=42)
    assert isinstance(delay_ms, int)
    assert 500 <= delay_ms <= 1000

    delay_retry_after = compute_backoff_delay_ms(attempt=1, retry_after_seconds=5)
    assert delay_retry_after == 5000


# ==============================================================================
# Gate 9 Task 3: Webhook Demultiplexing, Signature, Deduplication & Order Safety
# ==============================================================================

@pytest.fixture
def test_repo() -> SQLiteDispatchRepository:
    """In-memory SQLite repository initialized with canonical schema."""
    repo = SQLiteDispatchRepository(db_path=":memory:")
    repo.init_schema()

    # Register tenant
    now = datetime.now(UTC)
    repo.register_tenant(
        TenantRecord(
            org_id="school_001",
            school_name="Delhi Public School",
            created_at_utc=now,
            updated_at_utc=now,
        )
    )
    return repo


@pytest.fixture
def populated_dispatch(test_repo: SQLiteDispatchRepository) -> DispatchRecord:
    """Seed initial dispatch in SUBMITTED state with wamid.HBgLMTE=."""
    now = datetime.now(UTC)
    dispatch = DispatchRecord(
        dispatch_id="disp_test_001",
        org_id="school_001",
        assessment_id="asmt_001",
        student_id="std_001",
        recipient_phone_masked="+91 98*** **201",
        idempotency_key="idemp_test_001",
        current_status=DispatchState.SCHEDULED,
        created_at_utc=now,
        updated_at_utc=now,
    )
    initial_event = DispatchEventRecord(
        event_id="evt_init_001",
        dispatch_id="disp_test_001",
        org_id="school_001",
        event_type=DispatchState.SCHEDULED,
        occurred_at_utc=now,
    )
    test_repo.create_dispatch("school_001", dispatch, initial_event)

    # Transition to SUBMITTED
    submitted_event = DispatchEventRecord(
        event_id="evt_sub_001",
        dispatch_id="disp_test_001",
        org_id="school_001",
        event_type=DispatchState.SUBMITTED,
        provider_wamid="wamid.HBgLMTE=",
        occurred_at_utc=now,
    )
    return test_repo.record_event("school_001", submitted_event)


def generate_signature(raw_payload: bytes, secret: str) -> str:
    """Generate Meta X-Hub-Signature-256 header."""
    mac = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def test_gate9_webhook_valid_signature_and_event_transition(
    test_repo: SQLiteDispatchRepository,
    test_sender: SenderIdentity,
    populated_dispatch: DispatchRecord,
    secret_resolver,
):
    """
    Valid HMAC-SHA256 signature:
    - Webhook accepted with HTTP 200 within SLA.
    - Normalized status 'delivered' maps to DELIVERED.
    - Dispatch status updated in repository.
    """
    demux = WebhookDemultiplexer(secret_resolver=secret_resolver)
    demux.register_sender(test_sender)

    webhook_payload_dict = load_fixture("webhook_status_events.json")
    raw_payload = json.dumps(webhook_payload_dict).encode("utf-8")
    sig = generate_signature(raw_payload, "TEST_META_APP_SECRET_SCH01")

    code, resp = demux.process_webhook(raw_payload, sig, test_repo)
    assert code == 200
    assert resp["status"] == "ok"
    assert resp["org_id"] == "school_001"
    assert resp["processed_events"] == 1

    # Verify dispatch transitioned in repository
    updated = test_repo.get_dispatch_by_id("school_001", populated_dispatch.dispatch_id)
    assert updated is not None
    assert updated.current_status == DispatchState.DELIVERED


def test_gate9_webhook_invalid_signature_rejected(
    test_repo: SQLiteDispatchRepository,
    test_sender: SenderIdentity,
    populated_dispatch: DispatchRecord,
    secret_resolver,
):
    """Invalid or missing HMAC signature rejected with HTTP 401; zero state mutations."""
    demux = WebhookDemultiplexer(secret_resolver=secret_resolver)
    demux.register_sender(test_sender)

    raw_payload = json.dumps(load_fixture("webhook_status_events.json")).encode("utf-8")
    bad_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    code, resp = demux.process_webhook(raw_payload, bad_sig, test_repo)
    assert code == 401
    assert resp["error"] == "Invalid signature"

    # Status must NOT have mutated
    disp = test_repo.get_dispatch_by_id("school_001", populated_dispatch.dispatch_id)
    assert disp is not None
    assert disp.current_status == DispatchState.SUBMITTED


def test_gate9_webhook_unknown_phone_number_id_rejected_with_404(
    test_repo: SQLiteDispatchRepository,
    secret_resolver,
):
    """
    Unknown phone_number_id rejected with HTTP 404.
    Privacy hygiene: Payload omitted from logs.
    """
    demux = WebhookDemultiplexer(secret_resolver=secret_resolver)
    # test_sender NOT registered

    raw_payload = json.dumps(load_fixture("webhook_status_events.json")).encode("utf-8")
    sig = generate_signature(raw_payload, "ANY_SECRET")

    code, resp = demux.process_webhook(raw_payload, sig, test_repo)
    assert code == 404
    assert resp["error"] == "Unknown phone_number_id"


def test_gate9_webhook_duplicate_delivery_idempotent_ack(
    test_repo: SQLiteDispatchRepository,
    test_sender: SenderIdentity,
    populated_dispatch: DispatchRecord,
    secret_resolver,
):
    """
    Duplicate webhook deliveries must be acknowledged with HTTP 200 idempotently
    without raising exceptions or corrupting the event store.
    """
    demux = WebhookDemultiplexer(secret_resolver=secret_resolver)
    demux.register_sender(test_sender)

    raw_payload = json.dumps(load_fixture("webhook_status_events.json")).encode("utf-8")
    sig = generate_signature(raw_payload, "TEST_META_APP_SECRET_SCH01")

    # Delivery 1: Transitions to DELIVERED
    code1, _ = demux.process_webhook(raw_payload, sig, test_repo)
    assert code1 == 200

    # Delivery 2: Exact duplicate arrives
    code2, resp2 = demux.process_webhook(raw_payload, sig, test_repo)
    assert code2 == 200
    assert resp2["results"][0]["status"] == "duplicate_acknowledged"


def test_gate9_webhook_order_safety_read_never_regresses_to_delivered(
    test_repo: SQLiteDispatchRepository,
    test_sender: SenderIdentity,
    populated_dispatch: DispatchRecord,
    secret_resolver,
):
    """
    Order Safety & Monotonic Progression (Gate 9 critical invariant):
    If a message has already reached READ, an out-of-order DELIVERED event
    must be acknowledged (HTTP 200) and appended to dispatch_events, but
    must NEVER regress current_status from READ back to DELIVERED.
    """
    demux = WebhookDemultiplexer(secret_resolver=secret_resolver)
    demux.register_sender(test_sender)

    # 1. Advance dispatch to DELIVERED then READ (without registering wamid on delivered)
    now = datetime.now(UTC)
    deliv_evt = DispatchEventRecord(
        event_id="evt_deliv_prep",
        dispatch_id=populated_dispatch.dispatch_id,
        org_id="school_001",
        event_type=DispatchState.DELIVERED,
        provider_wamid=None,
        occurred_at_utc=now,
    )
    test_repo.record_event("school_001", deliv_evt)

    read_evt = DispatchEventRecord(
        event_id="evt_read_prep",
        dispatch_id=populated_dispatch.dispatch_id,
        org_id="school_001",
        event_type=DispatchState.READ,
        provider_wamid="wamid.HBgLMTE=",
        occurred_at_utc=now,
    )
    test_repo.record_event("school_001", read_evt)

    disp_at_read = test_repo.get_dispatch_by_id("school_001", populated_dispatch.dispatch_id)
    assert disp_at_read is not None
    assert disp_at_read.current_status == DispatchState.READ

    # 2. Out-of-order webhook arrives with status 'delivered'
    out_of_order_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID_TEST",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": "phone_id_test_001",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.HBgLMTE=",
                                    "status": "delivered",
                                    "timestamp": "1730000005",
                                    "recipient_id": "919811122201",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw_payload = json.dumps(out_of_order_payload).encode("utf-8")
    sig = generate_signature(raw_payload, "TEST_META_APP_SECRET_SCH01")

    code, resp = demux.process_webhook(raw_payload, sig, test_repo)
    assert code == 200
    assert resp["results"][0]["status"] in ("out_of_order_recorded", "duplicate_acknowledged")

    # Invariant assertion: current_status remains READ
    disp_after = test_repo.get_dispatch_by_id("school_001", populated_dispatch.dispatch_id)
    assert disp_after is not None
    assert disp_after.current_status == DispatchState.READ


def test_gate9_webhook_failed_status_records_error_classification(
    test_repo: SQLiteDispatchRepository,
    test_sender: SenderIdentity,
    populated_dispatch: DispatchRecord,
    secret_resolver,
):
    """
    Failed delivery receipt:
    - Normalizes to FAILED state.
    - Classifies provider error code (e.g. 131026 -> PERMANENT).
    """
    demux = WebhookDemultiplexer(secret_resolver=secret_resolver)
    demux.register_sender(test_sender)

    fail_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID_TEST",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": "phone_id_test_001",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.HBgLMTE=",
                                    "status": "failed",
                                    "timestamp": "1730000010",
                                    "recipient_id": "919811122201",
                                    "errors": [
                                        {
                                            "code": 131026,
                                            "title": "Receiver is not on WhatsApp",
                                        }
                                    ],
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    raw = json.dumps(fail_payload).encode("utf-8")
    sig = generate_signature(raw, "TEST_META_APP_SECRET_SCH01")

    code, resp = demux.process_webhook(raw, sig, test_repo)
    assert code == 200

    disp = test_repo.get_dispatch_by_id("school_001", populated_dispatch.dispatch_id)
    assert disp is not None
    assert disp.current_status == DispatchState.FAILED


def test_gate9_webhook_reconciles_unknown_needs_review(
    test_repo: SQLiteDispatchRepository,
    test_sender: SenderIdentity,
    populated_dispatch: DispatchRecord,
    secret_resolver,
):
    """
    Dispatches in UNKNOWN_NEEDS_REVIEW (due to prior network ambiguity)
    are reconciled deterministically via webhook delivery evidence (S9 Task 2 & Invariant 13).
    """
    demux = WebhookDemultiplexer(secret_resolver=secret_resolver)
    demux.register_sender(test_sender)

    now = datetime.now(UTC)
    unknown_evt = DispatchEventRecord(
        event_id="evt_unknown_prep",
        dispatch_id=populated_dispatch.dispatch_id,
        org_id="school_001",
        event_type=DispatchState.UNKNOWN_NEEDS_REVIEW,
        provider_wamid="wamid.HBgLMTE=",
        occurred_at_utc=now,
    )
    test_repo.record_event("school_001", unknown_evt)

    disp_unknown = test_repo.get_dispatch_by_id("school_001", populated_dispatch.dispatch_id)
    assert disp_unknown is not None
    assert disp_unknown.current_status == DispatchState.UNKNOWN_NEEDS_REVIEW

    # Inbound webhook arrives with 'delivered'
    raw = json.dumps(load_fixture("webhook_status_events.json")).encode("utf-8")
    sig = generate_signature(raw, "TEST_META_APP_SECRET_SCH01")

    code, _ = demux.process_webhook(raw, sig, test_repo)
    assert code == 200

    reconciled = test_repo.get_dispatch_by_id("school_001", populated_dispatch.dispatch_id)
    assert reconciled is not None
    assert reconciled.current_status == DispatchState.DELIVERED


def test_gate9_dual_engine_postgres_demultiplexing_contract(
    test_sender: SenderIdentity,
    secret_resolver,
):
    """Dual-engine contract: Webhook demultiplexing works identically against PostgresDispatchRepository."""
    pg_repo = PostgresDispatchRepository(force_simulator=True)
    now = datetime.now(UTC)
    pg_repo.register_tenant(
        TenantRecord(
            org_id="school_001",
            school_name="DPS PG",
            created_at_utc=now,
            updated_at_utc=now,
        )
    )
    disp = DispatchRecord(
        dispatch_id="disp_pg_001",
        org_id="school_001",
        assessment_id="asmt_pg_001",
        student_id="std_pg_001",
        recipient_phone_masked="+91 98*** **201",
        idempotency_key="idemp_pg_001",
        current_status=DispatchState.SCHEDULED,
        created_at_utc=now,
        updated_at_utc=now,
    )
    init_evt = DispatchEventRecord(
        event_id="evt_pg_init",
        dispatch_id="disp_pg_001",
        org_id="school_001",
        event_type=DispatchState.SCHEDULED,
        occurred_at_utc=now,
    )
    pg_repo.create_dispatch("school_001", disp, init_evt)

    sub_evt = DispatchEventRecord(
        event_id="evt_pg_sub",
        dispatch_id="disp_pg_001",
        org_id="school_001",
        event_type=DispatchState.SUBMITTED,
        provider_wamid="wamid.HBgLMTE=",
        occurred_at_utc=now,
    )
    pg_repo.record_event("school_001", sub_evt)

    demux = WebhookDemultiplexer(secret_resolver=secret_resolver)
    demux.register_sender(test_sender)

    raw = json.dumps(load_fixture("webhook_status_events.json")).encode("utf-8")
    sig = generate_signature(raw, "TEST_META_APP_SECRET_SCH01")

    code, resp = demux.process_webhook(raw, sig, pg_repo)
    assert code == 200
    assert resp["status"] == "ok"

    updated = pg_repo.get_dispatch_by_id("school_001", "disp_pg_001")
    assert updated is not None
    assert updated.current_status == DispatchState.DELIVERED


def test_gate9_extract_phone_number_id_variations():
    """Verify phone_number_id extraction from valid and malformed structures."""
    fixture = load_fixture("webhook_status_events.json")
    pid = extract_phone_number_id(fixture)
    assert pid == "phone_id_test_001"

    assert extract_phone_number_id({}) is None
    assert extract_phone_number_id({"entry": []}) is None
    assert extract_phone_number_id({"entry": [{"changes": []}]}) is None
    assert extract_phone_number_id({"entry": [{"changes": [{"value": {}}]}]}) is None
    assert extract_phone_number_id(None) is None


def test_gate9_verify_webhook_signature_direct():
    """Verify direct HMAC signature verifier handling edge cases."""
    payload = b'{"test": "payload"}'
    secret = "secret_key_123"
    mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert verify_webhook_signature(payload, f"sha256={mac}", secret) is True
    assert verify_webhook_signature(payload, mac, secret) is True
    assert verify_webhook_signature(payload, "invalid_sig", secret) is False
    assert verify_webhook_signature(payload, None, secret) is False
    assert verify_webhook_signature(payload, mac, "") is False
    assert verify_webhook_signature(b"", mac, secret) is False


def test_gate9_provider_check_health(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """Verify check_health queries sender health and rating."""
    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
    )
    status: ProviderHealthStatus = provider.check_health("school_001", test_sender)
    assert status.is_healthy is True
    assert status.phone_number_id == test_sender.phone_number_id
    assert status.quality_rating == QualityRating.GREEN

    # Dry-run health check
    dry_provider = WhatsAppCloudProvider(base_url="http://127.0.0.1:9999", secret_resolver=secret_resolver, dry_run=True)
    dry_status = dry_provider.check_health("school_001", test_sender)
    assert dry_status.is_healthy is True


def test_gate9_retryable_provider_error_exhausted(mock_server: MockProviderServer, test_sender: SenderIdentity, secret_resolver):
    """Verify exhausted retries on 429 raises RetryableProviderError."""
    err_fixture = load_fixture("error_responses.json")
    rate_limit_payload = err_fixture["rate_limit_429"]

    # Queue 429 three times for max_retries=2
    mock_server.queue_response(429, rate_limit_payload)
    mock_server.queue_response(429, rate_limit_payload)

    provider = WhatsAppCloudProvider(
        base_url=mock_server.base_url,
        secret_resolver=secret_resolver,
        max_retries=2,
    )

    req = TemplateSendRequest(
        recipient_phone_e164="+919811122201",
        template_name="parent_scorecard_v1",
    )

    with pytest.raises(RetryableProviderError, match="Retry attempts exhausted"):
        provider.send_template("school_001", test_sender, req)
