# Stage S0-R4 Independent Review Report

**Review Date:** 2026-10-20
**Reviewer:** Independent Reviewer Agent (Stage W2)
**Governing Rule:** `docs/prompt_pack/W2_review.md` and `AGENTS.md` Invariants
**Target Scope:** `git diff stage-0-r3..stage-0-r4` and working tree state (`git diff HEAD`)
**Commit Inspected:** `5e8377d43f206609c71ac4d2ed67bcd1f13f3ec9` (`tag: stage-0-r4`) on branch `agent-run`

---

## Executive Summary

| Check # | Check Topic | Status | Summary of Evidence |
| :---: | :--- | :---: | :--- |
| **1** | Scope Compliance | **PASS** | 30 files changed in git diff `stage-0-r3..stage-0-r4`. Zero changes in `src/`, `tests/`, or `fixtures/`. |
| **2** | Frozen Spec vs ADRs | **PASS** | Evaluated all 15 ADRs against D-01 through D-14. Zero contradictions found. |
| **3** | Stage Prompts vs ADRs | **PASS** | Prompt amendments are 1–3 lines each; no ADR contradicts prompts. S3 Gate 3 added walking skeleton acceptance criterion. |
| **4** | ADR Quality & Structure | **PASS** | All 15 ADRs have required sections and >=2 options. In git commit `5e8377d`, all ADRs were `PROPOSED`. |
| **5** | ADR-0002 Worked Examples | **FAIL** | 55/300, 80/300, 278/300, 90/300, 180/300 match exactly. Worked example for net of -75 is omitted (ADR provides net of -15 instead). |
| **6** | ADR-0003 / ADR-0007 Key & Persistence Rules | **PASS** | Idempotency keys avoid PII; `dispatch_events` is append-only with derived status; DB unique constraints defined; migrations start with first table. |
| **7** | ADR-0004 Marking Scheme Data Model | **PASS** | S1 golden test fixtures (+4/-1, 75 questions, single-correct) fit `QuestionMeta` without edits. |
| **8** | Part A: `provider_contract.json` Integrity | **PASS** | Valid JSON; all 73 codes have class, source URL, date, and `send_path`; `default_class` is `OUTCOME_UNKNOWN`; 0 RETRY_SAFE codes are 5xx/auth; all 10 re-checked codes quote official documentation. |
| **9** | Tooling & Guardrail Skips | **PASS** | `ruff` (exit code 0); `mypy` (exit code 1, missing executable); `pre-commit` (exit code 1, missing executable); `guardrails.py` (exit code 0, all 6 conditional checks skip cleanly). |
| **10** | Honesty & Claims Grounding | **FAIL** | R-11 confidence was downgraded to `MEDIUM` in master table and `STATE.md`, but line 18 summary and Section 11 line 301 still claim `HIGH`. |
| **11** | Working Tree Diff HEAD Review | **FAIL** | Operator modified status only in ADR-0003, ADR-0007, ADR-0010; but `docs/adr/README.md` was not updated and still lists them as `PROPOSED`, mismatching `docs/STATE.md`. |
| **12** | Independent Spec vs ADR & Prompt Comparison | **PASS** | Independently cross-compared D-01 to D-14 against all 15 ADRs and all 14 stage prompts (`S0`–`S13`). Zero contradictions found. |
| **13** | `DECISIONS_OPEN.md` Reference Resolution | **PASS** | Checklist item IDs `C-01`, `C-03`, `P-04` resolve in `docs/PRE_DEPLOYMENT_CHECKLIST.md`; all 8 cited ADRs resolve. |
| **14** | Operator Decisions Consistency (Items 1–4, 6–8) | **PASS** | All 7 operator decisions are consistent with related ADRs, specs, and golden fixture contracts. |

---

## Detailed Check Findings

### 1. Scope Check
* **Status:** **PASS**
* **Governing Rule:** Any file changed outside Stage S0-R4 allowed scope (`docs/adr`, `docs/domain_glossary.md`, `docs/data_map.md`, `docs/architecture_decisions.md`, `docs/research`, `DECISIONS_OPEN.md`, `STATE.md`, `docs/prompt_pack` amendments, `pyproject.toml` tool config, `.pre-commit-config.yaml`, `scripts/guardrails.py`) or any application code, fixture, or test modification = **FAIL**.
* **Evidence:**
  - Evaluated command: `git diff --name-status stage-0-r3..stage-0-r4`
  - Output files:
    - `.pre-commit-config.yaml` (`A`)
    - `docs/DECISIONS_OPEN.md` (`M`)
    - `docs/STATE.md` (`M`)
    - `docs/adr/ADR-0001-layering.md` (`A`)
    - `docs/adr/ADR-0002-numeric-semantics.md` (`A`)
    - `docs/adr/ADR-0003-identifiers-and-keys.md` (`A`)
    - `docs/adr/ADR-0004-marking-scheme-as-data.md` (`A`)
    - `docs/adr/ADR-0005-time-and-clocks.md` (`A`)
    - `docs/adr/ADR-0006-schema-and-contract-versioning.md` (`A`)
    - `docs/adr/ADR-0007-persistence-and-storage.md` (`A`)
    - `docs/adr/ADR-0008-errors-and-logging.md` (`A`)
    - `docs/adr/ADR-0009-configuration.md` (`A`)
    - `docs/adr/ADR-0010-text-and-unicode.md` (`A`)
    - `docs/adr/ADR-0011-canonical-environment-and-determinism.md` (`A`)
    - `docs/adr/ADR-0012-test-architecture.md` (`A`)
    - `docs/adr/ADR-0013-delivery-strategy.md` (`A`)
    - `docs/adr/ADR-0014-dependencies-and-supply-chain.md` (`A`)
    - `docs/adr/ADR-0015-data-classification-and-lifecycle.md` (`A`)
    - `docs/adr/README.md` (`A`)
    - `docs/architecture_decisions.md` (`M`)
    - `docs/data_map.md` (`A`)
    - `docs/domain_glossary.md` (`A`)
    - `docs/prompt_pack/S12.md` (`M`)
    - `docs/prompt_pack/S2.md` (`M`)
    - `docs/prompt_pack/S3.md` (`M`)
    - `docs/prompt_pack/S4.md` (`M`)
    - `docs/prompt_pack/S8.md` (`M`)
    - `docs/research/official_source_verification.md` (`M`)
    - `docs/research/provider_contract.json` (`M`)
    - `pyproject.toml` (`M`)
    - `scripts/guardrails.py` (`M`)
  - Verification: `git diff stage-0-r3..stage-0-r4 -- src/ tests/ fixtures/` returned 0 lines.
  - Working tree state: untracked file `docs/prompt_pack/W2_review.md` is this prompt file and expressly exempted.
  - Zero application code, zero fixtures, zero tests modified.

