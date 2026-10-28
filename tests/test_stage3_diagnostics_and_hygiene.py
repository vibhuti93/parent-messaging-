"""
Stage S3 Test Suite: Deterministic Diagnostics, Contact Hygiene, and Walking Skeleton CLI.

Compliant with:
- Global Invariants:
    1. Literals from approved fixtures.
    2. Zero float (ADR-0002).
    3. Fail closed on uncertain input.
    4. Mock only external boundaries (none here; 100% local components).
- ADR-0002: Exact Fraction arithmetic, integer cross-multiplication, Decimal ROUND_HALF_UP.
- ADR-0004: SINGLE_CORRECT question type supported; marking scheme as data.
- ADR-0008: Typed exception hierarchy.
- ADR-0010: Unicode NFC normalization.
- ADR-0013: Walking skeleton CLI verification (OMR_MCQ and MARKS_ENTRY_TOTALS).
- ADR-0016: Capability branching, NOT_AVAILABLE sentinels for marks entry.
- ADR-0017: Multi-tenant tenant context isolation.
"""

from __future__ import annotations

import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from omr_dispatch.cli import main as cli_main
from omr_dispatch.cli import run_batch_pipeline
from omr_dispatch.contacts import (
    PhoneNormalizationReason,
    format_e164,
    mask_phone,
    normalize_indian_mobile,
    normalize_indian_mobile_with_reason,
    validate_admission_batch,
)
from omr_dispatch.diagnostics import (
    check_requires_ptm_slip,
    classify_status_band,
    compute_standard_competition_ranks,
    evaluate_batch,
    evaluate_omr_mcq_batch,
    find_easy_questions,
    format_decimal_1dp,
    format_percentage_display,
)
from omr_dispatch.models import (
    NOT_AVAILABLE,
    AssessmentKind,
    AttendanceStatus,
    ContactQuarantineFlag,
    DuplicateRecordError,
    EvaluationBundle,
    MarksEntryRow,
    MarksEntrySheet,
    OrgIdMismatchError,
    QuestionMeta,
    SchemaValidationError,
    StatusBand,
    StudentAdmissionRow,
    StudentDiagnosticReport,
    StudentOMRSubmission,
    SubjectDiagnosticLabel,
    TestPaper,
)

TestPaper.__test__ = False  # Suppress pytest collection warning for model class

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden"


def load_fixture(filename: str) -> dict:
    path = FIXTURES_DIR / filename
    assert path.exists(), f"Fixture missing: {filename}"
    return json.loads(path.read_text(encoding="utf-8"))


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture(scope="module")
def golden_test_paper() -> dict:
    return load_fixture("test_paper_300.json")


@pytest.fixture(scope="module")
def golden_admissions() -> dict:
    return load_fixture("admissions_300.json")


@pytest.fixture(scope="module")
def golden_submissions() -> dict:
    return load_fixture("submissions_300.json")


@pytest.fixture(scope="module")
def golden_expected_reports() -> dict:
    return load_fixture("expected_reports.json")


@pytest.fixture(scope="module")
def golden_expected_contacts() -> dict:
    return load_fixture("expected_contacts.json")


@pytest.fixture(scope="module")
def golden_marks_entry() -> dict:
    return load_fixture("marks_entry_50.json")


@pytest.fixture(scope="module")
def golden_expected_marks_reports() -> dict:
    return load_fixture("expected_marks_reports.json")


@pytest.fixture(scope="module")
def edge_cases() -> dict:
    return load_fixture("edge_cases.json")


# ==============================================================================
# 1. Phone Normalization & Validation (S3 Task 1)
# ==============================================================================


class TestPhoneNormalization:
    """Test mobile number normalization and reason code tracking (S3 Task 1)."""

    def test_standard_valid_10_digit_numbers(self) -> None:
        valid_samples = [
            ("9811122201", "9811122201"),
            ("8811122202", "8811122202"),
            ("7811122203", "7811122203"),
            ("6811122204", "6811122204"),
        ]
        for raw, expected in valid_samples:
            norm, reason = normalize_indian_mobile_with_reason(raw)
            assert norm == expected
            assert reason == PhoneNormalizationReason.VALID
            assert normalize_indian_mobile(raw) == expected

    def test_prefix_stripping_and_formatting(self) -> None:
        # +91 prefix and formatting characters (spaces, hyphens, parentheses)
        raw_1 = "+91 98111-22201"
        assert normalize_indian_mobile(raw_1) == "9811122201"

        # 12 digits starting with 91
        raw_2 = "919811122202"
        assert normalize_indian_mobile(raw_2) == "9811122202"

        # 11 digits starting with trunk 0
        raw_3 = "09811122203"
        assert normalize_indian_mobile(raw_3) == "9811122203"

        # Combined parentheses and trunk 0
        raw_4 = "(098) 111-22204"
        assert normalize_indian_mobile(raw_4) == "9811122204"

        # Trailing / leading whitespace
        raw_5 = "  +91 (98200) 100-05   "
        assert normalize_indian_mobile(raw_5) == "9820010005"

    def test_rejection_of_invalid_starting_digit(self) -> None:
        # Indian mobile numbers must start with 6, 7, 8, or 9
        invalid_starters = ["5511122207", "4411122208", "3311122209", "1811122200", "0811122200"]
        for num in invalid_starters:
            norm, reason = normalize_indian_mobile_with_reason(num)
            # If 11 digits with 0, stripped to 10 digits starting with 8 is valid,
            # but if 10 digits starting with 0-5 it must be rejected
            if len(num) == 10 and num[0] in "012345":
                assert norm is None
                assert reason == PhoneNormalizationReason.INVALID_STARTING_DIGIT
                assert normalize_indian_mobile(num) is None

    def test_rejection_of_invalid_lengths(self) -> None:
        # Too short
        norm_short, reason_short = normalize_indian_mobile_with_reason("98111222")
        assert norm_short is None
        assert reason_short == PhoneNormalizationReason.INVALID_LENGTH

        # Too long (13 digits not matching 91 prefix)
        norm_long, reason_long = normalize_indian_mobile_with_reason("9811122201123")
        assert norm_long is None
        assert reason_long == PhoneNormalizationReason.INVALID_LENGTH

    def test_rejection_of_alphabetic_and_malformed_chars(self) -> None:
        malformed_inputs = [
            "98111ABCD1",
            "98111@22201",
            "98111#22201",
            "98111$22201",
            "phone-number",
        ]
        for mal in malformed_inputs:
            norm, reason = normalize_indian_mobile_with_reason(mal)
            assert norm is None
            assert reason == PhoneNormalizationReason.MALFORMED_CHARACTERS
            assert normalize_indian_mobile(mal) is None

    def test_empty_and_none_handling(self) -> None:
        for empty_val in [None, "", "   ", "---", "()"]:
            norm, reason = normalize_indian_mobile_with_reason(empty_val)
            assert norm is None
            assert reason == PhoneNormalizationReason.EMPTY
            assert normalize_indian_mobile(empty_val) is None

    def test_e164_formatting_and_masking(self) -> None:
        assert format_e164("9811122201") == "+919811122201"
        assert format_e164(None) is None
        assert format_e164("123") is None

        masked = mask_phone("9811122201")
        assert masked == "98*** **01"
        assert "9811122201" not in masked  # Unmasked number must never appear


