# Project State & Execution Log (`docs/STATE.md`)

## Current Status
- **Active Stage:** Stage S0-R5 (`Stage S0-R5: Assessment model, message identity and multi-school service design (docs/ADR only, no code)`) — **COMPLETED**
- **Next Stage:** Stage 1 (`S1 — Golden Dataset and Independent Contract`) — **AWAITING HUMAN GATE**
- **Live Dispatch:** **DISABLED** (`LIVE_DISPATCH_ENABLED=false` and `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`)
- **Legal/Compliance:** **DEFERRED** (fully collected and tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md`)
- **Fixture Manifest SHA-256:** `N/A` (Staged for S1 generation)
- **Stage Tag:** `stage-0-r5` (commit: `095559852103e9baedf31750f7ef6a7df4d69110` on `agent-run`)

---

## Architecture Decision Records (ADRs) Summary
*Per Stage S0-R5 rules, the agent only PROPOSES architectural decisions; the operator ACCEPTS. Zero new ADRs are marked `ACCEPTED`. ADR-0003 was modified to `ACCEPTED (modified)` pointing to ADR-0017.*

1. **[ADR-0001](adr/ADR-0001-layering.md) (Layering):** Pure Core (zero I/O) vs. Adapters architecture (`PROPOSED`).
2. **[ADR-0002](adr/ADR-0002-numeric-semantics.md) (Numeric Semantics):** Integer marks and half-marks (`Fraction | int`), integer cross-multiplication for threshold comparisons, `Decimal` ROUND_HALF_UP display, zero `float` in core (`PROPOSED`).
3. **[ADR-0003](adr/ADR-0003-identifiers-and-keys.md) (Identifiers & Keys):** Opaque surrogate UUIDs, composite idempotency keys (`ACCEPTED (modified)` — points to ADR-0017 for multi-tenancy).
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

## Operator Decisions Recorded (Decisions 1–5, 2026-10-21)
Recorded in `docs/DECISIONS_OPEN.md`:
1. Multi-tenant hosted service from inception superseding single-school part of ADR-0003.
2. Per-school WhatsApp Business number; no shared number.
3. v1 assessment source kinds: `OMR_MCQ` and `MARKS_ENTRY_TOTALS`.
4. Approved golden message for `MARKS_ENTRY_TOTALS`:
   `"प्रिय अभिभावक, आरव (कक्षा 8-B) के यूनिट टेस्ट 1 (अंग्रेज़ी) में 50 में से 30 नंबर आए हैं (60.0%)। 18 उपस्थित बच्चों में आरव का रैंक 7 है। क्लास का औसत स्कोर 32.4 है। क्लास में सबसे ज़्यादा नंबर 47 हैं।"`
5. Every parent-facing message names child and class/section after fixed leading greeting; never as first token; roll number omitted from text by default (`include_roll_in_text=False`).

---

## Stage S0-R5 Execution Evidence
- **All 5 new ADRs created:** `ADR-0016`, `ADR-0017`, `ADR-0018`, `ADR-0019`, `ADR-0020` (all marked `PROPOSED`).
- **ADR-0002 amended:** Half-marks representation, worked examples (2.5, 0.5, net -75 -> -25.0% RED), OMR golden values unchanged.
- **ADR-0003 updated:** Status `ACCEPTED (modified)` with pointer to ADR-0017.
- **ADR-0007 amended:** PostgreSQL target database, SQLite local tests, dual-engine repository contract suite.
- **Message Catalog & Templates:** Created `docs/message_catalog.md` and 5 templates in `docs/templates/**` with status `UNVERIFIED` for Meta approvals/categories.
- **Domain Glossary & Data Map:** Appended Sections 8-10 in glossary, updated data map with `child_display_name`, `class_section`, and Sections 2.11-2.15.
- **Pre-Deployment Checklist:** Appended items P-05 through P-11 (Section 4).
- **Prompt Pack Amendments:** `00_global_invariants.md`, `W2_review.md`, and stage prompts S1 to S4 and S6 to S13 amended (few lines each; S5 unchanged).
- **Decisions Open:** Recorded Operator Decisions 1-5 and proposed items (a) through (r) as `OWNER-CONFIRM`.

---

## Verification Commands & Execution Evidence
- Linter Check: `ruff check .` (Exit Code: 0)
- Guardrails Check: `python scripts/guardrails.py` (Exit Code: 0)
- Git Scope Check: `git diff --name-status` (Confirmed all changed files strictly within SCOPE).
- Stage Tag: `stage-0-r5` (Commit hash `095559852103e9baedf31750f7ef6a7df4d69110`).