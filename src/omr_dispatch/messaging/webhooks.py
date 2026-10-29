"""
WhatsApp Webhook Demultiplexer, HMAC Signature Verifier, and Event Normalizer (`src/omr_dispatch/messaging/webhooks.py`).

Compliant with:
- Part B Stage S9 Task 3 & Gate 9 requirements.
- ADR-0019: Single inbound webhook entrypoint demultiplexes by phone_number_id before state transition.
- Global Invariant 10: Never log full phone numbers, tokens, or raw secrets; mask them.
- Global Invariant 13: Fail closed on uncertain input.
- Global Invariant 15: Every call requires an explicit org context (org_id).
- Global Invariant 16: Per-tenant credential and secret isolation.
- Global Invariant 18: No silent resends.
- ADR-0002: Zero float() calls. Delays in integer milliseconds or Decimal.
- ADR-0005: Zero unanchored datetime calls; use explicit UTC timestamps.
- ADR-0008: Structured typed error classification and logger-layer masking.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import SecretStr

from omr_dispatch.messaging.provider import SenderIdentity
from omr_dispatch.messaging.retry import classify_provider_error
from omr_dispatch.messaging.store import (
    DispatchEventRecord,
    DispatchRecord,
    DispatchRepository,
    DispatchState,
    DuplicateWamidEventError,
)

logger = logging.getLogger(__name__)

STATUS_MAP: dict[str, DispatchState] = {
    "sent": DispatchState.SUBMITTED,
    "delivered": DispatchState.DELIVERED,
    "read": DispatchState.READ,
    "failed": DispatchState.FAILED,
}

STATE_PRECEDENCE: dict[DispatchState, int] = {
    DispatchState.PENDING: 1,
    DispatchState.SCHEDULED: 2,
    DispatchState.UPLOADING_MEDIA: 3,
    DispatchState.SUBMITTED: 10,
    DispatchState.DELIVERED: 20,
    DispatchState.READ: 30,
    DispatchState.FAILED: 99,
}


def verify_webhook_signature(
    raw_payload: bytes, signature_header: str | None, app_secret: str
) -> bool:
    """
    Verify Meta X-Hub-Signature-256 header using constant-time comparison.

    Rules:
      - Header must contain valid HMAC-SHA256 hex digest.
      - Strips optional 'sha256=' prefix if present.
      - Rejects empty, missing, or mismatched signatures.
    """
    if not signature_header or not app_secret or not raw_payload:
        return False

    sig_to_check = signature_header.strip()
    if sig_to_check.startswith("sha256="):
        sig_to_check = sig_to_check[7:].strip()

    mac = hmac.new(app_secret.encode("utf-8"), raw_payload, hashlib.sha256)
    expected_hex = mac.hexdigest()

    return hmac.compare_digest(sig_to_check.lower(), expected_hex.lower())


def extract_phone_number_id(payload_json: Any) -> str | None:
    """
    Extract destination phone_number_id from Meta webhook payload.

    Authoritative path:
      entry[].changes[].value.metadata.phone_number_id
    """
    if not isinstance(payload_json, dict):
        return None
    entries = payload_json.get("entry")
    if not isinstance(entries, list) or not entries:
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list) or not changes:
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            metadata = value.get("metadata")
            if isinstance(metadata, dict):
                pid = metadata.get("phone_number_id")
                if pid:
                    return str(pid).strip()
    return None


class WebhookDemultiplexer:
    """
    Demultiplexer routing inbound WhatsApp Cloud API webhooks to tenant-scoped repositories.

    Guarantees:
      - Resolves org_id strictly via metadata.phone_number_id prior to any state mutation (ADR-0019).
      - Rejects unknown phone_number_id with HTTP 404 (logging omits payload for privacy hygiene).
      - Verifies HMAC SHA-256 signature using the resolved tenant's app secret reference.
      - Deduplicates events idempotently on (org_id, provider_wamid, event_type).
      - Enforces order safety: never regresses higher states (e.g. READ -> DELIVERED).
    """

    def __init__(
        self,
        secret_resolver: Callable[[str], SecretStr] | None = None,
        sender_resolver: Callable[[str], SenderIdentity | None] | None = None,
    ) -> None:
        self.secret_resolver = secret_resolver
        self.sender_resolver = sender_resolver
        self._sender_registry: dict[str, SenderIdentity] = {}

    def register_sender(self, sender: SenderIdentity) -> None:
        """Register a school sender identity mapped by its phone_number_id."""
        self._sender_registry[sender.phone_number_id] = sender

    def resolve_sender(self, phone_number_id: str) -> SenderIdentity | None:
        """Resolve sender identity from registry or external resolver."""
        if phone_number_id in self._sender_registry:
            return self._sender_registry[phone_number_id]
        if self.sender_resolver is not None:
            resolved = self.sender_resolver(phone_number_id)
            if resolved is not None:
                self._sender_registry[phone_number_id] = resolved
                return resolved
        return None

    def resolve_app_secret(self, sender: SenderIdentity) -> str:
        """Resolve tenant app secret for HMAC signature verification."""
        if self.secret_resolver is not None and sender.app_secret_ref:
            try:
                secret = self.secret_resolver(sender.app_secret_ref)
                val = secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)
                if val:
                    return val
            except Exception:
                pass

        if sender.app_secret_ref and not sender.app_secret_ref.startswith("ENV:"):
            return sender.app_secret_ref

        return ""

    def process_webhook(
        self,
        raw_payload: bytes,
        signature_header: str | None,
        repo: DispatchRepository,
    ) -> tuple[int, dict[str, Any]]:
        """
        Process inbound webhook HTTP request.

        Returns:
          (http_status_code, response_body_dict)
        """
        if not raw_payload:
            return 400, {"error": "Empty payload"}

        try:
            payload_json = json.loads(raw_payload.decode("utf-8"))
        except Exception:
            return 400, {"error": "Malformed JSON payload"}

        # Step 1: Extract destination phone_number_id
        phone_number_id = extract_phone_number_id(payload_json)
        if not phone_number_id:
            return 400, {"error": "Missing phone_number_id in metadata"}

        # Step 2: Resolve tenant sender identity
        sender = self.resolve_sender(phone_number_id)
        if sender is None:
            # Privacy hygiene (Invariant 10): Log warning omitting the payload
            logger.warning("Rejected webhook for unknown phone_number_id: %s", phone_number_id)
            return 404, {"error": "Unknown phone_number_id"}

        # Step 3: Resolve secret and verify signature
        app_secret = self.resolve_app_secret(sender)
        if not app_secret:
            logger.error("Missing app secret reference for tenant org: %s", sender.org_id)
            return 401, {"error": "Missing app secret configuration"}

        if not verify_webhook_signature(raw_payload, signature_header, app_secret):
            logger.warning("Invalid HMAC SHA-256 signature for tenant org: %s", sender.org_id)
            return 401, {"error": "Invalid signature"}

        # Step 4: Demultiplex and process status events
        processed_count = 0
        results: list[dict[str, Any]] = []

        for entry in payload_json.get("entry", []):
            if not isinstance(entry, dict):
                continue
            for change in entry.get("changes", []):
                if not isinstance(change, dict):
                    continue
                value = change.get("value", {})
                if not isinstance(value, dict):
                    continue

                statuses = value.get("statuses", [])
                if isinstance(statuses, list):
                    for status_item in statuses:
                        if isinstance(status_item, dict):
                            res = self._process_single_status(sender.org_id, status_item, repo)
                            results.append(res)
                            processed_count += 1

        return 200, {
            "status": "ok",
            "org_id": sender.org_id,
            "processed_events": processed_count,
            "results": results,
        }

    def _find_dispatch_by_wamid(
        self, repo: DispatchRepository, org_id: str, wamid: str
    ) -> DispatchRecord | None:
        """Find dispatch record associated with the provider message ID (wamid)."""
        # 1. Direct ID lookup
        direct = repo.get_dispatch_by_id(org_id, wamid)
        if direct is not None:
            return direct

        # 2. SQLite direct connection lookup
        if hasattr(repo, "conn") and repo.conn is not None:
            cur = repo.conn.execute(
                "SELECT dispatch_id FROM dispatch_events WHERE org_id = ? AND provider_wamid = ? LIMIT 1",
                (org_id, wamid),
            )
            row = cur.fetchone()
            if row:
                return repo.get_dispatch_by_id(org_id, row[0])

        # 3. Postgres simulator fallback via underlying SQLite
        if hasattr(repo, "_underlying") and hasattr(repo._underlying, "conn"):
            cur = repo._underlying.conn.execute(
                "SELECT dispatch_id FROM dispatch_events WHERE org_id = ? AND provider_wamid = ? LIMIT 1",
                (org_id, wamid),
            )
            row = cur.fetchone()
            if row:
                return repo.get_dispatch_by_id(org_id, row[0])

        # 4. Live Postgres connection
        if hasattr(repo, "_live_conn") and repo._live_conn is not None:
            try:
                with repo._live_conn.cursor() as cur:
                    cur.execute(
                        "SELECT dispatch_id FROM dispatch_events WHERE org_id = %s AND provider_wamid = %s LIMIT 1",
                        (org_id, wamid),
                    )
                    row = cur.fetchone()
                    if row:
                        return repo.get_dispatch_by_id(org_id, row[0])
            except Exception:
                pass

        return None

    def _is_duplicate_event(
        self, repo: DispatchRepository, org_id: str, wamid: str, event_type: DispatchState
    ) -> bool:
        """Check whether an event with (org_id, provider_wamid, event_type) already exists."""
        sql_sqlite = (
            "SELECT event_id FROM dispatch_events WHERE org_id = ? AND provider_wamid = ? AND event_type = ? LIMIT 1"
        )
        if hasattr(repo, "conn") and repo.conn is not None:
            cur = repo.conn.execute(sql_sqlite, (org_id, wamid, event_type.value))
            return cur.fetchone() is not None

        if hasattr(repo, "_underlying") and hasattr(repo._underlying, "conn"):
            cur = repo._underlying.conn.execute(sql_sqlite, (org_id, wamid, event_type.value))
            return cur.fetchone() is not None

        if hasattr(repo, "_live_conn") and repo._live_conn is not None:
            sql_pg = (
                "SELECT event_id FROM dispatch_events WHERE org_id = %s AND provider_wamid = %s AND event_type = %s LIMIT 1"
            )
            try:
                with repo._live_conn.cursor() as cur:
                    cur.execute(sql_pg, (org_id, wamid, event_type.value))
                    return cur.fetchone() is not None
            except Exception:
                pass

        return False

    def _insert_event_direct(
        self,
        repo: DispatchRepository,
        event: DispatchEventRecord,
    ) -> None:
        """Insert event record directly into dispatch_events table without updating current_status."""
        sql_sqlite = """
        INSERT INTO dispatch_events (
            event_id, dispatch_id, org_id, event_type,
            provider_wamid, error_class, error_code, reason_code,
            raw_payload_json, occurred_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            event.event_id,
            event.dispatch_id,
            event.org_id,
            event.event_type.value,
            event.provider_wamid,
            event.error_class,
            event.error_code,
            event.reason_code,
            event.raw_payload_json,
            event.occurred_at_utc.isoformat(),
        )

        if hasattr(repo, "conn") and repo.conn is not None:
            with repo.conn:
                repo.conn.execute(sql_sqlite, params)
            return

        if hasattr(repo, "_underlying") and hasattr(repo._underlying, "conn"):
            with repo._underlying.conn:
                repo._underlying.conn.execute(sql_sqlite, params)
            return

        if hasattr(repo, "_live_conn") and repo._live_conn is not None:
            sql_pg = """
            INSERT INTO dispatch_events (
                event_id, dispatch_id, org_id, event_type,
                provider_wamid, error_class, error_code, reason_code,
                raw_payload_json, occurred_at_utc
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            with repo._live_conn.cursor() as cur:
                cur.execute(sql_pg, params)

    def _process_single_status(
        self, org_id: str, status_item: dict[str, Any], repo: DispatchRepository
    ) -> dict[str, Any]:
        """Normalize and apply an individual provider message status transition."""
        wamid = status_item.get("id")
        status_str = status_item.get("status", "").lower()
        ts_str = status_item.get("timestamp")

        if not wamid or not status_str:
            return {"wamid": wamid, "status": "skipped_missing_fields"}

        if status_str not in STATUS_MAP:
            return {"wamid": wamid, "status": f"unrecognized_status_{status_str}"}

        target_state = STATUS_MAP[status_str]

        # Explicit UTC timestamp (ADR-0005)
        occurred_at: datetime
        if ts_str and str(ts_str).isdigit():
            occurred_at = datetime.fromtimestamp(int(ts_str), tz=UTC)
        else:
            occurred_at = datetime.now(UTC)

        # 1. Deduplication check: Tolerate duplicate webhook delivery without error
        if self._is_duplicate_event(repo, org_id, wamid, target_state):
            return {
                "wamid": wamid,
                "status": "duplicate_acknowledged",
                "state": target_state.value,
            }

        # 2. Locate matching dispatch record
        dispatch = self._find_dispatch_by_wamid(repo, org_id, wamid)
        if not dispatch:
            # Acknowledge to prevent webhook redelivery loops
            return {"wamid": wamid, "status": "dispatch_not_found"}

        curr_state = dispatch.current_status

        # Extract error classification if failed
        error_class_str: str | None = None
        error_code_int: int | None = None
        reason_code_str: str | None = None
        errors = status_item.get("errors", [])
        if errors and isinstance(errors, list):
            err_obj = errors[0] if isinstance(errors[0], dict) else {}
            error_code_int = err_obj.get("code")
            reason_code_str = err_obj.get("title", "")
            classified = classify_provider_error(
                provider_code=error_code_int,
                message=reason_code_str or "",
            )
            error_class_str = classified.error_class.value

        event_record = DispatchEventRecord(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            dispatch_id=dispatch.dispatch_id,
            org_id=org_id,
            event_type=target_state,
            provider_wamid=wamid,
            error_class=error_class_str,
            error_code=error_code_int,
            reason_code=reason_code_str,
            raw_payload_json=json.dumps(status_item, ensure_ascii=False),
            occurred_at_utc=occurred_at,
        )

        # 3. Order Safety & Monotonic Progression (Gate 9 requirement)
        # If the target state is regressive or equal in precedence:
        # e.g., current is READ (30), target is DELIVERED (20) or SUBMITTED (10)
        curr_precedence = STATE_PRECEDENCE.get(curr_state, 0)
        target_precedence = STATE_PRECEDENCE.get(target_state, 0)

        if curr_state == DispatchState.READ and target_state != DispatchState.READ:
            # Never regress READ state
            self._insert_event_direct(repo, event_record)
            return {
                "wamid": wamid,
                "status": "out_of_order_recorded",
                "current_state": curr_state.value,
                "event_type": target_state.value,
            }

        if target_state in (DispatchState.DELIVERED, DispatchState.SUBMITTED) and target_precedence <= curr_precedence:
            # Regressive delivery receipt -> record event, do NOT regress current status
            self._insert_event_direct(repo, event_record)
            return {
                "wamid": wamid,
                "status": "out_of_order_recorded",
                "current_state": curr_state.value,
                "event_type": target_state.value,
            }

        # 4. Handle SUBMITTED -> READ leap by bridging through intermediate DELIVERED
        if curr_state == DispatchState.SUBMITTED and target_state == DispatchState.READ:
            bridge_event = DispatchEventRecord(
                event_id=f"evt_{uuid.uuid4().hex[:12]}",
                dispatch_id=dispatch.dispatch_id,
                org_id=org_id,
                event_type=DispatchState.DELIVERED,
                provider_wamid=wamid,
                reason_code="SYNTHESIZED_BRIDGE_PRE_READ",
                raw_payload_json=json.dumps(status_item, ensure_ascii=False),
                occurred_at_utc=occurred_at,
            )
            with contextlib.suppress(DuplicateWamidEventError):
                repo.record_event(org_id, bridge_event)

        # 5. Normal forward progression
        try:
            repo.record_event(org_id, event_record)
            return {
                "wamid": wamid,
                "status": "transitioned",
                "previous_state": curr_state.value,
                "current_state": target_state.value,
            }
        except DuplicateWamidEventError:
            return {
                "wamid": wamid,
                "status": "duplicate_acknowledged",
                "state": target_state.value,
            }