---

### 2. Frozen Spec Contradiction Check (ADRs vs. D-01 to D-14)
* **Status:** **PASS**
* **Governing Rule:** For EVERY ADR, identify and report any statement that contradicts a frozen decision in `PROJECT_SPEC.md` (D-01 to D-14), quoting both sides.
* **Evidence:**
  - Evaluated all 15 ADRs against `PROJECT_SPEC.md` clauses D-01 through D-14:
    1. **ADR-0001 (Layering):**
       - Spec D-06: *"Conversational Bolchal Hindi... Never claim lying, deliberate guessing, laziness, or psychological cause."*
       - ADR-0001 (line 32): *"hindi_templates: Conversational Bolchal Hindi copy assembly, vocabulary validation, parameter formatting."* (Aligned).
    2. **ADR-0002 (Numeric Semantics):**
       - Spec D-01: *"`< 30.0%` RED; `30.0%–60.0%` inclusive YELLOW; `> 60.0%` GREEN... negative nets are RED."*
       - ADR-0002 (lines 39–41): Cross-multiplication checks match D-01 boundaries exactly: `net * 100 < max_marks * 30` (RED); `30 * max <= net * 100 <= 60 * max` (YELLOW); `net * 100 > max * 60` (GREEN). (Aligned).
       - Spec D-02: *"`accuracy = correct among PRESENT / PRESENT count`; easy iff `accuracy >= 0.75` at full precision (exactly 0.75 qualifies)."*
       - ADR-0002 (line 42): *"`correct / present >= 75 / 100` $\iff$ `correct * 100 >= present * 75` (or `correct * 4 >= present * 3`)."* (Aligned).
       - Spec D-05: *"`gross = Σ positive marks of correct`; `bleed = Σ magnitude of negative marks of wrong`; `net = gross − bleed`; `percentage = net / max_positive_marks × 100`."*
       - ADR-0002 (lines 36–37): *"`gross: int`, `bleed: int`, `net: int = gross - bleed`. Percentage Ratio: `percentage_ratio = Fraction(net, max_positive_marks)`."* (Aligned).
    3. **ADR-0003 (Identifiers & Keys):**
       - Spec D-11: *"opaque random token, scoped to student/test/PTM event, stored hashed... single use"*
       - ADR-0003 (lines 32–36): *"`student_id`, `submission_id`, `dispatch_id`, `event_id` are 128-bit opaque UUIDs... Phone numbers, guardian names, tokens, and marks are never included in the idempotency key."* (Aligned).
    4. **ADR-0004 (Marking Scheme as Data):**
       - Spec D-14: *"test maximum configurable; golden exam is 300."*
       - ADR-0004 (lines 38–46): `positive_marks: int`, `negative_marks: int`, `question_type: QuestionType = QuestionType.SINGLE_CORRECT`. (Aligned).
    5. **ADR-0005 (Time & Clocks):**
       - Spec D-10: *"`Asia/Kolkata`. Primary: Sunday 20:30 IST... Monday 10:00 IST"*
       - ADR-0005 (lines 19–21): Storage in UTC, presentation and dispatch schedule in `Asia/Kolkata`. (Aligned).
    6. **ADR-0006 (Versioning):**
       - Spec D-13: *"Scans and reports: current academic year. Message/audit logs: 90 days, masked."*
       - ADR-0006 (lines 7, 19–23): Artifact `schema_version`, numbered SQL migrations. (Aligned).
    7. **ADR-0007 (Persistence Strategy):**
       - Spec D-09: *"Live dispatch disabled by default... Text/image template first"*
       - ADR-0007 (lines 20–25): SQLite WAL, append-only `dispatch_events`, persist intent before send. (Aligned).
       - Spec D-14: *"Up to 200 students per batch"*
       - ADR-0007 (line 9): *"batches of up to 200 students per batch (D-14)"*. (Aligned).
    8. **ADR-0008 (Errors & Logging):**
       - Spec D-02: *"If there are zero present students, no question is easy and batch average/topper are null."*
       - ADR-0008 (line 42): `ZeroPresentStudentsError`. (Aligned).
       - Spec D-06: *"Conversational Bolchal Hindi... Banned user-facing terms..."*
       - ADR-0008 (line 45): `BannedVocabularyError`. (Aligned).
    9. **ADR-0009 (Configuration):**
       - Spec D-09: *"Live dispatch disabled by default"*
       - ADR-0009 (lines 44–45): `live_dispatch_enabled: bool = Field(default=False)`. (Aligned).
       - Spec D-14: *"Up to 200 students per batch"*
       - ADR-0009 (line 51): `max_batch_size: int = Field(default=200)`. (Aligned).
    10. **ADR-0010 (Text & Unicode):**
        - Spec D-06: *"Conversational Bolchal Hindi for non-specialist parents... Always give denominators ('300 में से', 'N उपस्थित बच्चों में से')."*
        - ADR-0010 (lines 20–25, 34): Unicode NFC, grapheme-safe truncation, Latin digits (`0-9`) policy. (Aligned).
    11. **ADR-0011 (Canonical Environment):**
        - Spec D-07: *"Banner colours. RED `#D93025`, YELLOW `#F9AB00` (dark text), GREEN `#1E8E3E`, ABSENT `#5F6368`."*
        - Spec D-08: *"Audio. Primary mode `RECORDED_TOKEN_STITCH`... FFmpeg Opus"*
        - ADR-0011 (lines 20–23, 31–35): Pinned Linux Docker baseline for Chromium render and FFmpeg audio duration. (Aligned).
    12. **ADR-0012 (Test Architecture):**
        - Spec Part B: Strict mathematical and contract testing.
        - ADR-0012 (lines 19–25): Pytest strict markers, 95% branch coverage floor for core scoring and policy modules. (Aligned).
    13. **ADR-0013 (Delivery Strategy):**
        - Spec Product Boundary: Pipeline integrity across ingestion -> diagnostics -> templates -> provider.
        - ADR-0013 (lines 18–24): Walking skeleton delivery thread established post-S3. (Aligned).
    14. **ADR-0014 (Dependencies & Supply Chain):**
        - Spec Product Boundary: Permissive licensing and audited dependencies.
        - ADR-0014 (lines 30–44): Explicit justifications for Pydantic v2, Pillow, Playwright, ReportLab, etc. (Aligned).
    15. **ADR-0015 (Data Classification & Lifecycle):**
        - Spec D-13: *"Scans and reports: current academic year. Message/audit logs: 90 days, masked."*
        - ADR-0015 (lines 20–30): Three data tiers, `docs/data_map.md` registration, purge jobs. (Aligned).
  - **Result:** Zero contradictions found across all 15 ADRs.

