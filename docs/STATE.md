# Project State & Execution Log (`docs/STATE.md`)

## Current Status
- **Active Stage:** Stage S10 (`S10 — Multi-Tenant Scheduler & Send Window Engine`) — **COMPLETED**
- **Next Stage:** Stage S11 (`S11 — Parent Confirmation (QR + OTP)`)
- **Live Dispatch:** **DISABLED** (`LIVE_DISPATCH_ENABLED=false` and `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`)
- **Legal/Compliance:** **DEFERRED** (fully collected and tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md`)
- **Fixture Manifest SHA-256:** `baa580ebd32a942998b0aca4c01624e5d29f34da658155f33b0b42025452867a`
- **Stage Tag:** `stage-9` (commit resolving to `stage-9`)

---

## Architecture Decision Records (ADRs) Summary
*Per Stage S0-R7: operator accepted ADR-0001 through ADR-0011, and ADR-0014 through ADR-0020. ADR-0012 and ADR-0013 remain `PROPOSED`.*

1. **[ADR-0001](adr/ADR-0001-layering.md) (Layering):** Pure Core (zero I/O) vs. Adapters architecture (`ACCEPTED 2026-10-21`).
2. **[ADR-0002](adr/ADR-0002-numeric-semantics.md) (Numeric Semantics):** Integer marks and half-marks (`Fraction | int`), integer cross-multiplication for threshold comparisons, `Decimal` ROUND_HALF_UP display, zero `float` in core (`ACCEPTED 2026-10-21`).
3. **[ADR-0003](adr/ADR-0003-identifiers-and-keys.md) (Identifiers & Keys):** Opaque surrogate UUIDs, composite idempotency keys (`ACCEPTED`; multi-tenant amendment approved 2026-10-21, see ADR-0017).
4. **[ADR-0004](adr/ADR-0004-marking-scheme-as-data.md) (Marking Scheme as Data):** Question types and marks as data; Version 1 supports `SINGLE_CORRECT` only (`ACCEPTED 2026-10-21`).
5. **[ADR-0005](adr/ADR-0005-time-and-clocks.md) (Time & Clocks):** Injected `Clock` protocol, timezone-aware datetimes in UTC, `Asia/Kolkata` at presentation edges (`ACCEPTED 2026-10-21`).
6. **[ADR-0006](adr/ADR-0006-schema-and-contract-versioning.md) (Schema & Contract Versioning):** `schema_version` on every serialized artifact, linear numbered SQL migrations (`ACCEPTED 2026-10-21`).
7. **[ADR-0007](adr/ADR-0007-persistence-and-storage.md) (Persistence Strategy):** PostgreSQL target database with RLS as defence in depth; SQLite reference for local tests only; dual-engine repository contract test suite from S8 on (`ACCEPTED (amended)`).
8. **[ADR-0008](adr/ADR-0008-errors-and-logging.md) (Errors & Logging):** Typed exception hierarchy, structured JSON logs, Invariant 17 primary logging rule, logger-layer redaction as backup (`ACCEPTED 2026-10-21`).
9. **[ADR-0009](adr/ADR-0009-configuration.md) (Configuration):** Central typed `Settings` object with `pydantic-settings`, environment-only sourcing, `SecretStr` for credentials (`ACCEPTED 2026-10-21`).
10. **[ADR-0010](adr/ADR-0010-text-and-unicode.md) (Text & Unicode):** Unicode NFC normalization, grapheme-safe truncation, child display name and class placement after fixed greeting, Latin digits (`0-9`) across all parent copy (`ACCEPTED (amended)`).
11. **[ADR-0011](adr/ADR-0011-canonical-environment-and-determinism.md) (Canonical Environment & Determinism):** Linux Docker canonical for render/audio/PDF tests; Windows for non-render tests (`ACCEPTED 2026-10-21`).
12. **[ADR-0012](adr/ADR-0012-test-architecture.md) (Test Architecture):** Pytest markers, 95% branch coverage floor for core, property-based testing (`PROPOSED`).
13. **[ADR-0013](adr/ADR-0013-delivery-strategy.md) (Delivery Strategy):** Walking skeleton established after S3 (CLI runs ingestion -> diagnostics -> basic text -> JSON manifest) (`PROPOSED`).
14. **[ADR-0014](adr/ADR-0014-dependencies-and-supply-chain.md) (Dependencies & Supply Chain):** Locked hashes (`uv.lock`), 14-day dependency aging rule (`ACCEPTED 2026-10-21`).
15. **[ADR-0015](adr/ADR-0015-data-classification-and-lifecycle.md) (Data Classification & Lifecycle):** Classification tiers, field-level data map (`docs/data_map.md`), D-13 retention lifecycle (`ACCEPTED 2026-10-21`).
16. **[ADR-0016](adr/ADR-0016-assessment-model.md) (Assessment Model & Non-OMR Ingestion):** `Assessment` entity, capability flags per kind (`OMR_MCQ`, `MARKS_ENTRY_TOTALS`, `MARKS_ENTRY_QUESTION_WISE`), persistent student roster, half-marks representation, diagnostics availability matrix, cohort definition, PTM eligibility under D-04 applies to every assessment type (`ACCEPTED 2026-10-21`).
17. **[ADR-0017](adr/ADR-0017-tenancy-model.md) (Multi-School Hosted Service Tenancy Model):** Shared PostgreSQL database and schema with mandatory `org_id` on every row, tenant-scoped repositories, and PostgreSQL Row-Level Security (RLS) as defence in depth; SQLite for local test suites with dual-engine contract testing from S8 (`ACCEPTED 2026-10-21`).
18. **[ADR-0018](adr/ADR-0018-application-service-layer-and-security.md) (Application Service Layer & Security Context):** Boundary use-case functions, `Principal` security context, role-permission matrix, resumable `JobRecord` model, opaque `artifact_id` addressing, Invariant 17 primary logging rule (`ACCEPTED 2026-10-21`).
19. **[ADR-0019](adr/ADR-0019-per-school-sender-identity-and-routing.md) (Per-School WhatsApp Sender Identity, Secret References & Dynamic Webhook Routing):** Per-school `SenderIdentity`, phone-number ID routing, secret references outside DB, per-sender daily cap pacing (`ACCEPTED 2026-10-21`).
20. **[ADR-0020](adr/ADR-0020-tenant-lifecycle-and-controls.md) (Tenant Lifecycle, Administrative Controls & Tenant-Fair Scheduling):** Tenant onboarding/suspension/offboarding/deletion lifecycle, kill switches, per-tenant quotas, metering, Deficit Weighted Round-Robin fair scheduling (`ACCEPTED 2026-10-21`).

---

## Stage S0-R6 Execution Evidence (Review Findings Fixed)
- **F1 (Marks Entry Fixture Bands):** Corrected ME_01 and ME_03 in `docs/prompt_pack/S1.md` to `band YELLOW` per D-01 threshold (`30.0%–60.0%` inclusive; only `>60.0%` is GREEN).
- **F2 (Hindi Text Integrity):** Verified exact UTF-8 strings with Python across all documents: approved marks entry present message, greeting (`"प्रिय अभिभावक, "`), frozen OMR score line (`"कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)"`), and `"आपके बच्चे"`. Zero corruptions or missing conjuncts.
- **F3 (S2 Marks Representation):** Specified in `docs/prompt_pack/S2.md` that `MarksEntryRow` marks are parsed directly as exact `Fraction` from decimal text, never converted to `float` (ADR-0002).
- **F4 (OTP Child Name Exemption):** Added explicit child/class naming exemption for authentication/OTP messages in `docs/prompt_pack/S13.md`, `docs/prompt_pack/S4.md`, and `docs/message_catalog.md`. Documented `GUARDIAN_OTP_CHALLENGE` template and listed message types lacking child name.
- **F5 (S9 Webhook Path Notice):** Marked `entry[].changes[].value.metadata.phone_number_id` as `UNVERIFIED` in `docs/prompt_pack/S9.md` and instructed S9 to verify against contract fixtures.
- **F6 (Self-Check Evidence):** Verified ADR-0016 through ADR-0020 contain all 5 required sections with >=2 options; zero new ADRs marked `ACCEPTED`; git diff against `stage-0-r4` confirms zero changes to the frozen 20-student OMR golden table; approved message matches character-for-character.
- **F7 (Commit Hygiene):** Documented pre-existing uncommitted operator edits from 2026-10-20 that were part of the working tree during `stage-0-r5`.

---

## Verification Commands & Execution Evidence
- Linter Check: `ruff check .` (Exit Code: 0)
- Guardrails Check: `python scripts/guardrails.py` (Exit Code: 0)
- Git Scope Check: `git diff --name-status` (Confirmed all changed files strictly within SCOPE).
- Stage Tag: `stage-0-r6` (Commit hash `8f59ebda2fcf46e52bb76da2c2abdb02c89b4600`).

---

## Stage S0-R7 Execution Evidence (Fix Pass Completed)
- **F1 (Hindi Text Integrity):** Created `scripts/check_hindi_integrity.py`. Verified all `docs/**/*.md` are strict UTF-8, NFC normalized, zero U+FFFD, zero orphan combining marks, zero unapproved Devanagari digits. Verified D-06 banned terms (as `\u` escapes) appear only on normative line 11 of `message_catalog.md` and zero in templates. Verified byte-exact greeting matching across all notification templates.
- **F2 (Golden Table Byte Identity):** Created `scripts/check_golden_table_identity.py`. Verified lines 10–40 of `docs/prompt_pack/S1.md` (31 OMR rows and subject labels) are 100% byte-identical to `stage-0-r4`. Documented accurate line-9 roster description edit in `docs/reviews/stage-0-r7-fixes.md`.
- **F3 (State Hash & Tag Hygiene):** Created `scripts/check_state_hashes.py`. Resolved 40-char commit hash `8f59ebda2fcf46e52bb76da2c2abdb02c89b4600` matching `stage-0-r6` tag.
- **F4 (S1-Blocking Decisions):** Added `Part 1D: S1-BLOCKING Decisions` to `docs/DECISIONS_OPEN.md` enumerating items S1-BLOCK-01 through S1-BLOCK-06 with options and manifest hash consequences. Added blocking prerequisite note before marks entry fixture in `docs/prompt_pack/S1.md`.
- **F5 (ADR-0003 Status & Re-approval Record):** Updated ADR-0003 status to `ACCEPTED (original single-school scope); AMENDMENT PENDING RE-APPROVAL`. Added `Re-approval record` section. Updated `docs/adr/README.md` and `docs/STATE.md`.
- **F6 (Working Tree Cleanup):** Applied operator decisions cleanly: committed R-07 confidence to MEDIUM, committed dev dependencies to `pyproject.toml` and `uv.lock`, reverted uncommitted ADR-0014 and ADR-0016 to `PROPOSED`.
- **F7 (Stage-Aware Guardrails & Whitespace):** Created `docs/CURRENT_STAGE` with value `S0`. Updated `scripts/guardrails.py` so checks skip only when required stage > `CURRENT_STAGE`. Formatted summary line to print `PASSED n / SKIPPED n / FAILED n`. Fixed whitespace and EOF errors via `git diff --check`.
- **F8 (Invariants Synchronization):** Synchronized Invariants 15, 16, 17 into root `AGENTS.md`. Created `scripts/check_invariants_sync.py` enforcing exact alignment. Documented wording discrepancy (never logged vs masked).
- **F9 (Meta Pricing & Voice Notes):** Re-verified row R-05 against official Meta pricing docs with retrieval date 2026-10-21 and exact India rates. Recorded 1 Oct 2026 service-window utility charging conflict as OPEN. Added row R-16 for `"voice": true` (Ogg/Opus mono) and renumbered R-17/R-18. Added item `(s)` for 24h customer service window opening to `DECISIONS_OPEN.md`, referenced in `S9.md` and `ADR-0019`.
- **F10 (Review Rigor Requirements):** Updated `docs/prompt_pack/W2_review.md` adding requirements for raw command evidence, clean worktree execution, mandatory "Attempts to falsify" section (min 3 attempts), and zero-defect gating.

---

## Stage S2 Execution Evidence (Input Contracts and Import Completed)
- **Data Models (`src/omr_dispatch/models.py`):** Implemented strict Pydantic v2 models with `extra="forbid"`, mandatory `org_id`, and `schema_version`. Version 1 supports `SINGLE_CORRECT` only (ADR-0004); all other question types raise `NotSupportedError`.
- **Marks Numerics & Exactness (ADR-0002):** Marks parsed directly from decimal text as exact `fractions.Fraction` (e.g. `"2.5"` gives exactly `Fraction(5, 2)`). Zero `float` in core models. Rejects exponent notation, signs, thousands separators, NaN/inf, Devanagari numerals, and blanks. Only whole and half marks allowed (`denominator in (1, 2)`).
- **Attendance & Boundary Semantics:** `PRESENT` with blank marks rejected (`PRESENT_WITH_BLANK_MARKS`); `ABSENT` with marks rejected (`ABSENT_WITH_MARKS`); blanks never read as zero. `0 <= marks <= max_marks` enforced.
- **Importers (`src/omr_dispatch/ingestion.py`):** Ingests student roster, answer keys, OMR submissions, and marks entries. Guarantees atomic all-or-nothing import (zero partial import). Explicit required `org_id` argument stamps tenant context; tenant mismatches fail closed (`ORG_ID_MISMATCH`).
- **Zero-Dependency Excel Parser:** Stdlib-based `.xlsx` reader using `zipfile` and `xml.etree.ElementTree` strictly handling sparse cell coordinates (`r` attribute) and rejecting malformed/entity-expanded XML safely.
- **Central Configuration (`src/omr_dispatch/config.py`):** Typed `Settings` wrapping secrets in `SecretStr` and defaulting safety switches to disabled (`live_dispatch_enabled=False`, `deployment_compliance_acknowledged=False`, `include_roll_in_text=False`).
- **Tests & Verification:** 42 new unit and rejection tests in `tests/test_stage2_ingestion.py` (73 total tests across S1 and S2). 22 bad-input fixtures under `fixtures/ingestion/`. All 5 mutation tests verified to fail and discarded. All 11 guardrails pass natively (0 skipped, 0 failed).

---

## Stage S3 Execution Evidence (Deterministic Diagnostics and Contact Hygiene Completed)
- **Deterministic Diagnostics (`src/omr_dispatch/diagnostics.py`):** Pure core evaluation functions (`evaluate_student_omr`, `evaluate_batch_omr`, `evaluate_marks_entry_totals_batch`). Enforces standard competition rank (`1224`), integer cross-multiplication for D-01 percentage bands (`30.0%` and `60.0%`) and D-02 easy questions (`>= 75%` peer accuracy), and Decimal `ROUND_HALF_UP` for 1-decimal percentage display.
- **Contact Hygiene & Quarantining (`src/omr_dispatch/contacts.py`):** Phone normalization against national format `^[6-9]\d{9}$`. Strict quarantine criteria (shared phone across distinct admissions, invalid phone, missing consent, missing student id). Explicit `org_id` on all phone and dispatch eligibility queries.
- **Walking Skeleton CLI (`src/omr_dispatch/cli.py`):** Standalone zero-network CLI supporting `--kind OMR_MCQ` and `--kind MARKS_ENTRY_TOTALS`. Full pipeline from CSV ingestion to diagnostics to contact hygiene and JSON report manifest output.
- **Tests & Verification:** 42 new unit and integration tests in `tests/test_stage3_diagnostics_and_hygiene.py` (115 total tests across S1-S3). Tagged `stage-3` (commit `20f38b5bc57ea23df27f5a498830c8ae27175d81`).

---

## Stage S4 Execution Evidence (Conversational Hindi Templates Completed)
- **Template Constraints (`src/omr_dispatch/template_constraints.py`):** Strict Pydantic model enforcing S0 constraints (`max_body_length: 1024`, fixed anchors, no newlines or whitespace inside variables, max variable counts). Conservative defaults fallback sets `constraints_unverified=True` if constraints are unverified or missing.
- **Conversational Hindi Templates (`src/omr_dispatch/hindi_templates.py`):**
  - **Devanagari Grapheme Safety (ADR-0010):** Grapheme cluster segmentation preserving base consonants, combining matras, and conjuncts; safe 40-grapheme truncation; fallback to `"विद्यार्थी"` for invalid/empty names.
  - **Latin Digits & Numeric Formatting (ADR-0002, ADR-0010):** All numbers formatted strictly with ASCII Latin digits (`0-9`), never Devanagari numerals. Negative scores display with standard minus sign (`-`). Trailing `.0` stripped on whole numbers.
  - **Fixed Leading Greeting Anchor (Decision 5):** Every parent academic notification begins with byte-exact `"प्रिय अभिभावक, "` followed by child name and class/section. OTP challenge exempt per Decision 5 and message catalog.
  - **Observable Diagnostic Facts (D-03, D-06):** Observable diagnostic lines with zero internal enums leaked and zero banned Hindi vocabulary.
  - **Golden Equivalence:** 100% character-for-character match against all 20 golden OMR students, all 6 marks entry students, and Operator Decision 4 approved message.
- **Tests & Verification:** 25 new tests in `tests/test_stage4_hindi_templates.py` (140 total passing tests across S1-S4). All 4 deliberate mutations verified to fail and reverted. All 11 guardrails pass natively (0 skipped, 0 failed).
- **Workflow W7 Sign-Off:** Human-in-the-loop Hindi-fluent review for golden copy approved (rating 9.7/10) by Operator.

---

## Stage S5 Execution Evidence (OMR Proof Strip and Scan Provenance Completed)
- **Proof Strip Generator & Provenance (`src/omr_dispatch/omr_proof.py`):** Non-destructive Pillow overlay engine generating pixel-accurate proof strips. Tracks full scan provenance including source SHA-256, source reference, dimensions, coordinate-map version, ISO UTC timestamp, and recorded geometric transforms (`crop`).
- **Transform Discipline:** Applies crop offsets `(crop_left, crop_top, crop_right, crop_bottom)` exactly once (`cropped_x = source_x - crop_left`, `cropped_y = source_y - crop_top`). Zero silent rescaling.
- **Fail-Closed Validation (`REVIEW_REQUIRED`):** Fail-closed handling for missing coordinate maps, empty question coordinates, corrupt images, missing scan files, out-of-bounds coordinates (source and cropped bounds), dimension mismatches, and low alignment confidence (evaluated with exact `Fraction`).
- **Pillow Annotation Overlay & Legend:**
  - Correct response: `#1E8E3E` (RGB `(30, 142, 62)`) green ring and checkmark at/around selected bubble.
  - Wrong response: `#D93025` (RGB `(217, 48, 37)`) red cross at selected bubble + `#1E8E3E` green outline on correct answer key bubble.
  - Blank easy question: `#F9AB00` (RGB `(249, 171, 0)`) amber outline on key bubble.
  - Blank non-easy question: Clean unannotated bubble.
  - Legend: Deterministic visual legend indicating Correct, Wrong, and Blank Easy outside mapped bubble area.
- **Absence & Signature Integrity:**
  - ABSENT students return explicit `ABSENT_NO_PROOF` with no replacement sheet.
  - Source signature block pixels preserved byte-for-byte; zero synthetic signatures generated in production paths.
- **Source Immutability:** Input PIL objects and disk files verified 100% byte-for-byte unchanged before and after rendering.
- **Tests & Verification:** 17 new tests in `tests/test_stage5_omr_proof.py` (157 total passing tests across S1–S5). All 4 deliberate mutations caught and reverted. All 11 guardrails pass natively (0 skipped, 0 failed).

---

## Stage S6 Execution Evidence (Devanagari Rendering, Scorecard PNG, PTM PDF Completed)
- **Typography & Font Integrity (`assets/fonts/`):** Bundled licensed Noto Sans Devanagari (Regular and Bold, `v20201206-phase3`) under SIL OFL 1.1 with verified SHA-256 digests (`a048998...` and `a8318ef...`) in frozen metadata (`FONTS_METADATA.json`). Embedded via base64 local `@font-face` ensuring zero external network calls. Verified in-browser readiness (`document.fonts.ready` + `document.fonts.check`).
- **Context-Managed `PlaywrightRenderer` (`src/omr_dispatch/renderer.py`):** Launches Playwright's bundled Chromium (`156.0.8078.4`) in headless mode without system browser fallbacks. Page-level route interception aborts any non-local requests. Automatic cleanup of browser and child processes on exit.
- **Scorecard PNG Generation:**
  - Pixel-exact 800x1150 at scale 1 (`device_scale_factor=1`).
  - D-07 banner color mapping (`#1E8E3E` Green, `#F9AB00` Yellow, `#D93025` Red, `#5F6368` Absent/Neutral) verified with Pillow pixel sampling.
  - Strict file size budget < 500 KB enforced; over-budget renders fail explicitly (`BUDGET_EXCEEDED`) without silent degradation.
  - Assessment variant handling: `OMR_MCQ` includes score, mark-bleed breakdown, easy questions missed, subject table, and embedded OMR proof strip from real PNG bytes; `MARKS_ENTRY_TOTALS` shows subject totals only and omits proof, easy questions, and diagnostic bleed (omits `NOT_AVAILABLE` metrics, never showing 0); `ABSENT` displays neutral grey banner without score framing.
  - Strict Jinja2 autoescaping prevents XSS injection across all student identity fields.
- **PTM Slip A4 PDF Generation:**
  - A4 portrait (`@page { size: A4 portrait; margin: 6mm; }`), 2x4 grid (8 slips per page), total pages = `ceil(n/8)`.
  - Explicit empty result for `n = 0` (0 pages, no blank PDF).
  - Page counts verified for $n \in \{0, 1, 8, 9, 11, 16, 17\}$ slips producing $\{0, 1, 1, 2, 2, 2, 3\}$ pages.
  - Rasterisation and inspection with `pypdfium2` verifies non-blank pages and absence of text clipping or page overlap.
  - `QrTokenProvider` protocol interface supplies opaque confirmation tokens. Renders exact integer SVG QR matrix with zero personal data encoded. Unverified physical signature line rendered.
- **Tests & Verification:** 24 new tests in `tests/test_stage6_renderer.py` (181 total passing tests across S1–S6). 4 deliberate mutations caught and reverted. All 11 guardrails pass natively (0 skipped, 0 failed).
- **Open Risks & Deferred Verification:** QR matrix phone-scannability verified structurally and attribute-wise (zero PII, opaque token attribute), with optical barcode decoding deferred to Stage S11 when the acknowledgment endpoint is wired; PDF slip non-overlap verified via DOM bounding-box geometry with scale-2 rasterisation verifying non-blank pages.

---

## Stage S7 Execution Evidence (Hindi Audio S7A Asset Intake & S7B Audio Engine Completed)
- **Token Asset Intake & Recording Sheet (`assets/audio_tokens/`, `docs/audio_recording_sheet.md`):**
  - Cataloged 107 existing audio clips in `assets/audio_tokens/manifest.json` with token ID, spoken text, voice (`hi_IN_neutral`), license, sample rate (24,000 Hz), channels (1 mono), MP3 codec, SHA-256 hash, and duration in integer milliseconds.
  - Recording sheet specifies full vocabulary: numbers 0–100, arithmetic terms ("सौ", "माइनस"), greeting ("प्रिय अभिभावक"), "कुल नंबर", "में से", absence phrases, and pause tokens.
  - Mandates gender-neutral phrasing ("आपके बच्चे"); neither child name nor class/section is ever spoken in audio (Invariant 10).
  - Enforces fixed intonation rule: A fixed continuation word follows every number so numbers are never sentence-final (one continuation intonation variant per number is sufficient).
  - Preflight validator `validate_audio_tokens(tokens_dir)` verifies headers, formats, sample rates, channels, duration bounds, and SHA-256 digests against manifest; missing required tokens fail loudly.
- **Audio Token Stitcher (`RECORDED_TOKEN_STITCH`, `src/omr_dispatch/audio_engine.py`):**
  - Implemented `synthesize_token_voice_note(report, catalog, out_path)` stitching tokens via real FFmpeg (`concat` demuxer) and transcoding to WhatsApp-compatible Opus OGG.
  - Maps report facts to canonical token sequences: golden STU_01 maps to net 55 / 25 deductions / 300 max; absent STU_17 maps to neutral attendance context (300 max, 16 present) with zero score never framed; negative net scores map using `"माइनस"` (`w_minus`) + number.
  - Target duration 15–25s enforced (STU_01 renders at ~18.1s); hard maximum 45s (D-08). Over-duration triggers concise fallback; unresolvable overflows raise `AudioDurationOverflowError`.
- **Network TTS Adapter Interface (`NETWORK_TTS`):**
  - Implemented `NetworkTTSProvider` protocol interface and `synthesize_network_tts(...)`. Default disabled via `Settings.network_tts_enabled=False`. Fails closed (`NetworkTTSDisabledError`) when not opted-in.
  - Offline execution verified: pure local token stitching requires zero external network calls. Tones or noise are never returned as speech.
- **FFmpeg WhatsApp OGG/Opus Transcoder:**
  - Implemented `transcode_to_whatsapp_ogg(in_path, out_path)` using real FFmpeg (`-c:a libopus -b:a 32k -ar 48000 -ac 1`). Direct renaming from WAV/MP3 to `.ogg` is strictly rejected.
  - On non-zero exit or timeout, partial files are deleted and `FFmpegExecutionError` / `FFmpegTimeoutError` is raised.
- **Secure Caching (Invariant 10):**
  - Cache keys derived strictly from mode, voice/catalog version, language, rate/pitch, normalized token sequence, and encoder settings version (`v1-opus48k-mono32k`).
  - Filenames and paths are 64-character SHA-256 digests with zero student names, roll numbers, or rendered message text.
  - Cache hit returns immediately with byte copy, skipping FFmpeg invocation entirely.
- **Numerics & Hygiene (ADR-0002, ADR-0005, ADR-0008, ADR-0009):**
  - Zero `float()` calls in `audio_engine.py`: all durations parsed via `Decimal.quantize(..., rounding=ROUND_HALF_UP)` or exact integer milliseconds.
  - Zero `os.environ` or `os.getenv` calls in `audio_engine.py`.
  - Zero unanchored `datetime.now()` calls.
  - Zero raw `print()` calls in source files.
- **Tests & Verification:** 23 new tests in `tests/test_stage7_audio_engine.py` (204 total passing tests across S1–S7). All 4 deliberate mutations caught and reverted. All 11 guardrails pass natively (0 skipped, 0 failed).

---

## Stage S8 Execution Evidence (Messaging Policy Engine and Durable State Completed)
- **Messaging Policy Engine (`src/omr_dispatch/messaging/policy.py`):**
  - **Pre-Send Policy Decision Gating (Task 1):** Deterministic evaluation before every send checking guardian verification, consent (`OPT_IN` and purpose-aligned), contact quarantine flags, 24h customer service window state (free-form vs template), template approval and content constraints, sender identity readiness and credentials, billing status, daily quota, and live dispatch safety switch. Any failed or unknown check blocks/defers with an exact typed reason code (`PolicyReasonCode`).
  - **Gate 8 Golden Admissions Decisions:** Verified 100% against approved 20-student admissions fixture:
    - `STU_02` -> zero sends, exact block reason `INTERCEPTION_RISK_SAME_NUMBER` (`BLOCKED_HYGIENE`).
    - `STU_03` and `STU_04` -> blocked with `DUPLICATE_PARENT_UNVERIFIED` (`BLOCKED_HYGIENE`).
    - `STU_07` -> blocked with `INVALID_PHONE_NUMBER` (`BLOCKED_HYGIENE`).
    - `STU_08` -> blocked with `CONSENT_UNKNOWN` (`BLOCKED_CONSENT`).
    - `STU_09` -> blocked with `CONSENT_REVOKED` (`BLOCKED_CONSENT`).
    - `STU_10` -> blocked with `GUARDIAN_UNVERIFIED` (`BLOCKED_CONSENT`).
    - `STU_01` -> allowed to proceed to policy-permitted mode (`SCHEDULED`).
    - `STU_05` and `STU_06` -> verified siblings sharing guardian phone, both allowed to proceed (`SCHEDULED`).
    - `STU_17` -> absent student eligible only with verified consent; proceeds to policy-permitted mode.
    - `STU_19` -> absent student with revoked consent, blocked with `CONSENT_REVOKED`.
  - **Per-Org Idempotency Key (Task 3):** Formula `sha256(f"{org_id}:{student_id}:{assessment_id}:{purpose}:{channel}:{event_type}")`. Contains zero raw phone numbers or personal data. Distinct reminder event yields distinct key from primary event.
- **Tenant-Scoped Durable Repositories (`src/omr_dispatch/messaging/store.py`):**
  - **Mandatory Org Context (Invariant 15):** Every repository operation requires an explicit `org_id` parameter; calls without org context fail closed with `TenantContextMissingError`.
  - **Dual-Engine Repository Contract:** Passes identically against SQLite (WAL mode, foreign keys, busy timeout via stdlib `sqlite3`) and PostgreSQL (target production database with Row-Level Security defence in depth).
  - **13 Dispatch States & State-Transition Table (Task 2):** Implemented states `PENDING`, `BLOCKED_CONSENT`, `BLOCKED_HYGIENE`, `BLOCKED_POLICY`, `SCHEDULED`, `UPLOADING_MEDIA`, `SUBMITTED`, `DELIVERED`, `READ`, `FAILED`, `RETRY_PENDING`, `UNKNOWN_NEEDS_REVIEW`, `CANCELLED`. Invalid transitions strictly rejected with `IllegalStateTransitionError`.
  - **Append-Only Event Stream & Intent Persistence:** State transitions recorded in append-only `dispatch_events` table; dispatch intent persisted before provider network calls. Current status derived from latest event.
  - **DB-Level Unique Constraints & Deduplication:** Idempotency enforced on `(org_id, idempotency_key)`; duplicate job invocation yields exactly one logical delivery, rejecting duplicate insertions with `IdempotencyCollisionError`. Event deduplication enforced on `(org_id, provider_wamid, event_type)` rejecting duplicates with `DuplicateWamidEventError`.
  - **Global & Per-Tenant Emergency Kill-Switches (Task 4):** Engaging tenant kill-switch or suspension halts dispatches and transitions pending/scheduled jobs to `CANCELLED` for that org only without impacting other tenants.
  - **Restart Recovery:** Verified that reloading an existing database file reconstructs full dispatch state and event history.
- **Audit Logging & Privacy Sanitization (`src/omr_dispatch/messaging/audit.py`):**
  - **Mandatory Org Context:** All audit logging is tenant-scoped with explicit `org_id`.
  - **Privacy Sanitization:** Automatic recursive scrubbing ensures Indian mobile numbers are masked via `mask_phone` (Invariant 10), child display names and class labels are redacted (Invariant 17), and secrets/tokens/scores are redacted.
- **Tests & Verification:**
  - 25 new tests in `tests/test_stage8_policy_and_state.py` (229 total passing tests across S1–S8).
  - Dual-engine repository contract test suite passes against both SQLite and PostgreSQL.
  - All 11 guardrails pass natively (0 skipped, 0 failed). Mypy strict passes (0 issues across 16 files).

---

## Stage S9 Execution Evidence (Provider Adapter, Webhooks, and Retries Completed)
- **Messaging Provider Interface & WhatsApp Cloud Adapter (`src/omr_dispatch/messaging/provider.py`, `src/omr_dispatch/messaging/whatsapp_cloud.py`):**
  - **Contract & Protocols (Task 1):** Defined `MessagingProvider` protocol with typed methods: `send_template`, `send_freeform_text`, `send_media`, `upload_media`, and `check_health`.
  - **Strict Per-Org Sender Identity (ADR-0019, Invariants 15 & 16):** Every provider operation strictly resolves credentials, `phone_number_id`, and app secret from the calling tenant's `SenderIdentity`. Zero fallback to shared global tokens or phone IDs. Tenant context mismatches fail closed with `TenantContextMissingError`.
  - **Multipart Media Upload:** Implemented `upload_media` using RFC 2046 multipart/form-data encoding to upload JPEG, PNG, Opus/OGG, and PDF files, returning durable Meta media IDs.
  - **Service Window Audio Guard (Task 4 & DECISIONS_OPEN item s):** Audio voice notes outside an active 24h customer window fail closed immediately with `ServiceWindowClosedError` without network transmission.
  - **Dry-Run Mode:** Supports hermetic offline testing (`dry_run=True`), validating request payloads and returning synthetic wamids and media IDs with zero network calls.
- **Five-Class Error Classification & Bounded Backoff Engine (`src/omr_dispatch/messaging/retry.py`):**
  - **Five Error Classes (Task 2):**
    - `RETRY_SAFE`: Rate limits (`429`, `130429`, `80007`) safely retried with exponential backoff and jitter, honoring `Retry-After`.
    - `OUTCOME_UNKNOWN`: Ambiguous server outcomes (`5xx`, timeouts, socket resets) classified as `OUTCOME_UNKNOWN`; strictly ZERO auto-retries (Invariants 13 & 18).
    - `OPERATOR_ACTION`: Authentication/billing issues (`401`, `190`, `131037`) fail closed immediately; tenant isolated.
    - `PERMANENT`: Client errors (`400`, `131026` non-WhatsApp user) fail closed with zero retries.
    - `UNKNOWN`: Unrecognized errors fail closed with `OUTCOME_UNKNOWN` semantics.
  - **Numerics & Time (ADR-0002, ADR-0005):** Zero `float()` calls; all delays represented in integer milliseconds. Full decorrelated jitter and bounded delay capping enforced.
- **Webhook Demultiplexing & Signature Verification (`src/omr_dispatch/messaging/webhooks.py`):**
  - **Tenant Resolution (Task 3 & ADR-0019):** Single inbound endpoint resolves `org_id` via `entry[].changes[].value.metadata.phone_number_id` before applying any state changes. Unknown phone IDs are rejected with HTTP 404 (logging omits payload for privacy hygiene).
  - **HMAC SHA-256 Signature Verification:** Constant-time comparison verifies `X-Hub-Signature-256` using the specific tenant's resolved app secret. Rejects invalid signatures with HTTP 401.
  - **Deduplication:** Duplicate webhook deliveries are acknowledged with HTTP 200 within Meta SLA (`duplicate_acknowledged`) without raising duplicate key errors.
  - **Order Safety & Monotonic Progression:** Incoming out-of-order events (e.g. `delivered` after `READ`) are durably recorded in `dispatch_events`, but strictly never regress `dispatches.current_status` from `READ` back to `DELIVERED`.
  - **State Reconciliation:** Dispatches left in `UNKNOWN_NEEDS_REVIEW` due to prior network timeouts are deterministically reconciled to `DELIVERED` or `FAILED` via inbound webhook evidence.
- **Dual-Engine Gate 9 Tests (`tests/test_stage9_provider_and_webhooks.py`):**
  - All tests execute against a real local loopback `HTTPServer` on `127.0.0.1:0`.
  - Requests validated against authoritative fixtures in `tests/fixtures/provider_contract/**`.
  - Dual-engine contract verified: Webhook demultiplexing passes identically against both `SQLiteDispatchRepository` and `PostgresDispatchRepository`.
  - Includes explicit contract disclaimer that local tests prove request/state-machine behavior, not Meta Cloud API production delivery.
- **Verification Commands & Evidence:**
  - 25 new tests in `tests/test_stage9_provider_and_webhooks.py` (254 total passing tests across S1–S9).
  - All 4 deliberate mutations caught and reverted.
  - Guardrails: `python scripts/guardrails.py` reports `PASSED 11 / SKIPPED 0 / FAILED 0`.
  - Type Check: `uv run mypy src` reports `Success: no issues found in 20 source files`.
  - Linter: `uv run ruff check .` reports `All checks passed!`.

---

## Stage S10 Execution Evidence (Multi-Tenant Scheduler & Send Window Engine Completed)
- **Pure Schedule Planning (`src/omr_dispatch/scheduler.py`):**
  - **Deterministic Planning (`plan_schedule`):** Pure deterministic calculation anchored in `ZoneInfo("Asia/Kolkata")` with explicit `now: datetime` injection. Primary send window scheduled at D-10 Sunday 20:30 IST (`20:30:00+05:30`).
  - **Sunday Window Validation:** Strictly enforces `weekday() == 6` for events claiming the primary Sunday OMR window. Non-Sunday events fail closed with explicit `InvalidScheduleWindowError`.
  - **Target Fixture Match (D-10):** Event `2026-10-18 14:15+05:30` (Sunday) produces primary send `2026-10-18 20:30:00+05:30`, and reminder send `2026-10-19 10:00:00+05:30` (Monday morning) strictly when `reminder_enabled=True`. Exactly zero reminders generated when disabled.
  - **Distinct Idempotency Identities:** Primary vs. reminder dispatches compute distinct SHA-256 idempotency identities.
- **Multi-Tenant Fair Scheduling & Daily Cap Pacing:**
  - **Deficit Weighted Round-Robin (DWRR):** Implemented `DWRRQueue` maintaining integer quantum credits and deficit tracking per tenant. Proves that large tenants (e.g. Org A with 1,000 jobs) cannot starve small tenants (Org B with 10 jobs finishes in Round 1).
  - **Core Numerics Exactness (ADR-0002):** Zero `float()` calls in scheduler. All quantums, deficits, weights, caps, and intervals are exact integers.
  - **Daily Cap Spreading (`pace_batch_over_days`):** Batches exceeding a tenant's daily message quota (e.g. 600 items with 250 daily limit) spread across consecutive eligible days within allowed send windows, automatically skipping academic/institutional holidays.
- **Edge Conditions & Send Window Integrity:**
  - **Late Import:** Imports after window start are detected and deferred (`DEFERRED_LATE_IMPORT`) by default to prevent partial/rushed dispatches.
  - **Missed Window:** Current time exceeding window closure transitions jobs to `MISSED_WINDOW`.
  - **Holiday Override:** Institutional holidays postpone primary dispatches to the next eligible non-holiday day (`DEFERRED_HOLIDAY`).
  - **Provider Outage:** Upstream outage halts queued dispatches safely without dropping jobs (`HOLD_PROVIDER_OUTAGE`).
  - **Unapproved Template:** Missing template approval holds dispatches (`HOLD_UNAPPROVED_TEMPLATE`) without dropping jobs.
  - **Freeform Bypass Guardrail (Invariants 13 & 14):** Freeform messages are strictly prohibited from bypassing send window rules, failing closed with `WindowRuleBypassForbiddenError`.
- **Durable Persistence & Single-Instance Dispatch Lock:**
  - **Restart Recovery (`SchedulerStore`):** Schedules and queue orders persisted to SQLite survive store reloads from disk with byte-exact window and metadata fidelity.
  - **Single-Instance Lock (`DispatchLock`):** Concurrency lock backed by SQLite and reentrant mutex prevents multiple worker instances from claiming or dispatching the same scheduled job simultaneously.
- **Verification Commands & Evidence:**
  - 23 new tests in `tests/test_stage10_scheduler.py` (277 total passing tests across S1–S10).
  - 4 deliberate mutations caught and reverted.
  - Guardrails: `python scripts/guardrails.py` reports `PASSED 11 / SKIPPED 0 / FAILED 0`.
  - Type Check: `uv run mypy src` reports `Success: no issues found in 21 source files`.
  - Linter: `uv run ruff check .` reports `All checks passed!`.
