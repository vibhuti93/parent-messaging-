"""
Stage S1 Golden Fixture and Contract Lock Test Suite.

Verifies:
  - Fixture manifest integrity and SHA-256 hashes
  - Golden exam: 75 unique questions, 300 max marks, subjects, options, synthetic geometry
  - Roster and submissions: 20 unique students, 16/4 attendance split, 1-to-1 mapping
  - Valid response options and wrong-answer order rules
  - Contact and consent quarantine cases
  - Literal golden expected scores and ranks for STU_01 through STU_20
  - Per-question accuracy and exact easy questions set (Q1–20)
  - Batch aggregate metrics (present count, sum, average, topper, PTM count)
  - Marks entry 6-student cohort properties and standard competition rank
  - Multi-tenant two-org isolation properties
  - Edge cases: all-wrong student, tie-for-first, zero-present, one-student, percentage boundaries
  - Golden caption rendering invariants and character-for-character template match
  - Independent oracle arithmetic cross-check

All assertions compare against frozen literals. No mocks. Zero float.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
import unicodedata
from fractions import Fraction
from pathlib import Path

import pytest

from tests.oracle import (
    classify_contacts_oracle,
    compute_standard_competition_ranks,
    render_marks_entry_present_message,
    score_single_omr_submission,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden"
REPO_ROOT = FIXTURES_DIR.parent.parent


def load_fixture(filename: str) -> dict:
    fpath = FIXTURES_DIR / filename
    assert fpath.exists(), f"Required fixture missing: {filename}"
    return json.loads(fpath.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def manifest() -> dict:
    return load_fixture("manifest.json")


@pytest.fixture(scope="module")
def test_paper() -> dict:
    return load_fixture("test_paper_300.json")


@pytest.fixture(scope="module")
def admissions() -> dict:
    return load_fixture("admissions_300.json")


@pytest.fixture(scope="module")
def submissions() -> dict:
    return load_fixture("submissions_300.json")


@pytest.fixture(scope="module")
def expected_reports() -> dict:
    return load_fixture("expected_reports.json")


@pytest.fixture(scope="module")
def marks_entry() -> dict:
    return load_fixture("marks_entry_50.json")


@pytest.fixture(scope="module")
def expected_marks() -> dict:
    return load_fixture("expected_marks_reports.json")


@pytest.fixture(scope="module")
def isolation_data() -> dict:
    return load_fixture("isolation_two_orgs.json")


@pytest.fixture(scope="module")
def expected_contacts() -> dict:
    return load_fixture("expected_contacts.json")


@pytest.fixture(scope="module")
def edge_cases() -> dict:
    return load_fixture("edge_cases.json")


# ==============================================================================
# 1. Manifest Integrity & Hash Locking
# ==============================================================================

def test_manifest_file_hashes(manifest: dict) -> None:
    """Every file in manifest.json must exist and match its SHA-256 hash byte-for-byte."""
    files_map = manifest.get("files", {})
    assert len(files_map) >= 8, f"Expected at least 8 hashed files, got {len(files_map)}"

    for rel_path, expected_hash in files_map.items():
        target = REPO_ROOT / rel_path
        assert target.exists(), f"Hashed fixture file missing: {rel_path}"
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, (
            f"Hash mismatch on {rel_path}: expected {expected_hash}, got {actual_hash}"
        )


def test_fixtures_golden_no_crlf_line_endings() -> None:
    """No file under fixtures/golden/ may contain CRLF line endings (b'\\r\\n')."""
    for p in FIXTURES_DIR.glob("**/*"):
        if p.is_file():
            content = p.read_bytes()
            assert b"\r\n" not in content, f"File contains CRLF line endings: {p.relative_to(REPO_ROOT)}"


# ==============================================================================
# 2. Golden Exam Specification (test_paper_300.json)
# ==============================================================================

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
        assert coords["col_x"] == exp_col_x
        assert coords["center_y"] == exp_center_y

        # Option centers: col_x + 35 + opt_index * 24
        opt_coords = coords["options"]
        for opt_idx, opt_letter in enumerate(options):
            assert opt_coords[opt_letter]["x"] == exp_col_x + 35 + opt_idx * 24
            assert opt_coords[opt_letter]["y"] == exp_center_y


# ==============================================================================
# 3. Roster & Submission Invariants
# ==============================================================================

def test_roster_20_unique_students_and_attendance_split(admissions: dict, submissions: dict) -> None:
    """20 unique student IDs, 16 PRESENT, 4 ABSENT split, 1-to-1 submission mapping."""
    students = admissions["students"]
    sub_list = submissions["submissions"]

    assert len(students) == 20
    assert len(sub_list) == 20

    student_ids = [s["student_id"] for s in students]
    assert len(set(student_ids)) == 20, "Student IDs must be unique"
    assert student_ids == [f"STU_{i:02d}" for i in range(1, 21)]

    sub_student_ids = [s["student_id"] for s in sub_list]
    assert sub_student_ids == student_ids, "Submissions must map 1-to-1 with admissions"

    # 16 PRESENT, 4 ABSENT split
    present_subs = [s for s in sub_list if s["status"] == "PRESENT"]
    absent_subs = [s for s in sub_list if s["status"] == "ABSENT"]
    assert len(present_subs) == 16
    assert len(absent_subs) == 4
    assert [s["student_id"] for s in present_subs] == [f"STU_{i:02d}" for i in range(1, 17)]
    assert [s["student_id"] for s in absent_subs] == [f"STU_{i:02d}" for i in range(17, 21)]

    # Every student has child_display_name and class_section
    for s in students:
        assert s["child_display_name"], f"Missing child_display_name for {s['student_id']}"
        assert s["class_section"] == "कक्षा 10-A"


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
                    assert resp == expected_wrong, (
                        f"{sid} Q{q} wrong option mismatch: got '{resp}', expected cyclic next '{expected_wrong}'"
                    )


# ==============================================================================
# 4. Contact and Consent Contracts
# ==============================================================================

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
        assert students[sid]["verified_sibling"] is True
        assert contacts[sid]["is_quarantined"] is False
        assert contacts[sid]["quarantine_flags"] == []
        assert contacts[sid]["dispatch_eligible"] is True

    # STU_07: invalid parent 5511122207
    assert students["STU_07"]["raw_guardian_phone"] == "5511122207"
    assert "INVALID_PHONE_NUMBER" in contacts["STU_07"]["quarantine_flags"]
    assert contacts["STU_07"]["is_quarantined"] is True
    assert contacts["STU_07"]["dispatch_eligible"] is False

    # STU_08: consent UNKNOWN -> not quarantined, but not eligible
    assert students["STU_08"]["consent_status"] == "UNKNOWN"
    assert contacts["STU_08"]["is_quarantined"] is False
    assert contacts["STU_08"]["dispatch_eligible"] is False
    assert contacts["STU_08"]["exclusion_reason"] == "CONSENT_UNKNOWN"

    # STU_09: consent REVOKED -> not quarantined, but not eligible
    assert students["STU_09"]["consent_status"] == "REVOKED"
    assert contacts["STU_09"]["is_quarantined"] is False
    assert contacts["STU_09"]["dispatch_eligible"] is False
    assert contacts["STU_09"]["exclusion_reason"] == "CONSENT_REVOKED"

    # STU_10: guardian verification UNVERIFIED -> not quarantined, but not eligible
    assert students["STU_10"]["guardian_verification"] == "UNVERIFIED"
    assert contacts["STU_10"]["is_quarantined"] is False
    assert contacts["STU_10"]["dispatch_eligible"] is False
    assert contacts["STU_10"]["exclusion_reason"] == "GUARDIAN_UNVERIFIED"

    # STU_17: unique valid parent number, VERIFIED, OPT_IN -> eligible
    assert students["STU_17"]["raw_guardian_phone"] == "9830010017"
    assert students["STU_17"]["consent_status"] == "OPT_IN"
    assert students["STU_17"]["guardian_verification"] == "VERIFIED"
    assert contacts["STU_17"]["dispatch_eligible"] is True

    # STU_19: consent REVOKED
    assert students["STU_19"]["consent_status"] == "REVOKED"
    assert contacts["STU_19"]["dispatch_eligible"] is False


def test_contact_reason_codes_precedence() -> None:
    """
    Operator Ratified Exclusion Reason Precedence (2026-10-23):
      1. INVALID_PHONE_NUMBER
      2. INTERCEPTION_RISK_SAME_NUMBER
      3. DUPLICATE_PARENT_UNVERIFIED
      4. CONSENT_<STATUS> (CONSENT_UNKNOWN, CONSENT_REVOKED)
      5. GUARDIAN_<STATUS> (GUARDIAN_UNVERIFIED)

    Evaluates synthetic personas with overlapping issues to verify strict precedence.
    """
    synthetic_admissions = {
        "org_id": "PRECEDENCE_TEST_ORG",
        "schema_version": 1,
        "test_id": "PRECEDENCE_TEST",
        "students": [
            # Case 1: Invalid guardian phone + consent revoked -> INVALID_PHONE_NUMBER wins over CONSENT_REVOKED
            {
                "student_id": "SYN_01",
                "roll_number": "01",
                "child_display_name": "विद्यार्थी 1",
                "class_section": "कक्षा 10-A",
                "raw_student_phone": "9811122201",
                "raw_guardian_phone": "12345",  # Invalid
                "consent_status": "REVOKED",
                "guardian_verification": "UNVERIFIED",
                "verified_sibling": False,
            },
            # Case 2: Interception risk (same number) + duplicate unverified parent -> INTERCEPTION_RISK wins
            {
                "student_id": "SYN_02",
                "roll_number": "02",
                "child_display_name": "विद्यार्थी 2",
                "class_section": "कक्षा 10-A",
                "raw_student_phone": "9811122202",
                "raw_guardian_phone": "9811122202",  # Same as student
                "consent_status": "OPT_IN",
                "guardian_verification": "VERIFIED",
                "verified_sibling": False,
            },
            # Case 3: Paired with SYN_02 to make parent phone 9811122202 duplicate
            {
                "student_id": "SYN_03",
                "roll_number": "03",
                "child_display_name": "विद्यार्थी 3",
                "class_section": "कक्षा 10-A",
                "raw_student_phone": "9811122203",
                "raw_guardian_phone": "9811122202",  # Duplicate unverified
                "consent_status": "OPT_IN",
                "guardian_verification": "VERIFIED",
                "verified_sibling": False,
            },
            # Case 4: Duplicate parent + consent revoked -> DUPLICATE_PARENT_UNVERIFIED wins over CONSENT_REVOKED
            {
                "student_id": "SYN_04",
                "roll_number": "04",
                "child_display_name": "विद्यार्थी 4",
                "class_section": "कक्षा 10-A",
                "raw_student_phone": "9810000004",
                "raw_guardian_phone": "9810000045",  # Shared with SYN_05
                "consent_status": "REVOKED",
                "guardian_verification": "UNVERIFIED",
                "verified_sibling": False,
            },
            {
                "student_id": "SYN_05",
                "roll_number": "05",
                "child_display_name": "विद्यार्थी 5",
                "class_section": "कक्षा 10-A",
                "raw_student_phone": "9810000005",
                "raw_guardian_phone": "9810000045",  # Shared with SYN_04
                "consent_status": "OPT_IN",
                "guardian_verification": "VERIFIED",
                "verified_sibling": False,
            },
            # Case 5: Consent revoked + guardian unverified -> CONSENT_REVOKED wins over GUARDIAN_UNVERIFIED
            {
                "student_id": "SYN_06",
                "roll_number": "06",
                "child_display_name": "विद्यार्थी 6",
                "class_section": "कक्षा 10-A",
                "raw_student_phone": "9810000006",
                "raw_guardian_phone": "9810000066",  # unique, distinct from student
                "consent_status": "REVOKED",
                "guardian_verification": "UNVERIFIED",
                "verified_sibling": False,
            },
            # Case 6b: Interception risk + consent revoked -> INTERCEPTION_RISK_SAME_NUMBER wins over CONSENT_REVOKED
            {
                "student_id": "SYN_07",
                "roll_number": "07",
                "child_display_name": "विद्यार्थी 7",
                "class_section": "कक्षा 10-A",
                "raw_student_phone": "9810000007",
                "raw_guardian_phone": "9810000007",  # Same as student (interception risk)
                "consent_status": "REVOKED",
                "guardian_verification": "UNVERIFIED",
                "verified_sibling": False,
            },
            # Case 7: Only guardian unverified -> GUARDIAN_UNVERIFIED
            {
                "student_id": "SYN_08",
                "roll_number": "08",
                "child_display_name": "विद्यार्थी 8",
                "class_section": "कक्षा 10-A",
                "raw_student_phone": "9810000008",
                "raw_guardian_phone": "9810000088",  # unique, distinct from student
                "consent_status": "OPT_IN",
                "guardian_verification": "UNVERIFIED",
                "verified_sibling": False,
            },
            # Case 8: Clean student -> eligible
            {
                "student_id": "SYN_09",
                "roll_number": "09",
                "child_display_name": "विद्यार्थी 9",
                "class_section": "कक्षा 10-A",
                "raw_student_phone": "9810000009",
                "raw_guardian_phone": "9810000099",  # unique, distinct from student
                "consent_status": "OPT_IN",
                "guardian_verification": "VERIFIED",
                "verified_sibling": False,
            },
        ],
    }

    result = classify_contacts_oracle(synthetic_admissions)
    res_map = {c["student_id"]: c for c in result["contacts"]}

    # SYN_01: INVALID_PHONE_NUMBER
    assert res_map["SYN_01"]["is_quarantined"] is True
    assert res_map["SYN_01"]["exclusion_reason"] == "INVALID_PHONE_NUMBER"

    # SYN_02: INTERCEPTION_RISK_SAME_NUMBER
    assert res_map["SYN_02"]["is_quarantined"] is True
    assert res_map["SYN_02"]["exclusion_reason"] == "INTERCEPTION_RISK_SAME_NUMBER"

    # SYN_03: DUPLICATE_PARENT_UNVERIFIED
    assert res_map["SYN_03"]["is_quarantined"] is True
    assert res_map["SYN_03"]["exclusion_reason"] == "DUPLICATE_PARENT_UNVERIFIED"

    # SYN_04: DUPLICATE_PARENT_UNVERIFIED wins over CONSENT_REVOKED
    assert res_map["SYN_04"]["is_quarantined"] is True
    assert res_map["SYN_04"]["exclusion_reason"] == "DUPLICATE_PARENT_UNVERIFIED"

    # SYN_05: DUPLICATE_PARENT_UNVERIFIED
    assert res_map["SYN_05"]["exclusion_reason"] == "DUPLICATE_PARENT_UNVERIFIED"

    # SYN_06: CONSENT_REVOKED wins over GUARDIAN_UNVERIFIED
    assert res_map["SYN_06"]["is_quarantined"] is False
    assert res_map["SYN_06"]["exclusion_reason"] == "CONSENT_REVOKED"

    # SYN_07: INTERCEPTION_RISK_SAME_NUMBER wins over CONSENT_REVOKED
    assert res_map["SYN_07"]["is_quarantined"] is True
    assert res_map["SYN_07"]["exclusion_reason"] == "INTERCEPTION_RISK_SAME_NUMBER"

    # SYN_08: GUARDIAN_UNVERIFIED
    assert res_map["SYN_08"]["is_quarantined"] is False
    assert res_map["SYN_08"]["exclusion_reason"] == "GUARDIAN_UNVERIFIED"

    # SYN_09: Clean eligible
    assert res_map["SYN_09"]["is_quarantined"] is False
    assert res_map["SYN_09"]["dispatch_eligible"] is True
    assert res_map["SYN_09"]["exclusion_reason"] is None


# ==============================================================================
# 5. Literal Expected Report Values (S1.md 20-student Table)
# ==============================================================================

def test_stu_01_diagnostic_literals(expected_reports: dict) -> None:
    """STU_01 literal values from S1.md table: 45 att, 20 corr, 25 wrong, 55 net, 18.3%, rank 13, RED, PTM."""
    reports = {r["student_id"]: r for r in expected_reports["student_reports"]}
    r1 = reports["STU_01"]

    assert r1["attempted"] == 45
    assert r1["correct"] == 20
    assert r1["wrong"] == 25
    assert r1["blank"] == 30
    assert r1["gross_marks"] == 80
    assert r1["bleed_marks"] == 25
    assert r1["net_marks"] == 55
    assert r1["percentage"] == "18.33"
    assert r1["net_percentage"] == "18.3%"
    assert r1["competition_rank"] == 13
    assert r1["status_band"] == "RED"
    assert r1["requires_ptm_slip"] is True
    assert r1["easy_missed_question_ids"] == list(range(11, 21))
    assert r1["positive_marks_not_earned"] == 40
    assert r1["subject_diagnostics"] == {
        "PHYSICS": "ACCURACY_BLEED",
        "CHEMISTRY": "ACCURACY_BLEED",
        "MATHS": "CONCEPTUAL_SPEED_GAP",
    }


def test_stu_02_03_04_scores_and_bands(expected_reports: dict) -> None:
    """STU_02 (92.7% GREEN, rank 1), STU_03 (30.0% YELLOW, rank 3), STU_04 (60.0% YELLOW, rank 2)."""
    reports = {r["student_id"]: r for r in expected_reports["student_reports"]}

    # STU_02: 72 att, 70 corr, 2 wrong, 280 gross, 2 bleed, 278 net, 92.7%, rank 1, GREEN, no PTM
    r2 = reports["STU_02"]
    assert r2["attempted"] == 72
    assert r2["correct"] == 70
    assert r2["wrong"] == 2
    assert r2["blank"] == 3
    assert r2["gross_marks"] == 280
    assert r2["bleed_marks"] == 2
    assert r2["net_marks"] == 278
    assert r2["percentage"] == "92.67"
    assert r2["net_percentage"] == "92.7%"
    assert r2["competition_rank"] == 1
    assert r2["status_band"] == "GREEN"
    assert r2["requires_ptm_slip"] is False
    assert r2["easy_missed_question_ids"] == []
    assert r2["positive_marks_not_earned"] == 0
    assert r2["subject_diagnostics"] == {
        "PHYSICS": "MASTERY_ZONE",
        "CHEMISTRY": "MASTERY_ZONE",
        "MATHS": "MASTERY_ZONE",
    }

    # STU_03: 25 att, 23 corr, 2 wrong, 92 gross, 2 bleed, 90 net, 30.0%, rank 3, YELLOW, no PTM
    r3 = reports["STU_03"]
    assert r3["attempted"] == 25
    assert r3["correct"] == 23
    assert r3["wrong"] == 2
    assert r3["blank"] == 50
    assert r3["gross_marks"] == 92
    assert r3["bleed_marks"] == 2
    assert r3["net_marks"] == 90
    assert r3["percentage"] == "30.00"
    assert r3["net_percentage"] == "30.0%"
    assert r3["competition_rank"] == 3
    assert r3["status_band"] == "YELLOW"
    assert r3["requires_ptm_slip"] is False
    assert r3["easy_missed_question_ids"] == []
    assert r3["positive_marks_not_earned"] == 0
    assert r3["subject_diagnostics"] == {
        "PHYSICS": "MASTERY_ZONE",
        "CHEMISTRY": "FOUNDATIONAL_CRISIS",
        "MATHS": "NO_ATTEMPT",
    }

    # STU_04: 45 att, 45 corr, 0 wrong, 180 gross, 0 bleed, 180 net, 60.0%, rank 2, YELLOW, no PTM
    r4 = reports["STU_04"]
    assert r4["attempted"] == 45
    assert r4["correct"] == 45
    assert r4["wrong"] == 0
    assert r4["blank"] == 30
    assert r4["gross_marks"] == 180
    assert r4["bleed_marks"] == 0
    assert r4["net_marks"] == 180
    assert r4["percentage"] == "60.00"
    assert r4["net_percentage"] == "60.0%"
    assert r4["competition_rank"] == 2
    assert r4["status_band"] == "YELLOW"
    assert r4["requires_ptm_slip"] is False
    assert r4["easy_missed_question_ids"] == []
    assert r4["positive_marks_not_earned"] == 0
    assert r4["subject_diagnostics"] == {
        "PHYSICS": "MASTERY_ZONE",
        "CHEMISTRY": "MASTERY_ZONE",
        "MATHS": "NO_ATTEMPT",
    }


def test_boundary_persona_stu_03_percentage(expected_reports: dict) -> None:
    """STU_03 percentage is exactly 30.0% (boundary for YELLOW band)."""
    r3 = next(r for r in expected_reports["student_reports"] if r["student_id"] == "STU_03")
    assert r3["net_marks"] == 90
    assert r3["percentage"] == "30.00"
    assert r3["net_percentage"] == "30.0%"
    assert r3["status_band"] == "YELLOW"


def test_stu_05_to_13_tied_rank_and_scores(expected_reports: dict) -> None:
    """STU_05–13: 20 att, 20 corr, 80 net, 26.7%, rank 4 (tied), RED, PTM yes."""
    reports = {r["student_id"]: r for r in expected_reports["student_reports"]}

    for idx in range(5, 14):
        sid = f"STU_{idx:02d}"
        r = reports[sid]
        assert r["attempted"] == 20
        assert r["correct"] == 20
        assert r["wrong"] == 0
        assert r["gross_marks"] == 80
        assert r["bleed_marks"] == 0
        assert r["net_marks"] == 80
        assert r["percentage"] == "26.67"
        assert r["net_percentage"] == "26.7%"
        assert r["competition_rank"] == 4
        assert r["status_band"] == "RED"
        assert r["requires_ptm_slip"] is True
        assert r["easy_missed_question_ids"] == []
        assert r["positive_marks_not_earned"] == 0


def test_stu_14_to_16_zero_scores_and_missed_all_easy(expected_reports: dict) -> None:
    """STU_14–16: 0 att, 0 net, 0.0%, rank 14 (tied), RED, PTM yes, missed Q1–20 (80 marks)."""
    reports = {r["student_id"]: r for r in expected_reports["student_reports"]}

    for idx in range(14, 17):
        sid = f"STU_{idx:02d}"
        r = reports[sid]
        assert r["attempted"] == 0
        assert r["correct"] == 0
        assert r["wrong"] == 0
        assert r["net_marks"] == 0
        assert r["percentage"] == "0.00"
        assert r["net_percentage"] == "0.0%"
        assert r["competition_rank"] == 14
        assert r["status_band"] == "RED"
        assert r["requires_ptm_slip"] is True
        assert r["easy_missed_question_ids"] == list(range(1, 21))
        assert r["positive_marks_not_earned"] == 80


def test_stu_17_to_20_absent_literals(expected_reports: dict) -> None:
    """STU_17–20: score/rank/% null, band ABSENT, PTM yes."""
    reports = {r["student_id"]: r for r in expected_reports["student_reports"]}

    for idx in range(17, 21):
        sid = f"STU_{idx:02d}"
        r = reports[sid]
        assert r["status"] == "ABSENT"
        assert r["net_marks"] is None
        assert r["percentage"] is None
        assert r["net_percentage"] is None
        assert r["competition_rank"] is None
        assert r["status_band"] == "ABSENT"
        assert r["requires_ptm_slip"] is True
        assert r["subject_diagnostics"] is None


# ==============================================================================
# 6. Easy Questions & Batch Aggregate Properties
# ==============================================================================

def test_per_question_accuracy_and_easy_set(submissions: dict, test_paper: dict) -> None:
    """
    Task 2: Full per-question accuracy literals, computed from submissions:
    Q1-10: 13/16, Q11-20: 12/16 (0.75), Q21-23: 3/16, Q24-25: 2/16, Q26-30: 3/16,
    Q31-45: 2/16, Q46-50: 1/16, Q51-55: 2/16, Q56-70: 1/16, Q71-75: 0/16.
    Easy set is exactly Q1–20.
    """
    key_map = {q["question_id"]: q["correct_option"] for q in test_paper["questions"]}
    present_subs = [s for s in submissions["submissions"] if s["status"] == "PRESENT"]
    present_count = len(present_subs)
    assert present_count == 16

    accuracies: dict[int, Fraction] = {}
    for q in range(1, 76):
        correct_count = sum(1 for s in present_subs if s["responses"].get(str(q)) == key_map[q])
        accuracies[q] = Fraction(correct_count, present_count)

    # Q1-10 13/16
    for q in range(1, 11):
        assert accuracies[q] == Fraction(13, 16), f"Q{q} accuracy mismatch: got {accuracies[q]}, expected 13/16"

    # Q11-20 12/16
    for q in range(11, 21):
        assert accuracies[q] == Fraction(12, 16), f"Q{q} accuracy mismatch: got {accuracies[q]}, expected 12/16"

    # Q21-23 3/16
    for q in range(21, 24):
        assert accuracies[q] == Fraction(3, 16), f"Q{q} accuracy mismatch: got {accuracies[q]}, expected 3/16"

    # Q24-25 2/16
    for q in range(24, 26):
        assert accuracies[q] == Fraction(2, 16), f"Q{q} accuracy mismatch: got {accuracies[q]}, expected 2/16"

    # Q26-30 3/16
    for q in range(26, 31):
        assert accuracies[q] == Fraction(3, 16), f"Q{q} accuracy mismatch: got {accuracies[q]}, expected 3/16"

    # Q31-45 2/16
    for q in range(31, 46):
        assert accuracies[q] == Fraction(2, 16), f"Q{q} accuracy mismatch: got {accuracies[q]}, expected 2/16"

    # Q46-50 1/16
    for q in range(46, 51):
        assert accuracies[q] == Fraction(1, 16), f"Q{q} accuracy mismatch: got {accuracies[q]}, expected 1/16"

    # Q51-55 2/16
    for q in range(51, 56):
        assert accuracies[q] == Fraction(2, 16), f"Q{q} accuracy mismatch: got {accuracies[q]}, expected 2/16"

    # Q56-70 1/16
    for q in range(56, 71):
        assert accuracies[q] == Fraction(1, 16), f"Q{q} accuracy mismatch: got {accuracies[q]}, expected 1/16"

    # Q71-75 0/16
    for q in range(71, 76):
        assert accuracies[q] == Fraction(0, 16), f"Q{q} accuracy mismatch: got {accuracies[q]}, expected 0/16"

    # Easy set is exactly Q1-20 (accuracy >= 12/16)
    easy_set = {q for q, acc in accuracies.items() if acc >= Fraction(3, 4)}
    assert easy_set == set(range(1, 21)), f"Easy question set mismatch: {sorted(easy_set)}"


def test_d03_subject_labels_all_students(expected_reports: dict) -> None:
    """
    Task 3: D-03 Subject Labels for all 20 students:
    - STU_01: Physics ACCURACY_BLEED, Chemistry ACCURACY_BLEED, Maths CONCEPTUAL_SPEED_GAP
    - STU_02: all MASTERY_ZONE
    - STU_03: Physics MASTERY_ZONE, Chemistry FOUNDATIONAL_CRISIS, Maths NO_ATTEMPT
    - STU_04: Physics/Chemistry MASTERY_ZONE, Maths NO_ATTEMPT
    - STU_05–13: Physics MASTERY_ZONE, Chemistry NO_ATTEMPT, Maths NO_ATTEMPT
    - STU_14–16: all NO_ATTEMPT
    - STU_17–20 (ABSENT): none (subject_diagnostics is None)
    """
    reports = {r["student_id"]: r for r in expected_reports["student_reports"]}

    # STU_01
    assert reports["STU_01"]["subject_diagnostics"] == {
        "PHYSICS": "ACCURACY_BLEED",
        "CHEMISTRY": "ACCURACY_BLEED",
        "MATHS": "CONCEPTUAL_SPEED_GAP",
    }
    # STU_02
    assert reports["STU_02"]["subject_diagnostics"] == {
        "PHYSICS": "MASTERY_ZONE",
        "CHEMISTRY": "MASTERY_ZONE",
        "MATHS": "MASTERY_ZONE",
    }
    # STU_03
    assert reports["STU_03"]["subject_diagnostics"] == {
        "PHYSICS": "MASTERY_ZONE",
        "CHEMISTRY": "FOUNDATIONAL_CRISIS",
        "MATHS": "NO_ATTEMPT",
    }
    # STU_04
    assert reports["STU_04"]["subject_diagnostics"] == {
        "PHYSICS": "MASTERY_ZONE",
        "CHEMISTRY": "MASTERY_ZONE",
        "MATHS": "NO_ATTEMPT",
    }
    # STU_05 to 13
    for idx in range(5, 14):
        sid = f"STU_{idx:02d}"
        assert reports[sid]["subject_diagnostics"] == {
            "PHYSICS": "MASTERY_ZONE",
            "CHEMISTRY": "NO_ATTEMPT",
            "MATHS": "NO_ATTEMPT",
        }, f"Subject diagnostics mismatch for {sid}"
    # STU_14 to 16
    for idx in range(14, 17):
        sid = f"STU_{idx:02d}"
        assert reports[sid]["subject_diagnostics"] == {
            "PHYSICS": "NO_ATTEMPT",
            "CHEMISTRY": "NO_ATTEMPT",
            "MATHS": "NO_ATTEMPT",
        }, f"Subject diagnostics mismatch for {sid}"
    # STU_17 to 20 (ABSENT)
    for idx in range(17, 21):
        sid = f"STU_{idx:02d}"
        assert reports[sid]["subject_diagnostics"] is None, f"Absent student {sid} must have no subject diagnostics"


def test_batch_metrics_literals(expected_reports: dict) -> None:
    """Batch: enrolled 20, present 16, absent 4; sum 1323, average 82.7, topper 278, PTM 17."""
    metrics = expected_reports["batch_metrics"]
    assert metrics["enrolled_count"] == 20
    assert metrics["present_count"] == 16
    assert metrics["absent_count"] == 4
    assert metrics["total_score_sum"] == 1323
    assert metrics["class_average_exact"] == "82.6875"
    assert metrics["class_average"] == "82.7"
    assert metrics["class_average_fraction"] == "1323/16"
    assert metrics["topper_net_marks"] == 278
    assert metrics["easy_question_ids"] == list(range(1, 21))
    assert metrics["ptm_eligible_count"] == 17


# ==============================================================================
# 7. Marks Entry 6-Student Cohort (marks_entry_50.json)
# ==============================================================================

def test_marks_entry_6_student_fixture_properties(marks_entry: dict, expected_marks: dict) -> None:
    """
    Marks entry 6 students, English Class 8-B:
      - ME_01: 30.0 (60.0%), rank 2 (tie), YELLOW, PTM false
      - ME_02: 47.0 (94.0%), rank 1 (topper), GREEN, PTM false
      - ME_03: 30.0 (60.0%), rank 2 (tie), YELLOW, PTM false
      - ME_04: 2.5 (5.0%), rank 4, RED, PTM true
      - ME_05: 0.0 (0.0%), rank 5, RED, PTM true
      - ME_06: null marks, ABSENT, PTM true
    Standard competition ranks: [2, 1, 2, 4, 5, None] (skips rank 3!).
    """
    assert marks_entry["schema_version"] == 1
    assert marks_entry["max_marks"] == 50
    assert len(marks_entry["rows"]) == 6

    b_metrics = expected_marks["batch_metrics"]
    assert b_metrics["enrolled_count"] == 6
    assert b_metrics["present_count"] == 5
    assert b_metrics["absent_count"] == 1
    assert b_metrics["total_score_sum"] == "109.5"
    assert b_metrics["class_average"] == "21.9"
    assert b_metrics["topper_marks"] == "47.0"
    assert b_metrics["ptm_eligible_count"] == 3

    reports = {r["student_id"]: r for r in expected_marks["student_reports"]}

    # Verify standard competition ranks 2, 1, 2, 4, 5 specifically
    assert reports["ME_01"]["competition_rank"] == 2
    assert reports["ME_01"]["percentage"] == "60.00"
    assert reports["ME_02"]["competition_rank"] == 1
    assert reports["ME_02"]["percentage"] == "94.00"
    assert reports["ME_03"]["competition_rank"] == 2
    assert reports["ME_03"]["percentage"] == "60.00"
    assert reports["ME_04"]["competition_rank"] == 4
    assert reports["ME_04"]["percentage"] == "5.00"
    assert reports["ME_05"]["competition_rank"] == 5
    assert reports["ME_05"]["percentage"] == "0.00"
    assert reports["ME_06"]["competition_rank"] is None
    assert reports["ME_06"]["percentage"] is None

    # Verify status bands and PTM requirement
    assert reports["ME_01"]["status_band"] == "YELLOW"
    assert reports["ME_01"]["requires_ptm_slip"] is False

    assert reports["ME_02"]["status_band"] == "GREEN"
    assert reports["ME_02"]["requires_ptm_slip"] is False

    assert reports["ME_03"]["status_band"] == "YELLOW"
    assert reports["ME_03"]["requires_ptm_slip"] is False

    assert reports["ME_04"]["status_band"] == "RED"
    assert reports["ME_04"]["requires_ptm_slip"] is True

    assert reports["ME_05"]["status_band"] == "RED"
    assert reports["ME_05"]["requires_ptm_slip"] is True

    assert reports["ME_06"]["status_band"] == "ABSENT"
    assert reports["ME_06"]["requires_ptm_slip"] is True


def test_marks_entry_oracle_message_rendering_comparison(expected_marks: dict) -> None:
    """Compare oracle's render_marks_entry_present_message against expected_marks_reports.json ME_01..ME_05."""
    b_metrics = expected_marks["batch_metrics"]
    test_name = expected_marks["assessment_name"]
    subject = expected_marks["subject"]
    max_marks = expected_marks["max_marks"]
    present_count = b_metrics["present_count"]
    class_average = b_metrics["class_average"]
    topper_marks = b_metrics["topper_marks"]

    def format_marks(val: object) -> str:
        s = str(val)
        if s.endswith(".0"):
            return s[:-2]
        return s

    display_topper = format_marks(topper_marks)
    reports = {r["student_id"]: r for r in expected_marks["student_reports"]}

    for sid in ["ME_01", "ME_02", "ME_03", "ME_04", "ME_05"]:
        rep = reports[sid]
        rendered = render_marks_entry_present_message(
            child_name=rep["child_display_name"],
            class_section=rep["class_section"],
            test_name=test_name,
            subject=subject,
            max_marks=max_marks,
            marks=format_marks(rep["marks"]),
            percentage=rep["net_percentage"],
            present_count=present_count,
            rank=rep["competition_rank"],
            class_average=class_average,
            topper_marks=display_topper,
        )
        assert rendered == rep["message_text"], (
            f"Oracle rendering for {sid} must match expected_marks_reports.json byte-for-byte in NFC form"
        )