---

### 3. Stage Prompts vs. ADRs & Prompt Amendment Limits
* **Status:** **PASS**
* **Governing Rule:** List any ADR that contradicts any stage prompt; verify that every prompt amendment stays within the few-line limit and does not alter existing acceptance criteria.
* **Evidence:**
  - Evaluated `git diff stage-0-r3..stage-0-r4 docs/prompt_pack/`:
    1. `docs/prompt_pack/S2.md` (lines 5, 8):
       - Amendment: Allowed files added `config.py` (+1 line). Task 1 amended (+3 lines) to reference `QuestionMeta` type (ADR-0004), `schema_version` (ADR-0006), `org_id` (ADR-0003), and `Settings` in `config.py` (ADR-0009).
       - Length: 3 lines. Acceptance criteria: unchanged.
    2. `docs/prompt_pack/S3.md` (lines 3, 11, 15):
       - Amendment: Allowed files added `cli.py (thin skeleton only)`. Task 2 amended (+2 lines) to specify ADR-0002 numeric rules (`int` marks, `Fraction` ratios, cross-multiplication). Gate 3 amended (+1 line).
       - Acceptance Criterion Addition: Gate 3 added: *"Walking skeleton acceptance criterion (ADR-0013): a thin CLI command runs golden fixture ingestion -> batch evaluation -> basic text -> structured JSON manifest."*
       - Analysis: An additional acceptance criterion was introduced to implement the walking skeleton from ADR-0013; all existing acceptance criteria for the 20 golden students and boundary classifier cases were preserved.
       - Length: 2 lines.
    3. `docs/prompt_pack/S4.md` (line 5):
       - Amendment: Task 1 amended (+1 line) specifying ADR-0010 text rules (Unicode NFC, Latin digits `0-9`, grapheme-safe truncation).
       - Length: 1 line. Acceptance criteria: unchanged.
    4. `docs/prompt_pack/S8.md` (line 7):
       - Amendment: Task 2 amended (+2 lines) specifying ADR-0007 persistence rules (append-only `dispatch_events` with derived status, persist intent before provider call, DB unique constraints).
       - Length: 2 lines. Acceptance criteria: unchanged.
    5. `docs/prompt_pack/S12.md` (line 6):
       - Amendment: Orchestrator description amended (+1 line) clarifying that S12 extends and completes the walking skeleton established in S3–S11 (ADR-0013).
       - Length: 1 line. Acceptance criteria: unchanged.
  - Zero ADRs contradict any stage prompt. All amendments are within the 1–3 line threshold.

---

