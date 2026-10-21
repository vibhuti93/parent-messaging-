# Architecture Decisions & System Design (ADR Alignment)

**System Name:** `omr_dispatch_engine`
**Runtime:** Python 3.11+ / Pydantic v2
**Date:** 2026-10-21
**Stage:** S0-R5 (Multi-School Hosted Service, Assessment Model, and Message Identity)
**Governing ADRs:** [docs/adr/](adr/README.md) (ADR-0001 through ADR-0020)

---

## 1. Architectural Philosophy & Product Boundaries

The `omr_dispatch_engine` is a hosted, multi-tenant academic notification and diagnostics engine serving multiple educational institutions (ADR-0017). Each school operates via its own dedicated WhatsApp Business Phone Number (ADR-0019). It follows a **Hexagonal / Ports & Adapters Architecture** separating a pure deterministic core from outer I/O adapters (ADR-0001), accessed via an explicit Application Service Boundary (ADR-0018).

### Product Boundary Definition
* **In Scope:**
  1. Multi-kind assessment foundation: Optical mark recognition (`OMR_MCQ`) and manual teacher marks entry (`MARKS_ENTRY_TOTALS`), with persistent student rosters across assessments (ADR-0016).
  2. Ingestion and strict schema validation of student rosters, exam answer keys, decoded OMR responses, raw student scan images, and manual marks entry tabular sheets.
  3. Deterministic diagnostics computation: gross, bleed, net, percentage, rank, status band, easy question identification, and subject diagnosis labels using exact integer and fraction arithmetic, supporting half-marks (ADR-0002).
  4. Parent-facing asset generation: Conversational Bolchal Hindi text identifying child and class after a fixed greeting (Decision 4 & 5, ADR-0010), scorecard PNGs, A4 PTM slip PDFs, and stitched Hindi audio voice notes (gender-neutral "आपके बच्चे").
  5. Contact hygiene and quarantine: E.164 normalization, carrier check, duplicate parent collision resolution, guardian verification, and consent gating.
  6. WhatsApp Cloud API dispatch: Per-school sender identities, isolated credential references, template assembly, image attachment, retry policy, and daily rate pacing (ADR-0019).
  7. Inbound webhook processing: Single endpoint demultiplexing by `phone_number_id`, per-tenant HMAC SHA-256 signature verification, and delivery status tracking (`sent`, `delivered`, `read`, `failed`).
  8. Parent acknowledgment: Optional single-use QR token verification with OTP challenge.
  9. Structured audit logging, tenant lifecycle governance, tenant-fair scheduling, and automated retention purging (ADR-0015, ADR-0018, ADR-0020).
* **Explicitly Out of Scope:**
  - Optical bubble detection, sheet corner detection, and pixel alignment. Decoded OMR responses are supplied by an external OMR service whose contract is defined in S2.
  - User authentication, login screens, billing gateway, and web frontends in v1.

---

## 2. Layering & Module Decomposition (ADR-0001, ADR-0018)

Per ADR-0001 and ADR-0018, the system is organized into distinct layers with strict unidirectional dependency rules:

```
src/omr_dispatch/
├── core/                     # LAYER 1: Pure Core (Zero external I/O)
│   ├── models.py             # Immutable domain schemas, Assessment, schema_version (ADR-0006, 0016)
│   ├── diagnostics.py        # Exact integer marks, Fraction ratios, half-marks (ADR-0002)
│   ├── hindi_templates.py    # Bolchal Hindi copy, NFC, Latin digits, child identity (ADR-0010)
│   └── messaging_policy.py   # Pure consent, hygiene, and service window rules
│
├── adapters/                 # LAYER 2: I/O Adapters (Depend on Core protocols)
│   ├── provider.py           # WhatsApp Cloud API client (per-school sender identity, ADR-0019)
│   ├── durable_store.py      # PostgreSQL production repository + SQLite test engine (ADR-0007, 0017)
│   ├── renderer.py           # Scorecard PNG (Playwright) & PTM PDF generation
│   ├── audio_engine.py       # Token stitcher, duration guard, FFmpeg transcoder (ADR-0011)
│   ├── omr_proof.py          # Bubble crop and answer overlay generation
│   ├── webhooks.py           # Dynamic phone-id demultiplexing, X-Hub-Signature verifier (ADR-0019)
│   ├── confirmation.py       # Cryptographic token generator and SHA-256 hasher
│   └── clock.py              # System & Frozen clock adapters (ADR-0005)
│
├── service/                  # LAYER 3: Application Service Layer (ADR-0018)
│   ├── service.py            # Use-case boundary with Principal security context
│   ├── jobs.py               # Persisted, resumable job lifecycle engine
│   └── fair_scheduler.py     # Tenant-fair dispatch queue (ADR-0020)
│
├── orchestrator/             # LAYER 4: Pipeline Wiring & Lifecycle
│   ├── orchestrator.py       # Batch pipeline wiring (extends S3 walking skeleton, ADR-0013)
│   └── retention.py          # Automated purge jobs per D-13 lifecycle (ADR-0015)
│
├── cli.py                    # Unified CLI command suite (thin adapter with CLI Principal)
├── config.py                 # Central typed Settings object with SecretStr references (ADR-0009)
└── audit.py                  # Structured audit logger with automatic masking (ADR-0008)
```

