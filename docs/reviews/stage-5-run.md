# Stage S5 Run Review Report: OMR Proof Strip and Scan Provenance

**Date:** 2026-10-28
**Stage:** S5 (OMR Proof Strip and Scan Provenance)
**Target Package:** `omr_dispatch_engine` (`src/omr_dispatch/`)
**Status:** COMPLETE (Gate 5 Passed; Pending Operator Sign-Off)

---

## 1. Pre-Flight Verification Results

All pre-flight checks were executed before initiating Stage S5 implementation:

| Pre-Flight Step | Target / Invariant | Command Executed | Outcome / Evidence |
| :--- | :--- | :--- | :--- |
| **Stage Alignment** | `docs/CURRENT_STAGE` == `S5` | Read `docs/CURRENT_STAGE` | Verified: contains `S5\n` with LF normalized. |
| **Git Tag Base** | Base tag is `stage-4` | `git describe --tags --exact-match` | Resolved: `stage-4` (exit code 0). |
| **Baseline Tests** | S1-S4 passing baseline (140 tests) | `uv run --frozen pytest` | 140 passed in 1.59s (exit code 0). |
| **Pre-Flight Guardrails** | FAILED == 0 | `python scripts/guardrails.py` | `PASSED 11 / SKIPPED 0 / FAILED 0` (exit code 0). |
| **Frozen Fixtures Integrity** | Fixture hashes match manifest | Guardrail Check 6 | Verified: manifest SHA-256 `baa580ebd32a942998b0aca4c01624e5d29f34da658155f33b0b42025452867a` matches, zero tampering. |

---

## 2. Gate Execution Evidence

### Gate 1: Stage S5 Test Suite
**Command:** `uv run --frozen pytest -q tests/test_stage5_omr_proof.py`
**Exit Code:** `0`
**Raw Output:**
```text
.................                                                        [100%]
17 passed in 1.47s
```

### Gate 2: Full Test Suite (Stages S1 + S2 + S3 + S4 + S5)
**Command:** `uv run --frozen pytest`
**Exit Code:** `0`
**Raw Output:**
```text
........................................................................ [ 45%]
........................................................................ [ 91%]
.............                                                            [100%]
157 passed in 1.44s
```
*(31 Stage S1 golden contract tests + 42 Stage S2 ingestion tests + 42 Stage S3 diagnostics & hygiene tests + 25 Stage S4 Hindi template tests + 17 Stage S5 OMR proof tests = 157 total passing tests).*

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
pyproject.toml: note: unused section(s): module = ['playwright.*', 'reportlab.*', 'weasyprint.*']
Success: no issues found in 10 source files
```

### Gate 4: Stage Guardrails Execution
**Command:** `python scripts/guardrails.py`
**Exit Code:** `0`
**Raw Output:**
```text
=== Running Guardrails (Current Stage: S5) ===
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
**Command:** `git --no-pager diff --name-only stage-4`
**Exit Code:** `0`
**Raw Output:**
```text
docs/.test_count_baseline
docs/CURRENT_STAGE
docs/STATE.md
src/omr_dispatch/__init__.py
```

**Command:** `git --no-pager status --porcelain`
**Exit Code:** `0`
**Raw Output:**
```text
 M docs/.test_count_baseline
 M docs/CURRENT_STAGE
 M docs/STATE.md
 M src/omr_dispatch/__init__.py
?? docs/reviews/stage-5-run.md
?? src/omr_dispatch/omr_proof.py
?? tests/test_stage5_omr_proof.py
```
*(All created and modified files are strictly within the permitted set of Allowed Files per `S5.md`).*

---

## 3. Mutation Testing Table ("Prove the Tests Can Fail")

Four deliberate mutations were applied to `src/omr_dispatch/omr_proof.py`, verified to fail corresponding tests with exact assertion errors, and immediately reverted:

| Mutation | Description | Test That Caught It | Failure Evidence / Exception | Discarded & Reverted |
| :--- | :--- | :--- | :--- | :--- |
| **1. Subtract crop offset twice (`y - 2 * crop_top`)** | Mutated `cy = opt_pos["y"] - c_top` to `cy = opt_pos["y"] - 2 * c_top` | `tests/test_stage5_omr_proof.py::test_q1_correct_response_green_pixels_at_65_25` | `AssertionError: Expected green (#1E8E3E) pixels at/around cropped coordinate (65, 25)\nassert 0 > 0\n+ where 0 = len([])` | Yes |
| **2. Mutate source image in-place** | Mutated input image buffer via `actual_source.putpixel((0,0), (99,99,99))` instead of calling `.copy()` | `tests/test_stage5_omr_proof.py::test_source_immutability_disk_and_memory` | `AssertionError: Input PIL Image pixel buffer was mutated in place!\nassert b'\xff\xff\xf...f\xff\xff\xff' == b'ccc\xff\xff...f\xff\xff\xff'\nAt index 0 diff: b'\xff' != b'c'` | Yes |
| **3. Bypass low-confidence threshold check** | Bypassed `parsed_conf < min_conf_frac` check to allow processing to continue | `tests/test_stage5_omr_proof.py::test_fail_closed_low_alignment_confidence_exact_rational` | `AssertionError: assert <ProofStatus.SUCCESS: 'SUCCESS'> == <ProofStatus.REVIEW_REQUIRED: 'REVIEW_REQUIRED'>\n- REVIEW_REQUIRED\n+ SUCCESS` | Yes |
| **4. Alter green `#1E8E3E` RGB constant to `(0, 255, 0)`** | Mutated `COLOR_CORRECT = (0, 255, 0)` in `omr_proof.py` (leaving `HEX_COLOR_CORRECT` untouched) | `tests/test_stage5_omr_proof.py::test_q1_correct_response_green_pixels_at_65_25` | `AssertionError: Expected green (#1E8E3E) pixels at/around cropped coordinate (65, 25)\nassert 0 > 0\n+ where 0 = len([])` (also failed in `test_stu_01_q11...` and `test_legend_presence_verification`) | Yes |

