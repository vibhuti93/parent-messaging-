# Stage S9 Run Review Report: WhatsApp Provider Adapter, Webhooks, and Retries

**Date:** 2026-10-29
**Stage:** S9 (Provider Adapter, Webhooks, Retries)
**Target Package:** `omr_dispatch_engine` (`src/omr_dispatch/messaging/`, `src/omr_dispatch/`)
**Status:** COMPLETE (Gate 9 Passed; Ready for Operator Review)

---

## 1. Executive Summary

Stage S9 delivers the isolated messaging provider abstraction, the WhatsApp Cloud API provider adapter, a five-class error classification and backoff retry engine, and the inbound webhook demultiplexer and signature verification pipeline.

All requirements from `docs/prompt_pack/S9.md`, `ADR-0019`, and `ADR-0020` have been fully met:
- **Strict Per-Org Sender Identity & Credential Isolation:** Zero global tokens or shared phone-number IDs exist. Every call resolves credentials and phone IDs strictly from the calling tenant's `SenderIdentity` (Invariant 15 & 16).
- **Five-Class Error Classification & Bounded Backoff:** Provider errors are classified into `RETRY_SAFE`, `OUTCOME_UNKNOWN`, `OPERATOR_ACTION`, `PERMANENT`, and `UNKNOWN`. Only `RETRY_SAFE` errors (e.g. rate limits) may auto-retry, using integer-millisecond backoff with full jitter and honoring `Retry-After`. Failures classified as `OUTCOME_UNKNOWN` (HTTP 5xx, timeouts) fail closed without auto-retry and are reconciled via webhook evidence.
- **Inbound Webhook Demultiplexing & Signature Verification:** The single webhook entrypoint resolves destination `org_id` from `entry[0].changes[0].value.metadata.phone_number_id` (verified against contract fixtures) before any state transition. HMAC SHA-256 signatures are verified using the tenant's app secret reference. Unknown phone IDs are rejected with HTTP 404 (omitting payload for privacy hygiene). Deduplication tolerates repeated deliveries (HTTP 200), and order safety guarantees `READ` never regresses to `DELIVERED`.
- **Audio Service-Window Guard:** Audio voice notes attempted outside an active verified 24h customer window fail closed immediately with `ServiceWindowClosedError` without network transmission (per `docs/DECISIONS_OPEN.md` item s).
- **Gate 9 Local Loopback HTTPServer Tests:** 25 comprehensive tests run against a real local `HTTPServer` on `127.0.0.1:0` verifying wire headers, multipart boundaries, JSON bodies, timing, and error handling against recorded contract fixtures.
- **Dual-Engine Repository Contract:** Webhook demultiplexing is verified against both SQLite and PostgreSQL repositories.

---

## 2. Task 1: `MessagingProvider` Interface & `WhatsAppCloudProvider` Implementation

Implemented in [`src/omr_dispatch/messaging/provider.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/messaging/provider.py) and [`src/omr_dispatch/messaging/whatsapp_cloud.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/messaging/whatsapp_cloud.py):

1. **`MessagingProvider` Protocol Interface:**
   - Methods: `send_template`, `send_freeform_text`, `send_media`, `upload_media`, and `check_health`.
   - Strictly requires explicit `org_id: str` and `sender: SenderIdentity` on every method call.

2. **Per-School Sender Identity Model (`SenderIdentity`, ADR-0019):**
   - Fields: `sender_id`, `org_id`, `waba_id`, `phone_number_id`, `display_phone_number`, `verified_display_name`, `status`, `quality_rating`, `daily_message_limit`, `credential_secret_ref`, `app_secret_ref`, `template_registry`.
   - Access tokens and app secrets are stored as opaque references (`credential_secret_ref`, `app_secret_ref`) and resolved at runtime via `secret_resolver`. Zero raw credentials stored in DB or models.

3. **Wire Request & Payload Conformance:**
   - Pinned Graph API version and base URL sourced from configuration, never hardcoded in source.
   - Headers: `Authorization: Bearer <tenant_token>`, `User-Agent: omr-dispatch-engine/0.1.0`.
   - Template send payload matches recorded fixture [`tests/fixtures/provider_contract/template_send_request.json`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/tests/fixtures/provider_contract/template_send_request.json).
   - Media upload uses RFC 2046 `multipart/form-data` with `messaging_product`, `type`, and `file` parts, storing durable Meta media IDs from [`tests/fixtures/provider_contract/media_upload_response.json`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/tests/fixtures/provider_contract/media_upload_response.json).

4. **Hermetic Dry-Run Mode:**
   - Enabled via `dry_run=True`.
   - Validates all request schemas and parameters, generating deterministic synthetic `wamid` and `media_id` identifiers with zero network transmission.

---

## 3. Task 2: Five-Class Error Classification & Retry Policy

