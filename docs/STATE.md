# Project State & Execution Log (`docs/STATE.md`)

## Current Status
- **Active Stage:** Stage S0-R4 (`Stage S0-R4 — Foundation hardening (docs & config)`) — **COMPLETED**
- **Next Stage:** Stage 1 (`S1 — Golden Dataset and Independent Contract`) — **AWAITING HUMAN GATE**
- **Live Dispatch:** **DISABLED** (`LIVE_DISPATCH_ENABLED=false` and `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`)
- **Legal/Compliance:** **DEFERRED** (fully collected and tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md`)
- **Fixture Manifest SHA-256:** `N/A` (Staged for S1 generation)
- **Stage Tag:** `stage-0-r4` (tagged commit on `agent-run`)

---

## Architecture Decision Records (ADRs) Awaiting Human Acceptance
*Per Stage S0-R4 rules, the agent only PROPOSES architectural decisions; the operator ACCEPTS. All 15 ADRs have status `PROPOSED`. Zero ADRs are marked `ACCEPTED`.*

1. **[ADR-0001](adr/ADR-0001-layering.md) (Layering):** Pure Core (zero I/O) vs. Adapters architecture (`PROPOSED`).
2. **[ADR-0002](adr/ADR-0002-numeric-semantics.md) (Numeric Semantics):** Integer marks, `fractions.Fraction` ratios, integer cross-multiplication for threshold comparisons, `Decimal` ROUND_HALF_UP display, zero `float` in core (`PROPOSED`).
3. **[ADR-0003](adr/ADR-0003-identifiers-and-keys.md) (Identifiers & Keys):** Opaque surrogate UUIDs, PII-free composite idempotency keys, institutional tenancy (`PROPOSED` — **`OWNER-CONFIRM`**: Proposing `org_id` from inception).
4. **[ADR-0004](adr/ADR-0004-marking-scheme-as-data.md) (Marking Scheme as Data):** Question types and marks as data; Version 1 supports `SINGLE_CORRECT` only; subjects/sections as data (`PROPOSED`).
5. **[ADR-0005](adr/ADR-0005-time-and-clocks.md) (Time & Clocks):** Injected `Clock` protocol, timezone-aware datetimes in UTC, `Asia/Kolkata` at presentation edges, naive datetimes banned (`PROPOSED`).
6. **[ADR-0006](adr/ADR-0006-schema-and-contract-versioning.md) (Schema & Contract Versioning):** `schema_version` on every serialized artifact, linear numbered SQL migrations, immutable W4 fixtures (`PROPOSED`).
7. **[ADR-0007](adr/ADR-0007-persistence-and-storage.md) (Persistence Strategy):** SQLite WAL reference engine, Postgres-compatible SQL, append-only `dispatch_events` with derived status, DB unique constraints, persist-intent-before-send (`PROPOSED` — **`OWNER-CONFIRM`**: Proposing host disk encryption for dev; app-level encryption deferred to checklist).
8. **[ADR-0008](adr/ADR-0008-errors-and-logging.md) (Errors & Logging):** Typed exception hierarchy, structured JSON logs, logger-layer redaction, masking value types, correlation IDs (`PROPOSED`).
9. **[ADR-0009](adr/ADR-0009-configuration.md) (Configuration):** Central typed `Settings` object with `pydantic-settings`, environment-only sourcing, `SecretStr` for credentials, no scattered `os.environ` (`PROPOSED`).
10. **[ADR-0010](adr/ADR-0010-text-and-unicode.md) (Text & Unicode):** Unicode NFC normalization, grapheme-safe truncation, name display fallback (`PROPOSED` — **`OWNER-CONFIRM`**: Proposing Latin digits `0-9` across all parent copy).
11. **[ADR-0011](adr/ADR-0011-canonical-environment-and-determinism.md) (Canonical Environment & Determinism):** Linux Docker container canonical for render/audio/PDF tests; Windows supported for non-render tests; `PYTHONHASHSEED=0`; visual mismatch policy (`PROPOSED`).
12. **[ADR-0012](adr/ADR-0012-test-architecture.md) (Test Architecture):** Pytest markers (`unit`, `integration`, `render`, `audio`, `network`), strict markers, 95% branch coverage floor for core, property-based testing (`PROPOSED`).
13. **[ADR-0013](adr/ADR-0013-delivery-strategy.md) (Delivery Strategy):** Walking skeleton established after S3 (CLI runs ingestion -> diagnostics -> basic text -> JSON manifest); S12 hardens rather than invents the orchestrator (`PROPOSED`).
14. **[ADR-0014](adr/ADR-0014-dependencies-and-supply-chain.md) (Dependencies & Supply Chain):** Explicit justification for direct dependencies, locked hashes (`uv.lock`), 14-day dependency aging rule, isolated external adapters (`PROPOSED`).
15. **[ADR-0015](adr/ADR-0015-data-classification-and-lifecycle.md) (Data Classification & Lifecycle):** Classification tiers, field-level data map (`docs/data_map.md`), D-13 retention lifecycle, automated purge jobs (`PROPOSED`).

---

## Operator-Approved Additions to Allowed Files
Per operator instructions for S0-R, Stage D, S0-R2, S0-R3, and S0-R4:
1. `scripts/guardrails.py`: Automated W3 & Foundation invariant checker (pre-commit hook).
2. `scripts/split_prompt_pack.py`: Prompt pack splitter script.
3. `.gitignore`: Virtualenv, cache, and artifact exclusions.
4. `.python-version`: Local Python interpreter pin (`3.12`).
5. `.gitattributes`: Line ending normalization (`* text=auto eol=lf`).
6. `docs/PRE_DEPLOYMENT_CHECKLIST.md`: Deferred compliance, legal review, and carrier registration tracking list.
7. `docs/research/provider_contract.json`: Machine-readable provider specifications, 73 classified error codes with `send_path` flags, rate limits, and webhook retry contracts for S9.
8. `docs/adr/**`: Architecture Decision Records index and ADR-0001 through ADR-0015 (all `PROPOSED`).
9. `docs/domain_glossary.md`: Canonical domain terms, English code identifiers, and Bolchal Hindi wording.
10. `docs/data_map.md`: Field-level privacy inventory, classification tiers, retention rules, and logging policies.
11. `.pre-commit-config.yaml`: Pre-commit configuration for ruff, mypy, secrets scanning, and guardrails.

---

## Stage S0-R4 Execution Evidence (Foundation Hardening)

### 1. Step 0 Preconditions
- **Network Access Status:** Active (verified via HTTP query to Meta developer platform on 2026-10-20).
- **Current Shell Date:** `2026-10-20 12:13:17 +05:30` (command: `Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"`).

### 2. Part A: Research Corrections
- **A1 Official Error-Code Re-Check:**
  - `130472`: Verified on official page table 10: Details: `"Message was not sent as part of an experiment."`, Solution: `"See Marketing Message Experiment."` Corrected in `provider_contract.json` (previously misdescribed as certificate error).
  - `131030`: Confirmed **absent** from official documentation and all 12 tables. Not added to contract.
  - `131037`: Verified: `"The business phone number used to send the request does not have an approved display name."`
  - `131048`: Verified: `"Message failed to send because there are restrictions on how many messages can be sent from this phone number. This may be because too many previous messages were blocked or flagged as spam."`
  - `131050`: Verified: `"Unable to deliver the message. This recipient has chosen to stop receiving marketing messages on WhatsApp from your business."`
  - `131055`: Verified: `"(#131055) Method not allowed. Only marketing template messages are supported."` (HTTP 400).
  - `131057`: Verified: `"Business Account is in maintenance mode."`
  - `131064`: Verified: `"Message failed to send because this account has reached its messaging limit due to template classification violations."`
  - `132068`: Verified: `"Flow is in blocked state."`
  - `132069`: Verified: `"Flow is in throttled state and 10 messages using this flow were already sent in the last hour."`
  - `134011`: Verified: `"Message failed to send because WhatsApp Payments terms of service acceptance is pending for this WhatsApp Business Account."`
  - Standalone recipient-not-on-allowlist code: Confirmed **absent** from official error-codes page.
- **A2 Send-Path Classification:**
  - Evaluated all 73 codes in `provider_contract.json`: **52 codes marked `send_path: true`**, **21 codes marked `send_path: false`** (phone registration/deregistration, template creation/management, flows, partner onboarding).
- **A3 R-11 Downgrade:**
  - Downgraded `R-11` from `HIGH` to `MEDIUM` in `docs/research/official_source_verification.md` because `131030` is absent from official docs and `130472` had historical discrepancies in prior reports.
  - Re-checked and confirmed all columns preserved (Retrieval Date, Volatility, Confidence, Evidence Basis, Key Findings, Uncertainty & Cadence).
- **A4 Graph API Versioning Lifecycle:**
  - Verified changelog: `v26.0` released July 29, 2026, availability marked TBD. Table 0 states: `"The latest Graph API version is: v26.0"`. No version newer than `v26.0` exists in the changelog.
  - Changelog row for `v21.0`: `v21.0 | October 2, 2024 | January 21, 2027`.
  - Stated lifecycle rule: `"Each version is guaranteed to operate for at least two years. A version will no longer be usable two years after the date that the subsequent version is released."`
  - Reworded conclusion: `v21.0` is past its two-year guarantee (which ended October 2, 2026) but, per the changelog table, remains usable until its stated end date of **January 21, 2027** (~93 days remaining). Any deployment after that date would break because retired versions fall back to the next oldest available version, risking breaking schema changes. Updated `DECISIONS_OPEN.md`. Pinned configuration (`v21.0`) strictly retained.

### 3. Part B: Foundation Hardening
- **B1 Architecture Decision Records:** Created `docs/adr/README.md` (status legend, index) and 15 ADR files (`ADR-0001` through `ADR-0015`). All ADRs marked `PROPOSED`; zero ADRs marked `ACCEPTED`.
- **B2 Domain Glossary:** Created `docs/domain_glossary.md` covering all academic, band, diagnostic, contact hygiene, quarantine, dispatch state, and error classification terms with English code identifiers and Bolchal Hindi wording.
- **B3 Data Inventory & Privacy Map:** Created `docs/data_map.md` categorizing all fields across 10 subsystems into PII classification tiers, business purpose, D-13 development retention defaults, logger redaction policy, and purge behavior.
- **B4 Tooling Configuration & Guardrails:**
  - `pyproject.toml`: Configured reasoned ruff ruleset (`E`, `F`, `W`, `I`, `B`, `C4`, `UP`, `SIM`, `T20`, `PT`, `RET`), mypy strict with documented overrides for third-party modules, pytest markers (`unit`, `integration`, `render`, `audio`, `network`), and `--strict-markers`.
  - `.pre-commit-config.yaml`: Configured hooks for ruff, ruff-format, mypy, detect-secrets, and guardrails.
  - `scripts/guardrails.py`: Extended with 4 new lint rules:
    1. `check_time_hygiene`: Bans naive datetime calls and `datetime.now()` without timezone in `src/`.
    2. `check_no_float_in_core`: Bans `float` annotations/conversions in core package (skips cleanly when core is absent).
    3. `check_os_environ_hygiene`: Bans `os.environ` / `os.getenv` reads outside settings module (skips cleanly when non-settings files are absent).
    4. `check_no_print_in_src`: Bans raw `print()` statements in `src/` (skips cleanly when files are absent).
- **B5 Stage Prompt Amendments:**
  - `S2.md`: Added marking-scheme data model (ADR-0004), `schema_version` (ADR-0006), `org_id` if confirmed (ADR-0003), and typed `Settings` object in `config.py` (ADR-0009).
  - `S3.md`: Mandated ADR-0002 numeric rules (integer marks, Fraction ratios, cross-multiplication) and added walking-skeleton CLI path as acceptance criterion (ADR-0013).
  - `S4.md`: Added ADR-0010 text rules (Unicode NFC, Latin digit policy `0-9`, grapheme-safe truncation).
  - `S8.md`: Mandated append-only `dispatch_events` with derived status, persist-intent-before-send, and DB unique constraints (ADR-0007).
  - `S12.md`: Clarified that S12 extends and completes the walking skeleton established in S3–S11 rather than creating the orchestrator from scratch (ADR-0013).
- **B6 Architecture Decisions Alignment:** Updated `docs/architecture_decisions.md` to align with ADR-0001 through ADR-0015, eliminating contradictions regarding numeric representation and event persistence.

### 4. Verification Commands & Execution Evidence
- JSON Contract Validation:
  - Command: `python -c "import json; json.load(open('docs/research/provider_contract.json', encoding='utf-8'))"`
  - Exit Code: `0`
- Linter Check:
  - Command: `ruff check .`
  - Exit Code: `0` (`All checks passed!`)
- Static Type Checker:
  - Command: `uv run mypy src`
  - Exit Code: `1` (`mypy: program not found` — dev extra not synced, nothing to check yet in `src/` except empty `__init__.py`).
- Pre-Commit Tool Check:
  - Command: `pre-commit --version`
  - Exit Code: `1` (`pre-commit: The term is not recognized` — pre-commit executable not installed globally on host, `.pre-commit-config.yaml` created per B4).
- Invariant & Foundation Guardrails Check:
  - Command: `python scripts/guardrails.py`
  - Exit Code: `0` (`[GUARDRAIL PASS] All pre-commit guardrails satisfied.`)
- Git Diff Scope Check:
  - Files modified strictly within SCOPE:
    - `A .pre-commit-config.yaml`
    - `M pyproject.toml`
    - `M scripts/guardrails.py`
    - `M docs/DECISIONS_OPEN.md`
    - `M docs/STATE.md`
    - `M docs/architecture_decisions.md`
    - `M docs/research/official_source_verification.md`
    - `M docs/research/provider_contract.json`
    - `M docs/prompt_pack/S2.md`
    - `M docs/prompt_pack/S3.md`
    - `M docs/prompt_pack/S4.md`
    - `M docs/prompt_pack/S8.md`
    - `M docs/prompt_pack/S12.md`
    - `A docs/domain_glossary.md`
    - `A docs/data_map.md`
    - `A docs/adr/**` (15 ADRs + README)

---

## Active Operator Decisions Awaiting Confirmation (`docs/DECISIONS_OPEN.md`)
1. **D-04:** PTM slip requirement for bottom quartile in all-GREEN batches (`OWNER-CONFIRM`).
2. **D-11:** Parent confirmation QR token TTL default 72h (`OWNER-CONFIRM`).
3. **D-11:** Primary guardian OTP challenge channel: WhatsApp Authentication Template vs Indian SMS (`OWNER-CONFIRM`).
4. **D-12:** Display of class topper score on parent-facing report card (`OWNER-CONFIRM`).
5. **D-09 / Architecture:** Pinned Meta Graph API Version Upgrade (`STALE v21.0` -> `v26.0` recommended; decision required prior to Stage S9) (`OWNER-CONFIRM`).
6. **ADR-0003:** Institutional Tenancy Scope: Include `org_id` across data models from inception vs single-school (`OWNER-CONFIRM`).
7. **ADR-0007:** Database Encryption at Rest: Host disk encryption for dev vs app-level SQLCipher (`OWNER-CONFIRM`).
8. **ADR-0010:** Script Digit Policy: Latin digits (`0-9`) vs Devanagari numerals (`०-९`) in Hindi parent copy (`OWNER-CONFIRM`).