# ==============================================================================
# 2. Contact Hygiene & Admission Validation (S3 Task 2)
# ==============================================================================


class TestContactHygieneAndAdmissionValidation:
    """Test contact safety quarantine and eligibility validation (S3 Task 2)."""

    def test_golden_admissions_300_matches_expected_contacts_exactly(
        self,
        golden_admissions: dict,
        golden_expected_contacts: dict,
    ) -> None:
        """Every student in STU_01 through STU_20 matches expected_contacts.json."""
        evaluations = validate_admission_batch(golden_admissions["students"])
        eval_map = {e.student_id: e for e in evaluations}
        expected_map = {c["student_id"]: c for c in golden_expected_contacts["contacts"]}

        assert len(eval_map) == 20

        for sid, exp in expected_map.items():
            act = eval_map[sid]
            assert act.is_quarantined == exp["is_quarantined"], f"{sid} quarantine mismatch"
            assert act.quarantine_flags == exp["quarantine_flags"], f"{sid} flags mismatch"
            assert act.dispatch_eligible == exp["dispatch_eligible"], f"{sid} eligibility mismatch"
            assert act.exclusion_reason == exp["exclusion_reason"], f"{sid} exclusion mismatch"

    def test_interception_risk_same_number(self) -> None:
        """STU_02: student and guardian share normalized number 9811122203."""
        evals = validate_admission_batch([
            StudentAdmissionRow(
                id="STU_02",
                roll="02",
                child_display_name="प्रिया",
                class_section="कक्षा 10-A",
                raw_student_phone="09811122203",
                raw_guardian_phone="9811122203",
                verified_sibling=False,
                guardian_verification="VERIFIED",
                consent_status="OPT_IN",
            )
        ])
        assert len(evals) == 1
        e = evals[0]
        assert e.is_quarantined is True
        assert ContactQuarantineFlag.INTERCEPTION_RISK_SAME_NUMBER.value in e.quarantine_flags
        assert e.dispatch_eligible is False
        assert e.exclusion_reason == ContactQuarantineFlag.INTERCEPTION_RISK_SAME_NUMBER.value
        assert e.manual_resolution_status == "PENDING_OPERATOR_REVIEW"

    def test_duplicate_parent_unverified_collision(self) -> None:
        """STU_03 and STU_04: shared parent without verified siblings."""
        evals = validate_admission_batch([
            StudentAdmissionRow(
                id="STU_03",
                roll="03",
                child_display_name="रोहन",
                class_section="कक्षा 10-A",
                raw_guardian_phone="9811122299",
                verified_sibling=False,
                guardian_verification="VERIFIED",
                consent_status="OPT_IN",
            ),
            StudentAdmissionRow(
                id="STU_04",
                roll="04",
                child_display_name="ईशान",
                class_section="कक्षा 10-A",
                raw_guardian_phone="9811122299",
                verified_sibling=False,
                guardian_verification="VERIFIED",
                consent_status="OPT_IN",
            ),
        ])
        for e in evals:
            assert e.is_quarantined is True
            assert ContactQuarantineFlag.DUPLICATE_PARENT_UNVERIFIED.value in e.quarantine_flags
            assert e.dispatch_eligible is False
            assert e.exclusion_reason == ContactQuarantineFlag.DUPLICATE_PARENT_UNVERIFIED.value

    def test_sibling_exception_not_quarantined(self) -> None:
        """STU_05 and STU_06: shared parent with verified_sibling=True -> NOT quarantined."""
        evals = validate_admission_batch([
            StudentAdmissionRow(
                id="STU_05",
                roll="05",
                child_display_name="कबीर",
                class_section="कक्षा 10-A",
                raw_guardian_phone="9811122288",
                verified_sibling=True,
                guardian_verification="VERIFIED",
                consent_status="OPT_IN",
            ),
            StudentAdmissionRow(
                id="STU_06",
                roll="06",
                child_display_name="अनन्या",
                class_section="कक्षा 10-A",
                raw_guardian_phone="9811122288",
                verified_sibling=True,
                guardian_verification="VERIFIED",
                consent_status="OPT_IN",
            ),
        ])
        for e in evals:
            assert e.is_quarantined is False
            assert e.quarantine_flags == []
            assert e.dispatch_eligible is True
            assert e.exclusion_reason is None

    def test_invalid_phone_quarantine(self) -> None:
        """STU_07: invalid guardian phone (5511122207) -> INVALID_PHONE_NUMBER."""
        evals = validate_admission_batch([
            StudentAdmissionRow(
                id="STU_07",
                roll="07",
                child_display_name="विहान",
                class_section="कक्षा 10-A",
                raw_guardian_phone="5511122207",
                verified_sibling=False,
                guardian_verification="VERIFIED",
                consent_status="OPT_IN",
            )
        ])
        assert len(evals) == 1
        e = evals[0]
        assert e.is_quarantined is True
        assert ContactQuarantineFlag.INVALID_PHONE_NUMBER.value in e.quarantine_flags
        assert e.dispatch_eligible is False
        assert e.exclusion_reason == ContactQuarantineFlag.INVALID_PHONE_NUMBER.value

    def test_consent_and_verification_exclusions(self) -> None:
        """Consent not OPT_IN or guardian not VERIFIED -> blocked without quarantine."""
        rows = [
            StudentAdmissionRow(
                id="STU_08",
                roll="08",
                child_display_name="आदित्य",
                class_section="कक्षा 10-A",
                raw_guardian_phone="9830010008",
                consent_status="UNKNOWN",
                guardian_verification="VERIFIED",
            ),
            StudentAdmissionRow(
                id="STU_09",
                roll="09",
                child_display_name="दीया",
                class_section="कक्षा 10-A",
                raw_guardian_phone="9830010009",
                consent_status="REVOKED",
                guardian_verification="VERIFIED",
            ),
            StudentAdmissionRow(
                id="STU_10",
                roll="10",
                child_display_name="आरुष",
                class_section="कक्षा 10-A",
                raw_guardian_phone="9830010010",
                consent_status="OPT_IN",
                guardian_verification="UNVERIFIED",
            ),
        ]
        evals = validate_admission_batch(rows)
        e_map = {e.student_id: e for e in evals}

        # Consent UNKNOWN
        assert e_map["STU_08"].is_quarantined is False
        assert e_map["STU_08"].dispatch_eligible is False
        assert e_map["STU_08"].exclusion_reason == "CONSENT_UNKNOWN"

        # Consent REVOKED
        assert e_map["STU_09"].is_quarantined is False
        assert e_map["STU_09"].dispatch_eligible is False
        assert e_map["STU_09"].exclusion_reason == "CONSENT_REVOKED"

        # Guardian UNVERIFIED
        assert e_map["STU_10"].is_quarantined is False
        assert e_map["STU_10"].dispatch_eligible is False
        assert e_map["STU_10"].exclusion_reason == "GUARDIAN_UNVERIFIED"

    def test_deduplication_and_sorting_of_quarantine_flags(self) -> None:
        """Multiple quarantine flags on single record must be deduplicated and sorted."""
        # Row with invalid guardian phone AND same raw number (un-normalizable)
        row = StudentAdmissionRow(
            id="MULTI_FLAG",
            roll="99",
            child_display_name="Test",
            class_section="10-A",
            raw_guardian_phone="5511122201",  # Invalid
            raw_student_phone="invalid_phone",  # Invalid student phone
            verified_sibling=False,
        )
        evals = validate_admission_batch([row])
        flags = evals[0].quarantine_flags
        assert flags == sorted(set(flags))
        assert "INVALID_PHONE_NUMBER" in flags
        assert "INVALID_STUDENT_PHONE_NUMBER" in flags


