# Project State & Execution Log (`docs/STATE.md`)

## Current Status
- **Active Stage:** Stage S0-R7 (`Stage S0-R7 — Fix Pass (docs and tooling only)`) — **COMPLETED**
- **Next Stage:** Stage 1 (`S1 — Golden Dataset and Independent Contract`) — **BLOCKED on S1-BLOCK decisions in docs/DECISIONS_OPEN.md & operator sign-off**
- **Live Dispatch:** **DISABLED** (`LIVE_DISPATCH_ENABLED=false` and `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`)
- **Legal/Compliance:** **DEFERRED** (fully collected and tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md`)
- **Fixture Manifest SHA-256:** `N/A` (Staged for S1 generation)
- **Stage Tag:** `stage-0-r6` (commit: `8f59ebda2fcf46e52bb76da2c2abdb02c89b4600` on `agent-run`); `stage-0-r7` to be tagged by operator upon commit.

---

## Architecture Decision Records (ADRs) Summary
*Per Stage S0-R5/R6 rules, the agent only PROPOSES architectural decisions; the operator ACCEPTS. Zero new ADRs are marked `ACCEPTED`. ADR-0003 is `ACCEPTED (original single-school scope); AMENDMENT PENDING RE-APPROVAL` pointing to ADR-0017.*

1. **[ADR-0001](adr/ADR-0001-layering.md) (Layering):** Pure Core (zero I/O) vs. Adapters architecture (`PROPOSED`).
2. **[ADR-0002](adr/ADR-0002-numeric-semantics.md) (Numeric Semantics):** Integer marks and half-marks (`Fraction | int`), integer cross-multiplication for threshold comparisons, `Decimal` ROUND_HALF_UP display, zero `float` in core (`PROPOSED`).
3. **[ADR-0003](adr/ADR-0003-identifiers-and-keys.md) (Identifiers & Keys):** Opaque surrogate UUIDs, composite idempotency keys (`ACCEPTED (original single-school scope); AMENDMENT PENDING RE-APPROVAL` — points to ADR-0017 for multi-tenancy).
4. **[ADR-0004](adr/ADR-0004-marking-scheme-as-data.md) (Marking Scheme as Data):** Question types and marks as data; Version 1 supports `SINGLE_CORRECT` only (`PROPOSED`).
5. **[ADR-0005](adr/ADR-0005-time-and-clocks.md) (Time & Clocks):** Injected `Clock` protocol, timezone-aware datetimes in UTC, `Asia/Kolkata` at presentation edges (`PROPOSED`).
6. **[ADR-0006](adr/ADR-0006-schema-and-contract-versioning.md) (Schema & Contract Versioning):** `schema_version` on every serialized artifact, linear numbered SQL migrations (`PROPOSED`).
7. **[ADR-0007](adr/ADR-0007-persistence-and-storage.md) (Persistence Strategy):** PostgreSQL target database with RLS as defence in depth; SQLite reference for local tests only; dual-engine repository contract test suite from S8 on (`ACCEPTED (amended)`).
8. **[ADR-0008](adr/ADR-0008-errors-and-logging.md) (Errors & Logging):** Typed exception hierarchy, structured JSON logs, logger-layer redaction, masking value types (`PROPOSED`).
9. **[ADR-0009](adr/ADR-0009-configuration.md) (Configuration):** Central typed `Settings` object with `pydantic-settings`, environment-only sourcing, `SecretStr` for credentials (`PROPOSED`).
10. **[ADR-0010](adr/ADR-0010-text-and-unicode.md) (Text & Unicode):** Unicode NFC normalization, grapheme-safe truncation, child display name and class placement after fixed greeting, Latin digits (`0-9`) across all parent copy (`ACCEPTED (amended)`).
11. **[ADR-0011](adr/ADR-0011-canonical-environment-and-determinism.md) (Canonical Environment & Determinism):** Linux Docker canonical for render/audio/PDF tests; Windows for non-render tests (`PROPOSED`).
12. **[ADR-0012](adr/ADR-0012-test-architecture.md) (Test Architecture):** Pytest markers, 95% branch coverage floor for core, property-based testing (`PROPOSED`).
13. **[ADR-0013](adr/ADR-0013-delivery-strategy.md) (Delivery Strategy):** Walking skeleton established after S3 (CLI runs ingestion -> diagnostics -> basic text -> JSON manifest) (`PROPOSED`).
14. **[ADR-0014](adr/ADR-0014-dependencies-and-supply-chain.md) (Dependencies & Supply Chain):** Locked hashes (`uv.lock`), 14-day dependency aging rule (`PROPOSED`).
15. **[ADR-0015](adr/ADR-0015-data-classification-and-lifecycle.md) (Data Classification & Lifecycle):** Classification tiers, field-level data map (`docs/data_map.md`), D-13 retention lifecycle (`PROPOSED`).
16. **[ADR-0016](adr/ADR-0016-assessment-model.md) (Assessment Model & Non-OMR Ingestion):** `Assessment` entity, capability flags per kind (`OMR_MCQ`, `MARKS_ENTRY_TOTALS`, `MARKS_ENTRY_QUESTION_WISE`), persistent student roster, half-marks representation, diagnostics availability matrix, cohort definition (`PROPOSED`).
17. **[ADR-0017](adr/ADR-0017-tenancy-model.md) (Multi-School Hosted Service Tenancy Model):** Shared PostgreSQL database and schema with mandatory `org_id` on every row, tenant-scoped repositories, and PostgreSQL Row-Level Security (RLS) as defence in depth; SQLite for local test suites with dual-engine contract testing from S8 (`PROPOSED`).
18. **[ADR-0018](adr/ADR-0018-application-service-layer-and-security.md) (Application Service Layer & Security Context):** Boundary use-case functions, `Principal` security context, role-permission matrix, resumable `JobRecord` model, opaque `artifact_id` addressing (`PROPOSED`).
19. **[ADR-0019](adr/ADR-0019-per-school-sender-identity-and-routing.md) (Per-School WhatsApp Sender Identity, Secret References & Dynamic Webhook Routing):** Per-school `SenderIdentity`, phone-number ID routing, secret references outside DB, per-sender daily cap pacing, UNVERIFIED Meta onboarding questions (`PROPOSED`).
20. **[ADR-0020](adr/ADR-0020-tenant-lifecycle-and-controls.md) (Tenant Lifecycle, Administrative Controls & Tenant-Fair Scheduling):** Tenant onboarding/suspension/offboarding/deletion lifecycle, kill switches, per-tenant quotas, metering, Deficit Weighted Round-Robin fair scheduling (`PROPOSED`).

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