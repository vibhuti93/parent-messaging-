# Stage S3 Run Review Report: Deterministic Diagnostics, Contact Hygiene & Walking Skeleton CLI

**Date:** 2026-10-28
**Stage:** S3 (Deterministic Diagnostics and Contact Hygiene)
**Target Package:** `omr_dispatch_engine` (`src/omr_dispatch/`)
**Status:** COMPLETE (Approved for Stage-3 Tagging)

---

## 1. Pre-Flight Verification Results

All pre-flight checks were executed before initiating Stage S3 implementation:

| Pre-Flight Step | Target / Invariant | Command Executed | Outcome / Evidence |
| :--- | :--- | :--- | :--- |
| **Stage Alignment** | `docs/CURRENT_STAGE` == `S3` | Read `docs/CURRENT_STAGE` | Verified: contains `S3\n` with LF normalized. |
| **Baseline Tests** | S1 & S2 passing baseline | `uv run --frozen pytest` | 73 passed in 0.35s (exit code 0). |
| **Pre-Flight Guardrails** | FAILED == 0 | `python scripts/guardrails.py` | `PASSED 11 / SKIPPED 0 / FAILED 0` (exit code 0). |
| **Frozen Fixtures Integrity** | Fixture hashes match manifest | Guardrail Check 6 | Verified: manifest SHA-256 match, zero tampering. |

---

## 2. Gate Execution Evidence

### Gate 1: Stage S3 Test Suite
**Command:** `uv run --frozen pytest -q tests/test_stage3_diagnostics_and_hygiene.py`
**Exit Code:** `0`
**Raw Output:**
```text
..........................................                               [100%]
42 passed in 0.81s
```

### Gate 2: Full Test Suite (Stage S1 + S2 + S3)
**Command:** `uv run --frozen pytest`
**Exit Code:** `0`
**Raw Output:**
```text
........................................................................ [ 62%]
...........................................                              [100%]
115 passed in 0.71s
```
*(31 Stage S1 golden contract tests + 42 Stage S2 ingestion tests + 42 Stage S3 diagnostics & hygiene tests = 115 total passing tests).*

### Gate 3: Linters and Type Checking
**Command:** `uv run ruff check .`
**Exit Code:** `0`
**Raw Output:**
```text
All checks passed!
```

**Command:** `uv run mypy src`
**Exit Code:** `0`
**Raw Output:**
```text
pyproject.toml: note: unused section(s): module = ['PIL.*', 'playwright.*', 'reportlab.*', 'weasyprint.*']
Success: no issues found in 7 source files
```

### Gate 4: Stage Guardrails Execution
**Command:** `python scripts/guardrails.py`
**Exit Code:** `0`
**Raw Output:**
```text
=== Running Guardrails (Current Stage: S3) ===
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

### Gate 5: Repository Boundary Check
**Command:** `git --no-pager status --porcelain`
**Exit Code:** `0`
**Raw Output:**
```text
 M docs/.test_count_baseline
 M docs/CURRENT_STAGE
 M src/omr_dispatch/__init__.py
 M src/omr_dispatch/models.py
