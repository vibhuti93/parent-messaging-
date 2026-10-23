"""
Stage S2 Ingestion & Input Contracts Test Suite.

Verifies:
  - All golden fixtures load unchanged through the importers (test_paper_300, admissions_300, submissions_300, marks_entry_50, isolation_two_orgs)
  - Zero float in core numerics: type(marks) is Fraction, "2.5" gives Fraction(5, 2)
  - Strict decimal format rules: reject exponents, signs, commas, Devanagari numerals, NaN/inf, blank
  - Half-mark validation: whole and half marks allowed only per ADR-0002
  - Attendance & marks rules: PRESENT with blank rejected, ABSENT with marks rejected, blanks never read as zero
  - Boundary rules: 0 <= marks <= max_marks, max_marks consistent within assessment
  - Rejection paths: unknown columns, duplicate IDs/rows, out-of-range questions, invalid options, missing records
  - One test per rejection path using fixtures in fixtures/ingestion/ with literal expected errors
  - Strict multi-tenancy: explicit org_id stamp and mismatch fail-closed
  - Atomicity: no partial import (single bad row causes zero records returned)
  - Settings: typed, SecretStr hygiene, safe dispatch defaults, extra="forbid"

All assertions compare against frozen literals. No mocks. Zero float.
"""

from __future__ import annotations

import zipfile
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from omr_dispatch.config import Settings
from omr_dispatch.ingestion import (
    import_answer_key,
    import_marks_entry,
    import_marks_entry_sheet,
    import_roster,
    import_submissions,
    import_test_paper,
)
from omr_dispatch.models import (
    AttendanceStatus,
    IngestionReasonCode,
    MarksValidationError,
    QuestionMeta,
    QuestionType,
    StudentAdmissionRow,
    parse_marks_decimal,
)

FIXTURES_GOLDEN = Path(__file__).resolve().parent.parent / "fixtures" / "golden"
FIXTURES_INGESTION = Path(__file__).resolve().parent.parent / "fixtures" / "ingestion"


# ==============================================================================
# 1. Golden Fixtures Ingestion (Unchanged)
# ==============================================================================


def test_golden_fixture_test_paper_300_container():
    """Test full TestPaper container import from golden test_paper_300.json."""
    file_path = FIXTURES_GOLDEN / "test_paper_300.json"
    result = import_test_paper(file_path=file_path, org_id="DEFAULT_INSTITUTION")

    assert result.is_success is True
    assert result.errors == []
    assert result.records is not None
    assert len(result.records) == 1

    paper = result.records[0]
    assert paper.test_id == "TEST_300"
    assert paper.schema_version == 1
    assert paper.org_id == "DEFAULT_INSTITUTION"
    assert len(paper.questions) == 75
    assert paper.max_marks == 300
    assert paper.name == "टर्म 1 डायग्नोस्टिक टेस्ट"

    q1 = paper.questions[0]
    assert q1.id == 1
    assert q1.question_number == 1
    assert q1.subject == "PHYSICS"
    assert q1.correct_option == "A"
    assert q1.positive_marks == 4
    assert q1.negative_marks == 1
    assert q1.blank_marks == 0
    assert q1.question_type == QuestionType.SINGLE_CORRECT
    assert q1.org_id == "DEFAULT_INSTITUTION"
    assert q1.schema_version == 1


def test_golden_fixture_test_paper_300_answer_key():
    """Test importing answer key questions from golden test_paper_300.json."""
    file_path = FIXTURES_GOLDEN / "test_paper_300.json"
    result = import_answer_key(file_path=file_path, org_id="DEFAULT_INSTITUTION")

    assert result.is_success is True
    assert result.errors == []
    assert result.records is not None
    assert len(result.records) == 75

    first_q = result.records[0]
    last_q = result.records[74]
    assert first_q.id == 1
    assert first_q.correct_option == "A"
    assert last_q.id == 75
    assert last_q.correct_option == "C"