# ==============================================================================
# 3. Deterministic OMR Evaluation on Golden 20-Student Dataset (D-01 to D-05)
# ==============================================================================


class TestDeterministicOMREvaluationGolden20:
    """Test full evaluation bundle for 20-student golden dataset against expected_reports.json."""

    @pytest.fixture(scope="class")
    def evaluation_bundle(
        self,
        golden_test_paper: dict,
        golden_admissions: dict,
        golden_submissions: dict,
    ) -> EvaluationBundle:
        return evaluate_batch(
            assessment=golden_test_paper,
            admissions=golden_admissions["students"],
            submissions=golden_submissions["submissions"],
            org_id="DEFAULT_INSTITUTION",
        )

    def test_batch_aggregate_metrics(
        self,
        evaluation_bundle: EvaluationBundle,
        golden_expected_reports: dict,
    ) -> None:
        bm = evaluation_bundle.batch_metrics
        exp_bm = golden_expected_reports["batch_metrics"]

        assert bm.enrolled_count == exp_bm["enrolled_count"] == 20
        assert bm.present_count == exp_bm["present_count"] == 16
        assert bm.absent_count == exp_bm["absent_count"] == 4
        assert bm.total_score_sum == exp_bm["total_score_sum"] == 1323
        assert bm.class_average == exp_bm["class_average"] == "82.7"
        assert bm.class_average_exact == exp_bm["class_average_exact"] == "82.6875"
        assert bm.class_average_fraction == exp_bm["class_average_fraction"] == "1323/16"
        assert bm.topper_net_marks == exp_bm["topper_net_marks"] == 278
        assert bm.ptm_eligible_count == exp_bm["ptm_eligible_count"] == 17
        assert bm.easy_question_ids == exp_bm["easy_question_ids"] == list(range(1, 21))

    def test_all_20_students_match_golden_literals(
        self,
        evaluation_bundle: EvaluationBundle,
        golden_expected_reports: dict,
    ) -> None:
        """Every student report matches literal expected scores, band, rank, and PTM status."""
        reports_map = {r.student_id: r for r in evaluation_bundle.student_reports}
        exp_reports_map = {r["student_id"]: r for r in golden_expected_reports["student_reports"]}

        assert len(reports_map) == 20

        for sid, exp in exp_reports_map.items():
            act = reports_map[sid]

            assert act.status.value == exp["status"], f"{sid} status mismatch"
            assert act.status_band == exp["status_band"], f"{sid} band mismatch"
            assert act.competition_rank == exp["competition_rank"], f"{sid} rank mismatch"
            assert act.requires_ptm_slip == exp["requires_ptm_slip"], f"{sid} PTM mismatch"

            if exp["status"] == "PRESENT":
                assert act.attempted == exp["attempted"]
                assert act.correct == exp["correct"]
                assert act.wrong == exp["wrong"]
                assert act.blank == exp["blank"]
                assert act.gross_marks == exp["gross_marks"]
                assert act.bleed_marks == exp["bleed_marks"]
                assert act.net_marks == exp["net_marks"]
                assert act.percentage == exp["percentage"]
                assert act.net_percentage == exp["net_percentage"]
                assert act.easy_missed_question_ids == exp["easy_missed_question_ids"]
                assert act.positive_marks_not_earned == exp["positive_marks_not_earned"]
                assert act.subject_diagnostics == exp["subject_diagnostics"]
            else:
                assert act.net_marks is None
                assert act.competition_rank is None
                assert act.percentage is None
                assert act.subject_diagnostics is None

    def test_stu_01_detailed_diagnostics(self, evaluation_bundle: EvaluationBundle) -> None:
        """STU_01: Gross 80, Bleed 25, Net 55 (18.3%), Rank 13, RED, missed Q11–20 (40 marks)."""
        r = next(s for s in evaluation_bundle.student_reports if s.student_id == "STU_01")
        assert r.attempted == 45
        assert r.correct == 20
        assert r.wrong == 25
        assert r.blank == 30
        assert r.gross_marks == 80
        assert r.bleed_marks == 25
        assert r.net_marks == 55
        assert r.percentage == "18.33"
        assert r.net_percentage == "18.3%"
        assert r.competition_rank == 13
        assert r.status_band == StatusBand.RED.value
        assert r.requires_ptm_slip is True
        assert r.easy_missed_question_ids == list(range(11, 21))
        assert r.positive_marks_not_earned == 40
        assert r.subject_diagnostics == {
            "PHYSICS": SubjectDiagnosticLabel.ACCURACY_BLEED.value,
            "CHEMISTRY": SubjectDiagnosticLabel.ACCURACY_BLEED.value,
            "MATHS": SubjectDiagnosticLabel.CONCEPTUAL_SPEED_GAP.value,
        }

    def test_stu_02_topper_diagnostics(self, evaluation_bundle: EvaluationBundle) -> None:
        """STU_02: 278 topper marks (92.7%), Rank 1, GREEN, no missed easy questions, all MASTERY_ZONE."""
        r = next(s for s in evaluation_bundle.student_reports if s.student_id == "STU_02")
        assert r.net_marks == 278
        assert r.competition_rank == 1
        assert r.status_band == StatusBand.GREEN.value
        assert r.requires_ptm_slip is False
        assert r.easy_missed_question_ids == []
        assert r.positive_marks_not_earned == 0
        assert r.subject_diagnostics == {
            "PHYSICS": SubjectDiagnosticLabel.MASTERY_ZONE.value,
            "CHEMISTRY": SubjectDiagnosticLabel.MASTERY_ZONE.value,
            "MATHS": SubjectDiagnosticLabel.MASTERY_ZONE.value,
        }

    def test_stu_03_and_stu_04_yellow_boundary_students(
        self,
        evaluation_bundle: EvaluationBundle,
    ) -> None:
        """STU_03 (30.0%) and STU_04 (60.0%) are strictly YELLOW per D-01 inclusive boundary."""
        r3 = next(s for s in evaluation_bundle.student_reports if s.student_id == "STU_03")
        assert r3.net_marks == 90
        assert r3.net_percentage == "30.0%"
        assert r3.competition_rank == 3
        assert r3.status_band == StatusBand.YELLOW.value
        assert r3.requires_ptm_slip is False

        r4 = next(s for s in evaluation_bundle.student_reports if s.student_id == "STU_04")
        assert r4.net_marks == 180
        assert r4.net_percentage == "60.0%"
        assert r4.competition_rank == 2
        assert r4.status_band == StatusBand.YELLOW.value
        assert r4.requires_ptm_slip is False

    def test_tied_students_stu_05_through_stu_13(self, evaluation_bundle: EvaluationBundle) -> None:
        """STU_05–13: 9 students tied at 80 marks -> shared competition rank 4."""
        tied = [s for s in evaluation_bundle.student_reports if s.student_id in [f"STU_{i:02d}" for i in range(5, 14)]]
        assert len(tied) == 9
        for s in tied:
            assert s.net_marks == 80
            assert s.competition_rank == 4
            assert s.status_band == StatusBand.RED.value
            assert s.requires_ptm_slip is True

    def test_no_attempts_stu_14_through_stu_16(self, evaluation_bundle: EvaluationBundle) -> None:
        """STU_14–16: 0 marks, rank 14, missed all 20 easy questions (80 marks not earned)."""
        zeros = [s for s in evaluation_bundle.student_reports if s.student_id in ["STU_14", "STU_15", "STU_16"]]
        assert len(zeros) == 3
        for s in zeros:
            assert s.attempted == 0
            assert s.net_marks == 0
            assert s.competition_rank == 14
            assert s.status_band == StatusBand.RED.value
            assert s.requires_ptm_slip is True
            assert s.easy_missed_question_ids == list(range(1, 21))
            assert s.positive_marks_not_earned == 80


