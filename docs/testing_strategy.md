# Testing Strategy & Verification Architecture

**System:** `omr_dispatch_engine`  
**Date:** 2026-10-20  
**Stage:** S0 (Discovery, Contracts, Source Verification)

---

## 1. Core Testing Principles

The testing architecture for `omr_dispatch_engine` is governed by strict invariants defined in `AGENTS.md`:

1. **Independent Golden Contract (Rule 6):**  
   Expected values are literal constants specified in approved fixtures (`expected_reports.json`). Tests **never** compute expected values using the code under test (SUT).
2. **Strict Boundary Mocking (Rule 7):**  
   Only true external boundaries may be mocked:
   - External Network: Meta Graph API HTTP endpoints.
   - External Clock: Controlled frozen time for schedule calculations.  
   **No mocking of local components:** Scorecard image rendering (Playwright), audio transcoding (FFmpeg), database operations (SQLite), and cryptographic operations (HMAC SHA-256) run against real local implementations.
3. **No Network Contact:**  
   No automated test ever contacts a live messaging endpoint, cellular network, or real parent phone number.
4. **Monotonically Non-Decreasing Tests:**  
   `scripts/guardrails.py` enforces that the total test count recorded in `docs/.test_count_baseline` never decreases across stages. Tests may never be skipped, weakened, or removed to make a build pass.
5. **Fixture Immutability:**  
   Approved fixtures in `fixtures/golden/` are frozen and hashed in `manifest.json`. The pre-commit guardrail detects and blocks any hash mismatch.

---

## 2. Test Pyramid & Stage Progression

```
           [ S11 End-to-End Orchestration & Gates ]
          [ S9 Webhooks & S10 Parent Confirmation ]
         [ S7 Scorecard Render & S8 Audio Engine ]
        [ S3 Contacts, S4 Hindi Copy, S5 Proof Crops ]
       [ S2 OMR Ingestion & Score Diagnostics Engine ]
      [ S1 Golden Dataset, Expected Literals & Oracle ]
```

### Layer Breakdown

| Test Suite | Scope & Stage | Components Under Test | Mocking Policy |
| :--- | :--- | :--- | :--- |
| **Golden Contract** | S1 (`tests/test_stage1_golden_contract.py`) | Fixture integrity, manifest hashes, arithmetic properties, contact edge cases | Zero mocks. Pure data assertions against literals. |
| **Ingestion & Diagnostics** | S2 (`tests/test_stage2_diagnostics.py`) | Pydantic schema validation, scoring arithmetic, bands, easy questions, subject labels | Zero mocks. Pure deterministic calculations. |
| **Contact Hygiene** | S3 (`tests/test_stage3_contacts.py`) | E.164 normalization, interception detection, unverified sibling duplicate quarantine | Zero mocks. Pure logic. |
| **Hindi Templates** | S4 (`tests/test_stage4_hindi_templates.py`) | Bolchal Hindi copy generation, vocabulary lint, variable constraints | Zero mocks. Pure text generation & NFC Unicode assertions. |
| **OMR Proof Generation** | S5 (`tests/test_stage5_omr_proof.py`) | Bubble cropping, answer key overlay, coordinate transformation | Real Pillow / image processing; synthetic test scans. |
| **Visual Rendering** | S7 (`tests/test_stage7_rendering.py`) | Playwright Chromium headless rendering, PNG scorecard generation, A4 PTM PDF | Real Playwright, real Chromium, real fonts. |
| **Audio Engine** | S8 (`tests/test_stage8_audio.py`) | Token stitcher, duration guard (<45s), FFmpeg Opus transcoding | Real FFmpeg executable; real audio test tokens. |
| **Dispatch & Messaging** | S9 (`tests/test_stage9_messaging.py`) | Template serialization, retry policy, 24h window guard, rate limits | Mock HTTP transport for Meta API; real SQLite store. |
| **Webhooks & Status** | S10 (`tests/test_stage10_webhooks.py`) | Inbound webhook signature verification (`X-Hub-Signature-256`), status transition | Real cryptographic HMAC, real SQLite store. |
| **Parent Confirmation** | S11 (`tests/test_stage11_confirmation.py`) | QR token creation, OTP verification challenge, single-use invalidation | Real cryptographic random generator, real hashing. |
| **End-to-End Integration** | S12–S13 (`tests/test_stage12_e2e.py`) | Batch orchestrator, offline CLI, audit export, purge worker | Mock HTTP transport; real local storage and renderers. |

---

## 3. Independent Oracle Architecture (`tests/oracle.py`)

To ensure tests do not suffer from confirmation bias:
- S1 introduces `tests/oracle.py`, an independent, test-local scoring oracle written using basic Python arithmetic.
- The oracle shares **zero** imports and **zero** code with `src/omr_dispatch/`.
- The oracle is used strictly to cross-validate invariants and verify that test expectations align mathematically with `PROJECT_SPEC.md` rules.

---

## 4. Test Execution & Reporting Protocol

- All stage validations must be run using:
  ```powershell
  pytest -q tests/test_stage<N>_<name>.py
  ```
- Command evidence, exit codes, and test counts are recorded in `docs/STATE.md` at the end of each stage.
- Pre-commit checks are executed via:
  ```powershell
  python scripts/guardrails.py
  ```