### Layer Dependency Rules
- **Core** depends on **nothing** external (no network, no database, no subprocess, no `os.environ`, no `datetime.now()`).
- **Adapters** implement core protocol interfaces and depend on **Core**.
- **Orchestrator** and **CLI** wire Adapters with Core via dependency injection.

---

## 3. Module Responsibilities & Core Architectural Invariants

### 3.1 `models` & `diagnostics` (Numeric Semantics & Assessment Model, ADR-0002, ADR-0016)
- Strict Pydantic v2 schemas (`extra="forbid"`). All serialized models carry a `schema_version: int` (ADR-0006).
- **Multi-Kind Assessment Model (ADR-0016):**
  - Canonical `Assessment` entity supporting `OMR_MCQ` and `MARKS_ENTRY_TOTALS` (v1).
  - Student roster (`StudentAdmissionRow`) persists across assessments across the academic year.
  - Capability flags per kind (`has_attempt_data`, `has_negative_marking`, `has_question_level_data`). Uncomputable metrics marked `NOT_AVAILABLE` (never zero).
  - Cohort defined as data on Assessment; cohort label used as class descriptor.
- **Exact Numeric Representation (ADR-0002):**
  - Marks (`gross`, `bleed`, `net`, `positive_marks_not_earned`) are stored as exact integers (`int`) or exact fractions (`Fraction`), supporting half-marks (e.g. 0.5, 2.5).
  - Performance ratios (attempt ratio, accuracy ratio, percentage ratio) are computed as exact **`fractions.Fraction`**.
  - All boundary threshold comparisons (status bands, easy question 75% accuracy) are evaluated via **integer cross-multiplication** (`correct * 4 >= present * 3`).
  - Human-facing display percentages use **`decimal.Decimal`** with `ROUND_HALF_UP` to exactly one decimal place.
  - **Invariant**: The `float` primitive is strictly banned across the core package.

### 3.2 `contacts` (Contact Hygiene & Quarantine)
- Normalizes Indian phone numbers to E.164 format (`+91XXXXXXXXXX`). Format check only (`^[6-9]\d{9}$`).
- Quarantines contacts with `INTERCEPTION_RISK_SAME_NUMBER` (student == parent) or `DUPLICATE_PARENT_UNVERIFIED` (shared parent number with unverified siblings).
- **Invariant**: Quarantined contacts are never dispatched. A non-empty phone number does not constitute consent (Rule 9).