# ==============================================================================
# 8. Two-Org Isolation & Edge Cases
# ==============================================================================

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
    assert stu_b["roll_number"] == "01"
    assert stu_a["guardian_phone"] == stu_b["guardian_phone"]

    # Completely different student identities and scores
    assert stu_a["student_id"] != stu_b["student_id"]
    assert stu_a["child_display_name"] != stu_b["child_display_name"]
    assert stu_a["marks"] != stu_b["marks"]


def test_edge_cases_fixture_properties(edge_cases: dict) -> None:
    """All-wrong student, tie-for-first, zero-present, one-student, percentage boundaries."""
    # All wrong student
    aw = edge_cases["all_wrong_student"]
    assert aw["net_marks"] == -75
    assert aw["net_percentage"] == "-25.0%"
    assert aw["status_band"] == "RED"
    assert aw["requires_ptm_slip"] is True

    # Tie for first pair
    tie = edge_cases["tie_for_first_pair"]
    ranks = [s["competition_rank"] for s in tie["students"]]
    assert ranks == [1, 1, 3], "Two tied for 1st must cause next student to be rank 3"

    # Zero present batch
    zp = edge_cases["zero_present_batch"]
    assert zp["present_count"] == 0
    assert zp["class_average"] is None
    assert zp["topper_net_marks"] is None
    assert zp["easy_question_ids"] == []

    # One student batch
    os_batch = edge_cases["one_student_batch"]
    assert os_batch["present_count"] == 1
    assert os_batch["class_average"] == "200.0"
    assert os_batch["topper_net_marks"] == 200

    # Rounding tie batch (Task 5: 49/4 = 12.25 exact -> 12.3 under ROUND_HALF_UP)
    rt = edge_cases["rounding_tie_batch"]
    assert rt["present_count"] == 4
    assert rt["total_score_sum"] == 49
    assert rt["class_average_exact"] == "12.25"
    assert rt["class_average_display"] == "12.3"

    # Percentage boundaries
    for pb in edge_cases["percentage_boundaries"]:
        pct_val = float(pb["input_pct"])
        # Evaluate band directly at classifier level
        # For integer/fraction check: pct_val = net / max * 100
        # If pct_val < 30.0 -> RED, 30.0 <= pct_val <= 60.0 -> YELLOW, > 60.0 -> GREEN
        if pct_val < 30.0:
            exp_band = "RED"
        elif pct_val <= 60.0:
            exp_band = "YELLOW"
        else:
            exp_band = "GREEN"
        assert pb["expected_band"] == exp_band, f"Boundary failure on {pb['input_pct']}"


