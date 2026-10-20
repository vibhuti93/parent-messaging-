# Architecture Decisions & System Design (ADR Alignment)

**System Name:** `omr_dispatch_engine`  
**Runtime:** Python 3.11+ / Pydantic v2  
**Date:** 2026-10-20  
**Stage:** S0-R4 (Foundation Hardening & Architectural Governance)  
**Governing ADRs:** [docs/adr/](adr/README.md) (ADR-0001 through ADR-0015, all `PROPOSED`)

---

## 1. Architectural Philosophy & Product Boundaries

The `omr_dispatch_engine` is a deterministic, offline-capable notification and diagnostics engine for Indian educational institutions. It follows a **Hexagonal / Ports & Adapters Architecture** separating a pure deterministic core from outer I/O adapters (ADR-0001).

### Product Boundary Definition
* **In Scope:**
  1. Ingestion and strict schema validation of student rosters, exam answer keys, decoded OMR responses, and raw student scan images.
  2. Deterministic diagnostics computation: gross, bleed, net, percentage, rank, status band, easy question identification, and subject diagnosis labels using exact integer and fraction arithmetic (ADR-0002).
  3. Parent-facing asset generation: Conversational Bolchal Hindi text with Unicode NFC and Latin digits (ADR-0010), scorecard PNGs, A4 PTM slip PDFs, and stitched Hindi audio voice notes.
  4. Contact hygiene and quarantine: E.164 normalization, carrier check, duplicate parent collision resolution, guardian verification, and consent gating.
  5. WhatsApp Cloud API dispatch: Template assembly, image attachment, retry policy, and rate limiting.
  6. Inbound webhook processing: HMAC SHA-256 signature verification and delivery status tracking (`sent`, `delivered`, `read`, `failed`).
  7. Parent acknowledgment: Optional single-use QR token verification with OTP challenge.
  8. Structured audit logging and automated retention purging (ADR-0015).
* **Explicitly Out of Scope:**
  - Optical bubble detection, sheet corner detection, and pixel alignment. Decoded OMR responses are supplied by an external OMR service whose contract is defined in S2.

---

## 2. Layering & Module Decomposition (ADR-0001)

Per ADR-0001, the system is organized into three distinct layers with strict unidirectional dependency rules:

```
src/omr_dispatch/
├── core/                     # LAYER 1: Pure Core (Zero external I/O)
│   ├── models.py             # Immutable domain schemas, schema_version (ADR-0006)
│   ├── diagnostics.py        # Exact integer marks, Fraction ratios (ADR-0002)
│   ├── hindi_templates.py    # Bolchal Hindi copy, NFC, Latin digits (ADR-0010)
│   └── messaging_policy.py   # Pure consent, hygiene, and service window rules
│
├── adapters/                 # LAYER 2: I/O Adapters (Depend on Core protocols)
│   ├── provider.py           # WhatsApp Cloud API client (pinned v21.0 via env)
│   ├── durable_store.py      # SQLite WAL append-only repository (ADR-0007)
│   ├── renderer.py           # Scorecard PNG (Playwright) & PTM PDF generation
│   ├── audio_engine.py       # Token stitcher, duration guard, FFmpeg transcoder
│   ├── omr_proof.py          # Bubble crop and answer overlay generation
│   ├── webhooks.py           # Inbound HTTP handler, X-Hub-Signature-256 verifier
│   ├── confirmation.py       # Cryptographic token generator and SHA-256 hasher
│   └── clock.py              # System & Frozen clock adapters (ADR-0005)
│
├── orchestrator/             # LAYER 3: Application Orchestration
│   ├── orchestrator.py       # Pipeline wiring (extends S3 walking skeleton, ADR-0013)
│   └── retention.py          # Automated purge jobs per D-13 lifecycle (ADR-0015)
│
├── cli.py                    # Unified CLI command suite
├── config.py                 # Central typed Settings object with SecretStr (ADR-0009)
└── audit.py                  # Structured audit logger with automatic masking (ADR-0008)
```

### Layer Dependency Rules
- **Core** depends on **nothing** external (no network, no database, no subprocess, no `os.environ`, no `datetime.now()`).
- **Adapters** implement core protocol interfaces and depend on **Core**.
- **Orchestrator** and **CLI** wire Adapters with Core via dependency injection.

---

## 3. Module Responsibilities & Core Architectural Invariants

