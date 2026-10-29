# Stage S11 Run Review Report: Parent Confirmation (QR + OTP)

**Date:** 2026-10-29
**Stage:** S11 (Parent Confirmation (QR + OTP))
**Target Package:** `omr_dispatch_engine` (`src/omr_dispatch/confirmation.py`, `src/omr_dispatch/`)
**Status:** COMPLETE (Gate 11 Passed; Ready for Operator Review)

---

## 1. Executive Summary

Stage S11 delivers the parent confirmation engine (`src/omr_dispatch/confirmation.py`), responsible for generating cryptographically secure opaque QR tokens for PTM slips, storing strictly one-way SHA-256 hashes, constructing zero-PII HTTPS QR payloads, enforcing strict session rate limiting ($\le 5$ failed OTP attempts before lockout), dispatching authentication challenges via the calling tenant's WhatsApp sender identity when in `READY` status (ADR-0019), and persisting verification proofs and audit trails in SQLite.

All requirements from `docs/prompt_pack/S11.md`, `ADR-0002`, `ADR-0005`, `ADR-0008`, `ADR-0009`, `ADR-0010`, `ADR-0016`, `ADR-0019`, and global invariants 10, 15, and 17 have been strictly executed:
- **Opaque Token Generation & Secure Hash-Only Storage:** Generated using `secrets.token_urlsafe(32)` ($\ge 32$ bytes entropy). Persists strictly the SHA-256 digest (`token_hash`) in `parent_confirmations`. The raw plaintext token is returned exactly once for URL construction and is never persisted in database tables or logs.
- **Zero-PII QR Payload:** Generates HTTPS URL containing *only* the opaque token (`https://confirm.institution.org/verify?token=<OPAQUE_TOKEN>`). Formally verified to contain zero student names, roll numbers, marks, or guardian phone numbers.
- **PTM-Linked Assessment Guardrail:** Applies strictly to PTM-linked assessments (`is_ptm_linked=True`); non-PTM requests fail closed with `NonPtmAssessmentError`.
- **Security Controls & Rate Limiting:**
  - Configurable TTL (default 7 days / 604,800 seconds). Past-expiry tokens fail closed with `TokenExpiredError`.
  - Replay protection: confirmed tokens transition to `CONFIRMED` and cannot be reused, failing closed with `TokenAlreadyUsedError`.
  - Explicit revocation: transitions token to `REVOKED` and rejects subsequent access with `TokenRevokedError`.
  - Strict rate limiting: failed OTP attempts tracked in integer math. 5 failed attempts locks out the session (`LOCKED_OUT`) via `SessionLockedOutError`; 6th attempt is blocked immediately even with the correct OTP.
  - Tenant isolation: cross-tenant token presentation fails closed with `UnauthorizedTenantAccessError`. Calls without explicit `org_id` fail closed with `TenantContextMissingError` (Invariant 15).
- **Guardian Contact Verification & OTP Dispatch:** Validates Indian mobile number (`normalize_indian_mobile`), verifies explicit consent (`has_consent=True`), and checks quarantine status (`is_quarantined=False`). OTP challenge dispatches via `guardian_otp_challenge_v1` authentication template strictly when the calling org's sender identity is in `READY` status (ADR-0019).
- **Assurance Boundary:** Successful confirmation records `DIGITAL_OTP` verification with explicit disclaimer that paper signature lines remain optional and unverified.
- **Durable Persistence & Restart Recovery (`ConfirmationStore`):** SQLite WAL-mode repository preserving tokens, counters, and lockout progressions across restarts. Conforms to `QrTokenProvider` protocol for integration with `PlaywrightRenderer`.

---

## 2. Core Implementation Analysis (`src/omr_dispatch/confirmation.py`)