# ==============================================================================
# 4. Arithmetic and Structural Invariants (D-05)
# ==============================================================================


class TestDiagnosticInvariants:
    """Verify arithmetic and structural reconciliation invariants (D-05)."""

    def test_reconciliation_invariants(
        self,
        golden_test_paper: dict,
        golden_admissions: dict,
        golden_submissions: dict,
    ) -> None:
        bundle = evaluate_batch(
            assessment=golden_test_paper,
            admissions=golden_admissions["students"],
            submissions=golden_submissions["submissions"],
        )

        for rep in bundle.student_reports:
            if rep.status == AttendanceStatus.PRESENT:
                # Invariant 1: attempted == correct + wrong
                assert rep.attempted == rep.correct + rep.wrong
                # Invariant 2: total_questions == attempted + blank
                assert rep.attempted + rep.blank == 75
                # Invariant 3: net == gross - bleed
                assert rep.net_marks == rep.gross_marks - rep.bleed_marks
                # Invariant 4: Subject breakdown reconciles to totals
                if rep.subject_breakdown:
                    sum_att = sum(b["attempted"] for b in rep.subject_breakdown.values())
                    sum_cor = sum(b["correct"] for b in rep.subject_breakdown.values())
                    sum_wro = sum(b["wrong"] for b in rep.subject_breakdown.values())
                    sum_bla = sum(b["blank"] for b in rep.subject_breakdown.values())
                    assert sum_att == rep.attempted
                    assert sum_cor == rep.correct
                    assert sum_wro == rep.wrong
                    assert sum_bla == rep.blank