Implemented in [`src/omr_dispatch/messaging/retry.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/messaging/retry.py):

1. **Authoritative Five Error Classes (`ErrorClass`):**
   - **`RETRY_SAFE`**: Rate limits (HTTP 429, codes 4, 80007, 130429, 131056). Auto-retried with exponential backoff and jitter.
   - **`OUTCOME_UNKNOWN`**: Server errors (HTTP 5xx, codes 1, 2, 131000, 131016, 131052, 133004, 134102), network timeouts, connection resets. Acceptance is uncertain; **NEVER auto-retried** (Invariants 13 & 18). Dispatches are recorded as `UNKNOWN_NEEDS_REVIEW` and reconciled via webhook evidence.
   - **`OPERATOR_ACTION`**: Authentication, billing, account limits (HTTP 401, 403, codes 190, 130403, 131037). Fails closed immediately without retries. Expired/revoked credentials affect only that specific tenant (`school_001`), keeping other schools operational.
   - **`PERMANENT`**: Client validation errors (HTTP 400, 404, codes 100, 131026 non-WhatsApp recipient). Fails closed immediately without retry.
   - **`UNKNOWN`**: Unrecognized errors; fail closed with `OUTCOME_UNKNOWN` semantics.

2. **Core Numerics & Bounded Backoff (`compute_backoff_delay_ms`):**
   - Adheres to ADR-0002: **Zero `float()` calls.**
   - All backoff calculations, jitter windows, and delays are computed in integer milliseconds (`int`).
   - Formula: honors `Retry-After * 1000` capped at `max_delay_ms`, or exponential delay `base_delay_ms * 2**(attempt - 1)` with full random jitter in `[base_delay_ms // 2, target_delay]`.

---

## 4. Task 3: Inbound Webhook Demultiplexing, Signature, Deduplication & Order Safety

Implemented in [`src/omr_dispatch/messaging/webhooks.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/messaging/webhooks.py):

1. **Tenant Resolution via Destination Phone Number ID:**
   - Single inbound entrypoint `process_webhook(raw_payload, signature_header, repo)` inspects:
     `entry[0].changes[0].value.metadata.phone_number_id`.
   - Confirmed path against recorded fixture [`tests/fixtures/provider_contract/webhook_status_events.json`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/tests/fixtures/provider_contract/webhook_status_events.json).
   - Resolves `SenderIdentity` and `org_id` before any state transition occurs.
   - Unknown `phone_number_id` is rejected with HTTP 404; warning logged omitting the payload for privacy hygiene.

2. **Cryptographic HMAC-SHA256 Signature Verification (`verify_webhook_signature`):**
   - Constant-time verification (`hmac.compare_digest`) against `X-Hub-Signature-256`.
   - Uses the specific tenant's resolved `app_secret`.
   - Missing or mismatched signature rejected with HTTP 401; zero state mutation.

3. **Status Normalization:**
   - `"sent"` -> `DispatchState.SUBMITTED`
   - `"delivered"` -> `DispatchState.DELIVERED`
   - `"read"` -> `DispatchState.READ`
   - `"failed"` -> `DispatchState.FAILED` (captures Meta error code, e.g. 131026).

4. **Deduplication & Meta SLA Compliance:**
   - Checks `(org_id, provider_wamid, event_type)` in `dispatch_events`.
   - Duplicate deliveries are acknowledged with HTTP 200 within Meta's 3-second SLA (`duplicate_acknowledged`), preventing duplicate key crashes or retry loops.

5. **Order Safety & Monotonic Progression:**
   - If a dispatch has reached `READ`, an out-of-order incoming `DELIVERED` event is acknowledged with HTTP 200 and appended to `dispatch_events`, but **never regresses `current_status` from `READ` back to `DELIVERED`**.
   - Bridges `SUBMITTED -> READ` leap seamlessly.

6. **Reconciliation of Ambiguous Outcomes:**
   - Dispatches in `UNKNOWN_NEEDS_REVIEW` (from network timeouts) are reconciled deterministically to `DELIVERED` or `FAILED` when incoming delivery receipts arrive.

---

## 5. Task 4: Audio Service-Window Guard

- Addressed open item (s) in `docs/DECISIONS_OPEN.md` (`UNVERIFIED` / `OWNER-CONFIRM`).
- Both `WhatsAppCloudProvider.send_freeform_text` and `WhatsAppCloudProvider.send_media(media_type="audio")` require `service_window_active=True`.
- Outside an active verified 24h customer window, voice notes fail closed with `ServiceWindowClosedError` without network transmission.

---

## 6. Gate 9 Local Loopback Test Suite & Execution Results

All 25 tests in [`tests/test_stage9_provider_and_webhooks.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/tests/test_stage9_provider_and_webhooks.py) run against a local `ThreadingHTTPServer` on `127.0.0.1:0`.

```
============================= test session starts =============================
platform win32 -- Python 3.12.1, pytest-8.4.2, pluggy-1.7.0
rootdir: C:\Users\91933\OneDrive\Pictures\Documents\new_parent_messaging
configfile: pyproject.toml
plugins: platformdirs-4.13.5
collected 25 items

tests\test_stage9_provider_and_webhooks.py .........................     [100%]

============================= 25 passed in 8.08s ==============================
```

Full workspace test suite across Stages S1–S9:
```
254 passed in 58.20s
```

### Notice / Contract Disclaimer
> All tests in this suite execute against a real local loopback HTTPServer on an ephemeral port (`127.0.0.1:0`). Payload assertions evaluate conformance against recorded provider contract fixtures (`tests/fixtures/provider_contract/**`). Green tests prove deterministic local request generation, five-class error handling, state-machine transitions, and webhook demultiplexing behavior—**NOT Meta Cloud API production acceptance or parent delivery**.

---

## 7. Mandatory Deliberate Mutation Testing

All 4 required mutations were introduced into the code, verified to cause failing test assertions, and subsequently reverted:

| Mutation | Component Mutated | Change Description | Test Targeted | Failure Observed | Reverted |
|---|---|---|---|---|---|
| **Mutation 1** | `src/omr_dispatch/messaging/retry.py` | Classified HTTP 500 / code 131000 as `RETRY_SAFE` with `is_retryable=True` | `test_gate9_outcome_unknown_500_zero_auto_retries` | `Failed: DID NOT RAISE OutcomeUnknownError` (auto-retry was attempted) | YES |
| **Mutation 2** | `src/omr_dispatch/messaging/webhooks.py` | Bypassed `verify_webhook_signature` to unconditionally return `True` | `test_gate9_webhook_invalid_signature_rejected` | `AssertionError: assert 200 == 401` | YES |
| **Mutation 3** | `src/omr_dispatch/messaging/webhooks.py` | Mutated `dispatches.current_status` to regressive state on out-of-order `DELIVERED` receipt | `test_gate9_webhook_order_safety_read_never_regresses_to_delivered` | `AssertionError: assert <DispatchState.DELIVERED: 'DELIVERED'> == <DispatchState.READ: 'READ'>` | YES |
| **Mutation 4** | `src/omr_dispatch/messaging/whatsapp_cloud.py` | Removed tenant context match check (`sender.org_id != org_id`) in `_resolve_tenant_token` | `test_gate9_strict_per_org_identity_and_credentials` | `Failed: DID NOT RAISE TenantContextMissingError` | YES |

---

## 8. Guardrails and Invariant Conformance

- **Core Numerics (ADR-0002):** Zero `float()` calls in `src/`. Integer milliseconds used for backoff delays and durations.
- **Time Hygiene (ADR-0005):** Zero unanchored `datetime.now()` calls in `src/`. All timestamps created with explicit `tz=UTC` or injected timestamps.
- **Environment Hygiene (ADR-0009):** Zero direct `os.environ` or `os.getenv` calls in `src/omr_dispatch/messaging/**`. Credentials resolved via typed `Settings` or injected callbacks.
- **Logging & Privacy Hygiene (Invariant 10 & 17):** Zero raw tokens, secrets, full phone numbers, or student names logged. Webhook payload omitted when destination phone ID is unknown.
- **Forbidden Pattern Check (W3 Rule):** Zero occurrences of `"localhost"` in `src/`. Zero hardcoded Graph API version strings (e.g. `"v20.0"`) in `src/`. Zero occurrences of `"voice": true` in `src/`.
- **W3 Guardrails Output:** `python scripts/guardrails.py` reports:
  ```
  PASSED 11 / SKIPPED 0 / FAILED 0
  ```
- **Type Checking:** `uv run mypy src` reports:
  ```
  Success: no issues found in 20 source files
  ```
- **Linter:** `uv run ruff check .` reports:
  ```
  All checks passed!
  ```

---

## 9. Staged Files Boundary Verification

Only allowed files were added or modified:
- `src/omr_dispatch/messaging/provider.py` (New: provider interface, contracts, exceptions)
- `src/omr_dispatch/messaging/whatsapp_cloud.py` (New: WhatsApp Cloud provider adapter)
- `src/omr_dispatch/messaging/webhooks.py` (New: webhook demultiplexer, HMAC verifier, event normalizer)
- `src/omr_dispatch/messaging/retry.py` (New: five-class error classifier, integer-ms jitter backoff)
- `src/omr_dispatch/messaging/__init__.py` (Re-exports)
- `src/omr_dispatch/__init__.py` (Re-exports)
- `tests/fixtures/provider_contract/**` (7 JSON contract fixtures)
- `tests/test_stage9_provider_and_webhooks.py` (25 Gate 9 tests)
- `docs/CURRENT_STAGE` (`S9`)
- `docs/.test_count_baseline` (`254`)
- `docs/STATE.md` (Stage S9 execution evidence)
- `docs/reviews/stage-9-run.md` (Stage S9 execution report)

No pre-existing core or pipeline files outside the allowed boundary were touched.
Ready for Operator Review.