?? docs/reviews/stage-3-run.md
?? src/omr_dispatch/cli.py
?? src/omr_dispatch/contacts.py
?? src/omr_dispatch/diagnostics.py
?? tests/test_stage3_diagnostics_and_hygiene.py
```
*(All created and modified files are strictly within the permitted set of Allowed Files).*

---

## 3. Mutation Testing Table ("Prove the Tests Can Fail")

Five deliberate mutations were applied, verified to fail corresponding tests or guardrails, and immediately reverted:

| Mutation | Description | Test / Guardrail That Caught It | Failure Evidence / Exception | Discarded |
| :--- | :--- | :--- | :--- | :--- |
| **1. Break Standard Competition Rank** | In `compute_standard_competition_ranks`, dropped `+ 1` offset: `rank = sum(...)` instead of `rank = 1 + sum(...)` | `tests/test_stage3_diagnostics_and_hygiene.py::TestDeterministicOMREvaluationGolden20::test_all_20_students_match_golden_literals` (and 8 other tests) | `AssertionError: STU_01 rank mismatch: assert 12 == 13` | Yes |
| **2. Inject Forbidden `float()` Call** | Added `_illegal_float = float(10)` in `format_percentage_display` in `diagnostics.py` | `python scripts/guardrails.py` under `check_no_float_in_core` | `[FAIL] Core Numerics Check: Function call 'float()' is forbidden in core package; use int, Fraction, or Decimal per ADR-0002` | Yes |
| **3. Coerce `NOT_AVAILABLE` to 0 in Marks Entry** | In `evaluate_marks_entry_totals_batch`, replaced `NOT_AVAILABLE` with `0` for `gross_marks`/`bleed_marks` | `TestMarksEntryTotalsEvaluation` tests and `test_cli_marks_entry_pipeline` | `pydantic_core.ValidationError: 2 validation errors for StudentDiagnosticReport: Input should be a valid string` | Yes |
| **4. Bypass Contact Quarantine** | Bypassed quarantine check by conditioning on `if False and is_quarantined:` in `contacts.py` | `TestContactHygieneAndAdmissionValidation::test_golden_admissions_300_matches_expected_contacts_exactly` (and 3 other tests) | `AssertionError: STU_02 eligibility mismatch: assert True == False` (quarantined contact marked dispatch eligible) | Yes |
| **5. Harden Mutation 3 (Semantic Catch vs Pydantic Validation)** | Mutated ONLY `easy_missed_question_ids` to `[]` (empty list) in `evaluate_marks_entry_totals_batch` while keeping `gross_marks=NOT_AVAILABLE`. Pydantic allows `[]` because `list[int] \| Literal["NOT_AVAILABLE"]` accepts `[]`. Proved that semantic test assertion catches the bug. | `tests/test_stage3_diagnostics_and_hygiene.py::TestMarksEntryTotalsEvaluation::test_not_available_sentinels_handling` | `AssertionError: assert [] == 'NOT_AVAILABLE'` (Line 796: `assert r.easy_missed_question_ids == NOT_AVAILABLE`) | Yes |

---

## 4. Implementation Details and Architecture

### 1. Contact Hygiene Engine (`src/omr_dispatch/contacts.py`):
- `normalize_indian_mobile_with_reason(raw) -> tuple[str | None, PhoneNormalizationReason]`: Strips spaces, hyphens, parentheses, and `+`. Rejects alphabetic/malformed inputs with recorded reasons (`MALFORMED_CHARACTERS`, `INVALID_LENGTH`, `INVALID_STARTING_DIGIT`, `EMPTY`). Drops 91 prefix on 12-digit numbers and trunk 0 on 11-digit numbers. Validates national format against `^[6-9]\d{9}$`.
- `normalize_indian_mobile(raw) -> str | None`: Clean public interface returning 10-digit national string or `None`.
- `mask_phone(phone)`: Masks phone numbers (e.g. `98*** **01`) to comply with Global Invariant 10 (never log raw phone numbers).
- `validate_admission_batch(rows, assessment_purpose, org_id)`:
  - Detects invalid guardian phone numbers (`INVALID_PHONE_NUMBER`).
  - Detects invalid student phone numbers when provided (`INVALID_STUDENT_PHONE_NUMBER`).
  - Flags interception risks when student and guardian share identical normalized numbers (`INTERCEPTION_RISK_SAME_NUMBER`).
  - Flags duplicate parent contacts across different students without verified sibling status (`DUPLICATE_PARENT_UNVERIFIED`).
  - Preserves verified siblings sharing numbers (`verified_sibling=True`).
  - Quarantine flags are deduplicated and sorted alphabetically.
  - Dispatch eligibility strictly requires non-quarantined status, non-revoked `OPT_IN` consent, and verified guardian verification.
  - Provides `manual_resolution_status = "PENDING_OPERATOR_REVIEW"` when quarantined; fail-closed safety gate prevents quarantine bypass.

### 2. Deterministic Evaluation Engine (`src/omr_dispatch/diagnostics.py`):
- **ADR-0002 Zero-Float Rule:** All computations use exact rational arithmetic (`fractions.Fraction`), integer cross-multiplication for threshold boundaries, and `Decimal` with explicit `ROUND_HALF_UP` for 1-decimal display formatting.
- **OMR MCQ Evaluation (`evaluate_omr_mcq_batch`):**
  - Item accuracy threshold: easy questions detected at `accuracy >= 0.75` (exact `correct * 4 >= present * 3`). Golden test paper detects exactly Q1–Q20.
  - Question-level student metrics: `attempted`, `correct`, `wrong`, `blank`, `gross_marks`, `bleed_marks`, `net_marks`.
  - Invariants: `attempted == correct + wrong`, `total_questions == attempted + blank`, `net == gross - bleed`, subject breakdown reconciles to totals.
  - Subject diagnostic labels (D-03): priority evaluation of `NO_ATTEMPT`, `ACCURACY_BLEED`, `CONCEPTUAL_SPEED_GAP`, `FOUNDATIONAL_CRISIS`, `MASTERY_ZONE`, `MODERATE_ZONE`.
- **Marks Entry Totals Evaluation (`evaluate_marks_entry_totals_batch`):**
  - Evaluates scores, percentages, standard competition rank (1224 ties), class average, topper score, and band.
  - Unavailable diagnostic dimensions (`gross_marks`, `bleed_marks`, `easy_missed_question_ids`, `positive_marks_not_earned`, `subject_diagnostics`) are set to literal `NOT_AVAILABLE` sentinel (never zero or empty list).
  - Handles half marks (e.g., 2.5 marks as `Fraction(5, 2)`) with full mathematical precision.
- **Multi-Subject Attendance & Partial Attendance (ADR-0016 Section 5 & S3 Task 3):**
  - Per-subject competition ranks computed among `PRESENT` students for each subject (`subject_ranks: dict[str, int | None]`).
  - Overall rank (`overall_rank`) is computed **only** when a student is `PRESENT` in all subjects.
  - If a student is `PRESENT` in one subject and `ABSENT` in another within the same assessment:
    - Attended subject receives valid subject rank.
    - Absent subject receives rank `None`.
    - `overall_rank` is `None` (the absent subject is NEVER treated as zero marks).
    - Missing any subject triggers PTM slip requirement (`requires_ptm_slip = True`).
- **Strict `Literal["NOT_AVAILABLE"]` Type Enforcement:**
  - `StudentDiagnosticReport` fields (`attempted`, `correct`, `wrong`, `blank`, `gross_marks`, `bleed_marks`, `net_marks`, `easy_missed_question_ids`, `positive_marks_not_earned`, `subject_diagnostics`, `subject_breakdown`) strictly use `Literal["NOT_AVAILABLE"]` (`NotAvailable`) rather than unconstrained `str`.
  - Arbitrary sentinel strings like `"N/A"` or `"ZERO"` are strictly rejected by Pydantic validation (verified in unit test `test_student_diagnostic_report_rejects_arbitrary_sentinel_strings`).
- **ABSENT Handling:** Absent students carry `None` for score, rank, and percentage; status band is `ABSENT`; subject diagnostics are `None`; `requires_ptm_slip = True`.
- **Zero-Present Cohort Safety:** Batches with zero present students avoid `ZeroDivisionError`, reporting `None` for class average and topper score.

### 3. Unified Facade & Separation of Concerns:
- `evaluate_batch(assessment, admissions, submissions, org_id) -> EvaluationBundle`: The single public entry point exported in `omr_dispatch/__init__.py`. Routes internally based on `assessment.kind` or capability structures (`OMR_MCQ` vs `MARKS_ENTRY_TOTALS`).
- `StudentDiagnosticReport`: Academic metrics are cleanly segregated from parent communication hygiene. Contact evaluation is encapsulated in the nested `contact_eligibility: ContactEvaluation | None = None` sub-structure, ensuring student diagnostic results are never commingled with phone/quarantine metadata.

### 4. Walking Skeleton CLI (`src/omr_dispatch/cli.py`):
- Implements ADR-0013 acceptance criterion: thin walking skeleton CLI command (`run-batch`).
- Dry run: ingests golden fixtures (`fixtures/golden/`), evaluates batch, outputs clean summary text to `sys.stdout` (zero `print()` calls per ADR-0008), and emits structured JSON `run_manifest.json`.
- Handles both `OMR_MCQ` and `MARKS_ENTRY_TOTALS`.

---

## 5. Files Changed

Strictly within Allowed Files Boundary:
1. `src/omr_dispatch/contacts.py` (New: phone normalization, admission quarantine engine)
2. `src/omr_dispatch/diagnostics.py` (New: deterministic evaluation, D-01 to D-05 scoring, ranking, multi-subject support, batch metrics)
3. `src/omr_dispatch/models.py` (Extended: Assessment, AssessmentKind, AssessmentPurpose, StatusBand, SubjectDiagnosticLabel, ContactQuarantineFlag, ContactEvaluation, StudentDiagnosticReport, BatchMetrics, EvaluationBundle, NOT_AVAILABLE, NotAvailable with strict `Literal["NOT_AVAILABLE"]`)
4. `src/omr_dispatch/cli.py` (New: walking skeleton CLI per ADR-0013)
5. `src/omr_dispatch/__init__.py` (Updated: re-exports of S3 domain functions, CLI, and models)
6. `tests/test_stage3_diagnostics_and_hygiene.py` (New: 42 tests covering golden dataset, boundaries, ties, zero-present, edge cases, invariants, multi-subject partial attendance, strict sentinel literal typing, and CLI)
7. `docs/.test_count_baseline` (Advanced: 73 -> 115)
8. `docs/reviews/stage-3-run.md` (This document)

---

## 6. Verification Summary & Audit Evidence

### Raw Command 1: `git --no-pager diff --name-only stage-2`
```text
docs/.test_count_baseline
docs/CURRENT_STAGE
src/omr_dispatch/__init__.py
src/omr_dispatch/models.py
```

### Raw Command 2: `git --no-pager status --porcelain`
```text
 M docs/.test_count_baseline
 M docs/CURRENT_STAGE
 M src/omr_dispatch/__init__.py
 M src/omr_dispatch/models.py
?? docs/reviews/stage-3-run.md
?? src/omr_dispatch/cli.py
?? src/omr_dispatch/contacts.py
?? src/omr_dispatch/diagnostics.py
?? tests/test_stage3_diagnostics_and_hygiene.py
```

### Raw Command 3: `python scripts/guardrails.py`
```text
=== Running Guardrails (Current Stage: S3) ===
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

### Raw Command 4: `uv run --frozen pytest -q`
```text
........................................................................ [ 62%]
...........................................                              [100%]
```
*(Total: 115 passed in 0.71s)*