# ==============================================================================
# 5. Boundary Classifiers and Edge Cases (ADR-0002, edge_cases.json)
# ==============================================================================


class TestBoundaryClassifiersAndEdgeCases:
    """Test exact threshold comparisons, ties, all-absent, and negative scores."""

    def test_status_band_boundary_percentages(self, edge_cases: dict) -> None:
        """Percentage boundary classifier: 29.99 (RED), 30.0 (YELLOW), 60.0 (YELLOW), 60.01 (GREEN)."""
        for case in edge_cases["percentage_boundaries"]:
            pct_val = Decimal(case["input_pct"])
            # Synthesize score = pct_val over max_marks 100
            band = classify_status_band(Fraction(pct_val), 100, is_present=True)
            assert band == case["expected_band"], f"Failed for input {case['input_pct']}"

    def test_exactly_075_item_accuracy(self) -> None:
        """12 out of 16 is exactly 0.75 -> easy question; 11 out of 16 is 0.6875 -> not easy."""
        # Test easy questions detection with exact 0.75 accuracy
        q1 = QuestionMeta(id=1, subject="General", correct_option="A", positive_marks=4, negative_marks=1)
        q2 = QuestionMeta(id=2, subject="General", correct_option="A", positive_marks=4, negative_marks=1)

        # 16 present students: 12 answer Q1 correctly (0.75), 11 answer Q2 correctly (0.6875)
        subs = []
        for i in range(16):
            resp = {}
            if i < 12:
                resp["1"] = "A"
            if i < 11:
                resp["2"] = "A"
            subs.append(StudentOMRSubmission(id=f"SUB_{i}", student_id=f"S_{i}", status=AttendanceStatus.PRESENT, responses=resp))

        easy_ids = find_easy_questions([q1, q2], subs)
        assert 1 in easy_ids
        assert 2 not in easy_ids

    def test_standard_competition_ranking_with_ties(self, edge_cases: dict) -> None:
        """Tie for first pair: scores [250, 250, 200] -> ranks [1, 1, 3] (1224 rank)."""
        scores = [250, 250, 200]
        ranks = compute_standard_competition_ranks(scores)
        assert ranks == [1, 1, 3]

    def test_all_wrong_student_negative_net_score(self, edge_cases: dict) -> None:
        """75 questions wrong -> gross 0, bleed 75, net -75 (-25.0%), RED, PTM slip required."""
        exp = edge_cases["all_wrong_student"]
        band = classify_status_band(exp["net_marks"], exp["max_marks"], is_present=True)
        assert band == StatusBand.RED.value
        pct_display = format_percentage_display(exp["net_marks"], exp["max_marks"])
        assert pct_display == exp["net_percentage"]
        requires_ptm = check_requires_ptm_slip(is_present=True, status_band=band, rank=1, present_count=1)
        assert requires_ptm is True

    def test_zero_present_cohort_handles_division_by_zero_safely(
        self,
        edge_cases: dict,
    ) -> None:
        """Batch with zero present students must not raise ZeroDivisionError."""
        q = QuestionMeta(id=1, subject="General", correct_option="A", positive_marks=4, negative_marks=1)
        paper = TestPaper(
            test_id="TEST_ZERO",
            name="Zero Present Test",
            subjects=["General"],
            max_marks_per_subject={"General": 100},
            total_max_marks=100,
            total_questions=1,
            questions=[q],
        )
        roster = [
            StudentAdmissionRow(id=f"STU_{i}", roll=f"{i:02d}", child_display_name=f"Stu {i}", class_section="10-A")
            for i in range(5)
        ]
        subs = [
            StudentOMRSubmission(id=f"SUB_{i}", student_id=f"STU_{i}", status=AttendanceStatus.ABSENT, responses={})
            for i in range(5)
        ]
        bundle = evaluate_omr_mcq_batch(paper, roster, subs)
        bm = bundle.batch_metrics

        assert bm.present_count == 0
        assert bm.enrolled_count == 5
        assert bm.absent_count == 5
        assert bm.class_average is None
        assert bm.class_average_exact is None
        assert bm.topper_net_marks is None
        assert bm.total_score_sum is None

    def test_solo_student_batch(self, edge_cases: dict) -> None:
        """One-student cohort: class average == topper == student net marks."""
        exp = edge_cases["one_student_batch"]
        questions = [
            QuestionMeta(id=i, subject="General", correct_option="A", positive_marks=4, negative_marks=1)
            for i in range(1, 76)
        ]
        paper = TestPaper(
            test_id="TEST_SOLO",
            name="Solo Test",
            subjects=["General"],
            max_marks_per_subject={"General": 300},
            total_max_marks=300,
            total_questions=75,
            questions=questions,
        )
        roster = [StudentAdmissionRow(id="EDGE_SOLO", roll="01", child_display_name="Solo", class_section="10-A")]
        # Net 200: 50 correct (200 gross, 0 wrong, 25 blank)
        resp = {str(i): "A" for i in range(1, 51)}
        subs = [StudentOMRSubmission(id="SUB_SOLO", student_id="EDGE_SOLO", status=AttendanceStatus.PRESENT, responses=resp)]

        bundle = evaluate_omr_mcq_batch(paper, roster, subs)
        bm = bundle.batch_metrics
        assert bm.present_count == 1
        assert bm.class_average == exp["class_average"]
        assert bm.topper_net_marks == exp["topper_net_marks"]

    def test_rounding_tie_batch_round_half_up(self, edge_cases: dict) -> None:
        """Scores [12, 12, 12, 13] -> sum 49, avg 12.25 -> ROUND_HALF_UP formats to 12.3."""
        exp = edge_cases["rounding_tie_batch"]
        scores = exp["scores"]
        total_sum = sum(scores)
        disp = format_decimal_1dp(total_sum, len(scores))
        assert disp == exp["class_average_display"] == "12.3"


