# Stage S2 Run Review Report: Input Contracts & Ingestion

**Date:** 2026-10-23
**Stage:** S2 (Input Contracts and Import)
**Target Package:** `omr_dispatch_engine` (`src/omr_dispatch/`)
**Status:** COMPLETE (Ready for Operator Ratification)

---

## 1. Pre-Flight Verification Results

All pre-flight checks were executed before initiating Stage S2 implementation. The exact commands, authorized operator actions, and outcomes are recorded below:

| Pre-Flight Step | Target / Invariant | Command Executed | Outcome / Evidence |
| :--- | :--- | :--- | :--- |
| **Clean Git State** | Clean working tree | `git --no-pager status --porcelain` | Printed nothing (clean state at start). |
| **Exact Tag** | Commit tagged `stage-1` | `git describe --tags --exact-match` | Initially failed because tag was unannotated on commit `7a07476`. Operator authorized running `git tag stage-1`. Exited 0 printing `stage-1`. |
| **Stage Alignment** | `docs/CURRENT_STAGE` == `S1` | Read `docs/CURRENT_STAGE` | Verified: contains `S1`. |
| **Manifest Checksum** | Signed Manifest in `docs/STATE.md` | SHA-256 calculation | `baa580ebd32a942998b0aca4c01624e5d29f34da658155f33b0b42025452867a` matches `fixtures/golden/manifest.json` exactly. |
| **Pre-Flight Guardrails** | FAILED == 0 | `python scripts\guardrails.py` | `PASSED 7 / SKIPPED 4 / FAILED 0` (after authorized patch to invoke `pytest --collect-only` via `sys.executable`/`uv run`). |
| **Golden Contract Suite** | S1 contract passes | `uv run --frozen pytest -q tests/test_stage1_golden_contract.py` | 31 passed in 0.21s (exit code 0). |

---

## 2. Gate Execution Evidence

### Gate 1: Stage S2 Ingestion Test Suite
**Command:** `uv run --frozen pytest -q tests/test_stage2_ingestion.py`
**Exit Code:** `0`
**Raw Output:**
```text
.........................................                                [100%]
41 passed in 0.57s
```

### Gate 2: Full Test Suite (Stage S1 + Stage S2)
**Command:** `uv run --frozen pytest tests/test_stage1_golden_contract.py tests/test_stage2_ingestion.py`
**Exit Code:** `0`
**Raw Output:**
```text
........................................................................ [100%]
72 passed in 0.48s
```
*(31 Stage S1 golden contract tests + 41 Stage S2 ingestion tests = 72 tests total).*

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
Success: no issues found in 4 source files
```

### Gate 4: Stage Guardrails Execution
**Command:** `python scripts\guardrails.py`
**Exit Code:** `0`
**Raw Output:**
```text
=== Running Guardrails (Current Stage: S1) ===
[TEST INTEGRITY] Updated baseline test count: 71 -> 72
  [PASS] Forbidden Patterns & Secrets
  [PASS] Hindi Integrity Check
  [PASS] State Hashes & Tags Check
  [PASS] Invariants Synchronization Check
  [PASS] Git Diff & Whitespace Check
  [PASS] Fixture Hash Validation
  [PASS] Test Count Integrity Check
  [SKIP] Time Hygiene Check (src/ application code staged for S2)
  [SKIP] Core Numerics Check (Core package staged for S2)
  [SKIP] Environment Hygiene Check (src/ application code staged for S2)
  [SKIP] Logging Hygiene Check (src/ application code staged for S2)