### 4. ADR Quality & Status Review
* **Status:** **PASS**
* **Governing Rule:** Each ADR must have Context, Options (at least two), Proposed decision, Consequences, Revisit when; status values must be valid (`PROPOSED`, `ACCEPTED`, `SUPERSEDED`); any ADR marked `ACCEPTED` must have been accepted by the operator, not the agent.
* **Evidence:**
  - Automated inspection of all 15 files in `docs/adr/ADR-*.md`:
    - Context section present: 15/15
    - Options Considered present: 15/15 (ADR-0002 has 3 options; ADR-0001, ADR-0003–0015 each have 2 options)
    - Proposed Decision present: 15/15
    - Consequences present: 15/15
    - Revisit When present: 15/15
  - Git commit inspection (`5e8377d`):
    - Command: `git grep -n "ACCEPTED" 5e8377d -- "docs/adr/*.md"`
    - Output: Only `docs/adr/README.md:7` (in the legend). Zero ADRs were marked `ACCEPTED` by the agent in commit `5e8377d`.
  - Working tree uncommitted state (`git diff HEAD docs/adr/`):
    - Exactly 3 ADRs updated to `ACCEPTED` with explicit operator attribution and date:
      - `ADR-0003:4`: `` `ACCEPTED` (Accepted by operator, 2026-10-20. Tenancy decision recorded in `docs/DECISIONS_OPEN.md`, item 6.) ``
      - `ADR-0007:4`: `` `ACCEPTED` (Accepted by operator, 2026-10-20. Encryption decision recorded in `docs/DECISIONS_OPEN.md`, item 7.) ``
      - `ADR-0010:4`: `` `ACCEPTED` (Accepted by operator, 2026-10-20. Digit-style decision recorded in `docs/DECISIONS_OPEN.md`, item 8.) ``
    - All remaining 12 ADRs (0001, 0002, 0004, 0005, 0006, 0008, 0009, 0011, 0012, 0013, 0014, 0015) remain `PROPOSED`.

---

### 5. ADR-0002 Mathematical Recomputation
* **Status:** **FAIL**
* **Governing Rule:** Recompute 55/300, 80/300, 278/300, 90/300, 180/300, and a net of -75 with exact fractions and half-up rounding to one decimal place (`ROUND_HALF_UP`), and compare with ADR-0002 worked examples. Report any mismatch.
* **Evidence:**
  - Recomputation executed via Python standard library `fractions.Fraction` and `decimal.Decimal`:

| Case | Ratio | Exact Fraction | Exact Percentage | `ROUND_HALF_UP` 1-Dec String | ADR-0002 Example (Lines 47–75) | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **STU_01** | `55/300` | `Fraction(11, 60)` | `18.333333...%` | `"18.3%"` | `"18.3%"` (lines 47–52) | **MATCH** |
| **Boundary** | `80/300` | `Fraction(4, 15)` | `26.666666...%` | `"26.7%"` | `"26.7%"` (lines 53–57) | **MATCH** |
| **Topper** | `278/300` | `Fraction(139, 150)` | `92.666666...%` | `"92.7%"` | `"92.7%"` (lines 58–62) | **MATCH** |
| **Boundary 30%** | `90/300` | `Fraction(3, 10)` | `30.000000%` | `"30.0%"` | `"30.0%"` (lines 63–66) | **MATCH** |
| **Boundary 60%** | `180/300` | `Fraction(3, 5)` | `60.000000%` | `"60.0%"` | `"60.0%"` (lines 67–70) | **MATCH** |
| **Net of -75** | `-75/300` | `Fraction(-1, 4)` | `-25.000000%` | `"-25.0%"` | **Worked example 6 gives net of -15 (`"-5.0%"`), omitting net of -75** (lines 71–75) | **MISMATCH** |

* **Mismatch Details:**
  - In `docs/adr/ADR-0002-numeric-semantics.md`, lines 71–75: Worked Example 6 is titled: *"Negative Net Score (Gross 10, Bleed 25 -> Net -15 out of 300 marks):"* and calculates `"-5.0%"`.
  - The ADR omits the golden edge-fixture test case (S1 `edge_cases.json` line 42: *"an all-wrong student (net −75 → −25.00 %, RED)"* where 75 incorrect answers produce `net = -75` and `"-25.0%"`).
  - **Verdict:** **FAIL** due to the worked example omitting and mismatching the requested net of -75.

---

### 6. ADR-0003 & ADR-0007 Persistence and Idempotency Rules
* **Status:** **PASS**
* **Governing Rule:** Confirm whether idempotency keys avoid PII, dispatch events are append-only with derived status, DB-level uniqueness rules exist, and migrations start with the first table.
* **Evidence:**
  - **Idempotency Keys Avoid PII:**
    - ADR-0003 lines 22–23: `v1:{org_id}:{test_id}:{student_id}:{channel}:{purpose}:{sequence}`.
    - ADR-0003 lines 33–36: *"Strict Rule: Phone numbers, guardian names, tokens, and marks are never included in the idempotency key."*
  - **Dispatch Events Append-Only with Derived Status:**
    - ADR-0007 lines 22–23: *"State transitions are not in-place overwrites; they are written to an append-only `dispatch_events` table (`id`, `dispatch_id`, `event_type`, `payload`, `timestamp_utc`). The current status is derived from the latest event."*
    - ADR-0007 lines 47–57: DDL specifies `CREATE TABLE dispatch_events (...)`.
  - **DB-Level Uniqueness Rules:**
    - ADR-0007 line 41: `idempotency_key TEXT NOT NULL UNIQUE`.
    - ADR-0007 line 59: `CREATE UNIQUE INDEX idx_wamid_status_dedup ON dispatch_events(provider_wamid, event_type) WHERE provider_wamid IS NOT NULL;`.
  - **Migrations Start with the First Table:**
    - ADR-0006 lines 20, 39: Numbered linear SQL migrations starting from table 1 (`migrations/0001_initial_tables.sql`).
    - ADR-0006 line 40: `CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at_utc TEXT NOT NULL);`.

---