### 3.3 `hindi_templates` (Text Processing, Message Identity, ADR-0010, Decision 4 & 5)
- Generates natural, respectful Bolchal Hindi text for parents.
- Enforces D-06 vocabulary bans (`ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, `औसत मान`).
- Enforces Unicode Normalization Form C (`NFC`) and grapheme-safe truncation.
- **Message Identity Invariants (Decision 5):**
  - Every parent-facing text message names the child (`child_display_name`) and class/section (`class_section`) immediately after a fixed leading greeting (`"प्रिय अभिभावक, "`). The child name is never the first token.
  - Roll number is omitted from text by default (`include_roll_in_text=false`); appears on scorecard PNG and PTM slip.
  - Approved golden message for `MARKS_ENTRY_TOTALS` (Decision 4) is quoted character for character.
- **Digit Policy (ADR-0010):** Standard Latin digits (`0-9`) across all parent copy.
- Enforces `TemplateConstraints` (body <= 1024 chars, header <= 60 chars, no newlines in variables, no leading/trailing variables).

### 3.4 `renderer` & `audio_engine` (Deterministic Asset Generation, ADR-0011, S7)
- **Canonical Environment (ADR-0011):** Linux Docker container (`python:3.12-slim` + Debian font packages) is canonical for visual scorecard PNG, PDF slip, and audio transcoding tests. Windows dev is supported for non-render tests.
- **Scorecard Renderer:** Mobile-optimized PNG cards generated via Playwright Chromium. Scorecards for `MARKS_ENTRY_TOTALS` omit OMR proof strips and diagnostic sections; `NOT_AVAILABLE` items are omitted, never shown as zero.
- **PTM Slip Renderer:** A4 PDF documents generated only for assessments with the `PTM_LINKED` purpose flag.
- **Audio Engine:** `RECORDED_TOKEN_STITCH` concatenating human Hindi audio clips. Hard duration limit of 45s (fallback to concise script or `AUDIO_UNAVAILABLE` per D-08). Transcoded to OGG Opus (mono, 48kHz RFC 7845 convention) via FFmpeg.
- **Audio Personalization Rules:**
  - Audio notes never replace named text messages.
  - Script uses gender-neutral "आपके बच्चे". Spoken audio never speaks child name or class.
  - Audio is an optional extra sent only inside the 24-hour service window (R-02, R-07, R-08), e.g. after a button tap.
  - Quoted reply: where supported by the API, audio is sent as a reply to the named message (`context.message_id`) for sibling disambiguation.

### 3.5 `durable_store` (Persistence Strategy & Tenancy, ADR-0007, ADR-0017)
- **Target Production Database:** PostgreSQL with Row-Level Security (RLS) as defence in depth.
- **Local Test Engine:** SQLite in WAL mode for zero-dependency offline local test runs.
- **Dual-Engine Contract Suite:** Contract test suite runs against both SQLite and PostgreSQL from S8 on.
- **Append-Only Event Store:** State transitions are recorded as append-only records in `dispatch_events` table; current status is derived from the latest event.
- **Persist-Intent-Before-Send:** Dispatch intent (`SUBMITTED`) is committed to the database before the HTTP call is issued.
- **Tenant Scoping & Constraints:** All queries mandate `org_id`. Unique index on composite `idempotency_key` (`v1:{org_id}:...`) and deduplication on `(provider_wamid, event_type)`.

### 3.6 `provider` & `messaging_policy` (Per-School Sender Identity, ADR-0019)
- **Per-School Sender Identity (Decision 2):** Each school operates via its own dedicated WhatsApp Business Phone Number. No shared number.
- **Isolated Credential References:** Access tokens and app secrets are stored outside the database as environment references (`credential_secret_ref`), rotated per org, and never logged.
- **Failure Blast Radius:** Token revocation or rate limit on one school's sender blocks only that school; other tenants continue uninterrupted.
- **Safety Gate:** Live dispatch disabled by default (`LIVE_DISPATCH_ENABLED=false` and `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`).
- Error handling maps responses into five verified classes: `RETRY_SAFE`, `OUTCOME_UNKNOWN`, `OPERATOR_ACTION`, `PERMANENT`, `UNKNOWN` (ADR-0008). Only `RETRY_SAFE` auto-retries.

### 3.7 `webhooks` & `confirmation`
- Webhook processor receives all callbacks on a single endpoint, extracts `phone_number_id`, resolves the tenant `SenderIdentity`, verifies HMAC signature using the tenant's app secret, and routes to tenant-scoped handlers.
- Idempotent deduplication on `(wamid, status)`. Receipt of `read` implicitly satisfies and supersedes `delivered`.
- QR confirmation generates single-use 256-bit random tokens, stored hashed (SHA-256), 72h default TTL (`OWNER-CONFIRM`), max 5 failed OTP attempts.

### 3.8 `audit` & `retention` (Data Lifecycle & Privacy, ADR-0015, ADR-0018)
- Writes tamper-evident structured JSON logs with automatic logger-level redaction (ADR-0008).
- Every audit record mandates `org_id`, `actor_type`, and `actor_id` for complete forensic attribution.
- Sensitive values (`PhoneNumber`, `Token`, `StudentName`, `child_display_name`) masked across logs and traces.
- Enforces D-13 retention lifecycle: scans and reports purged after current academic year; message/audit logs purged after 90 days.

### 3.9 `service` & `tenancy` (Service Boundary & Lifecycle Controls, ADR-0018, ADR-0020)
- Explicit application service interface (`validate_batch`, `evaluate_batch`, `build_send_plan`, `approve_batch`, `cancel_batch`, `get_job_status`, `list_review_queue`, `resolve_review_item`, `get_artifact`).
- Every service call mandates a validated `Principal` context (`actor_type`, `actor_id`, `org_id`, `roles`).
- CLI is a thin wrapper that constructs a CLI Principal and invokes the service layer.
- Background workflows run as persisted, resumable `JobRecord` entities with cursor checkpoints.
- Artifacts addressed by opaque `artifact_id` with tenant isolation checks, never raw filesystem paths.
- Tenant lifecycle operations: onboarding, emergency kill-switch (`emergency_kill_switch`), cascade purge, per-tenant quotas, and deficit round-robin fair scheduling.