# ==============================================================================
# 6. Marks Entry Totals Evaluation (ADR-0016, expected_marks_reports.json)
# ==============================================================================


class TestMarksEntryTotalsEvaluation:
    """Test manual marks entry totals evaluation on 6-student fixture."""

    @pytest.fixture(scope="class")
    def marks_bundle(self, golden_marks_entry: dict) -> EvaluationBundle:
        return evaluate_batch(assessment=golden_marks_entry)

    def test_marks_entry_batch_metrics(
        self,
        marks_bundle: EvaluationBundle,
        golden_expected_marks_reports: dict,
    ) -> None:
        bm = marks_bundle.batch_metrics
        exp_bm = golden_expected_marks_reports["batch_metrics"]

        assert bm.enrolled_count == exp_bm["enrolled_count"] == 6
        assert bm.present_count == exp_bm["present_count"] == 5
        assert bm.absent_count == exp_bm["absent_count"] == 1
        assert bm.total_score_sum == exp_bm["total_score_sum"] == "109.5"
        assert bm.class_average == exp_bm["class_average"] == "21.9"
        assert bm.topper_marks == exp_bm["topper_marks"] == "47.0"
        assert bm.ptm_eligible_count == exp_bm["ptm_eligible_count"] == 3

    def test_all_6_students_match_golden_marks_reports(
        self,
        marks_bundle: EvaluationBundle,
        golden_expected_marks_reports: dict,
    ) -> None:
        reports_map = {r.student_id: r for r in marks_bundle.student_reports}
        exp_reports_map = {r["student_id"]: r for r in golden_expected_marks_reports["student_reports"]}

        assert len(reports_map) == 6

        for sid, exp in exp_reports_map.items():
            act = reports_map[sid]

            assert act.status.value == exp["status"]
            assert act.status_band == exp["status_band"]
            assert act.competition_rank == exp["competition_rank"]
            assert act.requires_ptm_slip == exp["requires_ptm_slip"]
            assert act.percentage == exp["percentage"]
            assert act.net_percentage == exp["net_percentage"]

    def test_not_available_sentinels_handling(self, marks_bundle: EvaluationBundle) -> None:
        """In MARKS_ENTRY_TOTALS, unavailable metrics are strictly literal NOT_AVAILABLE, never 0 or []."""
        for r in marks_bundle.student_reports:
            if r.status == AttendanceStatus.PRESENT:
                assert r.attempted == NOT_AVAILABLE
                assert r.correct == NOT_AVAILABLE
                assert r.wrong == NOT_AVAILABLE
                assert r.blank == NOT_AVAILABLE
                assert r.gross_marks == NOT_AVAILABLE
                assert r.bleed_marks == NOT_AVAILABLE
                assert r.easy_missed_question_ids == NOT_AVAILABLE
                assert r.positive_marks_not_earned == NOT_AVAILABLE
                assert r.subject_diagnostics == NOT_AVAILABLE

        assert marks_bundle.batch_metrics.easy_question_ids == NOT_AVAILABLE

    def test_half_marks_exact_evaluation(self, marks_bundle: EvaluationBundle) -> None:
        """ME_04 has half mark 2.5 (5.0%) -> rank 4, band RED, exact Fraction(5, 2)."""
        me_04 = next(s for s in marks_bundle.student_reports if s.student_id == "ME_04")
        assert me_04.net_marks == Fraction(5, 2)
        assert me_04.percentage == "5.00"
        assert me_04.net_percentage == "5.0%"
        assert me_04.competition_rank == 4
        assert me_04.status_band == StatusBand.RED.value
        assert me_04.requires_ptm_slip is True

    def test_marks_entry_partial_subject_attendance_no_overall_rank(self) -> None:
        """
        Verify multi-subject attendance per S3 Task 3 and ADR-0016:
        - Student 1 (S1): PRESENT in English (40/50), PRESENT in Mathematics (45/50) -> overall 85/100, rank 1
        - Student 2 (S2): PRESENT in English (35/50), ABSENT in Mathematics -> overall rank is None
          (attended subject gets rank, absent subject is None, NOT treated as 0)
        - Student 3 (S3): PRESENT in English (30/50), PRESENT in Mathematics (40/50) -> overall 70/100, rank 2
        """
        english_sheet = MarksEntrySheet(
            org_id="DEFAULT_INSTITUTION",
            schema_version=1,
            assessment_name="Midterm 2026",
            subject="English",
            cohort_label="Grade-10-A",
            max_marks=50,
            rows=[
                MarksEntryRow(roll_no="101", student_id="STU_101", child_display_name="Student One", status=AttendanceStatus.PRESENT, marks=Fraction(40, 1)),
                MarksEntryRow(roll_no="102", student_id="STU_102", child_display_name="Student Two", status=AttendanceStatus.PRESENT, marks=Fraction(35, 1)),
                MarksEntryRow(roll_no="103", student_id="STU_103", child_display_name="Student Three", status=AttendanceStatus.PRESENT, marks=Fraction(30, 1)),
            ],
        )
        maths_sheet = MarksEntrySheet(
            org_id="DEFAULT_INSTITUTION",
            schema_version=1,
            assessment_name="Midterm 2026",
            subject="Mathematics",
            cohort_label="Grade-10-A",
            max_marks=50,
            rows=[
                MarksEntryRow(roll_no="101", student_id="STU_101", child_display_name="Student One", status=AttendanceStatus.PRESENT, marks=Fraction(45, 1)),
                MarksEntryRow(roll_no="102", student_id="STU_102", child_display_name="Student Two", status=AttendanceStatus.ABSENT, marks=None),
                MarksEntryRow(roll_no="103", student_id="STU_103", child_display_name="Student Three", status=AttendanceStatus.PRESENT, marks=Fraction(40, 1)),
            ],
        )

        bundle = evaluate_batch(assessment=[english_sheet, maths_sheet])
        reports = {r.student_id: r for r in bundle.student_reports}

        # Student 1: Present in both subjects
        s1 = reports["STU_101"]
        assert s1.subject_ranks == {"English": 1, "Mathematics": 1}
        assert s1.overall_rank == 1
        assert s1.competition_rank == 1
        assert s1.marks == "85.0"
        assert s1.status == AttendanceStatus.PRESENT

        # Student 2: Present in English, ABSENT in Mathematics
        s2 = reports["STU_102"]
        assert s2.subject_ranks is not None
        assert s2.subject_ranks["English"] == 2
        assert s2.subject_ranks["Mathematics"] is None
        # Overall rank must be None because student missed a subject (not treated as zero)
        assert s2.overall_rank is None
        assert s2.competition_rank is None
        # Marks and percentages are not aggregated into a fake complete total
        assert s2.marks is None
        assert s2.percentage is None
        assert s2.net_percentage is None
        # Absence in any subject triggers PTM slip requirement (ADR-0016)
        assert s2.requires_ptm_slip is True

        # Student 3: Present in both subjects
        s3 = reports["STU_103"]
        assert s3.subject_ranks == {"English": 3, "Mathematics": 2}
        assert s3.overall_rank == 2
        assert s3.competition_rank == 2
        assert s3.marks == "70.0"
        assert s3.status == AttendanceStatus.PRESENT

    def test_student_diagnostic_report_rejects_arbitrary_sentinel_strings(self) -> None:
        """
        Verify strict typing of NOT_AVAILABLE sentinel:
        Arbitrary string sentinels like 'N/A' or 'ZERO' must raise ValidationError,
        while literal NOT_AVAILABLE succeeds.
        """
        from pydantic import ValidationError

        base_kwargs = {
            "student_id": "STU_TEST",
            "roll_number": "101",
            "child_display_name": "Test Child",
            "class_section": "10-A",
            "status": AttendanceStatus.PRESENT,
            "status_band": StatusBand.GREEN.value,
            "requires_ptm_slip": False,
        }

        # 1. Invalid sentinel string for easy_missed_question_ids raises ValidationError
        with pytest.raises(ValidationError):
            StudentDiagnosticReport(
                **base_kwargs,
                easy_missed_question_ids="N/A",  # type: ignore[arg-type]
            )

        # 2. Invalid sentinel string for gross_marks raises ValidationError
        with pytest.raises(ValidationError):
            StudentDiagnosticReport(
                **base_kwargs,
                gross_marks="ZERO",  # type: ignore[arg-type]
            )

        # 3. Invalid sentinel string for positive_marks_not_earned raises ValidationError
        with pytest.raises(ValidationError):
            StudentDiagnosticReport(
                **base_kwargs,
                positive_marks_not_earned="NOT_APPLICABLE",  # type: ignore[arg-type]
            )

        # 4. Literal NOT_AVAILABLE succeeds cleanly
        valid_report = StudentDiagnosticReport(
            **base_kwargs,
            gross_marks=NOT_AVAILABLE,
            bleed_marks=NOT_AVAILABLE,
            easy_missed_question_ids=NOT_AVAILABLE,
            positive_marks_not_earned=NOT_AVAILABLE,
            subject_diagnostics=NOT_AVAILABLE,
        )
        assert valid_report.gross_marks == "NOT_AVAILABLE"
        assert valid_report.easy_missed_question_ids == "NOT_AVAILABLE"


