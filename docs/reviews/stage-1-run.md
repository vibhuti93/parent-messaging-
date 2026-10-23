# Stage S1 Execution & Remediation Report (`docs/reviews/stage-1-run.md`)

## 1. Pre-Flight Verification & Git Provenance

### Git Provenance & Base State
#### Toolchain Provenance & Base State
- **`git rev-parse HEAD`:** `d697cbd1aee3dd2eba496618c7ddf296c96116d2`
- **`python --version`:** `Python 3.12.1`
- **`pytest --version`:** `pytest 8.4.2`
- **`uv.lock` SHA-256:** `221856687dea5137bca16da278b46aebdfd8146573b05237de53720472f0a846`

In earlier stage runs, it was asserted that HEAD was positioned strictly at tag `stage-0-r7`. Following operator instructions, a docs-only commit (`270214a`) was applied directly on top of `stage-0-r7` to formalize ADR decisions (ADR-0003 multi-tenant amendment accepted, ADR-0016 Section 4 universal PTM eligibility, and ADR-0008/ADR-0018 Invariant 17 logging discipline).

#### `git rev-parse HEAD`
```text
270214a71cf5c4d864e391687767e786b3cc024a
```
Exit code: `0`

#### `git log -n 6 --oneline --decorate`
```text
270214a (HEAD -> agent-run) docs(adr): accept ADRs, update ADR-0016 PTM eligibility, and enforce Invariant 17 logging discipline
6464ff5 (tag: stage-0-r7) S0-R7: operator decisions for S1-BLOCK items; accept ADR-0002/0003/0016
9b5b1e1 docs(reviews): trim trailing whitespace in historical review markdown per operator decision
4c63264 docs(stage-0-r7): fix review findings F1-F10 and strengthen verification tooling
7c61380 chore(deps): update uv.lock with dev dependencies
f0e0fa2 chore(deps): add mypy and pre-commit dev dependencies
```
Exit code: `0`

### Pre-Flight Verification Table

| Check | Command / Assertion | Actual Result | Status |
| :--- | :--- | :--- | :--- |
| Clean status | `git status --porcelain` | Clean / zero tracked modifications | **PASS** |
| Base commit check | `git rev-parse HEAD` | `270214a71cf5c4d864e391687767e786b3cc024a` (Docs-only ADR commit directly above `stage-0-r7`) | **PASS** |
| Unblock check | `Select-String -Path docs\prompt_pack\S1.md -Pattern "BLOCKED until" -CaseSensitive` | Zero matches / empty output | **PASS** |
| Decision check | All six S1-BLOCK items in `docs/DECISIONS_OPEN.md` say DECIDED | S1-BLOCK-01 through S1-BLOCK-06 all marked `DECIDED (Option 1, 2026-10-21, operator)` | **PASS** |
| Guardrails check | `python scripts\guardrails.py` | `PASSED 5 / SKIPPED 6 / FAILED 0` (Exit code: `0`) | **PASS** |

#### Raw Guardrails Output (`python scripts/guardrails.py`)
```text
=== Running Guardrails (Current Stage: S0) ===
  [PASS] Forbidden Patterns & Secrets
  [PASS] Hindi Integrity Check
  [PASS] State Hashes & Tags Check
  [PASS] Invariants Synchronization Check
  [PASS] Git Diff & Whitespace Check
  [SKIP] Fixture Hash Validation (fixtures/golden/manifest.json staged for S1)
  [SKIP] Test Count Integrity Check (docs/.test_count_baseline staged for S1)
  [SKIP] Time Hygiene Check (src/ application code staged for S2)
  [SKIP] Core Numerics Check (Core package staged for S2)
  [SKIP] Environment Hygiene Check (src/ application code staged for S2)
  [SKIP] Logging Hygiene Check (src/ application code staged for S2)

------------------------------------------------------------
PASSED 5 / SKIPPED 6 / FAILED 0
------------------------------------------------------------
```
Exit code: `0`

---

## 2. Requirement Mapping Table (S1.md "Tests" Specification)

Every bullet under "Tests" in `docs/prompt_pack/S1.md` and related stage specifications is explicitly mapped to its implementing test function in `tests/test_stage1_golden_contract.py`.

| S1.md Requirement Bullet | Test Function Name | Specific Invariants & Properties Verified | Coverage / Gap Status |
| :--- | :--- | :--- | :--- |
| **Hashes match manifest** | `test_manifest_file_hashes` | SHA-256 of all 10 fixture files match `fixtures/golden/manifest.json`. | **Full / Zero Gaps** |
| **Line endings invariant** | `test_fixtures_golden_no_crlf_line_endings` | Asserts no `\r\n` (`b"\r\n"`) exists in any golden fixture or README. | **Full / Zero Gaps** |
| **75 unique questions / 300 max** | `test_golden_exam_75_questions_300_max_marks` | 75 questions, IDs 1–75, 25 Physics, 25 Chemistry, 25 Maths; +4/-1/0 scoring; 800x600 synthetic bubble coordinate geometry formulas (`col_x`, `center_y`, option offsets). | **Full / Zero Gaps** |
| **20 unique IDs, 16/4 split, 1-to-1 mapping** | `test_roster_20_unique_students_and_attendance_split` | 20 unique IDs (`STU_01`–`STU_20`), exactly 16 PRESENT and 4 ABSENT (`STU_17`–`STU_20`); valid names and class labels. | **Full / Zero Gaps** |
| **Valid option values** | `test_submissions_valid_options_and_materialized_responses` | All responses in `{"A", "B", "C", "D", "BLANK"}`; ABSENT has empty dict `{}`; STU_01 Q11–20 wrong options strictly follow cyclic `A->B->C->D->A` progression after the key. | **Full / Zero Gaps** |
| **Contact/consent contract cases** | `test_contacts_and_consent_contract_cases` | Input/expected separation: `admissions_300.json` has inputs only. `expected_contacts.json` holds expected quarantine status, flags, and reasons (`INTERCEPTION_RISK_SAME_NUMBER`, `DUPLICATE_PARENT_UNVERIFIED`, `INVALID_PHONE_NUMBER`, `CONSENT_UNKNOWN`, `CONSENT_REVOKED`, `GUARDIAN_UNVERIFIED`). STU_05/STU_06 verified siblings. | **Full / Zero Gaps** |
| **STU_01 arithmetic and missed set** | `test_stu_01_diagnostic_literals` | Attempted 45, correct 20, wrong 25, blank 30, gross 80, bleed 25, net 55 (18.3%); missed Q11–20 easy questions; diagnostics (Physics/Chemistry ACCURACY_BLEED, Maths CONCEPTUAL_SPEED_GAP). | **Full / Zero Gaps** |
| **STU_02/03/04 scores** | `test_stu_02_03_04_scores_and_bands` | STU_02 (278 marks, 92.7%, GREEN, rank 1); STU_03 (90 marks, 30.0%, YELLOW, rank 3); STU_04 (180 marks, 60.0%, YELLOW, rank 2). | **Full / Zero Gaps** |
| **Boundary persona STU_03 percentage** | `test_boundary_persona_stu_03_percentage` | STU_03 exact percentage `"30.00"`, display `"30.0%"`, status band YELLOW. | **Full / Zero Gaps** |
| **STU_05 to 13 tied rank and scores** | `test_stu_05_to_13_tied_rank_and_scores` | STU_05–13 all net 80 (26.7%), RED, standard competition rank 4 (next rank 13). | **Full / Zero Gaps** |
| **STU_14 to 16 zero scores & missed all easy** | `test_stu_14_to_16_zero_scores_and_missed_all_easy` | STU_14–16 net 0 (0.0%), RED, rank 14; missed all easy Q1–20. | **Full / Zero Gaps** |
| **STU_17 to 20 absent literals** | `test_stu_17_to_20_absent_literals` | Status ABSENT, marks/percentage/rank null, band ABSENT, requires PTM slip true. | **Full / Zero Gaps** |
| **Per-question accuracy & easy set** | `test_per_question_accuracy_and_easy_set` | Q1–10 (13/16), Q11–20 (12/16 = 0.75 threshold). Easy set is exactly Q1–20. | **Full / Zero Gaps** |
| **Batch metrics literals** | `test_batch_metrics_literals` | Enrolled 20, present 16, absent 4; sum 1323, exact avg `"82.6875"`, display avg `"82.7"`, fraction `"1323/16"`, topper 278, PTM 17. | **Full / Zero Gaps** |
| **Marks entry 6-student fixture properties** | `test_marks_entry_6_student_fixture_properties` | Enrolled 6, present 5, absent 1; sum `"109.5"`, avg `"21.9"`, topper `"47.0"`, ranks `[2, 1, 2, 4, 5, None]`, universal D-04 PTM slips (`[False, False, False, True, True, True]`). Decimal strings for percentages and averages. | **Full / Zero Gaps** |
| **Two-org isolation fixture properties** | `test_two_org_isolation_fixture_properties` | Org Alpha and Org Beta have identical student roll number `"01"` and identical guardian phone `"+919811122201"`, but distinct student IDs, names, marks, and org contexts. | **Full / Zero Gaps** |
| **Edge-case fixture properties** | `test_edge_cases_fixture_properties` | All-wrong student (-75 marks, -25.0% RED), tie-for-first pair (ranks 1, 1, 3), zero-present batch, one-student batch, boundary percentages (`"29.99"`, `"30.0"`, `"60.0"`, `"60.01"`), and rounding-tie batch (49/4 = 12.25 exact -> display `"12.3"` under ROUND_HALF_UP). | **Full / Zero Gaps** |
| **Golden caption & sibling disambiguation** | `test_golden_captions_and_rendering` | STU_01 greeting, child name, class, scores. STU_05 ("कबीर") and STU_06 ("अनन्या") share guardian phone but have distinct names and different captions. | **Full / Zero Gaps** |
| **Decision 4 MARKS_ENTRY template rendering** | `test_direct_template_rendering_decision_4` | Approved MARKS_ENTRY message rendered with Decision 4 sample values matches byte-for-byte in Unicode NFC form. | **Full / Zero Gaps** |
| **Independent oracle cross-check** | `test_oracle_arithmetic_cross_check_golden_fixtures` | Independent oracle in `tests/oracle.py` cross-checks all 20 golden submissions and ranks, verifying zero arithmetic or classification drift. | **Full / Zero Gaps** |
| **Marks entry oracle message rendering comparison** | `test_marks_entry_oracle_message_rendering_comparison` | Compares oracle's `render_marks_entry_present_message` against `expected_marks_reports.json` for ME_01..ME_05 byte-for-byte in Unicode NFC form. | **Full / Zero Gaps** |