# ==============================================================================
# 9. Golden Caption & Direct Template Rendering Tests
# ==============================================================================

def test_golden_captions_and_rendering(expected_reports: dict) -> None:
    """STU_01 caption contains greeting, name, class, and exact frozen score line."""
    reports = {r["student_id"]: r for r in expected_reports["student_reports"]}

    msg1 = reports["STU_01"]["message_text"]
    assert msg1.startswith("प्रिय अभिभावक, ")
    assert "आरव (कक्षा 10-A)" in msg1
    assert "कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)" in msg1

    # Sibling disambiguation: STU_05 and STU_06 share parent phone 9811122288
    msg5 = reports["STU_05"]["message_text"]
    msg6 = reports["STU_06"]["message_text"]
    assert msg5 != msg6, "Sibling captions must not be identical"
    assert "कबीर" in msg5
    assert "अनन्या" in msg6


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
        "1": "आरव",
        "2": "कक्षा 8-B",
        "3": "यूनिट टेस्ट 1",
        "4": "अंग्रेज़ी",
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
    assert rendered_from_template == approved_decision_4, (
        "Rendered template from docs/templates does not match Decision 4 in docs/DECISIONS_OPEN.md"
    )
    assert rendered_from_oracle == approved_decision_4, (
        "Oracle rendered MARKS_ENTRY message does not match Decision 4 in docs/DECISIONS_OPEN.md"
    )