def test_golden_fixture_admissions_300():
    """Test importing student roster from golden admissions_300.json."""
    file_path = FIXTURES_GOLDEN / "admissions_300.json"
    result = import_roster(file_path=file_path, org_id="DEFAULT_INSTITUTION")

    assert result.is_success is True
    assert result.errors == []
    assert result.records is not None
    assert len(result.records) == 20

    first_student = result.records[0]
    assert first_student.id == "STU_01"
    assert first_student.roll == "01"
    assert first_student.child_display_name == "आरव"
    assert first_student.class_section == "कक्षा 10-A"
    assert first_student.guardian_phone == "+91 98111-22202"
    assert first_student.org_id == "DEFAULT_INSTITUTION"
    assert first_student.schema_version == 1

    last_student = result.records[19]
    assert last_student.id == "STU_20"
    assert last_student.roll == "20"


def test_golden_fixture_submissions_300():
    """Test importing decoded OMR submissions from golden submissions_300.json."""
    file_path = FIXTURES_GOLDEN / "submissions_300.json"
    paper_path = FIXTURES_GOLDEN / "test_paper_300.json"
    ak_result = import_answer_key(file_path=paper_path, org_id="DEFAULT_INSTITUTION")
    assert ak_result.records is not None

    result = import_submissions(
        file_path=file_path,
        org_id="DEFAULT_INSTITUTION",
        answer_key=ak_result.records,
    )

    assert result.is_success is True
    assert result.errors == []
    assert result.records is not None
    assert len(result.records) == 20

    first_sub = result.records[0]
    assert first_sub.id == "SUB_300_01"
    assert first_sub.student_id == "STU_01"
    assert first_sub.status == AttendanceStatus.PRESENT
    assert len(first_sub.responses) == 75
    assert first_sub.responses["1"] == "A"
    assert first_sub.org_id == "DEFAULT_INSTITUTION"
    assert first_sub.schema_version == 1

    # STU_17 is ABSENT in golden fixture
    sub_17 = next(s for s in result.records if s.student_id == "STU_17")
    assert sub_17.status == AttendanceStatus.ABSENT
    assert sub_17.responses == {}


def test_golden_fixture_marks_entry_50():
    """Test importing marks entry sheet from golden marks_entry_50.json."""
    file_path = FIXTURES_GOLDEN / "marks_entry_50.json"
    result = import_marks_entry(file_path=file_path, org_id="DEFAULT_INSTITUTION")

    assert result.is_success is True
    assert result.errors == []
    assert result.records is not None
    assert len(result.records) == 6

    # Verify exact types and Fraction values
    for row in result.records:
        assert row.org_id == "DEFAULT_INSTITUTION"
        assert row.schema_version == 1
        assert row.max_marks == 50
        assert row.assessment_name == "यूनिट टेस्ट 1"

        if row.status == AttendanceStatus.PRESENT:
            assert isinstance(row.marks, Fraction)
            assert type(row.marks) is Fraction
        else:
            assert row.status == AttendanceStatus.ABSENT
            assert row.marks is None

    # Roll 01: 30.0 (Fraction(30, 1))
    r1 = next(r for r in result.records if r.roll_no == "01")
    assert r1.marks == Fraction(30, 1)
    assert r1.status == AttendanceStatus.PRESENT

    # Roll 06: ABSENT
    r6 = next(r for r in result.records if r.roll_no == "06")
    assert r6.status == AttendanceStatus.ABSENT
    assert r6.marks is None


def test_golden_fixture_marks_entry_50_sheet_container():
    """Test importing full MarksEntrySheet container from golden marks_entry_50.json."""
    file_path = FIXTURES_GOLDEN / "marks_entry_50.json"
    result = import_marks_entry_sheet(file_path=file_path, org_id="DEFAULT_INSTITUTION")

    assert result.is_success is True
    assert result.errors == []
    assert result.records is not None
    assert len(result.records) == 1

    sheet = result.records[0]
    assert sheet.assessment_name == "यूनिट टेस्ट 1"
    assert sheet.max_marks == 50
    assert sheet.org_id == "DEFAULT_INSTITUTION"
    assert sheet.schema_version == 1
    assert len(sheet.rows) == 6