### 7. ADR-0004 Marking Scheme Data Model Compatibility
* **Status:** **PASS**
* **Governing Rule:** Confirm whether S1 golden fixtures (+4/-1, 75 questions) fit the marking-scheme data model without edits.
* **Evidence:**
  - ADR-0004 (lines 38–46) defines:
    ```python
    class QuestionMeta(BaseModel):
        id: int
        subject: str
        question_type: QuestionType = QuestionType.SINGLE_CORRECT
        correct_option: str
        positive_marks: int
        negative_marks: int
        bubble_coordinates: CoordinateMap | None = None
    ```
  - S1 Golden exam contract (`docs/prompt_pack/S1.md`, lines 7–8):
    - 75 questions, IDs 1–75 (`id: int`)
    - Q1–25 PHYSICS, Q26–50 CHEMISTRY, Q51–75 MATHS (`subject: str`)
    - Single-correct options: `["A","B","C","D"][(q-1) % 4]` (`correct_option: str`, `question_type: SINGLE_CORRECT`)
    - Marking weights: `+4` correct (`positive_marks = 4`), `-1` wrong (`negative_marks = 1`), `0` blank
    - Geometry: Synthetic 800×600 coordinates (`bubble_coordinates: CoordinateMap`)
  - The S1 golden fixtures fit the `QuestionMeta` data model completely without modifying the model schema or fixture values.

---

### 8. Part A: `provider_contract.json` Verification
* **Status:** **PASS**
* **Governing Rule:** `provider_contract.json` must parse as valid JSON; every error code must have `class`, `source_url`, `retrieval_date`, and `send_path`; `default_class` must be `OUTCOME_UNKNOWN`; no `RETRY_SAFE` code can be a 5xx or auth error; code `130472` and the other 9 re-checked codes must quote official documentation.
* **Evidence:**
  - JSON parsing: Validated via `python -c "import json; json.load(open('docs/research/provider_contract.json', encoding='utf-8'))"` (Exit code 0).
  - Code count: 73 total error codes in `error_codes`.
  - Completeness audit across all 73 codes:
    - `class`: 73/73 present
    - `source_url`: 73/73 present
    - `retrieval_date`: 73/73 present (`2026-10-20`)
    - `send_path`: 73/73 present (52 `true`, 21 `false`)
  - Default class: `default_class: "OUTCOME_UNKNOWN"` (top-level key).
  - `RETRY_SAFE` check: 4 codes (`4`, `80007`, `130429`, `131056`). None have HTTP 5xx (statuses are HTTP 400/429); none are auth errors.
  - Official quotation verification for 10 re-checked codes:
    1. `130472`: Quotes `"Message was not sent as part of an experiment. See Marketing Message Experiment."`
    2. `131037`: Quotes `"The 555 business phone number used to send the request does not have an approved display name..."`
    3. `131048`: Quotes `"Message failed to send because there are restrictions on how many messages can be sent from this phone number..."`
    4. `131050`: Quotes `"Unable to deliver the message. This recipient has chosen to stop receiving marketing messages on WhatsApp from your business..."`
    5. `131055`: Quotes `"(#131055) Method not allowed. Only marketing template messages are supported..."`
    6. `131057`: Quotes `"Business Account is in maintenance mode..."`
    7. `131064`: Quotes `"Message failed to send because this account has reached its messaging limit due to template classification violations..."`
    8. `132068`: Quotes `"Flow is in blocked state. Correct the Flow."`
    9. `132069`: Quotes `"Flow is in throttled state and 10 messages using this flow were already sent in the last hour. Correct the Flow."`
    10. `134011`: Quotes `"Message failed to send because WhatsApp Payments terms of service acceptance is pending for this WhatsApp Business Account..."`

---

### 9. Tooling & Guardrail Clean Skip Check
* **Status:** **PASS**
* **Governing Rule:** Run `ruff`, `mypy`, `pre-commit`, and `scripts/guardrails.py`; report actual exit codes. Verify that new foundation guardrail rules skip cleanly when target packages do not exist.
* **Evidence:**
  - **Tool 1 (`ruff check .`):**
    - Command: `ruff check .`
    - Exit Code: `0`
    - Output: `All checks passed!`
  - **Tool 2 (`mypy src`):**
    - Command: `mypy src` / `uv run mypy src`
    - Exit Code: `1`
    - Output: `error: Failed to spawn: mypy / program not found` (mypy is not installed in the global environment, documented in `docs/STATE.md`).
  - **Tool 3 (`pre-commit run --all-files`):**
    - Command: `pre-commit run --all-files`
    - Exit Code: `1`
    - Output: `pre-commit: The term is not recognized / program not found` (`.pre-commit-config.yaml` is configured per S0-R4; executable not installed on host, documented in `docs/STATE.md`).
  - **Tool 4 (`scripts/guardrails.py`):**
    - Command: `python scripts/guardrails.py`
    - Exit Code: `0`
    - Output:
      ```
      === Running W3 & Foundation Guardrails ===
      [FIXTURE GUARD] fixtures/golden/manifest.json not present yet (S1 pending) -> SKIPPED
      [TEST INTEGRITY] docs/.test_count_baseline not found -> SKIPPED (staged for S1)
      [TIME HYGIENE] No application source files in src/ yet -> SKIPPED
      [CORE NUMERICS] Core package not present yet -> SKIPPED (ADR-0002 staged)
      [ENV HYGIENE] No non-settings source files in src/ yet -> SKIPPED (ADR-0009 staged)
      [LOGGING HYGIENE] No application source files in src/ yet -> SKIPPED (ADR-0008 staged)
      [GUARDRAIL PASS] All pre-commit guardrails satisfied.
      ```
  - Clean Skip Verification: All 6 conditional checks skipped without raising errors or false failures when target files/modules are absent.

---