# ==============================================================================
# 10. Independent Oracle Cross-Check
# ==============================================================================

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
        assert scored["correct"] == exp["correct"], f"{sid} correct mismatch: oracle={scored['correct']} != expected={exp['correct']}"
        assert scored["wrong"] == exp["wrong"], f"{sid} wrong mismatch: oracle={scored['wrong']} != expected={exp['wrong']}"
        assert scored["blank"] == exp["blank"], f"{sid} blank mismatch: oracle={scored['blank']} != expected={exp['blank']}"
        assert scored["gross_marks"] == exp["gross_marks"], f"{sid} gross_marks mismatch: oracle={scored['gross_marks']} != expected={exp['gross_marks']}"
        assert scored["bleed_marks"] == exp["bleed_marks"], f"{sid} bleed_marks mismatch: oracle={scored['bleed_marks']} != expected={exp['bleed_marks']}"
        assert scored["net_marks"] == exp["net_marks"], f"{sid} net_marks mismatch: oracle={scored['net_marks']} != expected={exp['net_marks']}"
        assert scored["net_percentage"] == exp["net_percentage"], f"{sid} net_percentage mismatch: oracle={scored['net_percentage']} != expected={exp['net_percentage']}"
        assert scored["status_band"] == exp["status_band"], f"{sid} status_band mismatch: oracle={scored['status_band']} != expected={exp['status_band']}"
        assert scored["subject_diagnostics"] == exp["subject_diagnostics"], f"{sid} subject_diagnostics mismatch"

    # Cross check competition ranks
    oracle_ranks = compute_standard_competition_ranks(all_scores)
    for idx, sub in enumerate(submissions["submissions"]):
        sid = sub["student_id"]
        assert oracle_ranks[idx] == reports_map[sid]["competition_rank"], f"{sid} rank mismatch: oracle={oracle_ranks[idx]} != expected={reports_map[sid]['competition_rank']}"