---

## 3. Gate Execution Evidence

### Gate 1: Contract Test Suite & Test Count
**Command:** `uv run --frozen pytest tests/test_stage1_golden_contract.py -v`
**Exit code:** `0`
**Actual test count:** `25 core contract tests + 6 purity snippet checks (31 passed items)`

**Raw Output:**
```text
============================= test session starts =============================
platform win32 -- Python 3.12.1, pytest-8.4.2, pluggy-1.7.0
rootdir: C:\Users\91933\OneDrive\Pictures\Documents\new_parent_messaging
configfile: pyproject.toml
plugins: platformdirs-4.13.5
collected 31 items

tests\test_stage1_golden_contract.py ...............................     [100%]

============================= 31 passed in 0.12s ==============================
```

### Gate 2: Guardrails Verification
**Command:** `python scripts\guardrails.py`
**Exit code:** `0`

**Raw Output:**
```text
=== Running Guardrails (Current Stage: S0) ===
  [PASS] Forbidden Patterns & Secrets
  [PASS] Hindi Integrity Check
  [PASS] State Hashes & Tags Check
  [PASS] Invariants Synchronization Check
  [PASS] Git Diff & Whitespace Check
  [SKIP] Fixture Hash Validation (fixtures/golden/manifest.json staged for S1)
  [SKIP] Test Count Integrity Check (docs/.test_count_baseline staged for S1)
  [SKIP] Time Hygiene Check (src/ application code staged for S2)
  [SKIP] Core Numerics Check (Core package staged for S2)
  [SKIP] Environment Hygiene Check (src/ application code staged for S2)
  [SKIP] Logging Hygiene Check (src/ application code staged for S2)

------------------------------------------------------------
PASSED 5 / SKIPPED 6 / FAILED 0
------------------------------------------------------------
```

### Gate 3: Ruff Linter
**Command:** `ruff check .`
**Exit code:** `0`

**Raw Output:**
```text
All checks passed!
```

### Gate 4: Deliverables Scope Check
**Command:** `git status --porcelain`
**Exit code:** `0`

**Raw Output:**
```text
?? docs/reviews/stage-1-run.md
?? fixtures/
?? tests/oracle.py
?? tests/test_stage1_golden_contract.py
```
*Note: All created files strictly reside within `fixtures/golden/`, `tests/`, and `docs/reviews/stage-1-run.md`. No pre-existing files, specs, ADRs, or docs were modified.*

### Gate 5: Fixture Hash Validation via Test & PowerShell Get-FileHash
**Command:** `uv run --frozen pytest tests/test_stage1_golden_contract.py -k test_manifest_file_hashes -v`
**Exit code:** `0`

**Raw Output:**
```text
============================= test session starts =============================
platform win32 -- Python 3.12.1, pytest-8.4.2, pluggy-1.7.0 -- C:\Users\91933\OneDrive\Pictures\Documents\new_parent_messaging\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\91933\OneDrive\Pictures\Documents\new_parent_messaging
configfile: pyproject.toml
plugins: platformdirs-4.13.5
collecting ... collected 31 items / 30 deselected / 1 selected

tests/test_stage1_golden_contract.py::test_manifest_file_hashes PASSED   [100%]

====================== 1 passed, 30 deselected in 0.12s =======================
```

**PowerShell Get-FileHash Verification:**
**Command:** `Get-FileHash fixtures\golden\manifest.json -Algorithm SHA256`
**Exit code:** `0`

**Raw Output:**
```text
Algorithm       Hash                                                                   Path
---------       ----                                                                   ----
SHA256          BAA580EBD32A942998B0ACA4C01624E5D29F34DA658155F33B0B42025452867A     C:\Users\91933\OneDrive\Pictures\Documents\new_parent_messaging\fixtures\golden\manifest.json
```

---

## 4. Falsification Verification (Tasks 1 & 8 Evidence)

Every mutation was applied to a scratch copy, tested with pytest, confirmed to fail with precise diagnostic evidence, and cleanly reverted.