def test_golden_fixture_isolation_two_orgs():
    """Test multi-tenant roster import with strict org isolation."""
    file_path = FIXTURES_GOLDEN / "isolation_two_orgs.json"

    # Ingestion for ORG_ALPHA
    res_alpha = import_roster(file_path=file_path, org_id="ORG_ALPHA")
    assert res_alpha.is_success is True
    assert res_alpha.records is not None
    assert len(res_alpha.records) == 1
    stu_alpha = res_alpha.records[0]
    assert stu_alpha.id == "STU_ALPHA_01"
    assert stu_alpha.org_id == "ORG_ALPHA"
    assert stu_alpha.marks == Fraction(55, 1)

    # Ingestion for ORG_BETA
    res_beta = import_roster(file_path=file_path, org_id="ORG_BETA")
    assert res_beta.is_success is True
    assert res_beta.records is not None
    assert len(res_beta.records) == 1
    stu_beta = res_beta.records[0]
    assert stu_beta.id == "STU_BETA_01"
    assert stu_beta.org_id == "ORG_BETA"
    assert stu_beta.marks == Fraction(90, 1)

    # Ingestion for unknown org fails closed
    res_gamma = import_roster(file_path=file_path, org_id="ORG_GAMMA")
    assert res_gamma.is_success is False
    assert res_gamma.records is None
    assert len(res_gamma.errors) == 1
    assert res_gamma.errors[0].reason_code == IngestionReasonCode.ORG_ID_MISMATCH


def test_marks_boundary_exact_max_marks_allowed(tmp_path: Path):
    """Verify that marks == max_marks (boundary condition 0 <= marks <= max_marks) is accepted."""
    csv_file = tmp_path / "full_marks.csv"
    csv_file.write_text("roll_no,status,marks,max_marks\n101,PRESENT,50,50\n", encoding="utf-8")
    res = import_marks_entry(csv_file, org_id="org_test")
    assert res.is_success is True
    assert res.records is not None
    assert len(res.records) == 1
    assert res.records[0].marks == Fraction(50, 1)


# ==============================================================================
# 2. Exact Fraction Marks Arithmetic & Validation
# ==============================================================================


def test_marks_parsing_exactness_2_point_5():
    """Verify '2.5' gives exactly Fraction(5, 2) and type is Fraction."""
    f = parse_marks_decimal("2.5")
    assert type(f) is Fraction
    assert f == Fraction(5, 2)
    assert f.numerator == 5
    assert f.denominator == 2


def test_marks_parsing_valid_whole_and_half_marks():
    """Verify valid whole and half marks parse to exact fractions."""
    cases = [
        ("0", Fraction(0, 1)),
        ("0.0", Fraction(0, 1)),
        ("0.5", Fraction(1, 2)),
        ("1", Fraction(1, 1)),
        ("1.0", Fraction(1, 1)),
        ("1.5", Fraction(3, 2)),
        ("42", Fraction(42, 1)),
        ("99.5", Fraction(199, 2)),
        ("100", Fraction(100, 1)),
        ("100.0", Fraction(100, 1)),
    ]
    for text_val, expected in cases:
        parsed = parse_marks_decimal(text_val)
        assert type(parsed) is Fraction
        assert parsed == expected
        assert parsed.numerator == expected.numerator
        assert parsed.denominator == expected.denominator


def test_marks_parsing_rejects_non_half_fractions():
    """Reject fractions other than .0 or .5 per ADR-0002."""
    invalid_cases = ["2.3", "2.75", "0.25", "1.1", "10.2", "45.7"]
    for text_val in invalid_cases:
        with pytest.raises(MarksValidationError) as exc_info:
            parse_marks_decimal(text_val)
        assert "not a whole or half mark" in str(exc_info.value)