def test_oracle_contact_classification_cross_check(admissions: dict, expected_contacts: dict) -> None:
    """Task 5: Oracle independently classifies contacts and reproduces expected_contacts.json for all 20 students."""
    derived = classify_contacts_oracle(admissions)
    assert derived == expected_contacts, "Oracle contact classification mismatch against expected_contacts.json"


FORBIDDEN_DYNAMIC_MODULES = frozenset({"importlib", "pkgutil"})
FORBIDDEN_DYNAMIC_CALLS = frozenset({"__import__", "eval", "exec"})


def check_oracle_source_purity_ast(source: str, filename: str = "oracle.py") -> None:
    """Validate that source AST imports ONLY stdlib modules (allowlist), has zero dynamic/relative imports, and zero float usage."""
    tree = ast.parse(source, filename=filename)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root in sys.stdlib_module_names, (
                    f"Oracle purity violation: non-stdlib import '{alias.name}' at line {node.lineno}"
                )
                assert root not in FORBIDDEN_DYNAMIC_MODULES, (
                    f"Oracle purity violation: forbidden dynamic module '{alias.name}' at line {node.lineno}"
                )
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, (
                f"Oracle purity violation: forbidden relative import at line {node.lineno}"
            )
            mod = node.module or ""
            root = mod.split(".")[0]
            assert root in sys.stdlib_module_names, (
                f"Oracle purity violation: non-stdlib from-import '{mod}' at line {node.lineno}"
            )
            assert root not in FORBIDDEN_DYNAMIC_MODULES, (
                f"Oracle purity violation: forbidden dynamic module '{mod}' at line {node.lineno}"
            )
        elif isinstance(node, ast.Attribute) and node.attr == "modules" and isinstance(node.value, ast.Name):
            assert node.value.id != "sys", (
                f"Oracle purity violation: forbidden access to sys.modules at line {node.lineno}"
            )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in FORBIDDEN_DYNAMIC_CALLS, (
                f"Oracle purity violation: forbidden dynamic execution call '{node.func.id}' at line {node.lineno}"
            )
        elif isinstance(node, ast.Name):
            assert node.id != "float", (
                f"Oracle purity violation: forbidden use of 'float' name at line {node.lineno}"
            )
        elif isinstance(node, ast.Constant):
            assert not isinstance(node.value, float), (
                f"Oracle purity violation: forbidden float literal '{node.value}' at line {node.lineno}"
            )


def test_oracle_purity_ast() -> None:
    """Oracle purity: tests/oracle.py must import only stdlib modules and must never use float name or literals."""
    oracle_path = Path(__file__).parent / "oracle.py"
    source = oracle_path.read_text(encoding="utf-8")
    check_oracle_source_purity_ast(source, filename=str(oracle_path))


@pytest.mark.parametrize(
    ("snippet", "error_match"),
    [
        ("import src", "non-stdlib import 'src'"),
        ("from omr_dispatch.x import y", "non-stdlib from-import 'omr_dispatch.x'"),
        ("import importlib", "forbidden dynamic module 'importlib'"),
        ("from . import x", "forbidden relative import"),
        ('__import__("src")', "forbidden dynamic execution call '__import__'"),
        ("import yaml", "non-stdlib import 'yaml'"),
    ],
)
def test_oracle_purity_ast_bad_snippets(snippet: str, error_match: str) -> None:
    """Parametrized test running check_oracle_source_purity_ast on bad snippets, expecting each to fail."""
    with pytest.raises(AssertionError, match=re.escape(error_match)):
        check_oracle_source_purity_ast(snippet, filename="<snippet>")