# ==============================================================================
# 7. Validation and Rejection Tests (ADR-0008, Invariant 13)
# ==============================================================================


class TestValidationAndRejection:
    """Test fail-closed error handling on malformed or contradictory inputs."""

    def test_student_in_submissions_missing_from_admissions(
        self,
        golden_test_paper: dict,
        golden_admissions: dict,
    ) -> None:
        """A submission for an unregistered student ID must raise SchemaValidationError."""
        bad_subs = [
            StudentOMRSubmission(
                id="SUB_UNKNOWN",
                student_id="STU_GHOST",
                status=AttendanceStatus.PRESENT,
                responses={},
            )
        ]
        with pytest.raises(SchemaValidationError, match="not enrolled"):
            evaluate_omr_mcq_batch(golden_test_paper, golden_admissions["students"], bad_subs)

    def test_duplicate_submission_raises_error(
        self,
        golden_test_paper: dict,
        golden_admissions: dict,
    ) -> None:
        """Duplicate submission for the same student ID raises DuplicateRecordError."""
        sub1 = StudentOMRSubmission(id="SUB_1", student_id="STU_01", status=AttendanceStatus.PRESENT, responses={})
        sub2 = StudentOMRSubmission(id="SUB_2", student_id="STU_01", status=AttendanceStatus.PRESENT, responses={})
        with pytest.raises(DuplicateRecordError, match="Duplicate submission"):
            evaluate_omr_mcq_batch(golden_test_paper, golden_admissions["students"], [sub1, sub2])

    def test_org_id_mismatch_fails_closed(
        self,
        golden_test_paper: dict,
        golden_admissions: dict,
        golden_submissions: dict,
    ) -> None:
        """Mismatched tenant org_id across components raises OrgIdMismatchError."""
        paper = dict(golden_test_paper)
        paper["org_id"] = "WRONG_INSTITUTION"
        with pytest.raises(OrgIdMismatchError):
            evaluate_omr_mcq_batch(
                paper=paper,
                roster=golden_admissions["students"],
                submissions=golden_submissions["submissions"],
                org_id="DEFAULT_INSTITUTION",
            )

    def test_invalid_option_response_raises_error(
        self,
        golden_test_paper: dict,
        golden_admissions: dict,
    ) -> None:
        """An invalid option token (e.g. 'Z') raises SchemaValidationError."""
        sub = StudentOMRSubmission(
            id="SUB_01",
            student_id="STU_01",
            status=AttendanceStatus.PRESENT,
            responses={"1": "Z"},  # Invalid
        )
        with pytest.raises(SchemaValidationError, match="Invalid response option"):
            evaluate_omr_mcq_batch(golden_test_paper, golden_admissions["students"][:1], [sub])