### 3.1 `models` & `diagnostics` (Numeric Semantics, ADR-0002)
- Strict Pydantic v2 schemas (`extra="forbid"`). All serialized models carry a `schema_version: int` (ADR-0006).
- **Exact Numeric Representation (ADR-0002):**
  - Marks (`gross`, `bleed`, `net`, `positive_marks_not_earned`) are stored as exact **integers** (`int`).
  - Performance ratios (attempt ratio, accuracy ratio, percentage ratio) are computed as exact **`fractions.Fraction`**.
  - All boundary threshold comparisons (status bands, easy question 75% accuracy) are evaluated via **integer cross-multiplication** (`correct * 4 >= present * 3`).
  - Human-facing display percentages use **`decimal.Decimal`** with `ROUND_HALF_UP` to exactly one decimal place.
  - **Invariant**: The `float` primitive is strictly banned across the core package.

### 3.2 `contacts` (Contact Hygiene & Quarantine)
- Normalizes Indian phone numbers to E.164 format (`+91XXXXXXXXXX`). Format check only (`^[6-9]\d{9}$`).
- Quarantines contacts with `INTERCEPTION_RISK_SAME_NUMBER` (student == parent) or `DUPLICATE_PARENT_UNVERIFIED` (shared parent number with unverified siblings).
- **Invariant**: Quarantined contacts are never dispatched. A non-empty phone number does not constitute consent (Rule 9).

### 3.3 `hindi_templates` (Text Processing & Unicode, ADR-0010)
- Generates natural, respectful Bolchal Hindi text for parents.
- Enforces D-06 vocabulary bans (`ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, `औसत मान`).
- Enforces Unicode Normalization Form C (`NFC`) and grapheme-safe truncation.
- **Digit Policy (ADR-0010, `OWNER-CONFIRM`):** Proposes Latin digits (`0-9`) across all parent-facing text, scorecards, and PTM slips.
- Enforces `TemplateConstraints` (body <= 1024 chars, header <= 60 chars, no newlines in variables, no leading/trailing variables).

### 3.4 `renderer` & `audio_engine` (Deterministic Asset Generation, ADR-0011)
- **Canonical Environment (ADR-0011):** Linux Docker container (`python:3.12-slim` + Debian font packages) is canonical for visual scorecard PNG, PDF slip, and audio transcoding tests. Windows dev is supported for non-render tests.
- **Scorecard Renderer:** Mobile-optimized PNG cards generated via Playwright Chromium.
- **PTM Slip Renderer:** A4 PDF documents generated for students requiring guardian consultation.
- **Audio Engine:** `RECORDED_TOKEN_STITCH` concatenating human Hindi audio clips. Hard duration limit of 45s (fallback to concise script or `AUDIO_UNAVAILABLE` per D-08). Transcoded to OGG Opus (mono, 48kHz RFC 7845 convention) via FFmpeg. Direct file renames are banned.

### 3.5 `durable_store` (Persistence Strategy, ADR-0007)
- Persistence layer based on SQLite in WAL (Write-Ahead Logging) mode.
- **Append-Only Event Store:** State transitions are recorded as append-only records in `dispatch_events` table; current status is derived from the latest event.
- **Persist-Intent-Before-Send:** Dispatch intent (`SUBMITTED`) is committed to the database before the HTTP call is issued.
- **DB Unique Constraints:** Enforces idempotency via unique index on composite `idempotency_key` (PII-free) and deduplication on `(provider_wamid, event_type)`.

### 3.6 `provider` & `messaging_policy` (Provider Contract & Safety Gates)
- Communicates with Meta WhatsApp Cloud API using pinned version (`WHATSAPP_CLOUD_API_VERSION=v21.0`).
- **Safety Gate:** Live dispatch disabled by default (`LIVE_DISPATCH_ENABLED=false` and `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`).
- Error handling maps responses into five verified classes: `RETRY_SAFE`, `OUTCOME_UNKNOWN`, `OPERATOR_ACTION`, `PERMANENT`, `UNKNOWN` (ADR-0008). Only `RETRY_SAFE` auto-retries.

### 3.7 `webhooks` & `confirmation`
- Webhook processor verifies `X-Hub-Signature-256` HMAC with `APP_SECRET` over raw request bytes.
- Idempotent deduplication on `(wamid, status)`. Receipt of `read` implicitly satisfies and supersedes `delivered`.
- QR confirmation generates single-use 256-bit random tokens, stored hashed (SHA-256), 72h default TTL (`OWNER-CONFIRM`), max 5 failed OTP attempts.

### 3.8 `audit` & `retention` (Data Lifecycle & Privacy, ADR-0015)
- Writes tamper-evident structured JSON logs with automatic logger-level redaction (ADR-0008).
- Sensitive values (`PhoneNumber`, `Token`, `StudentName`) masked across logs and traces.
- Enforces D-13 retention lifecycle: scans and reports purged after current academic year; message/audit logs purged after 90 days.