### Task 1: Re-run Falsification Mutation "STU_01 Q1 A->B"
- **Mutation:** In `fixtures/golden/submissions_300.json`, modified STU_01 Q1 response from `"A"` to `"B"`.
- **Reasoning Check:** STU_01 correct drops from 20 to 19, wrong increases from 25 to 26, net drops from 55 to 50. The previous review report had erroneously recorded STU_02 numbers (`273 != 278`) due to missing assertion context messages. `test_oracle_arithmetic_cross_check_golden_fixtures` was updated to explicitly format `{sid}` in its assertion messages.
- **Raw Pytest Output:**
```text
F                                                                        [100%]
================================== FAILURES ===================================
_____________ test_oracle_arithmetic_cross_check_golden_fixtures ______________

test_paper = {'max_marks_per_subject': {'CHEMISTRY': 100, 'MATHS': 100, 'PHYSICS': 100}, 'name': '\u091f\u0930\u094d\u092e 1 \u0921\u093e\u092f\u0917\u094d\u0928\u094b\u0938\u094d\u091f\u093f\u0915 \u091f\u0947\u0938\u094d\u091f', 'org_...': {'x': 113, 'y': 340}, 'D': {'x': 137, 'y': 340}}, ...}, 'correct_option': 'B', 'negative_marks': 1, ...}, ...], ...}
submissions = {'org_id': 'DEFAULT_INSTITUTION', 'schema_version': 1, 'submissions': [{'responses': {'1': 'B', '10': 'B', '11': 'D', ...': 'D', ...}, 'status': 'PRESENT', 'student_id': 'STU_06', 'submission_id': 'SUB_300_06'}, ...], 'test_id': 'TEST_300'}
expected_reports = {'batch_metrics': {'absent_count': 4, 'class_average': '82.7', 'class_average_exact': '82.6875', 'class_average_fracti..._name': '\u0915\u092c\u0940\u0930', ...}, {'attempted': 20, 'blank': 55, 'bleed_marks': 0, 'child_display_name': '\u0905\u0928\u0928\u094d\u092f\u093e', ...}, ...], ...}

    def test_oracle_arithmetic_cross_check_golden_fixtures(
        test_paper: dict, submissions: dict, expected_reports: dict
    ) -> None:
        """Oracle scorer independently derives identical values for all 20 golden OMR submissions."""
        reports_map = {r["student_id"]: r for r in expected_reports["student_reports"]}

        all_scores: list[int | None] = []

        for sub in submissions["submissions"]:
            scored = score_single_omr_submission(test_paper, sub)
            all_scores.append(scored["net_marks"])

            sid = sub["student_id"]
            exp = reports_map[sid]

            assert scored["status"] == exp["status"], f"{sid} status mismatch: oracle={scored['status']} != expected={exp['status']}"
            assert scored["attempted"] == exp["attempted"], f"{sid} attempted mismatch: oracle={scored['attempted']} != expected={exp['attempted']}"
>           assert scored["correct"] == exp["correct"], f"{sid} correct mismatch: oracle={scored['correct']} != expected={exp['correct']}"
E           AssertionError: STU_01 correct mismatch: oracle=19 != expected=20
E           assert 19 == 20

tests\test_stage1_golden_contract.py:1096: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_stage1_golden_contract.py::test_oracle_arithmetic_cross_check_golden_fixtures
1 failed in 0.15s
```
Exit code: `1`

---

### Task 8: Extra Falsification Mutations (a through h)

#### 8(a) One Wrong Answer Changed to a Non-Cyclic Wrong Option
- **Mutation:** In STU_01 responses, Q11 wrong option changed to `"A"` (non-cyclic, instead of cyclic next option `"D"` after key `"C"`). Manifest regenerated so `test_manifest_file_hashes` passes.
- **Failing Test:** `test_submissions_valid_options_and_materialized_responses`
- **Raw Pytest Output:**
```text
F                                                                        [100%]
================================== FAILURES ===================================
__________ test_submissions_valid_options_and_materialized_responses __________

submissions = {'org_id': 'DEFAULT_INSTITUTION', 'schema_version': 1, 'submissions': [{'responses': {'1': 'A', '10': 'B', '11': 'A', ...': 'D', ...}, 'status': 'PRESENT', 'student_id': 'STU_06', 'submission_id': 'SUB_300_06'}, ...], 'test_id': 'TEST_300'}
test_paper = {'max_marks_per_subject': {'CHEMISTRY': 100, 'MATHS': 100, 'PHYSICS': 100}, 'name': '\u091f\u0930\u094d\u092e 1 \u0921\u093e\u092f\u0917\u094d\u0928\u094b\u0938\u094d\u091f\u093f\u0915 \u091f\u0947\u0938\u094d\u091f', 'org_...': {'x': 113, 'y': 340}, 'D': {'x': 137, 'y': 340}}, ...}, 'correct_option': 'B', 'negative_marks': 1, ...}, ...], ...}

    def test_submissions_valid_options_and_materialized_responses(submissions: dict, test_paper: dict) -> None:
        """Responses contain only valid options; absent students have empty responses."""
        valid_options = {"A", "B", "C", "D", "BLANK"}
        options = ["A", "B", "C", "D"]
        key_map = {q["question_id"]: q["correct_option"] for q in test_paper["questions"]}

        for sub in submissions["submissions"]:
            stu_id = sub["student_id"]
            status = sub["status"]
            responses = sub["responses"]

            if status == "ABSENT":
                assert responses == {}, f"Absent student {stu_id} must have empty responses"
            else:
                assert len(responses) == 75, f"Present student {stu_id} must have all 75 responses materialized"
                for q_id_str, resp in responses.items():
                    assert resp in valid_options, f"Invalid option '{resp}' on {stu_id} Q{q_id_str}"

        # Task 1: Cyclic wrong answers for EVERY student (next option in A->B->C->D->A order after key)
        # For every PRESENT student and every question where response is not BLANK and not the key
        for sub in submissions["submissions"]:
            if sub["status"] == "PRESENT":
                sid = sub["student_id"]
                for q in range(1, 76):
                    resp = sub["responses"][str(q)]
                    key = key_map[q]
                    if resp != "BLANK" and resp != key:
                        key_idx = options.index(key)
                        expected_wrong = options[(key_idx + 1) % 4]
>                       assert resp == expected_wrong, (
                            f"{sid} Q{q} wrong option mismatch: got '{resp}', expected cyclic next '{expected_wrong}'"
                        )
E                       AssertionError: STU_01 Q11 wrong option mismatch: got 'A', expected cyclic next 'D'
E                       assert 'A' == 'D'
E
E                         - D
E                         + A

tests\test_stage1_golden_contract.py:247: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_stage1_golden_contract.py::test_submissions_valid_options_and_materialized_responses
1 failed in 0.18s
```
Exit code: `1`

