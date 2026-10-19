# Architecture Decisions & System Design (ADR)

**System Name:** `omr_dispatch_engine`  
**Runtime:** Python 3.11+ / Pydantic v2  
**Date:** 2026-10-20  
**Stage:** S0 (Discovery, Contracts, Source Verification)

---

## 1. Architectural Philosophy & Product Boundaries

The `omr_dispatch_engine` is a deterministic, offline-capable notification and diagnostics engine for Indian educational institutions.

### Product Boundary Definition
* **In Scope:**
  1. Ingestion and strict schema validation of student rosters, exam answer keys, decoded OMR responses, and raw student scan images.
  2. Deterministic diagnostics computation: gross, bleed, net, percentage, rank, status band, easy question identification, and subject diagnosis labels.
  3. Parent-facing asset generation: Conversational Bolchal Hindi text, scorecard PNGs, A4 PTM slip PDFs, and stitched Hindi audio voice notes.
  4. Contact hygiene and quarantine: E.164 normalization, carrier check, duplicate parent collision resolution, guardian verification, and consent gating.
  5. WhatsApp Cloud API dispatch: Template assembly, image attachment, retry policy, and rate limiting.
  6. Inbound webhook processing: HMAC SHA-256 signature verification and delivery status tracking (`sent`, `delivered`, `read`, `failed`).
  7. Parent acknowledgment: Optional single-use QR token verification with OTP challenge.
  8. Structured audit logging and automated retention purging.
* **Explicitly Out of Scope:**
  - Optical bubble detection, sheet corner detection, and pixel alignment. Decoded OMR responses are supplied by an external OMR service whose contract is defined in S2.

---

## 2. Planned Module Decomposition

The core package `src/omr_dispatch/` is organized into focused, decoupled modules:

```
src/omr_dispatch/
├── __init__.py
├── models/               # Domain Pydantic v2 data models (immutable, strictly typed)
├── contacts/             # Contact hygiene, E.164 normalization, quarantine logic
├── ingestion/            # Schema validation for roster, answer keys, OMR JSON
├── diagnostics/          # Pure deterministic scoring, ranks, bands, easy questions
├── hindi_templates/      # Conversational Hindi copy generation & constraint checking
├── omr_proof/            # Visual bubble crop & answer overlay generation
├── renderer/             # Scorecard PNG (Playwright) and PTM Slip PDF generation
├── audio_engine/         # Token stitcher, duration guard, FFmpeg Opus transcoding
├── messaging_policy/     # Consent check, quarantine gating, 24h window guard
├── provider/             # WhatsApp Cloud API client (pinned v21.0 via env)
├── scheduler/            # Durable job scheduler (Asia/Kolkata timezone)
├── durable_store/        # SQLite WAL persistence for jobs, dispatches, tokens
├── webhooks/             # Webhook HTTP handler, X-Hub-Signature-256 verification
├── confirmation/         # QR token generator, hash storage, OTP challenge
├── orchestrator/         # End-to-end pipeline coordinator (fail-closed)
├── cli/                  # CLI commands for batch run, render, audit, and verify
└── audit/                # Structured audit logger with automatic field masking
```

---

## 3. Module Responsibilities & Invariants

### 3.1 `models`
- Contains Pydantic v2 schemas: `Student`, `TestPaper`, `AnswerKey`, `Submission`, `DiagnosticReport`, `ContactRecord`, `DispatchJob`.
- Strictly enforces type safety and prevents arbitrary field assignment. Full-precision decimals used for arithmetic calculations.

### 3.2 `contacts` (Contact Hygiene)
- Normalizes Indian phone numbers to E.164 format (`+91XXXXXXXXXX`).
- Detects invalid prefixes (`5511...`), identical student/parent numbers (`INTERCEPTION_RISK_SAME_NUMBER`), and shared parent numbers with unverified siblings (`DUPLICATE_PARENT_UNVERIFIED`).
- Quarantines unverified contacts; quarantined contacts are never dispatched.

### 3.3 `diagnostics`
- Pure, side-effect-free scoring logic:
  - Gross marks, bleed marks, net marks, percentage (D-05).
  - Easy question identification (`accuracy >= 0.75` among present students) (D-02).
  - Subject classification labels (`ACCURACY_BLEED`, `CONCEPTUAL_SPEED_GAP`, `FOUNDATIONAL_CRISIS`, `MASTERY_ZONE`, `NO_ATTEMPT`, `MODERATE_ZONE`) (D-03).
  - Competition rank and PTM slip necessity (D-04).

### 3.4 `hindi_templates`
- Generates natural, respectful Bolchal Hindi text for parents.
- Enforces D-06 vocabulary bans (`ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, `औसत मान`).
- Enforces `TemplateConstraints` (body length <= 1024, header <= 60, no newlines in variables, no leading/trailing whitespace, proper punctuation around parameters).

### 3.5 `renderer` & `omr_proof`
- Scorecard renderer: Generates mobile-optimized PNG cards using Playwright headless Chromium or local Pillow composition.
- PTM slip renderer: Generates A4 PDF documents for students requiring guardian consultation.
- OMR proof generator: Crops question response regions and overlays answer key indicators for transparency.

### 3.6 `audio_engine`
- Primary engine: `RECORDED_TOKEN_STITCH` concatenating pre-recorded human Hindi audio clips.
- Enforces hard duration limits: typical 15–25s, hard cutoff at 45s with fallback to concise script or `AUDIO_UNAVAILABLE` (D-08).
- Transcodes all audio through FFmpeg to Ogg Opus format (mono, 48kHz, 32kbps). Direct file renames are prohibited.

### 3.7 `provider` & `messaging_policy`
- Communicates with Meta WhatsApp Cloud API using pinned version from environment (`WHATSAPP_CLOUD_API_VERSION`).
- Live dispatch is disabled by default (`LIVE_DISPATCH_ENABLED=false`).
- Ensures outbound messages use verified Utility templates. Initial outbound messages never attach audio in headers (not supported by Meta).

### 3.8 `durable_store` & `scheduler`
- Persistence layer based on SQLite in WAL (Write-Ahead Logging) mode.
- Schema tables: `dispatches`, `delivery_events`, `qr_tokens`, `audit_log`.
- All scheduling is anchored to `Asia/Kolkata` (Sunday 20:30 IST primary dispatch; Monday 10:00 IST reminder).
- **Concurrency & Scaling Boundaries:** Designed for up to 200 students per batch. SQLite connection uses a busy timeout (5000ms) with single-writer serialization to eliminate lock contention. In-memory scheduling is explicitly forbidden to prevent job loss across process restarts.

### 3.9 `webhooks` & `confirmation`
- Webhook handles inbound Meta event callbacks, verifying `X-Hub-Signature-256` HMAC with `APP_SECRET` over raw request bytes.
- **Architectural Decision (Webhook Idempotency & Deduplication):** Because Meta's Cloud API provides no guarantee of strict FIFO delivery and may deliver duplicate webhook events during retries, the webhook processor enforces idempotent deduplication on the composite key `(wamid, status)`. Duplicate events are recorded in audit logs but produce no redundant state transitions. Furthermore, receipt of a `read` status implicitly satisfies and supersedes `delivered`, preventing regressive transitions if a delayed `delivered` webhook arrives after `read`.
- QR confirmation generates cryptographically secure 256-bit random tokens, stored hashed (SHA-256). Single use, max 5 failed attempts, 72h default TTL.

### 3.10 `audit`
- Writes tamper-evident append-only JSON logs.
- Automatic masking of sensitive personal information (phone numbers, student names, scores, QR tokens, audio payloads) per Part C Rule 10.