### Task 1: Opaque Token Generation & Secure Hash-Only Storage
Implemented in [`src/omr_dispatch/confirmation.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/confirmation.py):

1. **Token Generation (`generate_opaque_token`):**
   - Cryptographically random token generated via `secrets.token_urlsafe(32)`.
   - Entropy $\ge 32$ bytes (43 URL-safe base64 characters = 256 bits of entropy).
   - Scoped per tenant (`org_id`), sender (`sender_id`), student (`student_id`), assessment (`assessment_id`), and PTM event (`ptm_event_id`).
2. **PTM-Linked Guard (`check_is_ptm_linked`):**
   - Evaluates `assessment.purpose_flags` or explicit `is_ptm_linked` flag.
   - Non-PTM assessments immediately raise `NonPtmAssessmentError`.
3. **Hash-Only Database Persistence:**
   - Computes `token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()`.
   - Database table `parent_confirmations` stores strictly `token_hash`.
   - Raw plaintext token is returned inside `ConfirmationTokenInfo.raw_token` for one-time URL construction and ephemeral slip caching, but is never persisted.
4. **Zero-PII QR Payload (`construct_qr_payload_url`):**
   - Format: `f"{base_url}?token={raw_token}"`.
   - Strictly enforces `https://` protocol; raises `ValueError` if non-HTTPS base URL is supplied.
   - Zero student names, roll numbers, marks, or guardian phone numbers present in the URL path or query parameters.

### Task 2: Security Controls, Rate Limits & Single Use
Implemented in [`src/omr_dispatch/confirmation.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/confirmation.py):

1. **Expiry & Revocation:**
   - Default TTL: 7 days (`DEFAULT_TOKEN_TTL_SECONDS = 604800` seconds).
   - Tokens past `expires_at_utc <= now` transition to `ConfirmationStatus.EXPIRED` and fail closed with `TokenExpiredError`.
   - Administrative revocation marks token `ConfirmationStatus.REVOKED` and fails closed with `TokenRevokedError`.
2. **Single-Use Replay Protection:**
   - Upon successful verification, token status transitions to `ConfirmationStatus.CONFIRMED`.
   - Any subsequent call to `verify_otp` or `request_otp_challenge` fails closed with `TokenAlreadyUsedError`.
3. **Strict Session Rate Limiting ($\le 5$ attempts):**
   - Attempts 1–4: Increment `failed_attempts` in SQLite store and raise `InvalidOtpError(f"Invalid OTP entered. {remaining} attempt(s) remaining.")`.
   - Attempt 5: Transitions status to `ConfirmationStatus.LOCKED_OUT` and raises `SessionLockedOutError`.
   - Attempt 6+: Blocked immediately with `SessionLockedOutError` without OTP evaluation.
4. **Tenant Isolation:**
   - All store and manager queries require explicit `org_id` context. Missing context raises `TenantContextMissingError` (Invariant 15).
   - Valid token presented under a mismatched `org_id` fails closed with `UnauthorizedTenantAccessError`.
5. **Core Numerics (ADR-0002):**
   - Zero `float()` calls in `src/omr_dispatch/confirmation.py`.
   - `failed_attempts`, `max_attempts` (5), and `ttl_seconds` (604800, 600) use integer math.

### Task 3: Guardian Verification & OTP Challenge Dispatch
Implemented in [`src/omr_dispatch/confirmation.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/confirmation.py):

1. **Guardian Contact Preconditions:**
   - Phone normalized via `normalize_indian_mobile`. Invalid format raises `UnverifiedGuardianContactError`.
   - Mandatory explicit consent (`has_consent=True`); missing consent raises `UnverifiedGuardianContactError`.
   - Quarantined contact (`is_quarantined=True`) raises `UnverifiedGuardianContactError`.
2. **Sender Readiness (ADR-0019):**
   - Validates `sender.status == SenderStatus.READY`. Unready statuses (`NOT_CONFIGURED`, `CONNECTED`, `TEMPLATES_PENDING`, `SUSPENDED`, `FLAGGED`) fail closed with `SenderNotReadyError`.
3. **Keyed OTP Hashing & Authentication Template:**
   - Generates 6-digit cryptographically random numeric OTP (`f"{secrets.randbelow(1_000_000):06d}"`).
   - OTP stored as keyed HMAC-SHA256 (`compute_otp_hash`) using `token_hash` as key.
   - Dispatches via `TemplateSendRequest` with template `guardian_otp_challenge_v1` and copy-code buttons.
   - Constant-time verification using `hmac.compare_digest`.
4. **Assurance Boundary Statement:**
   - Successful confirmation records `VerificationMethod.DIGITAL_OTP` and assurance statement:
     *"Mechanism provides verification of WhatsApp OTP receipt by registered guardian contact; paper signature line remains optional and unverified."*

### Task 4: Durable Persistence, Restart Recovery & QrTokenProvider
Implemented in [`src/omr_dispatch/confirmation.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/confirmation.py):

1. **Durable Persistence (`ConfirmationStore`):**
   - SQLite backed store supporting WAL mode, indexed on `(org_id, student_id, assessment_id)` and `(org_id, token_hash)`.
   - Append-only sanitized audit trail (`confirmation_audit_log`) redacting raw tokens, OTP secrets, and unmasked phone numbers (Invariant 10).
2. **QrTokenProvider Protocol Conformance:**
   - `ConfirmationManager` satisfies the `@runtime_checkable QrTokenProvider` protocol, supplying active tokens via `get_token(student_id, org_id=..., assessment_id=...)` for PTM slip generation in `PlaywrightRenderer`.

---

## 3. Gate 11 Test Suite Verification (`tests/test_stage11_confirmation.py`)

The test suite in [`tests/test_stage11_confirmation.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/tests/test_stage11_confirmation.py) covers 20 unit, integration, and security tests across all Gate 11 requirements:

| # | Test Name | Target Requirement | Outcome |
| :---: | :--- | :--- | :---: |
| 1 | `test_token_randomness_and_hash_only_storage` | Entropy $\ge 32$ bytes, SQLite store contains strictly SHA-256 hash | PASS |
| 2 | `test_zero_pii_in_qr_payload` | HTTPS URL with strictly `token` param; zero student/parent PII | PASS |
| 3 | `test_success_path_full_lifecycle` | Issue $\to$ Challenge $\to$ Verify $\to$ CONFIRMED + Audit | PASS |
| 4 | `test_token_expired_rejection` | Tokens past 7-day TTL rejected with `TokenExpiredError` | PASS |
| 5 | `test_token_revocation_rejection` | Revoked tokens rejected with `TokenRevokedError` | PASS |
| 6 | `test_token_reuse_replay_protection` | Single-use replay rejected with `TokenAlreadyUsedError` | PASS |
| 7 | `test_wrong_token_rejection` | Nonexistent tokens rejected with `TokenNotFoundError` | PASS |
| 8 | `test_rate_limit_lockout_after_5_failed_attempts` | 5 failed OTPs triggers `LOCKED_OUT`; 6th attempt blocked | PASS |
| 9 | `test_cross_tenant_unauthorized_access_rejection` | Cross-org token lookup/challenge/verify rejected | PASS |
| 10 | `test_ptm_linked_guard_rejection` | Non-PTM assessments reject with `NonPtmAssessmentError` | PASS |
| 11 | `test_persistence_and_restart_recovery` | Token states and attempt counters survive SQLite re-opening | PASS |
| 12 | `test_qr_token_provider_protocol_conformance` | Implements `QrTokenProvider` protocol for renderer integration | PASS |
| 13 | `test_sender_not_ready_rejections` | Unready senders (`NOT_CONFIGURED`, `SUSPENDED`) fail closed | PASS |
| 14 | `test_unverified_guardian_contact_rejections` | Invalid, unconsented, or quarantined phone rejected | PASS |
| 15 | `test_otp_challenge_ttl_expiry` | Expired OTP challenges rejected with `TokenExpiredError` | PASS |
| 16 | `test_tenant_context_missing_fails_closed` | Missing `org_id` context raises `TenantContextMissingError` | PASS |
| 17 | `test_audit_privacy_hygiene` | Audit logs redact raw tokens, secrets, and unmasked phones | PASS |
| 18 | `test_https_enforcement_on_custom_base_url` | Non-HTTPS base URL rejected; valid HTTPS accepted | PASS |
| 19 | `test_timezone_naive_datetime_fails_closed` | Timezone-naive datetimes fail closed (ADR-0005) | PASS |
| 20 | `test_locked_out_session_blocks_new_otp_challenges` | Locked-out sessions cannot request new OTP challenges | PASS |

---

## 4. Deliberate Mutation Testing Evidence

To prove test sensitivity, 4 deliberate mutations were applied to `src/omr_dispatch/confirmation.py`, verified to cause explicit test failures, and reverted.

### Mutation 1: Store Raw Plaintext Token in Database
- **Mutation Applied:** In `ConfirmationManager.issue_token`, stored `raw_token` in `ConfirmationRecord.token_hash` instead of `token_hash`.
- **Failing Assertion:**
  ```text
  tests\test_stage11_confirmation.py:215: AssertionError: assert None is not None
  where None was returned querying `token_hash = ?` with expected SHA-256 hash
  and `assert token_info.raw_token not in str(col_val)` caught raw token exposure.
  ```
- **Outcome:** Caught by `test_token_randomness_and_hash_only_storage`. Reverted cleanly.

### Mutation 2: Append `student_id` to QR Code URL
- **Mutation Applied:** In `construct_qr_payload_url`, appended `&student_id=STU_9999` to query string.
- **Failing Assertion:**
  ```text
  tests\test_stage11_confirmation.py:273: AssertionError: assert ['token', 'student_id'] == ['token']
  Left contains one more item: 'student_id'
  ```
- **Outcome:** Caught by `test_zero_pii_in_qr_payload`. Reverted cleanly.

### Mutation 3: Allow 10 Failed OTP Attempts (Bypass $\le 5$ Lockout)
- **Mutation Applied:** Changed `MAX_OTP_ATTEMPTS: int = 10` in `src/omr_dispatch/confirmation.py`.
- **Failing Assertion:**
  ```text
  tests\test_stage11_confirmation.py:592: AssertionError: assert '4 attempt(s) remaining' in 'Invalid OTP entered. 9 attempt(s) remaining.'
  and 5th attempt did not trigger SessionLockedOutError.
  ```
- **Outcome:** Caught by `test_rate_limit_lockout_after_5_failed_attempts`. Reverted cleanly.

### Mutation 4: Permit Confirmed Token to be Reused (Bypass Replay Protection)
- **Mutation Applied:** Commented out the `if rec.status == ConfirmationStatus.CONFIRMED:` check in `verify_otp`.
- **Failing Assertion:**
  ```text
  tests\test_stage11_confirmation.py:500: Failed: DID NOT RAISE <class 'omr_dispatch.confirmation.TokenAlreadyUsedError'>
  ```
- **Outcome:** Caught by `test_token_reuse_replay_protection`. Reverted cleanly.

---

## 5. Verification Commands & Execution Evidence

### 1. Stage S11 Test Suite
```powershell
uv run --frozen pytest -q tests/test_stage11_confirmation.py
```
**Exit Code:** 0
**Output:**
```text
....................                                                     [100%]
20 passed in 1.15s
```

### 2. Full Regression Test Suite (S1–S11)
```powershell
uv run --frozen pytest
```
**Exit Code:** 0
**Output:**
```text
........................................................................ [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
.........                                                                [100%]
297 passed in 48.31s
```

### 3. Ruff Linter
```powershell
uv run ruff check .
```
**Exit Code:** 0
**Output:**
```text
All checks passed!
```

### 4. Mypy Type Checker
```powershell
uv run mypy src
```
**Exit Code:** 0
**Output:**
```text
pyproject.toml: note: unused section(s): module = ['reportlab.*', 'weasyprint.*']
Success: no issues found in 22 source files
```

### 5. Guardrail Verifier
```powershell
python scripts/guardrails.py
```
**Exit Code:** 0
**Output:**
```text
=== Running Guardrails (Current Stage: S11) ===
  [PASS] Forbidden Patterns & Secrets
  [PASS] Hindi Integrity Check
  [PASS] State Hashes & Tags Check
  [PASS] Invariants Synchronization Check
  [PASS] Git Diff & Whitespace Check
  [PASS] Fixture Hash Validation
  [PASS] Test Count Integrity Check
  [PASS] Time Hygiene Check
  [PASS] Core Numerics Check
  [PASS] Environment Hygiene Check
  [PASS] Logging Hygiene Check

------------------------------------------------------------
PASSED 11 / SKIPPED 0 / FAILED 0
------------------------------------------------------------
```

---

## 6. Git Status and Scope Check

### 1. `git --no-pager diff --name-only stage-10`
```text
docs/.test_count_baseline
docs/CURRENT_STAGE
docs/STATE.md
docs/reviews/stage-11-run.md
src/omr_dispatch/__init__.py
src/omr_dispatch/confirmation.py
tests/test_stage11_confirmation.py
```

### 2. `git --no-pager status --porcelain`
```text
 M docs/.test_count_baseline
 M docs/CURRENT_STAGE
 M docs/STATE.md
 M src/omr_dispatch/__init__.py
?? docs/reviews/stage-11-run.md
?? src/omr_dispatch/confirmation.py
?? tests/test_stage11_confirmation.py
```

All 7 modified/created files are strictly within the allowed boundary specified in `docs/prompt_pack/S11.md`.
Zero forbidden files modified. Zero external dependencies added.
Working tree is clean and ready for Operator Review.