#### 8(b) STU_05 `verified_sibling` Set to False
- **Mutation:** In `admissions_300.json`, set STU_05 `verified_sibling = False`. Manifest regenerated.
- **Failing Test:** `test_contacts_and_consent_contract_cases`
- **Raw Pytest Output:**
```text
F                                                                        [100%]
================================== FAILURES ===================================
__________________ test_contacts_and_consent_contract_cases ___________________

admissions = {'cohort_label': '\u0915\u0915\u094d\u0937\u093e 10-A', 'org_id': 'DEFAULT_INSTITUTION', 'schema_version': 1, 'students': [{'child_display_name...\u0928\u094d\u092f\u093e', 'class_section': '\u0915\u0915\u094d\u0937\u093e 10-A', 'consent_status': 'OPT_IN', 'guardian_verification': 'VERIFIED', ...}, ...], ...}
expected_contacts = {'contacts': [{'dispatch_eligible': True, 'exclusion_reason': None, 'is_quarantined': False, 'quarantine_flags': [], ....False, 'quarantine_flags': [], ...}, ...], 'org_id': 'DEFAULT_INSTITUTION', 'schema_version': 1, 'test_id': 'TEST_300'}

    def test_contacts_and_consent_contract_cases(admissions: dict, expected_contacts: dict) -> None:
        """Verify all contact/consent exception personas from S1.md, separating inputs and expected outcomes."""
        students = {s["student_id"]: s for s in admissions["students"]}
        contacts = {c["student_id"]: c for c in expected_contacts["contacts"]}

        # Admissions contains inputs only (no quarantine flags or is_quarantined fields)
        for s in admissions["students"]:
            assert "is_quarantined" not in s, f"Input roster {s['student_id']} must not contain is_quarantined"
            assert "quarantine_flags" not in s, f"Input roster {s['student_id']} must not contain quarantine_flags"

        # STU_01: student +91 98111-22201, parent +91 98111-22202 -> eligible, not quarantined
        assert students["STU_01"]["raw_student_phone"] == "+91 98111-22201"
        assert students["STU_01"]["raw_guardian_phone"] == "+91 98111-22202"
        assert contacts["STU_01"]["is_quarantined"] is False
        assert contacts["STU_01"]["quarantine_flags"] == []
        assert contacts["STU_01"]["dispatch_eligible"] is True

        # STU_02: same normalized number -> INTERCEPTION_RISK_SAME_NUMBER, quarantined
        assert students["STU_02"]["raw_student_phone"] == "09811122203"
        assert students["STU_02"]["raw_guardian_phone"] == "9811122203"
        assert "INTERCEPTION_RISK_SAME_NUMBER" in contacts["STU_02"]["quarantine_flags"]
        assert contacts["STU_02"]["is_quarantined"] is True
        assert contacts["STU_02"]["dispatch_eligible"] is False

        # STU_03, STU_04: shared parent 9811122299, verified_sibling=false -> DUPLICATE_PARENT_UNVERIFIED
        for sid in ("STU_03", "STU_04"):
            assert students[sid]["raw_guardian_phone"] == "9811122299"
            assert students[sid]["verified_sibling"] is False
            assert "DUPLICATE_PARENT_UNVERIFIED" in contacts[sid]["quarantine_flags"]
            assert contacts[sid]["is_quarantined"] is True
            assert contacts[sid]["dispatch_eligible"] is False

        # STU_05, STU_06: shared parent 9811122288, verified_sibling=true -> not quarantined, eligible
        for sid in ("STU_05", "STU_06"):
            assert students[sid]["raw_guardian_phone"] == "9811122288"
>           assert students[sid]["verified_sibling"] is True
E           assert False is True

tests\test_stage1_golden_contract.py:291: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_stage1_golden_contract.py::test_contacts_and_consent_contract_cases
1 failed in 0.16s
```
Exit code: `1`

#### 8(c) STU_02 Parent Number Changed to Not Match Student Number
- **Mutation:** In `admissions_300.json`, changed STU_02 `raw_guardian_phone` from `"9811122203"` to `"9811122294"`. Manifest regenerated.
- **Failing Test:** `test_contacts_and_consent_contract_cases`
- **Raw Pytest Output:**
```text
F                                                                        [100%]
================================== FAILURES ===================================
__________________ test_contacts_and_consent_contract_cases ___________________

admissions = {'cohort_label': '\u0915\u0915\u094d\u0937\u093e 10-A', 'org_id': 'DEFAULT_INSTITUTION', 'schema_version': 1, 'students': [{'child_display_name...\u0928\u094d\u092f\u093e', 'class_section': '\u0915\u0915\u094d\u0937\u093e 10-A', 'consent_status': 'OPT_IN', 'guardian_verification': 'VERIFIED', ...}, ...], ...}
expected_contacts = {'contacts': [{'dispatch_eligible': True, 'exclusion_reason': None, 'is_quarantined': False, 'quarantine_flags': [], ....False, 'quarantine_flags': [], ...}, ...], 'org_id': 'DEFAULT_INSTITUTION', 'schema_version': 1, 'test_id': 'TEST_300'}

    def test_contacts_and_consent_contract_cases(admissions: dict, expected_contacts: dict) -> None:
        """Verify all contact/consent exception personas from S1.md, separating inputs and expected outcomes."""
        students = {s["student_id"]: s for s in admissions["students"]}
        contacts = {c["student_id"]: c for c in expected_contacts["contacts"]}

        # Admissions contains inputs only (no quarantine flags or is_quarantined fields)
        for s in admissions["students"]:
            assert "is_quarantined" not in s, f"Input roster {s['student_id']} must not contain is_quarantined"
            assert "quarantine_flags" not in s, f"Input roster {s['student_id']} must not contain quarantine_flags"

        # STU_01: student +91 98111-22201, parent +91 98111-22202 -> eligible, not quarantined
        assert students["STU_01"]["raw_student_phone"] == "+91 98111-22201"
        assert students["STU_01"]["raw_guardian_phone"] == "+91 98111-22202"
        assert contacts["STU_01"]["is_quarantined"] is False
        assert contacts["STU_01"]["quarantine_flags"] == []
        assert contacts["STU_01"]["dispatch_eligible"] is True

        # STU_02: same normalized number -> INTERCEPTION_RISK_SAME_NUMBER, quarantined
        assert students["STU_02"]["raw_student_phone"] == "09811122203"
>       assert students["STU_02"]["raw_guardian_phone"] == "9811122203"
E       AssertionError: assert '9811122294' == '9811122203'
E
E         - 9811122203
E         ?         ^^
E         + 9811122294
E         ?         ^^

tests\test_stage1_golden_contract.py:275: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_stage1_golden_contract.py::test_contacts_and_consent_contract_cases
1 failed in 0.18s
```
Exit code: `1`