### 10. Honesty & Claims Grounding
* **Status:** **FAIL**
* **Governing Rule:** Flag any "verified", "compliant", or "HIGH" claim that lacks a cited page and date, or that contradicts the evidentiary record.
* **Evidence:**
  - Evaluated `docs/research/official_source_verification.md`:
    - All 17 rows cite exact URLs and retrieval date `2026-10-20`.
    - **Contradiction on R-11 Confidence:**
      - In `docs/STATE.md` (lines 73–74): `A3 R-11 Downgrade: Downgraded R-11 from HIGH to MEDIUM in docs/research/official_source_verification.md because 131030 is absent from official docs and 130472 had historical discrepancies in prior reports.`
      - In `docs/research/official_source_verification.md`:
        - Master table row R-11 (line 43) correctly records: `Confidence: MEDIUM`.
        - HOWEVER, in Section 15 "Row-Level Summary" (line 18), R-11 is still listed under `HIGH (12): R-01, R-02, R-04, R-05, R-06, R-07, R-09, R-10, R-11, R-12, R-14, R-15`.
        - In Section 11 "Detailed Findings by Topic" (line 301), the header states: `* Confidence: HIGH`.
    - **Finding:** Asserting `Confidence: HIGH` for R-11 in summary line 18 and section line 301 is an internal contradiction with the downgrade recorded in the master table (line 43) and in `docs/STATE.md`.
    - **Verdict:** **FAIL**.

---

### 11. Working Tree Uncommitted Edits Review
* **Status:** **FAIL**
* **Governing Rule:** Review `git diff HEAD` (uncommitted operator edits). Confirm the three ADRs (0003, 0007, 0010) were changed only in their Status section, that `README.md` and `STATE.md` match, and that no ADR other than 0003, 0007, and 0010 was marked `ACCEPTED`.
* **Evidence:**
  - Uncommitted modified files in working tree (`git status`):
    - `docs/DECISIONS_OPEN.md`
    - `docs/STATE.md`
    - `docs/adr/ADR-0003-identifiers-and-keys.md`
    - `docs/adr/ADR-0007-persistence-and-storage.md`
    - `docs/adr/ADR-0010-text-and-unicode.md`
  - ADR Status section review (`git diff HEAD docs/adr/`):
    - `ADR-0003`: Changed line 4 only to `ACCEPTED (Accepted by operator, 2026-10-20. Tenancy decision recorded in docs/DECISIONS_OPEN.md, item 6.)`.
    - `ADR-0007`: Changed line 4 only to `ACCEPTED (Accepted by operator, 2026-10-20. Encryption decision recorded in docs/DECISIONS_OPEN.md, item 7.)`.
    - `ADR-0010`: Changed line 4 only to `ACCEPTED (Accepted by operator, 2026-10-20. Digit-style decision recorded in docs/DECISIONS_OPEN.md, item 8.)`.
    - Zero other lines modified in these files.
  - Other ADRs ACCEPTED check:
    - Confirmed via `git grep -n "ACCEPTED" -- "docs/adr/*.md"` that no other ADR is marked `ACCEPTED`. All other 12 ADRs remain `PROPOSED`.
  - `docs/adr/README.md` vs `docs/STATE.md` match check:
    - In `docs/STATE.md` (lines 157–159):
      - `ADR-0003 (ACCEPTED)`
      - `ADR-0007 (ACCEPTED)`
      - `ADR-0010 (ACCEPTED)`
    - In `docs/adr/README.md` (lines 6, 18, 22, 25):
      - Line 6: `(All ADRs in this directory are currently PROPOSED).`
      - Line 18: `ADR-0003 ... PROPOSED`
      - Line 22: `ADR-0007 ... PROPOSED`
      - Line 25: `ADR-0010 ... PROPOSED`
    - **Finding:** `docs/adr/README.md` was not updated when the operator accepted ADR-0003, ADR-0007, and ADR-0010. Therefore, `docs/adr/README.md` and `docs/STATE.md` do NOT match.
    - **Verdict:** **FAIL**.

---