def test_marks_parsing_rejects_invalid_formats():
    """Reject exponents, signs, commas, Devanagari digits, NaN, inf, and blanks."""
    invalid_formats = [
        "1e2",          # Exponent notation
        "2.5e0",        # Exponent notation
        "+2.5",         # Explicit plus sign
        "-1.0",         # Negative sign
        "-0.5",         # Negative sign
        "1,000",        # Thousands separator
        "1,000.5",      # Thousands separator
        "२.५",          # Devanagari digits
        "५०",           # Devanagari digits
        "NaN",          # Special float token
        "nan",          # Special float token
        "inf",          # Infinity
        "-Infinity",    # Infinity
        "",             # Empty string
        "   ",          # Whitespace
        "abc",          # Non-numeric string
        "1.5.0",        # Multiple decimal points
    ]
    for text_val in invalid_formats:
        with pytest.raises(MarksValidationError):
            parse_marks_decimal(text_val)


def test_marks_parsing_rejects_float_input():
    """Reject passing float objects directly to prevent precision loss."""
    with pytest.raises(MarksValidationError) as exc_info:
        parse_marks_decimal(2.5)  # type: ignore[arg-type]
    assert "Native float marks are forbidden per ADR-0002" in str(exc_info.value)


# ==============================================================================
# 3. Rejection Paths via Fixtures (One test per rejection path)
# ==============================================================================