#### 8(d) One Character Changed in STU_01 Hindi Caption
- **Mutation:** Changed comma to semicolon after `"प्रिय अभिभावक"` in STU_01's message text in `expected_reports.json`. Manifest regenerated.
- **Failing Test:** `test_golden_captions_and_rendering`
- **Raw Pytest Output:**
```text
F                                                                        [100%]
================================== FAILURES ===================================
_____________________ test_golden_captions_and_rendering ______________________

expected_reports = {'batch_metrics': {'absent_count': 4, 'class_average': '82.7', 'class_average_exact': '82.6875', 'class_average_fracti..._name': '\u0915\u092c\u0940\u0930', ...}, {'attempted': 20, 'blank': 55, 'bleed_marks': 0, 'child_display_name': '\u0905\u0928\u0928\u094d\u092f\u093e', ...}, ...], ...}

    def test_golden_captions_and_rendering(expected_reports: dict) -> None:
        """STU_01 caption contains greeting, name, class, and exact frozen score line."""
        reports = {r["student_id"]: r for r in expected_reports["student_reports"]}

        msg1 = reports["STU_01"]["message_text"]
>       assert msg1.startswith("\u092a\u094d\u0930\u093f\u092f \u0905\u092d\u093f\u092d\u093e\u0935\u0915, ")
E       AssertionError: assert False
E        +  where False = <built-in method startswith of str object at 0x0000022D8F324800>('\u092a\u094d\u0930\u093f\u092f \u0905\u092d\u093f\u092d\u093e\u0935\u0915, ')
E        +    where <built-in method startswith of str object at 0x0000022D8F324800> = '\u092a\u094d\u0930\u093f\u092f \u0905\u092d\u093f\u092d\u093e\u0935\u0915; \u0906\u0930\u0935 (\u0915\u0915\u094d\u0937\u093e 10-A) \u0915\u0947 \u091f\u0930\u094d\u092e 1 \u0921\u093e\u092f\u0917\u094d\u0928\u094b\u0938\u094d\u091f\u093f\u0915 \u091f\u0947\u0938\u094d\u091f \u092e\u0947\u0902 \u0915\u0941\u0932 \u0928\u0902\u092c\u0930: 300 \u092e\u0947\u0902 \u0938\u0947 55 \u0928\u0902\u092c\u0930 \u0906\u090f \u0939\u0948\u0902 (18.3%)\u0964 16 \u0909\u092a\u0938\u094d...\u093e\u0938 \u0915\u093e \u0914\u0938\u0924 \u0938\u094d\u0915\u094b\u0930 82.7 \u0939\u0948\u0964 \u0915\u094d\u0932\u093e\u0938 \u092e\u0947\u0902 \u0938\u092c\u0938\u0947 \u091c\u093c\u094d\u092f\u093e\u0926\u093e \u0928\u0902\u092c\u0930 278 \u0939\u0948\u0902\u0964 \u0938\u0939\u0940 \u091c\u0935\u093e\u092c\u094b\u0902 \u0938\u0947 \u092e\u093f\u0932\u0947 80 \u0928\u0902\u092c\u0930, \u0917\u0932\u0924 \u091c\u0935\u093e\u092c\u094b\u0902 \u0938\u0947 25 \u0928\u0902\u092c\u0930 \u0915\u091f \u0917\u090f\u0964'.startswith

tests\test_stage1_golden_contract.py:993: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_stage1_golden_contract.py::test_golden_captions_and_rendering
1 failed in 0.17s
```
Exit code: `1`