---

## 4. Implementation Details and Architecture

### 1. Proof Strip Generator & Provenance (`src/omr_dispatch/omr_proof.py`)
- **`generate_omr_proof` Function:** Pure Python/Pillow adapter accepting a scan (`str | Path | bytes | Image.Image`), `StudentOMRSubmission`, `list[QuestionMeta]`, and `CoordinateMap`.
- **Scan Provenance (`ProofProvenance` & `TransformRecord`):** Records:
  - Exact SHA-256 hex digest of the original source scan bytes (`source_sha256`).
  - Source reference (`source_ref`), original image dimensions `(width, height)`, `processing_version` (`"1.0.0"`), `coordinate_map_version` (`1`), ISO UTC timestamp (ADR-0005).
  - An ordered list of transforms applied (`TransformRecord` recording crop box and offsets).
- **Transform Discipline:** Applies crop offsets `(crop_left, crop_top, crop_right, crop_bottom)` **exactly once** (`cropped_x = source_x - crop_left`, `cropped_y = source_y - crop_top`). Strictly prohibits silent rescaling or resizing.

### 2. Fail-Closed Validation (`REVIEW_REQUIRED`)
Returns structured `OMRProofResult` with `status=ProofStatus.REVIEW_REQUIRED` (and explicit machine-readable `ProofReasonCode`) under all adverse conditions:
- `MISSING_COORDINATE_MAP` / `MISSING_QUESTION_COORDINATES`: Missing or incomplete question/option coordinates.
- `CORRUPT_IMAGE` / `UNREADABLE_IMAGE`: Corrupted or non-image bytes.
- `MISSING_SCAN_FILE`: Missing scan file on disk for a `PRESENT` student.
- `DIMENSION_MISMATCH`: Image dimensions do not match expected `(800, 600)`. Fails closed without silent rescaling.
- `INVALID_CROP_BOX`: Crop boundaries out of bounds or negative dimensions.
- `COORDINATE_OUT_OF_BOUNDS`: Bubble coordinates falling outside the source dimensions `(800, 600)` or outside the cropped proof region `(0, 230, 800, 600)`.
- `LOW_ALIGNMENT_CONFIDENCE`: Alignment confidence below minimum threshold (`Fraction(95, 100)`), evaluated using exact `Fraction` rational comparisons (ADR-0002).

### 3. Non-Destructive Pillow Overlay & Visual Legend
- **Source Immutability:** Always opens or copies the input image in memory via `.copy()`. Disk files and input PIL Image objects are verified byte-for-byte unchanged.
- **Visual Annotations:**
  - **Correct response:** Green ring/check using exact hex `#1E8E3E` — RGB `(30, 142, 62)` — around/at the selected bubble centre.
  - **Wrong response:** Red cross using exact hex `#D93025` — RGB `(217, 48, 37)` — on the student's selected bubble, plus a green outline (`#1E8E3E`) on the correct answer-key bubble when `outline_correct_on_wrong=True`.
  - **Blank easy question:** Amber outline using exact hex `#F9AB00` — RGB `(249, 171, 0)` — on the answer-key bubble.
  - **Blank non-easy question:** Left clean without error annotations.
- **Deterministic Legend:** Renders outside the mapped question bubbles (`y=310`, safely below row 14 which ends at `y=269`), displaying Correct, Wrong, and Blank Easy indicators.

### 4. ABSENT & Signature Integrity
- **ABSENT Student:** Returns `ProofStatus.ABSENT_NO_PROOF` with `proof_image=None`, `proof_bytes=None`. Strictly generates no replacement sheet.
- **Signature Pixel Integrity:** Existing signature pixels in the source scan are preserved byte-for-byte in the output. No synthetic signatures are generated in production paths (Invariant 11).

### 5. Synthetic Geometry Specification
Matches the exact geometry contract:
- Source dimensions: `800×600`
- Crop box: `(0, 230, 800, 600)` $\rightarrow$ Output dimensions: `800×370`
- `Q1` option bubble centre at `(65, 255)` in source $\rightarrow$ maps to `(65, 25)` in the `800×370` cropped output.
- `STU_01` `Q11` selected bubble (option `D`) at `(137, 425)` in source $\rightarrow$ maps to `(137, 195)` in the `800×370` cropped output.

---

## 5. Summary of Changed Files

1. `src/omr_dispatch/omr_proof.py` (New file: 648 lines)
2. `src/omr_dispatch/__init__.py` (Re-exports of public S5 symbols)
3. `tests/test_stage5_omr_proof.py` (New file: 761 lines, 17 unit tests)
4. `docs/.test_count_baseline` (Updated: 140 -> 157)
5. `docs/CURRENT_STAGE` (`S5`)
6. `docs/STATE.md` (Updated state log with S5 execution evidence)
7. `docs/reviews/stage-5-run.md` (Stage S5 execution report)

---

## 6. Handover Note & Next Stage Readiness

- Stage S5 implementation and test verification are complete.
- All 157 repository tests pass cleanly.
- `ruff check .`, `mypy src`, and `scripts/guardrails.py` pass with zero warnings and zero errors.
- Per Process Invariant 1 and AGENTS.md, execution is stopped here at Stage S5. The `stage-5` git tag will be applied only upon operator review and authorization.