def test_rejection_roster_unknown_column():
    """Rejection path: roster with unknown column returns UNKNOWN_COLUMN error."""
    file_path = FIXTURES_INGESTION / "roster_unknown_col.csv"
    res = import_roster(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.row == 1
    assert err.field == "unexpected_col"
    assert err.reason_code == IngestionReasonCode.UNKNOWN_COLUMN


def test_rejection_roster_duplicate_id():
    """Rejection path: roster with duplicate student_id returns DUPLICATE_ID error."""
    file_path = FIXTURES_INGESTION / "roster_duplicate_id.json"
    res = import_roster(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.row == 2
    assert err.field == "student_id"
    assert err.reason_code == IngestionReasonCode.DUPLICATE_ID


def test_rejection_roster_duplicate_roll():
    """Rejection path: roster with duplicate roll in cohort returns DUPLICATE_ROW error."""
    file_path = FIXTURES_INGESTION / "roster_duplicate_roll.csv"
    res = import_roster(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.row == 2
    assert err.field == "roll_number"
    assert err.reason_code == IngestionReasonCode.DUPLICATE_ROW


def test_rejection_test_paper_unsupported_question_type():
    """Rejection path: question_type other than SINGLE_CORRECT raises NotSupportedError / UNSUPPORTED_QUESTION_TYPE."""
    file_path = FIXTURES_INGESTION / "test_paper_unsupported_type.json"
    res = import_answer_key(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "question_type"
    assert err.reason_code == IngestionReasonCode.UNSUPPORTED_QUESTION_TYPE


def test_rejection_test_paper_invalid_option():
    """Rejection path: correct_option outside {A, B, C, D} returns INVALID_OPTION error."""
    file_path = FIXTURES_INGESTION / "test_paper_invalid_option.json"
    res = import_answer_key(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "correct_option"
    assert err.reason_code == IngestionReasonCode.INVALID_OPTION


def test_rejection_test_paper_duplicate_question():
    """Rejection path: duplicate question ID returns DUPLICATE_ID error."""
    file_path = FIXTURES_INGESTION / "test_paper_duplicate_q.json"
    res = import_answer_key(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "question_id"
    assert err.reason_code == IngestionReasonCode.DUPLICATE_ID


def test_rejection_submissions_out_of_range_question():
    """Rejection path: submission responding to question not in answer key returns OUT_OF_RANGE_QUESTION_ID."""
    file_path = FIXTURES_INGESTION / "submissions_out_of_range.json"
    ak = [
        QuestionMeta(
            id=1,
            subject="General",
            question_type=QuestionType.SINGLE_CORRECT,
            correct_option="A",
            positive_marks=4,
            negative_marks=1,
            org_id="org_test",
            schema_version=1,
        )
    ]
    res = import_submissions(file_path=file_path, org_id="org_test", answer_key=ak)

    assert res.is_success is False
    assert res.records is None
    assert any(err.reason_code == IngestionReasonCode.OUT_OF_RANGE_QUESTION_ID for err in res.errors)


def test_rejection_submissions_missing_record():
    """Rejection path: present student missing required questions returns MISSING_RECORD error."""
    file_path = FIXTURES_INGESTION / "submissions_missing_record.json"
    ak = [
        QuestionMeta(
            id=1,
            subject="General",
            question_type=QuestionType.SINGLE_CORRECT,
            correct_option="A",
            positive_marks=4,
            negative_marks=1,
            org_id="org_test",
            schema_version=1,
        ),
        QuestionMeta(
            id=2,
            subject="General",
            question_type=QuestionType.SINGLE_CORRECT,
            correct_option="B",
            positive_marks=4,
            negative_marks=1,
            org_id="org_test",
            schema_version=1,
        ),
    ]
    res = import_submissions(file_path=file_path, org_id="org_test", answer_key=ak)

    assert res.is_success is False
    assert res.records is None
    assert any(err.reason_code == IngestionReasonCode.MISSING_RECORD for err in res.errors)


def test_rejection_submissions_invalid_option():
    """Rejection path: submission with invalid bubble character returns INVALID_OPTION error."""
    file_path = FIXTURES_INGESTION / "submissions_invalid_option.csv"
    res = import_submissions(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert any(err.reason_code == IngestionReasonCode.INVALID_OPTION for err in res.errors)


def test_rejection_submissions_duplicate_student():
    """Rejection path: multiple submissions for same student returns DUPLICATE_ID error."""
    file_path = FIXTURES_INGESTION / "submissions_duplicate_student.json"
    res = import_submissions(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert any(err.reason_code == IngestionReasonCode.DUPLICATE_ID for err in res.errors)


def test_rejection_marks_present_blank():
    """Rejection path: PRESENT student with blank marks returns PRESENT_WITH_BLANK_MARKS error."""
    file_path = FIXTURES_INGESTION / "marks_present_blank.csv"
    res = import_marks_entry(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "marks"
    assert err.reason_code == IngestionReasonCode.PRESENT_WITH_BLANK_MARKS


def test_rejection_marks_absent_with_marks():
    """Rejection path: ABSENT student with recorded marks returns ABSENT_WITH_MARKS error."""
    file_path = FIXTURES_INGESTION / "marks_absent_with_marks.csv"
    res = import_marks_entry(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "marks"
    assert err.reason_code == IngestionReasonCode.ABSENT_WITH_MARKS


def test_rejection_marks_non_half_fraction():
    """Rejection path: marks with non-half fraction returns FRACTIONAL_MARK_NOT_HALF error."""
    file_path = FIXTURES_INGESTION / "marks_non_half_fraction.csv"
    res = import_marks_entry(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "marks"
    assert err.reason_code == IngestionReasonCode.FRACTIONAL_MARK_NOT_HALF


def test_rejection_marks_devanagari_digits():
    """Rejection path: Devanagari numerals in marks return INVALID_MARK_FORMAT error."""
    file_path = FIXTURES_INGESTION / "marks_devanagari_digits.csv"
    res = import_marks_entry(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "marks"
    assert err.reason_code == IngestionReasonCode.INVALID_MARK_FORMAT


def test_rejection_marks_exponent_notation():
    """Rejection path: exponent notation in marks returns INVALID_MARK_FORMAT error."""
    file_path = FIXTURES_INGESTION / "marks_exponent_notation.csv"
    res = import_marks_entry(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "marks"
    assert err.reason_code == IngestionReasonCode.INVALID_MARK_FORMAT


def test_rejection_marks_negative():
    """Rejection path: negative marks return INVALID_MARK_FORMAT / MARK_BELOW_ZERO error."""
    file_path = FIXTURES_INGESTION / "marks_negative.csv"
    res = import_marks_entry(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "marks"
    assert err.reason_code in (
        IngestionReasonCode.INVALID_MARK_FORMAT,
        IngestionReasonCode.MARK_BELOW_ZERO,
    )


def test_rejection_marks_exceeds_max():
    """Rejection path: marks exceeding max_marks return MARK_EXCEEDS_MAX error."""
    file_path = FIXTURES_INGESTION / "marks_exceeds_max.csv"
    res = import_marks_entry(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "marks"
    assert err.reason_code == IngestionReasonCode.MARK_EXCEEDS_MAX


def test_rejection_marks_duplicate_roll():
    """Rejection path: duplicate roll number in marks entry returns DUPLICATE_ROW error."""
    file_path = FIXTURES_INGESTION / "marks_duplicate_roll.csv"
    res = import_marks_entry(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "roll_no"
    assert err.reason_code == IngestionReasonCode.DUPLICATE_ROW


def test_rejection_marks_unknown_roll():
    """Rejection path: roll number not enrolled in roster returns UNKNOWN_ROLL_NUMBER error."""
    file_path = FIXTURES_INGESTION / "marks_unknown_roll.csv"
    roster = [
        StudentAdmissionRow(
            id="STU-001",
            roll="101",
            class_section="10-A",
            child_display_name="Aarav",
            org_id="org_test",
            schema_version=1,
        )
    ]
    res = import_marks_entry(file_path=file_path, org_id="org_test", roster=roster)

    assert res.is_success is False
    assert res.records is None
    assert any(err.reason_code == IngestionReasonCode.UNKNOWN_ROLL_NUMBER for err in res.errors)


def test_rejection_marks_inconsistent_max():
    """Rejection path: inconsistent max_marks values return INCONSISTENT_MAX_MARKS error."""
    file_path = FIXTURES_INGESTION / "marks_inconsistent_max.csv"
    res = import_marks_entry(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "max_marks"
    assert err.reason_code == IngestionReasonCode.INCONSISTENT_MAX_MARKS


def test_rejection_org_id_mismatch():
    """Rejection path: file carrying mismatched org_id fails closed."""
    file_path = FIXTURES_INGESTION / "org_id_mismatch.json"
    res = import_answer_key(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.field == "org_id"
    assert err.reason_code == IngestionReasonCode.ORG_ID_MISMATCH


def test_rejection_corrupted_file():
    """Rejection path: malformed JSON returns CORRUPTED_FILE error."""
    file_path = FIXTURES_INGESTION / "corrupted.json"
    res = import_roster(file_path=file_path, org_id="org_test")

    assert res.is_success is False
    assert res.records is None
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.reason_code == IngestionReasonCode.CORRUPTED_FILE


# ==============================================================================
# 4. Atomicity & Invariants
# ==============================================================================


def test_no_partial_import_guarantee(tmp_path: Path):
    """
    Verify the strict no-partial-import guarantee:
    Even if 9 out of 10 rows are completely valid, a single invalid row causes
    the entire import to return records=None and is_success=False.
    """
    csv_content = (
        "roll_no,status,marks,max_marks\n"
        "101,PRESENT,40,50\n"
        "102,PRESENT,42,50\n"
        "103,PRESENT,38.5,50\n"
        "104,PRESENT,45,50\n"
        "105,ABSENT,,50\n"
        "106,PRESENT,48,50\n"
        "107,PRESENT,35,50\n"
        "108,PRESENT,2.3,50\n"  # BAD ROW: 2.3 is not whole or half mark
        "109,PRESENT,41,50\n"
        "110,PRESENT,39,50\n"
    )
    bad_file = tmp_path / "mixed_marks.csv"
    bad_file.write_text(csv_content, encoding="utf-8")

    result = import_marks_entry(file_path=bad_file, org_id="org_test")

    assert result.is_success is False
    assert result.records is None
    assert len(result.errors) == 1
    assert result.errors[0].row == 8
    assert result.errors[0].reason_code == IngestionReasonCode.FRACTIONAL_MARK_NOT_HALF


def test_org_id_mismatch_across_all_importers(tmp_path: Path):
    """Verify that every importer rejects a file when org_id differs from function argument."""
    # JSON with conflicting org
    mismatched_json = (
        '{"org_id": "ORG_FOREIGN", "schema_version": 1, "test_id": "T1", '
        '"questions": [{"id": 1, "question_number": 1, "question_type": "SINGLE_CORRECT", '
        '"correct_option": "A", "positive_marks": 4, "negative_marks": 1, "blank_marks": 0}], '
        '"students": [{"id": "S1", "student_id": "S1", "roll_number": "01", "class_section": "10-A"}], '
        '"submissions": [{"submission_id": "SUB-1", "student_id": "S1", "status": "PRESENT", "responses": {"1": "A"}}]}'
    )
    test_file = tmp_path / "mismatched.json"
    test_file.write_text(mismatched_json, encoding="utf-8")

    res_roster = import_roster(test_file, org_id="ORG_LOCAL")
    assert res_roster.is_success is False
    assert res_roster.records is None
    assert any(e.reason_code == IngestionReasonCode.ORG_ID_MISMATCH for e in res_roster.errors)

    res_paper = import_test_paper(test_file, org_id="ORG_LOCAL")
    assert res_paper.is_success is False
    assert res_paper.records is None
    assert any(e.reason_code == IngestionReasonCode.ORG_ID_MISMATCH for e in res_paper.errors)

    res_ak = import_answer_key(test_file, org_id="ORG_LOCAL")
    assert res_ak.is_success is False
    assert res_ak.records is None
    assert any(e.reason_code == IngestionReasonCode.ORG_ID_MISMATCH for e in res_ak.errors)

    res_sub = import_submissions(test_file, org_id="ORG_LOCAL")
    assert res_sub.is_success is False
    assert res_sub.records is None
    assert any(e.reason_code == IngestionReasonCode.ORG_ID_MISMATCH for e in res_sub.errors)


# ==============================================================================
# 5. Zero-Dependency XLSX Parsing
# ==============================================================================


def test_zero_dependency_xlsx_parsing(tmp_path: Path):
    """
    Verify that our stdlib zipfile/xml parser parses .xlsx marks entry files correctly
    without requiring openpyxl or other external dependencies.
    """
    xlsx_path = tmp_path / "marks_sample.xlsx"

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        '<row r="1">'
        '<c r="A1" t="s"><v>0</v></c>'
        '<c r="B1" t="s"><v>1</v></c>'
        '<c r="C1" t="s"><v>2</v></c>'
        '<c r="D1" t="s"><v>3</v></c>'
        '</row>'
        '<row r="2">'
        '<c r="A2" t="s"><v>4</v></c>'
        '<c r="B2" t="s"><v>5</v></c>'
        '<c r="C2"><v>45.5</v></c>'
        '<c r="D2"><v>50</v></c>'
        '</row>'
        '</sheetData>'
        '</worksheet>'
    )

    shared_strings_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="6" uniqueCount="6">'
        '<si><t>roll_no</t></si>'
        '<si><t>status</t></si>'
        '<si><t>marks</t></si>'
        '<si><t>max_marks</t></si>'
        '<si><t>101</t></si>'
        '<si><t>PRESENT</t></si>'
        '</sst>'
    )

    with zipfile.ZipFile(xlsx_path, "w") as zf:
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/sharedStrings.xml", shared_strings_xml)

    res = import_marks_entry(file_path=xlsx_path, org_id="org_test")
    assert res.is_success is True
    assert res.records is not None
    assert len(res.records) == 1
    row = res.records[0]
    assert row.roll_no == "101"
    assert row.status == AttendanceStatus.PRESENT
    assert row.marks == Fraction(91, 2)
    assert row.max_marks == 50


def test_xlsx_sparse_cell_and_corrupt_xml_handling(tmp_path: Path):
    """
    Verify sparse cell coordinate mapping (missing cell B2/C2 does not misalign columns)
    and safe handling of malformed XML in .xlsx packages.
    """
    # 1. Sparse row: Row 2 is ABSENT student with no C2 cell (sparse marks cell)
    sparse_xlsx = tmp_path / "sparse.xlsx"
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        '<row r="1">'
        '<c r="A1" t="s"><v>0</v></c>'
        '<c r="B1" t="s"><v>1</v></c>'
        '<c r="C1" t="s"><v>2</v></c>'
        '<c r="D1" t="s"><v>3</v></c>'
        '</row>'
        '<row r="2">'
        '<c r="A2" t="s"><v>4</v></c>'
        '<c r="B2" t="s"><v>5</v></c>'
        '<!-- C2 omitted: sparse missing cell -->'
        '<c r="D2"><v>50</v></c>'
        '</row>'
        '</sheetData>'
        '</worksheet>'
    )
    shared_strings_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="6" uniqueCount="6">'
        '<si><t>roll_no</t></si>'
        '<si><t>status</t></si>'
        '<si><t>marks</t></si>'
        '<si><t>max_marks</t></si>'
        '<si><t>102</t></si>'
        '<si><t>ABSENT</t></si>'
        '</sst>'
    )
    with zipfile.ZipFile(sparse_xlsx, "w") as zf:
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/sharedStrings.xml", shared_strings_xml)

    res = import_marks_entry(file_path=sparse_xlsx, org_id="org_test")
    assert res.is_success is True
    assert res.records is not None
    assert len(res.records) == 1
    assert res.records[0].roll_no == "102"
    assert res.records[0].status == AttendanceStatus.ABSENT
    assert res.records[0].marks is None
    assert res.records[0].max_marks == 50

    # 2. Corrupted / entity-expanded XML in xlsx
    corrupt_xlsx = tmp_path / "corrupt.xlsx"
    with zipfile.ZipFile(corrupt_xlsx, "w") as zf:
        zf.writestr("xl/worksheets/sheet1.xml", "<worksheet><malformed>")

    res_corrupt = import_marks_entry(file_path=corrupt_xlsx, org_id="org_test")
    assert res_corrupt.is_success is False
    assert res_corrupt.records is None
    assert len(res_corrupt.errors) == 1
    assert res_corrupt.errors[0].reason_code == IngestionReasonCode.CORRUPTED_FILE


# ==============================================================================
# 6. Configuration & Settings Security Hygiene
# ==============================================================================


def test_settings_safe_defaults():
    """Verify Settings initializes with safe production-fail-closed defaults."""
    settings = Settings()

    # Safety switches default to False
    assert settings.live_dispatch_enabled is False
    assert settings.deployment_compliance_acknowledged is False
    assert settings.network_tts_enabled is False
    assert settings.include_roll_in_text is False

    # Operational defaults
    assert settings.max_batch_size == 200
    assert settings.default_timezone == "Asia/Kolkata"
    assert settings.sqlite_db_path == "omr_dispatch.db"
    assert settings.audio_assets_dir == "assets/audio"

    # Credentials default to empty SecretStr
    assert settings.whatsapp_cloud_api_token.get_secret_value() == ""
    assert settings.whatsapp_access_token.get_secret_value() == ""
    assert settings.whatsapp_app_secret.get_secret_value() == ""


def test_settings_secret_hygiene():
    """Verify credentials use SecretStr and do not expose secrets in __repr__."""
    settings = Settings(
        whatsapp_cloud_api_token=SecretStr("super_secret_token_123"),
        whatsapp_app_secret=SecretStr("super_secret_app_secret_456"),
    )

    assert settings.whatsapp_cloud_api_token.get_secret_value() == "super_secret_token_123"
    assert settings.whatsapp_app_secret.get_secret_value() == "super_secret_app_secret_456"

    repr_str = repr(settings)
    assert "super_secret_token_123" not in repr_str
    assert "super_secret_app_secret_456" not in repr_str
    assert "**********" in repr_str


def test_settings_forbids_extra_fields():
    """Verify Settings raises ValidationError if unknown config keys are supplied."""
    with pytest.raises(ValidationError):
        Settings.model_validate({"unknown_config_key": "some_value"})