#### 8(e) STU_06 Caption Child Name Changed to Equal STU_05's
- **Mutation:** Changed STU_06 child name in `expected_reports.json` to `"कबीर"` (equal to STU_05's name, violating sibling disambiguation). Manifest regenerated.
- **Failing Test:** `test_golden_captions_and_rendering`
- **Raw Pytest Output:**
```text
F                                                                        [100%]
================================== FAILURES ===================================
_____________________ test_golden_captions_and_rendering ______________________

expected_reports = {'batch_metrics': {'absent_count': 4, 'class_average': '82.7', 'class_average_exact': '82.6875', 'class_average_fracti...ay_name': '\u0915\u092c\u0940\u0930', ...}, {'attempted': 20, 'blank': 55, 'bleed_marks': 0, 'child_display_name': '\u0915\u092c\u0940\u0930', ...}, ...], ...}

    def test_golden_captions_and_rendering(expected_reports: dict) -> None:
        """STU_01 caption contains greeting, name, class, and exact frozen score line."""
        reports = {r["student_id"]: r for r in expected_reports["student_reports"]}

        msg1 = reports["STU_01"]["message_text"]
        assert msg1.startswith("\u092a\u094d\u0930\u093f\u092f \u0905\u092d\u093f\u092d\u093e\u0935\u0915, ")
        assert "\u0906\u0930\u0935 (\u0915\u0915\u094d\u0937\u093e 10-A)" in msg1
        assert "\u0915\u0941\u0932 \u0928\u0902\u092c\u0930: 300 \u092e\u0947\u0902 \u0938\u0947 55 \u0928\u0902\u092c\u0930 \u0906\u090f \u0939\u0948\u0902 (18.3%)" in msg1

        # Sibling disambiguation: STU_05 and STU_06 share parent phone 9811122288
        msg5 = reports["STU_05"]["message_text"]
        msg6 = reports["STU_06"]["message_text"]
>       assert msg5 != msg6, "Sibling captions must not be identical"
E       AssertionError: Sibling captions must not be identical
E       assert '\u092a\u094d\u0930\u093f\u092f \u0905\u092d\u093f\u092d\u093e\u0935\u0915, \u0915\u092c\u0940\u0930 (\u0915\u0915\u094d\u0937\u093e 10-A) \u0915\u0947 \u091f\u0930\u094d\u092e 1 \u0921\u093e\u092f\u0917\u094d\u0928\u094b\u0938\u094d\u091f\u093f\u0915 \u091f\u0947\u0938\u094d\u091f \u092e\u0947\u0902 \u0915\u0941\u0932 \u0928\u0902\u092c\u0930: 300 \u092e\u0947\u0902 \u0938\u0947 80 \u0928\u0902\u092c\u0930 \u0906\u090f \u0939\u0948\u0902 (26.7%)\u0964 16 \u0909\u092a\u0938...\u0932\u093e\u0938 \u0915\u093e \u0914\u0938\u0924 \u0938\u094d\u0915\u094b\u0930 82.7 \u0939\u0948\u0964 \u0915\u094d\u0932\u093e\u0938 \u092e\u0947\u0902 \u0938\u092c\u0938\u0947 \u091c\u093c\u094d\u092f\u093e\u0926\u093e \u0928\u0902\u092c\u0930 278 \u0939\u0948\u0902\u0964 \u0938\u0939\u0940 \u091c\u0935\u093e\u092c\u094b\u0902 \u0938\u0947 \u092e\u093f\u0932\u0947 80 \u0928\u0902\u092c\u0930, \u0917\u0932\u0924 \u091c\u0935\u093e\u092c\u094b\u0902 \u0938\u0947 0 \u0928\u0902\u092c\u0930 \u0915\u091f \u0917\u090f\u0964' != '\u092a\u094d\u0930\u093f\u092f \u0905\u092d\u093f\u092d\u093e\u0935\u0915, \u0915\u092c\u0940\u0930 (\u0915\u0915\u094d\u0937\u093e 10-A) \u0915\u0947 \u091f\u0930\u094d\u092e 1 \u0921\u093e\u092f\u0917\u094d\u0928\u094b\u0938\u094d\u091f\u093f\u0915 \u091f\u0947\u0938\u094d\u091f \u092e\u0947\u0902 \u0915\u0941\u0932 \u0928\u0902\u092c\u0930: 300 \u092e\u0947\u0902 \u0938\u0947 80 \u0928\u0902\u092c\u0930 \u0906\u090f \u0939\u0948\u0902 (26.7%)\u0964 16 \u0909\u092a\u0938...\u0932\u093e\u0938 \u0915\u093e \u0914\u0938\u0924 \u0938\u094d\u0915\u094b\u0930 82.7 \u0939\u0948\u0964 \u0915\u094d\u0932\u093e\u0938 \u092e\u0947\u0902 \u0938\u092c\u0938\u0947 \u091c\u093c\u094d\u092f\u093e\u0926\u093e \u0928\u0902\u092c\u0930 278 \u0939\u0948\u0902\u0964 \u0938\u0939\u0940 \u091c\u0935\u093e\u092c\u094b\u0902 \u0938\u0947 \u092e\u093f\u0932\u0947 80 \u0928\u0902\u092c\u0930, \u0917\u0932\u0924 \u091c\u0935\u093e\u092c\u094b\u0902 \u0938\u0947 0 \u0928\u0902\u092c\u0930 \u0915\u091f \u0917\u090f\u0964'

tests\test_stage1_golden_contract.py:1000: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_stage1_golden_contract.py::test_golden_captions_and_rendering
1 failed in 0.12s
```
Exit code: `1`

#### 8(f) Org Beta Roll Number Made Unique in `isolation_two_orgs.json`
- **Mutation:** Changed Org Beta student roll number from `"01"` to `"99"` in `isolation_two_orgs.json`. Manifest regenerated.
- **Failing Test:** `test_two_org_isolation_fixture_properties`
- **Raw Pytest Output:**
```text
F                                                                        [100%]
================================== FAILURES ===================================
__________________ test_two_org_isolation_fixture_properties __________________

isolation_data = {'org_alpha': {'org_id': 'ORG_ALPHA', 'school_name': '\u0906\u0926\u0930\u094d\u0936 \u0935\u093f\u0926\u094d\u092f\u093e\u0932\u092f', 'students': [{'child_display_name': '\u0906\u0930\u0935', 'cla...e': '\u0935\u093f\u0935\u0947\u0915', 'class_section': '\u0915\u0915\u094d\u0937\u093e 8-B', 'guardian_phone': '+919811122201', 'marks': 90, ...}]}, 'schema_version': 1}

    def test_two_org_isolation_fixture_properties(isolation_data: dict) -> None:
        """Overlapping roll numbers ('01') and identical parent phones across distinct orgs."""
        alpha = isolation_data["org_alpha"]
        beta = isolation_data["org_beta"]

        assert alpha["org_id"] == "ORG_ALPHA"
        assert beta["org_id"] == "ORG_BETA"

        stu_a = alpha["students"][0]
        stu_b = beta["students"][0]

        # Identical roll numbers and parent phone
        assert stu_a["roll_number"] == "01"
>       assert stu_b["roll_number"] == "01"
E       AssertionError: assert '99' == '01'
E
E         - 01
E         + 99

tests\test_stage1_golden_contract.py:926: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_stage1_golden_contract.py::test_two_org_isolation_fixture_properties
1 failed in 0.13s
```
Exit code: `1`

#### 8(g) Geometry Constant `col_x` Changed in Generator
- **Mutation:** In `generate_fixtures.py`, changed `col_x` offset from `30` to `35`. Regenerated `test_paper_300.json` and manifest.
- **Failing Test:** `test_golden_exam_75_questions_300_max_marks`
- **Raw Pytest Output:**
```text
F                                                                        [100%]
================================== FAILURES ===================================
_________________ test_golden_exam_75_questions_300_max_marks _________________

test_paper = {'max_marks_per_subject': {'CHEMISTRY': 100, 'MATHS': 100, 'PHYSICS': 100}, 'name': '\u091f\u0930\u094d\u092e 1 \u0921\u093e\u092f\u0917\u094d\u0928\u094b\u0938\u094d\u091f\u093f\u0915 \u091f\u0947\u0938\u094d\u091f', 'org_...': {'x': 113, 'y': 340}, 'D': {'x': 137, 'y': 340}}, ...}, 'correct_option': 'B', 'negative_marks': 1, ...}, ...], ...}

    def test_golden_exam_75_questions_300_max_marks(test_paper: dict) -> None:
        """Golden exam has 75 questions, max marks 300, 25/25/25 split, and synthetic geometry."""
        assert test_paper["schema_version"] == 1
        assert test_paper["test_id"] == "TEST_300"
        assert test_paper["total_questions"] == 75
        assert test_paper["total_max_marks"] == 300

        questions = test_paper["questions"]
        assert len(questions) == 75

        question_ids = [q["question_id"] for q in questions]
        assert question_ids == list(range(1, 76)), "Question IDs must be exactly 1 to 75"

        options = ["A", "B", "C", "D"]

        for q in questions:
            q_id = q["question_id"]
            assert q["question_type"] == "SINGLE_CORRECT"
            assert q["positive_marks"] == 4
            assert q["negative_marks"] == 1
            assert q["blank_marks"] == 0

            # Subject allocation
            if 1 <= q_id <= 25:
                assert q["subject"] == "PHYSICS"
            elif 26 <= q_id <= 50:
                assert q["subject"] == "CHEMISTRY"
            else:
                assert q["subject"] == "MATHS"

            # Correct option formula: ["A","B","C","D"][(q-1) % 4]
            expected_opt = options[(q_id - 1) % 4]
            assert q["correct_option"] == expected_opt

            # Synthetic 800x600 geometry formula
            coords = q["bubble_coordinates"]
            exp_col = (q_id - 1) // 15
            exp_row = (q_id - 1) % 15
            exp_col_x = 30 + exp_col * 150
            exp_center_y = 255 + exp_row * 17

            assert coords["col"] == exp_col
            assert coords["row"] == exp_row
>           assert coords["col_x"] == exp_col_x
E           assert 35 == 30

tests\test_stage1_golden_contract.py:175: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_stage1_golden_contract.py::test_golden_exam_75_questions_300_max_marks
1 failed in 0.14s
```
Exit code: `1`

#### 8(h) One Character Changed in `marks_entry_notification.md` Placeholder Template
- **Mutation:** In `docs/templates/marks_entry_notification.md`, changed `{{11}} हैं।` to `{{11}} हैं;` in the raw template placeholder block.
- **Failing Test:** `test_direct_template_rendering_decision_4`
- **Raw Pytest Output:**
```text
F                                                                        [100%]
================================== FAILURES ===================================
__________________ test_direct_template_rendering_decision_4 __________________

    def test_direct_template_rendering_decision_4() -> None:
        """
        Direct template-rendering test: Approved MARKS_ENTRY message dynamically loaded
        from docs/DECISIONS_OPEN.md Decision 4 and raw template loaded from
        docs/templates/marks_entry_notification.md, not a literal copied into the test.
        Renders with Decision 4 sample values and matches character-for-character.
        """
        # 1. Dynamically load approved text from docs/DECISIONS_OPEN.md (Decision 4)
        decisions_file = REPO_ROOT / "docs" / "DECISIONS_OPEN.md"
        decisions_content = decisions_file.read_text(encoding="utf-8")
        m_dec = re.search(
            r"### Decision 4: Approved Golden Message for `MARKS_ENTRY_TOTALS`.*?^\s*>\s*\"([^\"]+)\"",
            decisions_content,
            re.MULTILINE | re.DOTALL,
        )
        assert m_dec, "Could not extract approved golden message from docs/DECISIONS_OPEN.md Decision 4"
        approved_decision_4 = unicodedata.normalize("NFC", m_dec.group(1).strip())

        # 2. Dynamically load raw template body from docs/templates/marks_entry_notification.md
        template_file = REPO_ROOT / "docs" / "templates" / "marks_entry_notification.md"
        template_content = template_file.read_text(encoding="utf-8")
        m_tpl = re.search(
            r"## Raw Template Body with Placeholders\s*```text\s*\n(.*?)\n```",
            template_content,
            re.DOTALL,
        )
        assert m_tpl, "Could not extract raw template body from docs/templates/marks_entry_notification.md"
        raw_template = unicodedata.normalize("NFC", m_tpl.group(1).strip())

        # 3. Substitute Decision 4 sample parameters into raw template
        params = {
            "1": "\u0906\u0930\u0935",
            "2": "\u0915\u0915\u094d\u0937\u093e 8-B",
            "3": "\u092f\u0942\u0928\u093f\u091f \u091f\u0947\u0938\u094d\u091f 1",
            "4": "\u0905\u0902\u0917\u094d\u0930\u0947\u091c\u093c\u0940",
            "5": "50",
            "6": "30",
            "7": "60.0%",
            "8": "18",
            "9": "7",
            "10": "32.4",
            "11": "47",
        }
        rendered_from_template = re.sub(r"\{\{(\d+)\}\}", lambda m: params[m.group(1)], raw_template)
        rendered_from_template = unicodedata.normalize("NFC", rendered_from_template)

        # 4. Render using oracle helper
        rendered_from_oracle = render_marks_entry_present_message(
            child_name=params["1"],
            class_section=params["2"],
            test_name=params["3"],
            subject=params["4"],
            max_marks=int(params["5"]),
            marks=int(params["6"]),
            percentage=params["7"],
            present_count=int(params["8"]),
            rank=int(params["9"]),
            class_average=params["10"],
            topper_marks=int(params["11"]),
        )

        # Character-for-character assertions against the approved document text
>       assert rendered_from_template == approved_decision_4, (
            "Rendered template from docs/templates does not match Decision 4 in docs/DECISIONS_OPEN.md"
        )
E       AssertionError: Rendered template from docs/templates does not match Decision 4 in docs/DECISIONS_OPEN.md
E       assert '\u092a\u094d\u0930\u093f\u092f \u0905\u092d\u093f\u092d\u093e\u0935... \u0928\u0902\u092c\u0930 47 \u0939\u0948\u0902;' == '\u092a\u094d\u0930\u093f\u092f \u0905\u092d\u093f\u092d\u093e\u0935... \u0928\u0902\u092c\u0930 47 \u0939\u0948\u0902\u0964'
E
E         Skipping 190 identical leading characters in diff, use -v to show
E         - \u0902\u092c\u0930 47 \u0939\u0948\u0902\u0964
E         ?           ^
E         + \u0902\u092c\u0930 47 \u0939\u0948\u0902;
E         ?           ^

tests\test_stage1_golden_contract.py:1067: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_stage1_golden_contract.py::test_direct_template_rendering_decision_4
1 failed in 0.13s
```
Exit code: `1`

---


### 4.2 H7/H8 Extended Hardening Proofs

#### H7/H8.1 Hindi Integrity Guard Rejection Proofs (`scripts/check_hindi_integrity.py`)
Tested against `fixtures/golden/expected_marks_reports.json` with temporary single-mutation injections, verified to fail with exit code `1`, and cleanly discarded:

1. **Devanagari digit in string (`'१'` instead of `'1'`):**
```text
[FAIL] Hindi integrity check failed with 14 error(s):
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json:2 contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json:23 contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json:38 contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json:53 contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json:68 contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json:83 contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json:98 contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.assessment_name contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[0].message_text contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[1].message_text contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[2].message_text contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[3].message_text contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[4].message_text contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[5].message_text contains Devanagari numeral '१'
```
Exit code: `1`

2. **Banned Hindi Term (D-06 `प्राप्तांक` / `\u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093e\u0902\u0915`):**
```text
[FAIL] Hindi integrity check failed with 6 error(s):
  - [BANNED TERM] fixtures\golden\expected_marks_reports.json contains banned Hindi term (\u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093e\u0902\u0915)
  - [BANNED TERM] fixtures\golden\expected_marks_reports.json at $.student_reports[0].message_text contains banned Hindi term (\u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093e\u0902\u0915)
  - [BANNED TERM] fixtures\golden\expected_marks_reports.json at $.student_reports[1].message_text contains banned Hindi term (\u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093e\u0902\u0915)
  - [BANNED TERM] fixtures\golden\expected_marks_reports.json at $.student_reports[2].message_text contains banned Hindi term (\u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093e\u0902\u0915)
  - [BANNED TERM] fixtures\golden\expected_marks_reports.json at $.student_reports[3].message_text contains banned Hindi term (\u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093e\u0902\u0915)
  - [BANNED TERM] fixtures\golden\expected_marks_reports.json at $.student_reports[4].message_text contains banned Hindi term (\u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093e\u0902\u0915)
```
Exit code: `1`

3. **Non-NFC Sequence (Precomposed Nukhta `\u095b` non-NFC):**
```text
[FAIL] Hindi integrity check failed with 8 error(s):
  - [NON-NFC NORMALIZATION] fixtures\golden\expected_marks_reports.json is not in Unicode NFC form
  - [NON-NFC NORMALIZATION] fixtures\golden\expected_marks_reports.json at $.student_reports[0].message_text is not in Unicode NFC form
  - [NON-NFC NORMALIZATION] fixtures\golden\expected_marks_reports.json at $.student_reports[1].message_text is not in Unicode NFC form
  - [NON-NFC NORMALIZATION] fixtures\golden\expected_marks_reports.json at $.student_reports[2].message_text is not in Unicode NFC form
  - [NON-NFC NORMALIZATION] fixtures\golden\expected_marks_reports.json at $.student_reports[3].message_text is not in Unicode NFC form
  - [NON-NFC NORMALIZATION] fixtures\golden\expected_marks_reports.json at $.student_reports[4].message_text is not in Unicode NFC form
  - [NON-NFC NORMALIZATION] fixtures\golden\expected_marks_reports.json at $.student_reports[5].message_text is not in Unicode NFC form
  - [NON-NFC NORMALIZATION] fixtures\golden\expected_marks_reports.json at $.subject is not in Unicode NFC form
```
Exit code: `1`

4. **Devanagari Digit Written as `\uXXXX` JSON Escape (`\u0967`):**
```text
[FAIL] Hindi integrity check failed with 7 error(s):
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.assessment_name contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[0].message_text contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[1].message_text contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[2].message_text contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[3].message_text contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[4].message_text contains Devanagari numeral '१'
  - [DEVANAGARI DIGIT] fixtures\golden\expected_marks_reports.json at $.student_reports[5].message_text contains Devanagari numeral '१'
```
Exit code: `1`

#### H7/H8.2 Oracle Purity Allowlist & Bad Snippets Verification
Parametrized test `test_oracle_purity_ast_bad_snippets` verified 6 forbidden snippets:
- `import src` -> rejected: `Oracle purity violation: non-stdlib import 'src'`
- `from omr_dispatch.x import y` -> rejected: `Oracle purity violation: non-stdlib from-import 'omr_dispatch.x'`
- `import importlib` -> rejected: `Oracle purity violation: forbidden dynamic module 'importlib'`
- `from . import x` -> rejected: `Oracle purity violation: forbidden relative import`
- `__import__("src")` -> rejected: `Oracle purity violation: forbidden dynamic execution call '__import__'`
- `import yaml` -> rejected: `Oracle purity violation: non-stdlib import 'yaml'`

Scratch copy of `tests/oracle.py` with `import yaml` added evaluated against `check_oracle_source_purity_ast`:
```text
SUCCESSFULLY REJECTED WITH ASSERTIONERROR:
Oracle purity violation: non-stdlib import 'yaml' at line 1
```

#### H7/H8.3 Marks Entry ME_01..ME_05 Oracle Message Comparison
Test `test_marks_entry_oracle_message_rendering_comparison` asserts that `render_marks_entry_present_message` produces message texts matching `expected_marks_reports.json` byte-for-byte in Unicode NFC form for all students ME_01 through ME_05:
```text
tests/test_stage1_golden_contract.py::test_marks_entry_oracle_message_rendering_comparison PASSED
```

## 5. Deliverables Created & Final Manifest SHA-256

| Deliverable Path | Description & Conformance |
| :--- | :--- |
| `fixtures/golden/test_paper_300.json` | 75 questions, IDs 1–75, Physics (1–25), Chemistry (26–50), Mathematics (51–75). Synthetic bounding coordinates (800x600 coordinate space) with `+4/-1/0` scoring scheme. |
| `fixtures/golden/admissions_300.json` | 20 students (`STU_01`–`STU_20`), sections A/B, synthesized Indian test phone numbers, consent status, guardian verification, and verified sibling flags. Pure input roster (contains no quarantine flags or reason codes). |
| `fixtures/golden/expected_contacts.json` | Expected contact outcomes separated from input roster. Contains quarantine statuses, quarantine flags, dispatch eligibility, and exclusion reason codes (`INTERCEPTION_RISK_SAME_NUMBER`, `DUPLICATE_PARENT_UNVERIFIED`, `INVALID_PHONE_NUMBER`, `CONSENT_UNKNOWN`, `CONSENT_REVOKED`, `GUARDIAN_UNVERIFIED`). |
| `fixtures/golden/submissions_300.json` | 20 student submissions: 16 PRESENT students (all 75 responses fully materialized; wrong answers strictly follow `A->B->C->D->A` pattern), 4 ABSENT students with empty response maps. |
| `fixtures/golden/expected_reports.json` | 20 expected student reports with exact literal scores, ranks, performance bands (GREEN/YELLOW/RED/ABSENT), `requires_ptm_slip`, subject breakdowns, missed questions, batch statistics (`class_average_exact: "82.6875"`, `class_average: "82.7"`, topper 278, PTM 17), percentages as fixed-decimal JSON strings, and full rendered Hindi notification text. |
| `fixtures/golden/marks_entry_50.json` | 6 students (`ME_01`–`ME_06`), English Class 8-B, Max Marks 50. Includes non-integer half-marks (`2.5` for ME_05) and absent student ME_06. |
| `fixtures/golden/expected_marks_reports.json` | 6 expected reports for marks entry assessment. Standard competition ranks `[2, 1, 2, 4, 5, null]`, class average `"21.9"`, topper `"47.0"`, sum `"109.5"`, percentages as fixed-decimal JSON strings (`"60.00"`, `"94.00"`, `"5.00"`, `"0.00"`, `null`), universal D-04 PTM slip flags (`[false, false, false, true, true, true]`), and full rendered Hindi notification messages. |
| `fixtures/golden/isolation_two_orgs.json` | Multi-tenancy isolation fixture: Org Alpha (`ORG_ALPHA`) and Org Beta (`ORG_BETA`) with overlapping student roll numbers (`"01"`) and identical parent phone numbers (`"+919811122201"`), proving strict tenant partitioning. |
| `fixtures/golden/edge_cases.json` | Comprehensive edge-case fixtures: All-wrong student (-25.0% RED), tie-for-first pair (ranks 1, 1, 3), zero-present batch, single-student batch, percentage threshold boundaries (`"29.99"`, `"30.0"`, `"60.0"`, `"60.01"`), and rounding-tie batch (49/4 = 12.25 exact -> display `"12.3"` under ROUND_HALF_UP). |
| `fixtures/golden/README.md` | Catalog of golden fixtures, numeric representation rules, POSIX newline rules, and strict instructions that tests never dynamically compute expected values. |
| `fixtures/golden/generate_fixtures.py` | Deterministic fixture generator writing all golden fixtures with strict key sorting, 2-space indentation, POSIX `\n` line endings (`write_bytes`), and automatic manifest calculation. |
| `fixtures/golden/manifest.json` | SHA-256 integrity map locking all 10 fixture files. |
| `tests/oracle.py` | Self-contained independent oracle scorer sharing zero code with `src/`. Uses exact integer and `fractions.Fraction` / `decimal.Decimal` arithmetic to verify fixtures against specification invariants. |
| `tests/test_stage1_golden_contract.py` | 25 automated pytest tests (plus 6 parametrized purity snippet checks) verifying file hashes, POSIX line endings, golden OMR tables, boundary personas, marks entry properties, edge cases, multi-tenant isolation, Hindi text hygiene, and oracle cross-checks. |

### Manifest Files SHA-256 Table (`fixtures/golden/manifest.json`)
```json
{
  "files": {
    "fixtures/golden/README.md": "bc5eb8c37ce63a8391c88945936702a7ebc5d73d1278ff610ec050ce2c9d7dcf",
    "fixtures/golden/admissions_300.json": "2e3f34dbd4c1767e65f1b5fc52f85c5375516bd5e1f48a9b868f78d1228ace3c",
    "fixtures/golden/edge_cases.json": "bb5ce52e72f7313d6b2d7177d250654482c0eb5bbb1460f303c676eae67f797a",
    "fixtures/golden/expected_contacts.json": "b7f6fcbd1cc64bb55809ee80d8e22a9a01479c4919c61b31bdf7369719869508",
    "fixtures/golden/expected_marks_reports.json": "b1c9c177d02f88dda6fb03bc4a224d07a05b70448e83d7195951047ef7de9208",
    "fixtures/golden/expected_reports.json": "a13abad0990bf86fbc0df96e910f30973ea10666a16938c62b11b39f01b5e407",
    "fixtures/golden/isolation_two_orgs.json": "fb52a7ea748e2b4f10564a95355e887b66f43a095ae290bd415524c297900809",
    "fixtures/golden/marks_entry_50.json": "19479248afd8f6ecbc6f3668ea2534a8820b8324ce640fd6dc3174182414cfb2",
    "fixtures/golden/submissions_300.json": "b8321da221f4433fe5fc571aa29c8f1aebcfb027b2a8a4d7548c1b02341283f2",
    "fixtures/golden/test_paper_300.json": "3b3ff09957220da86ef63e44e061060d19a1bec2ad12e64d45f386dcc2fdd973"
  },
  "fixture_version": "1.0.0",
  "schema_version": 1
}
```

### Final Manifest File SHA-256 (for human signature in `docs/STATE.md`)
```text
baa580ebd32a942998b0aca4c01624e5d29f34da658155f33b0b42025452867a
```
*(Per instructions, the agent does NOT sign `docs/STATE.md`. The operator must sign the manifest SHA-256 hash in `docs/STATE.md`.)*

---

## 6. Discrepancies and Observations

1. **Numeric Representation Discipline:**
   Integers (counts, marks, ranks) are stored as JSON integers. Decimals (percentages, class averages, toppers, boundary thresholds) are strictly stored as JSON strings with explicit formatting (`"82.6875"`, `"82.7"`, `"18.33"`, `"109.5"`, `"21.9"`, `"47.0"`, `"29.99"`, `"30.0"`, `"60.0"`, `"60.01"`).
2. **Line Endings:**
   All fixture files and docs are serialized using POSIX LF (`\n`). `test_fixtures_golden_no_crlf_line_endings` continuously verifies no `\r\n` byte sequences enter `fixtures/golden/`.
3. **Input vs Expected Outcome Separation:**
   `admissions_300.json` acts purely as an input roster. Quarantined status, quarantine flags, and reason codes reside solely in `expected_contacts.json`.
4. **Rounding Tie Batch:**
   `edge_cases.json` includes `rounding_tie_batch` with 4 students totalling 49 marks (`12.25` exact class average), demonstrating `"12.3"` display quantization under `ROUND_HALF_UP`.
5. **Stage Isolation:**
   No edits were made to `src/`, `scripts/`, `PROJECT_SPEC.md`, ADRs, or `docs/STATE.md`.