# ==============================================================================
# 8. Walking Skeleton Acceptance Tests (ADR-0013)
# ==============================================================================


class TestWalkingSkeletonCLI:
    """Acceptance criterion for Stage S3 per ADR-0013: thin dry run CLI."""

    def test_cli_omr_mcq_pipeline(self, tmp_path: Path) -> None:
        """CLI runs golden OMR fixture ingestion -> evaluation -> summary text -> run_manifest.json."""
        out_dir = tmp_path / "omr_run"
        bundle = run_batch_pipeline(
            input_path=FIXTURES_DIR,
            output_path=out_dir,
            kind=AssessmentKind.OMR_MCQ,
            org_id="DEFAULT_INSTITUTION",
        )

        assert bundle.kind == AssessmentKind.OMR_MCQ
        assert bundle.batch_metrics.enrolled_count == 20
        assert bundle.batch_metrics.present_count == 16
        assert bundle.batch_metrics.topper_net_marks == 278

        manifest_file = out_dir / "run_manifest.json"
        assert manifest_file.exists()
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))

        assert manifest_data["schema_version"] == 1
        assert manifest_data["kind"] == "OMR_MCQ"
        assert manifest_data["batch_metrics"]["class_average"] == "82.7"
        assert len(manifest_data["student_reports"]) == 20
        assert len(manifest_data["contacts"]) == 20

    def test_cli_marks_entry_pipeline(self, tmp_path: Path) -> None:
        """CLI runs golden marks entry fixture ingestion -> evaluation -> summary text -> run_manifest.json."""
        out_dir = tmp_path / "marks_run"
        sheet_file = FIXTURES_DIR / "marks_entry_50.json"
        bundle = run_batch_pipeline(
            input_path=sheet_file,
            output_path=out_dir,
            kind=AssessmentKind.MARKS_ENTRY_TOTALS,
            org_id="DEFAULT_INSTITUTION",
        )

        assert bundle.kind == AssessmentKind.MARKS_ENTRY_TOTALS
        assert bundle.batch_metrics.enrolled_count == 6
        assert bundle.batch_metrics.present_count == 5
        assert bundle.batch_metrics.topper_marks == "47.0"

        manifest_file = out_dir / "run_manifest.json"
        assert manifest_file.exists()
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))

        assert manifest_data["kind"] == "MARKS_ENTRY_TOTALS"
        assert manifest_data["batch_metrics"]["class_average"] == "21.9"
        assert len(manifest_data["student_reports"]) == 6

    def test_cli_main_entrypoint_execution(self, tmp_path: Path) -> None:
        """Invoking cli_main with argv produces exit code 0 and valid manifest."""
        out_dir = tmp_path / "cli_main_test"
        exit_code = cli_main([
            "run-batch",
            "--input",
            str(FIXTURES_DIR),
            "--output",
            str(out_dir),
            "--kind",
            "OMR_MCQ",
        ])
        assert exit_code == 0
        assert (out_dir / "run_manifest.json").exists()