### 12. Independent Spec vs. ADR & Prompt Comparison
* **Status:** **PASS**
* **Governing Rule:** DECISIONS_OPEN.md Part 3 says "No contradictions found." Do NOT trust it. Independently compare `PROJECT_SPEC.md` D-01 to D-14 against each ADR and each stage prompt, and report every contradiction with both quotes. If you find none, list what you compared.
* **Evidence:**
  - Independently compared each specification clause D-01 through D-14 against all 15 ADRs and all 14 stage prompts:
    1. **D-01 (Status bands & Absent band):** Compared with ADR-0001 (line 30), ADR-0002 (lines 38–41), S1 (lines 28–36), S3 (lines 14–16), S4 (lines 7–9), S5 (line 9), S6 (line 8). All agree: RED `< 30.0%`, YELLOW `30.0%–60.0%` inclusive, GREEN `> 60.0%`, negative nets are RED; ABSENT has null score/rank/%, neutral grey `#5F6368`.
    2. **D-02 (Easy question accuracy):** Compared with ADR-0002 (line 42), ADR-0008 (line 42), S1 (line 38), S3 (lines 14–16). All agree: `accuracy = correct / present >= 0.75`; zero present -> no easy questions, null avg/topper.
    3. **D-03 (Subject diagnostic labels & priority ordering):** Compared with ADR-0002 (line 25), S1 (line 40), S3 (lines 14–16). All agree: 6 priority labels (`NO_ATTEMPT`, `ACCURACY_BLEED`, `CONCEPTUAL_SPEED_GAP`, `FOUNDATIONAL_CRISIS`, `MASTERY_ZONE`, `MODERATE_ZONE`).
    4. **D-04 (Rank & PTM slip criteria):** Compared with ADR-0002 (lines 7–8), DECISIONS_OPEN item 1 (lines 9–21), S1 (lines 28–38), S3 (lines 14–16). All agree: Standard competition rank `1 + count(higher)`; PTM slip iff ABSENT, RED, or `rank > floor(0.75 * present_count)`; bottom-quarter rule applies even if all students are GREEN.
    5. **D-05 (Scoring arithmetic):** Compared with ADR-0002 (lines 36–45), S1 (lines 7, 28–35), S3 (lines 11, 14–16), S4 (lines 7–9). All agree: `gross = Σ correct`, `bleed = Σ wrong`, `net = gross - bleed`, `percentage = net/max * 100`, full precision internally, 1 decimal display with `ROUND_HALF_UP`, `positive_marks_not_earned` for easy questions missed.
    6. **D-06 (Hindi wording & banned terms):** Compared with ADR-0001 (line 32), ADR-0008 (line 45), ADR-0010 (lines 7, 20–25), S4 (lines 7–9), S7 (line 6), `scripts/guardrails.py` (lines 43–50). All agree: Conversational Bolchal Hindi; banned terms: `ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, `औसत मान`; observable indicators only; denominators always printed.
    7. **D-07 (Banner colours):** Compared with ADR-0011 (line 31), S4 (line 5), S5 (line 8), S6 (line 8), `docs/domain_glossary.md` (lines 19–24). All agree: RED `#D93025`, YELLOW `#F9AB00`, GREEN `#1E8E3E`, ABSENT `#5F6368`.
    8. **D-08 (Audio duration & token stitching):** Compared with ADR-0002 (line 75), ADR-0008 (line 48), ADR-0011 (line 35), S7 (lines 6, 14–17). All agree: `RECORDED_TOKEN_STITCH` primary, `NETWORK_TTS` optional; target 15–25s, hard max 45s; overflow concise script; negative net uses recorded "minus" token.
    9. **D-09 (Messaging dispatch defaults):** Compared with ADR-0007 (line 23), ADR-0009 (lines 44–45), S0 (lines 11, 22), S8 (lines 4–9), S9 (line 6). All agree: Live dispatch disabled by default; text/image template first; audio only if verified.
    10. **D-10 (Scheduling):** Compared with ADR-0005 (lines 19–21), S8 (line 5), S10 (lines 5–7). All agree: `Asia/Kolkata` timezone; primary Sunday 20:30 IST; Monday 10:00 IST reminder only if `reminder_enabled = true`.
    11. **D-11 (QR Confirmation):** Compared with ADR-0003 (line 36), ADR-0005 (line 7), ADR-0007 (line 41), ADR-0009 (line 7), DECISIONS_OPEN items 2 & 3 (lines 24–49), S11 (lines 7–11). All agree: Disabled by default; opaque random token; 72h default TTL; single-use; <=5 attempts; HTTPS; guardian OTP via WhatsApp authentication template.
    12. **D-12 (Disclosure to parents):** Compared with ADR-0008 (line 22), ADR-0010 (line 24), DECISIONS_OPEN item 4 (lines 52–64), S1 (line 38), S4 (lines 7–9). All agree: Own child report + class average + topper score (default true) + rank X out of N present; no peer response data.
    13. **D-13 (Data retention):** Compared with ADR-0006 (lines 7, 22), ADR-0015 (lines 25–29), DECISIONS_OPEN item 9 (lines 136–141), S0 (line 21), S12 (line 8), `docs/PRE_DEPLOYMENT_CHECKLIST.md` items C-01 & C-03. All agree: Current academic year for scans/reports; 90 days masked for logs; deletion on verified request; statutory review deferred to pre-deployment checklist.
    14. **D-14 (Scale):** Compared with ADR-0007 (line 9), ADR-0009 (line 51), S1 (lines 7, 28–38). All agree: Up to 200 students per batch; golden exam is 300 marks.
  - **Result:** Zero contradictions found.

---

### 13. `DECISIONS_OPEN.md` Reference Resolution
* **Status:** **PASS**
* **Governing Rule:** Check that every checklist item ID cited in `DECISIONS_OPEN.md` (`C-01`, `C-03`, `P-04`) exists in `docs/PRE_DEPLOYMENT_CHECKLIST.md`, and that every ADR cited exists.
* **Evidence:**
  - Checklist item IDs cited in `docs/DECISIONS_OPEN.md`:
    - `C-01` cited in Section 9 (line 140) -> Resolves to `docs/PRE_DEPLOYMENT_CHECKLIST.md:13` (*"India DPDP Act & Rules Legal Review"*).
    - `C-03` cited in Section 9 (line 140) -> Resolves to `docs/PRE_DEPLOYMENT_CHECKLIST.md:15` (*"Data Retention Schedule Confirmation"*).
    - `P-04` cited in Section 7 (line 110) -> Resolves to `docs/PRE_DEPLOYMENT_CHECKLIST.md:27` (*"Signed Launch Checklist & Canary Rollout (W8)"*).
      - *Note on P-04:* Line 110 of `DECISIONS_OPEN.md` states: *"Application-level database encryption (SQLCipher) is formally deferred to the pre-deployment compliance checklist (`docs/PRE_DEPLOYMENT_CHECKLIST.md`, Item P-04)."* Item `P-04` exists in the checklist, but its text defines launch sign-off and canary rollout rather than explicit SQLCipher / database encryption requirements.
  - ADR references cited in `docs/DECISIONS_OPEN.md`:
    - `ADR-0002` (cited in Part 3, line 149) -> Resolves to `docs/adr/ADR-0002-numeric-semantics.md`.
    - `ADR-0003` (cited in Section 6, lines 92, 99) -> Resolves to `docs/adr/ADR-0003-identifiers-and-keys.md`.
    - `ADR-0005` (cited in Part 3, line 153) -> Resolves to `docs/adr/ADR-0005-time-and-clocks.md`.
    - `ADR-0007` (cited in Section 7, line 106, 114; Part 3, line 154) -> Resolves to `docs/adr/ADR-0007-persistence-and-storage.md`.
    - `ADR-0009` (cited in Part 3, line 153) -> Resolves to `docs/adr/ADR-0009-configuration.md`.
    - `ADR-0010` (cited in Section 8, line 120; Part 3, line 150) -> Resolves to `docs/adr/ADR-0010-text-and-unicode.md`.
    - `ADR-0011` (cited in Part 3, lines 151, 152) -> Resolves to `docs/adr/ADR-0011-canonical-environment-and-determinism.md`.
    - `ADR-0013` (cited in Section 5) -> Resolves to `docs/adr/ADR-0013-delivery-strategy.md`.
  - All cited references resolve to existing target identifiers and files.