------------------------------------------------------------
PASSED 7 / SKIPPED 4 / FAILED 0
------------------------------------------------------------
```

#### Independent Verification of S2-Level Hygiene Rules (Without Editing `docs/CURRENT_STAGE`):
The four checks staged for S2 were directly executed via Python against the live codebase:
**Command:**
```powershell
python -c "import scripts.guardrails as g; print('Time:', g.check_time_hygiene(2)); print('Numerics:', g.check_no_float_in_core(2)); print('Env:', g.check_os_environ_hygiene(2)); print('Logging:', g.check_no_print_in_src(2))"
```
**Exit Code:** `0`
**Raw Output:**
```text
Time: ('PASSED', [])
Numerics: ('PASSED', [])
Env: ('PASSED', [])
Logging: ('PASSED', [])
```
- **Time Hygiene:** Zero calls to `datetime.now()` without explicit UTC timezone, `datetime.utcnow()`, or `datetime.today()`.
- **Core Numerics:** Zero `float` type annotations, return types, or `float(` constructor calls in core application code. Marks parsed directly to `fractions.Fraction`.
- **Environment Hygiene:** Zero access to `os.environ` or `os.getenv` outside `src/omr_dispatch/config.py`.
- **Logging Hygiene:** Zero raw `print(` statements in `src/`. Child names and class/section labels are never emitted to logs.

### Gate 5: Repository Boundary Check
**Command:** `git --no-pager diff --name-only stage-1`
**Exit Code:** `0`
**Raw Output:**
```text
docs/.test_count_baseline
scripts/guardrails.py
src/omr_dispatch/__init__.py
```

**Command:** `git --no-pager status --porcelain`
**Exit Code:** `0`
**Raw Output:**
```text
 M docs/.test_count_baseline
 M scripts/guardrails.py
 M src/omr_dispatch/__init__.py
?? docs/input_contracts.md
?? docs/reviews/stage-2-run.md
?? fixtures/ingestion/
?? src/omr_dispatch/config.py
?? src/omr_dispatch/ingestion.py
?? src/omr_dispatch/models.py
?? tests/test_stage2_ingestion.py
```
*(All modified and created files are strictly within the permitted set of Allowed Files).*

---

## 3. Mutation Testing Table ("Prove the Tests Can Fail")

Each required mutation was applied in a temporary scratch edit, verified to fail the relevant test, and immediately discarded:

| Mutation | Description | Test That Caught It | Failure Evidence / Exception | Discarded |
| :--- | :--- | :--- | :--- | :--- |
| **1. Change `<=` to `<` in `max_marks` check** | Changed `parsed_mark > detected_max_marks` to `parsed_mark >= detected_max_marks` | `tests/test_stage2_ingestion.py::test_marks_boundary_exact_max_marks_allowed` | `AssertionError: assert False is True` (error code: `MARK_EXCEEDS_MAX` for a student earning full marks `50` out of `50`) | Yes |
| **2. Remove blank-marks rejection** | Replaced `PRESENT_WITH_BLANK_MARKS` check with `pass` | `tests/test_stage2_ingestion.py::test_rejection_marks_present_blank` | `AssertionError: assert True is False` (import succeeded with records populated instead of failing) | Yes |
| **3. Parse marks through `float`** | Changed `Fraction(val)` to `Fraction(float(val))` | `scripts.guardrails.check_no_float_in_core(2)` and `test_marks_parsing_rejects_float_input` | `('FAILED', ["[src/omr_dispatch/models.py] [CORE NUMERICS] Function call 'float()' is forbidden in core package; use int, Fraction, or Decimal per ADR-0002"])` | Yes |
| **4. Remove duplicate-row detection** | Commented out `roll_str in seen_rolls` check in `import_marks_entry` | `tests/test_stage2_ingestion.py::test_rejection_marks_duplicate_roll` | `AssertionError: assert True is False` (duplicate roll import succeeded with records populated) | Yes |
| **5. Remove `org_id` equality check** | Commented out tenant equality comparison in `import_answer_key` | `tests/test_stage2_ingestion.py::test_rejection_org_id_mismatch` & `test_org_id_mismatch_across_all_importers` | `AssertionError: assert False` (`ORG_ID_MISMATCH` was not emitted when mismatched org was passed) | Yes |

---

## 4. Files Created and Modified

### Allowed Files Created / Updated:
1. `src/omr_dispatch/config.py`:
   - Central typed `Settings` model using Pydantic v2 with `extra="forbid"`.
   - Credentials wrapped in `SecretStr` to prevent leak in logs/repr.
   - Safe-by-default production switches: `live_dispatch_enabled=False`, `deployment_compliance_acknowledged=False`, `include_roll_in_text=False`.
2. `src/omr_dispatch/models.py`:
   - Strict Pydantic models with `extra="forbid"`, `org_id: str`, and `schema_version: int`.
   - `parse_marks_decimal`: parses directly from decimal text as exact `fractions.Fraction`; enforces whole or half marks (`denominator in (1, 2)`); rejects exponents, signs, commas, Devanagari numerals, NaN/inf, and blanks.
   - Models: `QuestionMeta` (SINGLE_CORRECT enforced per ADR-0004; all others raise `NotSupportedError`), `TestPaper`, `StudentAdmissionRow`, `StudentRoster`, `ScanProvenance`, `StudentOMRSubmission`, `OMRSubmissionsBatch`, `MarksEntryRow`, `MarksEntrySheet`, `ImportResult[T]`, and `IngestionErrorDetail`.
3. `src/omr_dispatch/ingestion.py`:
   - Full importers: `import_roster`, `import_answer_key`, `import_test_paper`, `import_submissions`, `import_marks_entry`, `import_marks_entry_sheet`.
   - Atomic all-or-nothing guarantee: any error returns `records=None` and structured `errors`.
   - Explicit required `org_id` parameter; rejects mismatched files.
   - Built-in zero-dependency Excel parser using stdlib `zipfile` and `xml.etree.ElementTree`.
4. `src/omr_dispatch/__init__.py`:
   - Clean re-exports of models, settings, and importers.
5. `docs/input_contracts.md`:
   - Comprehensive input specifications for decoded OMR, roster, answer keys, and manual marks sheets.
   - Explicit scope statement: OMR bubble detection and computer vision are out of scope.
   - Documentation of all 20 `IngestionReasonCode` values.
6. `tests/test_stage2_ingestion.py`:
   - 41 tests verifying golden fixtures, exact fraction arithmetic, rejection paths, no partial imports, tenant isolation, zero-dependency Excel parsing, and settings security hygiene.
7. `fixtures/ingestion/**`:
   - 22 isolated bad-input fixtures testing every single rejection path.
8. `docs/reviews/stage-2-run.md`:
   - This comprehensive review document.

---

## 5. Assumptions Made for Operator Ratification

1. **`IngestionReasonCode` Enum:**
   Defined 20 stable, machine-readable reason codes grouped by domain:
   - File & Structure: `CORRUPTED_FILE`, `UNKNOWN_COLUMN`, `MISSING_REQUIRED_FIELD`, `ORG_ID_MISMATCH`
   - Identifier & Uniqueness: `DUPLICATE_ID`, `DUPLICATE_ROW`, `UNKNOWN_ROLL_NUMBER`
   - Examination & Question: `UNSUPPORTED_QUESTION_TYPE`, `INVALID_OPTION`, `OUT_OF_RANGE_QUESTION_ID`
   - Attendance & Record Completeness: `INVALID_ATTENDANCE_STATUS`, `MISSING_RECORD`
   - Marks Semantics & Bounds: `PRESENT_WITH_BLANK_MARKS`, `ABSENT_WITH_MARKS`, `INVALID_MARK_FORMAT`, `FRACTIONAL_MARK_NOT_HALF`, `INVALID_MARK_VALUE`, `MARK_BELOW_ZERO`, `MARK_EXCEEDS_MAX`, `INCONSISTENT_MAX_MARKS`
2. **Zero-Dependency `.xlsx` Ingestion:**
   Per Hard Rule 1, `pyproject.toml` could not be modified to add `openpyxl`. We implemented an exact XML parser over `.xlsx` zip archives using Python stdlib (`zipfile` and `xml.etree.ElementTree`) to support Excel marks sheets out-of-the-box.
3. **Multi-Tenant Roster Fixture Format:**
   `fixtures/golden/isolation_two_orgs.json` is organized as a nested dictionary keyed by org (`org_alpha`, `org_beta`). `import_roster` extracts the matching organization's slice when called with the respective `org_id`, failing closed if the requested tenant is absent.

---

## 6. Anything Added That S2.md Did Not Ask For

- Added stdlib `.xlsx` support in `ingestion.py` to allow teachers to supply Excel sheets directly without requiring external pip packages.
- Added explicit boundary condition test (`test_marks_boundary_exact_max_marks_allowed`) to guarantee that obtaining exactly `max_marks` (e.g. 50/50) is allowed and not rejected.

---

## 7. Operator Decisions Needed

1. **Ratification of `IngestionReasonCode`:**
   Operator is requested to review and ratify the 20 stable error codes documented in `docs/input_contracts.md`.
2. **Excel Parser Strategy for Future Stages:**
   Confirm whether the stdlib `.xlsx` parser is sufficient for production or if `openpyxl` should be authorized in `pyproject.toml` during later integration stages.
3. **Stage S3 Gate Advance:**
   Stage S2 is complete with 72 passing tests. All global invariants remain satisfied. Ready to advance to Stage S3 upon operator instruction.