---

### 14. Consistency of Operator Decisions (Items 1–4, 6–8)
* **Status:** **PASS**
* **Governing Rule:** Confirm each operator decision in `DECISIONS_OPEN.md` items 1–4 and 6–8 is consistent with the ADR or spec text it relates to.
* **Evidence:**
  1. **Item 1 (D-04 bottom-quarter rule in all-GREEN batches):**
     - Operator Decision (lines 17–20): Accept proposal; bottom-quarter rule applies even if whole batch is GREEN.
     - Consistency: Matches `PROJECT_SPEC.md` D-04 (`OWNER-CONFIRM: bottom-quarter rule applies even when a whole batch is GREEN`) and S1 golden fixtures.
  2. **Item 2 (D-11 QR token TTL):**
     - Operator Decision (lines 31–34): `QR_TOKEN_TTL_HOURS` defaults to 72 (min 12, max 168); QR confirmation stays disabled by default.
     - Consistency: Matches `PROJECT_SPEC.md` D-11 (`TTL default 72 h (OWNER-CONFIRM)`), ADR-0005, and ADR-0009.
  3. **Item 3 (D-11 Guardian OTP channel):**
     - Operator Decision (lines 45–48): WhatsApp authentication template is primary OTP channel; SMS adapter dormant.
     - Consistency: Matches `PROJECT_SPEC.md` D-11, ADR-0001, ADR-0008, and `PRE_DEPLOYMENT_CHECKLIST.md` item C-04.
  4. **Item 4 (D-12 Topper score disclosure):**
     - Operator Decision (lines 60–63): Show class topper score on parent report, controlled by `show_topper_score` (default true).
     - Consistency: Matches `PROJECT_SPEC.md` D-12 (`OWNER-CONFIRM: topper score may be shown`), S1 `expected_reports.json` (topper 278), and S4 prompt rules.
  5. **Item 6 (ADR-0003 Institutional tenancy scope):**
     - Operator Decision (lines 99–102): Single school for now, but include `org_id` with default value `"DEFAULT_INSTITUTION"` from the start across models, dispatch tables, and idempotency keys.
     - Consistency: Matches ADR-0003 composite idempotency key design (`v1:{org_id}:{test_id}:{student_id}:{channel}:{purpose}:{sequence}`), ADR-0007 DDL (`org_id TEXT NOT NULL`), and S2 Task 1.
  6. **Item 7 (ADR-0007 Database encryption at rest):**
     - Operator Decision (lines 113–116): Disk-level encryption for development (synthetic data only); app-level encryption deferred to pre-deployment checklist.
     - Consistency: Matches ADR-0007 lines 26 & 65.
  7. **Item 8 (ADR-0010 Script digit policy):**
     - Operator Decision (lines 127–130): Latin digits (`0-9`) in all parent-facing Hindi text, scorecards, and PTM slips.
     - Consistency: Matches ADR-0010 lines 24 & 34, S1 golden expected literals (`"18.33"`, `"92.67"`, `"30.00"`, `"60.00"`, `"26.67"`, `"0.00"`), and S4 prompt rules (`"300 में से 55 नंबर"`).

---

## Actionable Remediations for Operator

Before approving Gate 0 and unblocking Stage S1, the operator should address the three failed checks:

1. **Check 5 Remediation (ADR-0002):**
   - Add a worked example for the golden all-wrong edge fixture student (`net = -75 out of 300` -> `"-25.0%"`, Status Band RED) in `docs/adr/ADR-0002-numeric-semantics.md` lines 71–75 alongside or replacing the current net of -15 example.
2. **Check 10 Remediation (Honesty / R-11 Confidence):**
   - In `docs/research/official_source_verification.md`:
     - Line 18: Update distribution count to `HIGH (11)` (removing R-11) and `MEDIUM (4)` (adding R-11).
     - Line 301: Change `* Confidence: HIGH` to `* Confidence: MEDIUM` to match row R-11 of the master table and `docs/STATE.md`.
3. **Check 11 Remediation (ADR Index / README.md Alignment):**
   - In `docs/adr/README.md`:
     - Update lines 6, 18, 22, and 25 to reflect that ADR-0003, ADR-0007, and ADR-0010 have been `ACCEPTED` by the operator on 2026-10-20, so that `docs/adr/README.md` and `docs/STATE.md` match.
