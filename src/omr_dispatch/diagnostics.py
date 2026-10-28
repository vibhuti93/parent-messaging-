"""
Deterministic Evaluation Engine and Diagnostic Scoring (`src/omr_dispatch/diagnostics.py`).

Compliant with:
- ADR-0002: Zero-float rule. Exact Fraction, integer cross-multiplication, Decimal ROUND_HALF_UP.
- ADR-0003: Deterministic surrogate IDs and keys.
- ADR-0004: SINGLE_CORRECT supported in v1; marking scheme as data.
- ADR-0008: Typed exception hierarchy, fail-closed handling.
- ADR-0010: Unicode NFC normalization for all student/class text.
- ADR-0016: Unified Assessment entity, capability flags, and NOT_AVAILABLE sentinels.
- ADR-0017: Multi-tenant institutional isolation (mandatory org_id).
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any

from omr_dispatch.contacts import validate_admission_batch
from omr_dispatch.models import (
    NOT_AVAILABLE,
    Assessment,
    AssessmentKind,
    AttendanceStatus,
    BatchMetrics,
    ContactEvaluation,
    DuplicateRecordError,
    EvaluationBundle,
    IngestionError,
    MarksEntryRow,
    MarksEntrySheet,
    NotSupportedError,
    OrgIdMismatchError,
    QuestionMeta,
    SchemaValidationError,
    StatusBand,
    StudentAdmissionRow,
    StudentDiagnosticReport,
    StudentOMRSubmission,
    StudentRoster,
    SubjectDiagnosticLabel,
    TestPaper,
)

# Valid multiple-choice response options for v1
VALID_OPTION_VALUES = frozenset({"A", "B", "C", "D", "BLANK", ""})


# ------------------------------------------------------------------------------
# Numeric Semantics & Formatting Helpers (ADR-0002)
# ------------------------------------------------------------------------------


def format_percentage_display(net: int | Fraction, max_marks: int) -> str:
    """Format net / max_marks as a percentage string with 1 decimal place using ROUND_HALF_UP."""
    if isinstance(net, Fraction):
        pct = (Decimal(net.numerator) * Decimal(100)) / (
            Decimal(net.denominator) * Decimal(max_marks)
        )
    else:
        pct = (Decimal(net) * Decimal(100)) / Decimal(max_marks)
    rounded = pct.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded}%"


def format_percentage_raw(net: int | Fraction, max_marks: int) -> str:
    """Format net / max_marks as a raw percentage string with 2 decimal places using ROUND_HALF_UP."""
    if isinstance(net, Fraction):
        pct = (Decimal(net.numerator) * Decimal(100)) / (
            Decimal(net.denominator) * Decimal(max_marks)
        )
    else:
        pct = (Decimal(net) * Decimal(100)) / Decimal(max_marks)
    rounded = pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{rounded}"


def format_decimal_1dp(value: int | Fraction, divisor: int = 1) -> str:
    """Format value / divisor as a decimal string with 1 decimal place using ROUND_HALF_UP."""
    if isinstance(value, Fraction):
        num = Decimal(value.numerator)
        den = Decimal(value.denominator) * Decimal(divisor)
        val = num / den
    else:
        val = Decimal(value) / Decimal(divisor)
    rounded = val.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded}"


def classify_status_band(
    net: int | Fraction | None,
    max_marks: int,
    is_present: bool = True,
) -> str:
    """
    D-01 Status Band Classification.
    PRESENT:
      - < 30.0%: RED
      - 30.0% to 60.0% inclusive: YELLOW
      - > 60.0%: GREEN
    ABSENT: band ABSENT.
    Evaluated using exact integer cross-multiplication (zero float per ADR-0002).
    """
    if not is_present or net is None:
        return StatusBand.ABSENT.value

    if isinstance(net, Fraction):
        # net.num / (net.den * max_marks) < 30 / 100
        # net.num * 100 < net.den * max_marks * 30
        lhs = net.numerator * 100
        rhs_red = net.denominator * max_marks * 30
        rhs_yellow = net.denominator * max_marks * 60
    else:
        lhs = net * 100
        rhs_red = max_marks * 30
        rhs_yellow = max_marks * 60

    if lhs < rhs_red:
        return StatusBand.RED.value
    if lhs <= rhs_yellow:
        return StatusBand.YELLOW.value
    return StatusBand.GREEN.value


def classify_subject_label(
    attempted: int,
    correct: int,
    total_subject_questions: int,
) -> str:
    """
    D-03 Subject Diagnostic Labels evaluated in priority order via exact cross-multiplication:
      1. attempted == 0 -> NO_ATTEMPT
      2. attempt_ratio >= 0.60 and accuracy_ratio < 0.65 -> ACCURACY_BLEED
      3. attempt_ratio < 0.50 and accuracy_ratio >= 0.75 -> CONCEPTUAL_SPEED_GAP
      4. attempt_ratio < 0.50 and accuracy_ratio < 0.65 -> FOUNDATIONAL_CRISIS
      5. attempt_ratio >= 0.60 and accuracy_ratio >= 0.75 -> MASTERY_ZONE
      6. otherwise -> MODERATE_ZONE
    """
    if attempted == 0:
        return SubjectDiagnosticLabel.NO_ATTEMPT.value

    # Cross-multiplication equivalents:
    # attempt_ratio >= 0.60 <=> attempted * 10 >= total_subject_questions * 6
    # attempt_ratio < 0.50  <=> attempted * 2 < total_subject_questions
    # accuracy_ratio >= 0.75 <=> correct * 4 >= attempted * 3
    # accuracy_ratio < 0.65  <=> correct * 100 < attempted * 65

    attempt_ge_60 = attempted * 10 >= total_subject_questions * 6
    attempt_lt_50 = attempted * 2 < total_subject_questions
    accuracy_ge_75 = correct * 4 >= attempted * 3
    accuracy_lt_65 = correct * 100 < attempted * 65

    if attempt_ge_60 and accuracy_lt_65:
        return SubjectDiagnosticLabel.ACCURACY_BLEED.value
    if attempt_lt_50 and accuracy_ge_75:
        return SubjectDiagnosticLabel.CONCEPTUAL_SPEED_GAP.value
    if attempt_lt_50 and accuracy_lt_65:
        return SubjectDiagnosticLabel.FOUNDATIONAL_CRISIS.value
    if attempt_ge_60 and accuracy_ge_75:
        return SubjectDiagnosticLabel.MASTERY_ZONE.value
    return SubjectDiagnosticLabel.MODERATE_ZONE.value


def compute_standard_competition_ranks(
    scores: Sequence[int | Fraction | None],
) -> list[int | None]:
    """
    D-04 Standard competition rank (1224 ranking):
    rank = 1 + count(present students with strictly higher score).
    Returns None for absent students.
    """
    ranks: list[int | None] = []
    present_scores = [s for s in scores if s is not None]

    for s in scores:
        if s is None:
            ranks.append(None)
        else:
            rank = 1 + sum(1 for other in present_scores if other > s)
            ranks.append(rank)

    return ranks


def check_requires_ptm_slip(
    is_present: bool,
    status_band: str,
    rank: int | None,
    present_count: int,
) -> bool:
    """
    D-04 Rank and PTM eligibility:
    A student requires a PTM consultation slip iff:
      - Attendance is ABSENT, OR
      - Status band is RED, OR
      - Competition rank > floor(0.75 * present_count).
    In integer arithmetic: floor(0.75 * present_count) == (present_count * 3) // 4.
    """
    if not is_present:
        return True
    if status_band == StatusBand.RED.value:
        return True
    if rank is not None:
        threshold = (present_count * 3) // 4
        if rank > threshold:
            return True
    return False


def find_easy_questions(
    questions: list[QuestionMeta],
    submissions: list[StudentOMRSubmission],
) -> list[int]:
    """
    D-02 Easy questions detection:
    Item accuracy = correct answers among PRESENT students / present_count.
    Question is easy iff accuracy >= 0.75 (exact: correct * 4 >= present_count * 3).
    Returns deterministically sorted list of question IDs.
    """
    present_subs = [s for s in submissions if s.status == AttendanceStatus.PRESENT]
    present_count = len(present_subs)
    if present_count == 0:
        return []

    easy_ids: list[int] = []
    for q in questions:
        qid_str = str(q.id)
        key = q.correct_option
        correct_count = 0
        for sub in present_subs:
            resp = sub.responses.get(qid_str)
            if resp == key:
                correct_count += 1

        # accuracy >= 0.75 <=> correct_count * 4 >= present_count * 3
        if correct_count * 4 >= present_count * 3:
            easy_ids.append(q.id)

    return sorted(easy_ids)


# ------------------------------------------------------------------------------
# OMR MCQ Batch Evaluation (S3 Task 3)
# ------------------------------------------------------------------------------


def evaluate_omr_mcq_batch(
    paper: TestPaper | dict[str, Any],
    roster: StudentRoster | list[StudentAdmissionRow] | list[dict[str, Any]],
    submissions: list[StudentOMRSubmission] | dict[str, Any] | list[dict[str, Any]],
    org_id: str | None = None,
) -> EvaluationBundle:
    """
    Evaluate a batch of OMR multiple-choice submissions (D-01 to D-05).
    """
    # 1. Normalize models
    test_paper = (
        paper if isinstance(paper, TestPaper) else TestPaper.model_validate(paper)
    )

    admissions_list: list[StudentAdmissionRow]
    if isinstance(roster, StudentRoster):
        admissions_list = roster.students
    elif isinstance(roster, list):
        admissions_list = [
            item if isinstance(item, StudentAdmissionRow) else StudentAdmissionRow.model_validate(item)
            for item in roster
        ]
    else:
        raise TypeError(f"Unsupported roster type: {type(roster).__name__}")

    sub_list: list[StudentOMRSubmission]
    if isinstance(submissions, list):
        sub_list = [
            item if isinstance(item, StudentOMRSubmission) else StudentOMRSubmission.model_validate(item)
            for item in submissions
        ]
    elif isinstance(submissions, dict) and "submissions" in submissions:
        sub_list = [StudentOMRSubmission.model_validate(s) for s in submissions["submissions"]]
    else:
        raise TypeError(f"Unsupported submissions type: {type(submissions).__name__}")

    active_org_id = org_id or test_paper.org_id

    # 2. Strict validation: Tenant context isolation (Invariant 15)
    if test_paper.org_id != active_org_id:
        raise OrgIdMismatchError(
            f"Test paper org_id '{test_paper.org_id}' does not match active org_id '{active_org_id}'"
        )
    for adm in admissions_list:
        if adm.org_id and adm.org_id != active_org_id:
            raise OrgIdMismatchError(
                f"Admission row org_id '{adm.org_id}' does not match active org_id '{active_org_id}'"
            )
    for sub in sub_list:
        if sub.org_id and sub.org_id != active_org_id:
            raise OrgIdMismatchError(
                f"Submission org_id '{sub.org_id}' does not match active org_id '{active_org_id}'"
            )

    # 3. ID and Roster Reconciliation
    admission_map: dict[str, StudentAdmissionRow] = {}
    for adm in admissions_list:
        if adm.student_id in admission_map:
            raise DuplicateRecordError(f"Duplicate student ID '{adm.student_id}' in admission roster")
        admission_map[adm.student_id] = adm

    submission_map: dict[str, StudentOMRSubmission] = {}
    for sub in sub_list:
        if sub.student_id in submission_map:
            raise DuplicateRecordError(f"Duplicate submission for student ID '{sub.student_id}'")
        if sub.student_id not in admission_map:
            raise SchemaValidationError(
                f"Submission student ID '{sub.student_id}' is not enrolled in admission roster"
            )
        submission_map[sub.student_id] = sub

    # Check for admissions missing from submissions
    for sid in admission_map:
        if sid not in submission_map:
            raise SchemaValidationError(
                f"Enrolled student ID '{sid}' has no corresponding submission record"
            )

    # Validate response options against valid option tokens
    for sub in sub_list:
        for qid_str, opt in sub.responses.items():
            if opt not in VALID_OPTION_VALUES:
                raise SchemaValidationError(
                    f"Invalid response option '{opt}' for question {qid_str} in student '{sub.student_id}'"
                )

    # 4. Cohort metrics setup
    enrolled_count = len(admission_map)
    present_subs = [s for s in sub_list if s.status == AttendanceStatus.PRESENT]
    present_count = len(present_subs)
    absent_count = enrolled_count - present_count

    # 5. D-02: Easy questions detection (accuracy >= 0.75 among present students)
    easy_question_ids = find_easy_questions(test_paper.questions, sub_list)
    q_meta_map = {q.id: q for q in test_paper.questions}

    # 6. Contact Hygiene evaluation (S3 Task 2)
    contact_evaluations = validate_admission_batch(admissions_list, org_id=active_org_id)
    contact_eval_map = {c.student_id: c for c in contact_evaluations}

    # 7. Student-level question scoring
    student_scores: list[int | None] = []
    student_raw_reports: list[dict[str, Any]] = []

    for adm in admissions_list:
        sid = adm.student_id
        sub = submission_map[sid]
        contact_eval = contact_eval_map.get(sid)

        if sub.status == AttendanceStatus.ABSENT:
            student_scores.append(None)
            student_raw_reports.append({
                "student_id": sid,
                "roll_number": adm.roll_number,
                "child_display_name": unicodedata.normalize("NFC", adm.child_display_name),
                "class_section": unicodedata.normalize("NFC", adm.class_section),
                "status": AttendanceStatus.ABSENT,
                "attempted": None,
                "correct": None,
                "wrong": None,
                "blank": None,
                "gross_marks": None,
                "bleed_marks": None,
                "net_marks": None,
                "marks": None,
                "max_marks": test_paper.total_max_marks,
                "percentage": None,
                "net_percentage": None,
                "status_band": StatusBand.ABSENT.value,
                "easy_missed_question_ids": [],
                "positive_marks_not_earned": None,
                "subject_diagnostics": None,
                "subject_breakdown": None,
                "contact_eligibility": contact_eval,
                "dispatch_eligible": contact_eval.dispatch_eligible if contact_eval else False,
                "exclusion_reason": contact_eval.exclusion_reason if contact_eval else None,
                "org_id": active_org_id,
                "schema_version": adm.schema_version,
            })
            continue

        # Score PRESENT student responses
        correct_count = 0
        wrong_count = 0
        blank_count = 0
        gross = 0
        bleed = 0

        # Subject breakdown counts
        subj_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "attempted": 0, "correct": 0, "wrong": 0, "blank": 0, "net": 0}
        )

        for q in test_paper.questions:
            subj = q.subject
            subj_counts[subj]["total"] += 1

            qid_str = str(q.id)
            resp = sub.responses.get(qid_str)

            if resp is None or resp == "BLANK" or resp == "":
                blank_count += 1
                subj_counts[subj]["blank"] += 1
            elif resp == q.correct_option:
                correct_count += 1
                gross += q.positive_marks
                subj_counts[subj]["attempted"] += 1
                subj_counts[subj]["correct"] += 1
                subj_counts[subj]["net"] += q.positive_marks
            else:
                wrong_count += 1
                bleed += q.negative_marks
                subj_counts[subj]["attempted"] += 1
                subj_counts[subj]["wrong"] += 1
                subj_counts[subj]["net"] -= q.negative_marks

        attempted_count = correct_count + wrong_count
        net = gross - bleed

        # Verify scoring invariants:
        # attempted == correct + wrong
        assert attempted_count == correct_count + wrong_count
        # total_questions == attempted + blank
        assert len(test_paper.questions) == attempted_count + blank_count
        # net == gross - bleed
        assert net == gross - bleed

        # Subject totals reconciliation invariant (D-05)
        sum_subj_att = sum(c["attempted"] for c in subj_counts.values())
        sum_subj_cor = sum(c["correct"] for c in subj_counts.values())
        sum_subj_wro = sum(c["wrong"] for c in subj_counts.values())
        sum_subj_bla = sum(c["blank"] for c in subj_counts.values())
        sum_subj_net = sum(c["net"] for c in subj_counts.values())
        assert sum_subj_att == attempted_count
        assert sum_subj_cor == correct_count
        assert sum_subj_wro == wrong_count
        assert sum_subj_bla == blank_count
        assert sum_subj_net == net

        # D-02: Easy questions missed
        missed_easy_ids = [
            qid
            for qid in easy_question_ids
            if sub.responses.get(str(qid)) != q_meta_map[qid].correct_option
        ]
        positive_marks_not_earned = sum(q_meta_map[qid].positive_marks for qid in missed_easy_ids)

        # D-03: Subject diagnostic labels
        subj_diagnostics: dict[str, str] = {}
        subj_breakdown_out: dict[str, dict[str, int]] = {}
        for subj in sorted(subj_counts.keys()):
            cnts = subj_counts[subj]
            subj_diagnostics[subj] = classify_subject_label(
                cnts["attempted"], cnts["correct"], cnts["total"]
            )
            subj_breakdown_out[subj] = {
                "total": cnts["total"],
                "attempted": cnts["attempted"],
                "correct": cnts["correct"],
                "wrong": cnts["wrong"],
                "blank": cnts["blank"],
            }

        status_band = classify_status_band(net, test_paper.total_max_marks, is_present=True)
        pct_display = format_percentage_display(net, test_paper.total_max_marks)
        pct_raw = format_percentage_raw(net, test_paper.total_max_marks)

        student_scores.append(net)
        student_raw_reports.append({
            "student_id": sid,
            "roll_number": adm.roll_number,
            "child_display_name": unicodedata.normalize("NFC", adm.child_display_name),
            "class_section": unicodedata.normalize("NFC", adm.class_section),
            "status": AttendanceStatus.PRESENT,
            "attempted": attempted_count,
            "correct": correct_count,
            "wrong": wrong_count,
            "blank": blank_count,
            "gross_marks": gross,
            "bleed_marks": bleed,
            "net_marks": net,
            "marks": net,
            "max_marks": test_paper.total_max_marks,
            "percentage": pct_raw,
            "net_percentage": pct_display,
            "status_band": status_band,
            "easy_missed_question_ids": missed_easy_ids,
            "positive_marks_not_earned": positive_marks_not_earned,
            "subject_diagnostics": subj_diagnostics,
            "subject_breakdown": subj_breakdown_out,
            "contact_eligibility": contact_eval,
            "dispatch_eligible": contact_eval.dispatch_eligible if contact_eval else False,
            "exclusion_reason": contact_eval.exclusion_reason if contact_eval else None,
            "org_id": active_org_id,
            "schema_version": adm.schema_version,
        })

    # 8. Standard competition ranking across present students
    ranks = compute_standard_competition_ranks(student_scores)

    # 9. Class average and topper computation (safe against zero-present division by zero)
    present_scores = [s for s in student_scores if s is not None]
    if present_count > 0:
        total_score_sum = sum(present_scores)
        topper_score = max(present_scores)
        class_avg_exact = str(Decimal(total_score_sum) / Decimal(present_count))
        class_avg_frac = f"{total_score_sum}/{present_count}"
        class_avg_display = format_decimal_1dp(total_score_sum, present_count)
    else:
        total_score_sum = None
        topper_score = None
        class_avg_exact = None
        class_avg_frac = None
        class_avg_display = None

    # 10. Assemble final StudentDiagnosticReports with PTM check and cohort metrics
    reports: list[StudentDiagnosticReport] = []
    ptm_eligible_count = 0

    for idx, raw_rep in enumerate(student_raw_reports):
        rank = ranks[idx]
        is_pres = raw_rep["status"] == AttendanceStatus.PRESENT
        requires_ptm = check_requires_ptm_slip(
            is_present=is_pres,
            status_band=raw_rep["status_band"],
            rank=rank,
            present_count=present_count,
        )
        if requires_ptm:
            ptm_eligible_count += 1

        raw_rep["competition_rank"] = rank
        raw_rep["requires_ptm_slip"] = requires_ptm
        raw_rep["enrolled_count"] = enrolled_count
        raw_rep["present_count"] = present_count
        raw_rep["class_average"] = class_avg_display
        raw_rep["topper_score"] = topper_score

        reports.append(StudentDiagnosticReport(**raw_rep))

    batch_metrics = BatchMetrics(
        enrolled_count=enrolled_count,
        present_count=present_count,
        absent_count=absent_count,
        total_score_sum=total_score_sum,
        class_average=class_avg_display,
        class_average_exact=class_avg_exact,
        class_average_fraction=class_avg_frac,
        topper_net_marks=topper_score,
        ptm_eligible_count=ptm_eligible_count,
        easy_question_ids=easy_question_ids,
    )

    return EvaluationBundle(
        org_id=active_org_id,
        schema_version=test_paper.schema_version,
        test_id=test_paper.test_id,
        assessment_name=test_paper.name,
        kind=AssessmentKind.OMR_MCQ,
        batch_metrics=batch_metrics,
        student_reports=reports,
        contacts=contact_evaluations,
    )


# ------------------------------------------------------------------------------
# Marks Entry Totals Batch Evaluation (ADR-0016, S3 Task 3)
# ------------------------------------------------------------------------------


def evaluate_marks_entry_totals_batch(
    sheet: MarksEntrySheet | Sequence[MarksEntrySheet] | dict[str, Any] | Sequence[dict[str, Any]],
    roster: StudentRoster | list[StudentAdmissionRow] | list[dict[str, Any]] | None = None,
    org_id: str | None = None,
) -> EvaluationBundle:
    """
    Evaluate a batch of teacher manual marks entry totals (ADR-0016).
    Supports single-subject or multi-subject assessments.
    Unavailable dimensions (bleed, gross, easy questions, subject diagnostics)
    are strictly represented as literal NOT_AVAILABLE, never 0 or empty list.
    """
    sheets: list[MarksEntrySheet]
    if isinstance(sheet, (list, tuple)):
        sheets = [
            s if isinstance(s, MarksEntrySheet) else MarksEntrySheet.model_validate(s)
            for s in sheet
        ]
    else:
        sheets = [
            sheet if isinstance(sheet, MarksEntrySheet) else MarksEntrySheet.model_validate(sheet)
        ]

    if not sheets:
        raise IngestionError("At least one MarksEntrySheet is required for evaluation")

    active_org_id = org_id or sheets[0].org_id
    for s in sheets:
        if s.org_id != active_org_id:
            raise OrgIdMismatchError(
                f"Marks entry sheet org_id '{s.org_id}' does not match active org_id '{active_org_id}'"
            )

    # Optional roster reconciliation
    admissions_map: dict[str, StudentAdmissionRow] = {}
    contact_evaluations: list[ContactEvaluation] = []
    contact_eval_map: dict[str, ContactEvaluation] = {}

    if roster is not None:
        adm_list: list[StudentAdmissionRow]
        if isinstance(roster, StudentRoster):
            adm_list = roster.students
        elif isinstance(roster, list):
            adm_list = [
                item if isinstance(item, StudentAdmissionRow) else StudentAdmissionRow.model_validate(item)
                for item in roster
            ]
        else:
            raise TypeError(f"Unsupported roster type: {type(roster).__name__}")

        for adm in adm_list:
            if adm.org_id and adm.org_id != active_org_id:
                raise OrgIdMismatchError(
                    f"Roster student org_id '{adm.org_id}' does not match active org_id '{active_org_id}'"
                )
            admissions_map[adm.roll_number] = adm
            if adm.student_id:
                admissions_map[adm.student_id] = adm

        contact_evaluations = validate_admission_batch(adm_list, org_id=active_org_id)
        contact_eval_map = {c.student_id: c for c in contact_evaluations}

    # Verify duplicate entries within each sheet
    for s in sheets:
        seen_rolls: set[str] = set()
        for row in s.rows:
            if row.roll_no in seen_rolls:
                raise DuplicateRecordError(
                    f"Duplicate entry for roll number '{row.roll_no}' in marks entry sheet for subject '{s.subject}'"
                )
            seen_rolls.add(row.roll_no)

    if len(sheets) == 1:
        # Single sheet path (preserves exact golden test outputs)
        marks_sheet = sheets[0]
        enrolled_count = len(marks_sheet.rows)
        present_rows = [r for r in marks_sheet.rows if r.status == AttendanceStatus.PRESENT]
        present_count = len(present_rows)
        absent_count = enrolled_count - present_count

        scores_for_rank: list[Fraction | None] = []
        for r in marks_sheet.rows:
            if r.status == AttendanceStatus.PRESENT and r.marks is not None:
                scores_for_rank.append(r.marks)
            else:
                scores_for_rank.append(None)

        ranks = compute_standard_competition_ranks(scores_for_rank)

        if present_count > 0:
            present_marks = [r.marks for r in present_rows if r.marks is not None]
            total_sum_frac: Fraction = sum(present_marks, Fraction(0, 1))
            topper_mark_frac: Fraction = max(present_marks)

            class_avg_display = format_decimal_1dp(total_sum_frac, present_count)
            topper_display = format_decimal_1dp(topper_mark_frac, 1)
            total_sum_display = format_decimal_1dp(total_sum_frac, 1)
        else:
            total_sum_frac = Fraction(0, 1)
            class_avg_display = None
            topper_display = None
            total_sum_display = None

        student_reports: list[StudentDiagnosticReport] = []
        ptm_eligible_count = 0

        for idx, r in enumerate(marks_sheet.rows):
            rank = ranks[idx]
            is_pres = r.status == AttendanceStatus.PRESENT

            adm_match = admissions_map.get(r.roll_no) or (
                admissions_map.get(r.student_id) if r.student_id else None
            )
            c_eval = contact_eval_map.get(adm_match.student_id) if adm_match else None

            sid = r.student_id or (adm_match.student_id if adm_match else f"STU_{r.roll_no}")
            cname = r.child_display_name or (adm_match.child_display_name if adm_match else "")
            csec = marks_sheet.cohort_label or (adm_match.class_section if adm_match else "")

            if is_pres and r.marks is not None:
                pct_raw = format_percentage_raw(r.marks, marks_sheet.max_marks)
                pct_display = format_percentage_display(r.marks, marks_sheet.max_marks)
                status_band = classify_status_band(r.marks, marks_sheet.max_marks, is_present=True)
                marks_display = format_decimal_1dp(r.marks, 1)
            else:
                pct_raw = None
                pct_display = None
                status_band = StatusBand.ABSENT.value
                marks_display = None

            requires_ptm = check_requires_ptm_slip(
                is_present=is_pres,
                status_band=status_band,
                rank=rank,
                present_count=present_count,
            )
            if requires_ptm:
                ptm_eligible_count += 1

            student_reports.append(
                StudentDiagnosticReport(
                    student_id=sid,
                    roll_number=r.roll_no,
                    child_display_name=unicodedata.normalize("NFC", cname),
                    class_section=unicodedata.normalize("NFC", csec),
                    status=r.status,
                    attempted=NOT_AVAILABLE if is_pres else None,
                    correct=NOT_AVAILABLE if is_pres else None,
                    wrong=NOT_AVAILABLE if is_pres else None,
                    blank=NOT_AVAILABLE if is_pres else None,
                    gross_marks=NOT_AVAILABLE if is_pres else None,
                    bleed_marks=NOT_AVAILABLE if is_pres else None,
                    net_marks=r.marks if is_pres else None,
                    marks=marks_display,
                    max_marks=marks_sheet.max_marks,
                    percentage=pct_raw,
                    net_percentage=pct_display,
                    competition_rank=rank,
                    subject_ranks={marks_sheet.subject: rank if is_pres else None},
                    overall_rank=None,
                    status_band=status_band,
                    requires_ptm_slip=requires_ptm,
                    easy_missed_question_ids=NOT_AVAILABLE,
                    positive_marks_not_earned=NOT_AVAILABLE if is_pres else None,
                    subject_diagnostics=NOT_AVAILABLE if is_pres else None,
                    subject_breakdown=None,
                    enrolled_count=enrolled_count,
                    present_count=present_count,
                    class_average=class_avg_display,
                    topper_score=topper_display,
                    contact_eligibility=c_eval,
                    dispatch_eligible=c_eval.dispatch_eligible if c_eval else False,
                    exclusion_reason=c_eval.exclusion_reason if c_eval else None,
                    org_id=active_org_id,
                    schema_version=marks_sheet.schema_version,
                )
            )

        batch_metrics = BatchMetrics(
            enrolled_count=enrolled_count,
            present_count=present_count,
            absent_count=absent_count,
            total_score_sum=total_sum_display,
            class_average=class_avg_display,
            topper_marks=topper_display,
            ptm_eligible_count=ptm_eligible_count,
            easy_question_ids=NOT_AVAILABLE,
        )

        return EvaluationBundle(
            org_id=active_org_id,
            schema_version=marks_sheet.schema_version,
            assessment_name=marks_sheet.assessment_name,
            subject=marks_sheet.subject,
            cohort_label=marks_sheet.cohort_label,
            max_marks=marks_sheet.max_marks,
            kind=AssessmentKind.MARKS_ENTRY_TOTALS,
            batch_metrics=batch_metrics,
            student_reports=student_reports,
            contacts=contact_evaluations,
        )

    # --------------------------------------------------------------------------
    # Multi-subject assessment evaluation (ADR-0016 Section 5 & S3 Task 3)
    # --------------------------------------------------------------------------
    seen_subjects: set[str] = set()
    for s in sheets:
        if s.subject in seen_subjects:
            raise DuplicateRecordError(f"Duplicate marks entry sheet for subject '{s.subject}'")
        seen_subjects.add(s.subject)

    # 1. Unique students across all sheets (order preserved)
    unique_students: list[dict[str, Any]] = []
    seen_student_rolls: set[str] = set()
    for s in sheets:
        for r in s.rows:
            if r.roll_no not in seen_student_rolls:
                seen_student_rolls.add(r.roll_no)
                unique_students.append({
                    "roll_no": r.roll_no,
                    "student_id": r.student_id,
                    "child_display_name": r.child_display_name,
                })
            else:
                curr = next(st for st in unique_students if st["roll_no"] == r.roll_no)
                if not curr["student_id"] and r.student_id:
                    curr["student_id"] = r.student_id
                if not curr["child_display_name"] and r.child_display_name:
                    curr["child_display_name"] = r.child_display_name

    # 2. Per-subject ranks computed among PRESENT students in each subject
    subject_ranks_map: dict[str, dict[str, int | None]] = {}
    subject_row_map: dict[str, dict[str, MarksEntryRow]] = {}

    for s in sheets:
        row_map = {r.roll_no: r for r in s.rows}
        subject_row_map[s.subject] = row_map

        s_scores: list[Fraction | None] = [
            r.marks if r.status == AttendanceStatus.PRESENT and r.marks is not None else None
            for r in s.rows
        ]
        s_ranks = compute_standard_competition_ranks(s_scores)
        subject_ranks_map[s.subject] = {
            r.roll_no: s_ranks[i] for i, r in enumerate(s.rows)
        }

    # 3. Attendance and score aggregation across all subjects
    total_assessment_max_marks = sum(s.max_marks for s in sheets)
    student_evals: list[dict[str, Any]] = []

    for st in unique_students:
        roll = st["roll_no"]
        st_subj_ranks: dict[str, int | None] = {}
        is_all_present = True
        is_any_present = False
        total_score = Fraction(0, 1)

        for s in sheets:
            row_entry: MarksEntryRow | None = subject_row_map[s.subject].get(roll)
            if row_entry is not None and row_entry.status == AttendanceStatus.PRESENT and row_entry.marks is not None:
                st_subj_ranks[s.subject] = subject_ranks_map[s.subject].get(roll)
                total_score += row_entry.marks
                is_any_present = True
            else:
                st_subj_ranks[s.subject] = None
                is_all_present = False

        student_evals.append({
            "meta": st,
            "subject_ranks": st_subj_ranks,
            "is_all_present": is_all_present,
            "is_any_present": is_any_present,
            "total_score": total_score if is_all_present else None,
        })

    # 4. Standard competition ranking across students PRESENT in ALL subjects
    # If a student is absent in ANY subject, their overall_rank is None (ADR-0016)
    overall_scores_for_rank: list[Fraction | None] = [
        ev["total_score"] if ev["is_all_present"] else None
        for ev in student_evals
    ]
    computed_overall_ranks = compute_standard_competition_ranks(overall_scores_for_rank)

    # 5. Cohort metrics (over students present in all subjects)
    all_present_evals = [ev for ev in student_evals if ev["is_all_present"]]
    present_count = len(all_present_evals)
    enrolled_count = len(student_evals)
    absent_count = enrolled_count - present_count

    if present_count > 0:
        present_totals = [ev["total_score"] for ev in all_present_evals if ev["total_score"] is not None]
        total_sum_frac = sum(present_totals, Fraction(0, 1))
        topper_total_frac = max(present_totals)
        class_avg_display = format_decimal_1dp(total_sum_frac, present_count)
        topper_display = format_decimal_1dp(topper_total_frac, 1)
        total_sum_display = format_decimal_1dp(total_sum_frac, 1)
    else:
        total_sum_frac = Fraction(0, 1)
        class_avg_display = None
        topper_display = None
        total_sum_display = None

    # 6. Assemble StudentDiagnosticReports
    student_reports = []
    ptm_eligible_count = 0

    for idx, ev in enumerate(student_evals):
        st = ev["meta"]
        roll = st["roll_no"]
        is_all_pres = ev["is_all_present"]
        is_any_pres = ev["is_any_present"]
        ov_rank = computed_overall_ranks[idx]

        adm_match = admissions_map.get(roll) or (
            admissions_map.get(st["student_id"]) if st["student_id"] else None
        )
        c_eval = contact_eval_map.get(adm_match.student_id) if adm_match else None

        sid = st["student_id"] or (adm_match.student_id if adm_match else f"STU_{roll}")
        cname = st["child_display_name"] or (adm_match.child_display_name if adm_match else "")
        csec = sheets[0].cohort_label or (adm_match.class_section if adm_match else "")

        if is_all_pres and ev["total_score"] is not None:
            pct_raw = format_percentage_raw(ev["total_score"], total_assessment_max_marks)
            pct_display = format_percentage_display(ev["total_score"], total_assessment_max_marks)
            status_band = classify_status_band(ev["total_score"], total_assessment_max_marks, is_present=True)
            marks_display = format_decimal_1dp(ev["total_score"], 1)
            status_enum = AttendanceStatus.PRESENT
        else:
            pct_raw = None
            pct_display = None
            status_band = StatusBand.ABSENT.value
            marks_display = None
            status_enum = AttendanceStatus.PRESENT if is_any_pres else AttendanceStatus.ABSENT

        requires_ptm = check_requires_ptm_slip(
            is_present=is_all_pres,
            status_band=status_band,
            rank=ov_rank,
            present_count=present_count,
        )
        if requires_ptm:
            ptm_eligible_count += 1

        student_reports.append(
            StudentDiagnosticReport(
                student_id=sid,
                roll_number=roll,
                child_display_name=unicodedata.normalize("NFC", cname),
                class_section=unicodedata.normalize("NFC", csec),
                status=status_enum,
                attempted=NOT_AVAILABLE if is_any_pres else None,
                correct=NOT_AVAILABLE if is_any_pres else None,
                wrong=NOT_AVAILABLE if is_any_pres else None,
                blank=NOT_AVAILABLE if is_any_pres else None,
                gross_marks=NOT_AVAILABLE if is_any_pres else None,
                bleed_marks=NOT_AVAILABLE if is_any_pres else None,
                net_marks=ev["total_score"] if is_all_pres else None,
                marks=marks_display,
                max_marks=total_assessment_max_marks,
                percentage=pct_raw,
                net_percentage=pct_display,
                competition_rank=ov_rank,
                subject_ranks=ev["subject_ranks"],
                overall_rank=ov_rank,
                status_band=status_band,
                requires_ptm_slip=requires_ptm,
                easy_missed_question_ids=NOT_AVAILABLE,
                positive_marks_not_earned=NOT_AVAILABLE if is_any_pres else None,
                subject_diagnostics=NOT_AVAILABLE if is_any_pres else None,
                subject_breakdown=None,
                enrolled_count=enrolled_count,
                present_count=present_count,
                class_average=class_avg_display,
                topper_score=topper_display,
                contact_eligibility=c_eval,
                dispatch_eligible=c_eval.dispatch_eligible if c_eval else False,
                exclusion_reason=c_eval.exclusion_reason if c_eval else None,
                org_id=active_org_id,
                schema_version=sheets[0].schema_version,
            )
        )

    batch_metrics = BatchMetrics(
        enrolled_count=enrolled_count,
        present_count=present_count,
        absent_count=absent_count,
        total_score_sum=total_sum_display,
        class_average=class_avg_display,
        topper_marks=topper_display,
        ptm_eligible_count=ptm_eligible_count,
        easy_question_ids=NOT_AVAILABLE,
    )

    return EvaluationBundle(
        org_id=active_org_id,
        schema_version=sheets[0].schema_version,
        assessment_name=sheets[0].assessment_name,
        subject=", ".join(s.subject for s in sheets),
        cohort_label=sheets[0].cohort_label,
        max_marks=total_assessment_max_marks,
        kind=AssessmentKind.MARKS_ENTRY_TOTALS,
        batch_metrics=batch_metrics,
        student_reports=student_reports,
        contacts=contact_evaluations,
    )


# ------------------------------------------------------------------------------
# Unified Batch Evaluation Facade (S3 Task 3)
# ------------------------------------------------------------------------------


def evaluate_batch(
    assessment: Any,
    admissions: Any = None,
    submissions: Any = None,
    org_id: str | None = None,
) -> EvaluationBundle:
    """
    Unified batch evaluation entry point branching on AssessmentKind (ADR-0016).
    """
    # 1. Assessment entity passed directly
    if isinstance(assessment, Assessment):
        if assessment.kind == AssessmentKind.OMR_MCQ:
            target_paper = submissions if isinstance(submissions, (TestPaper, dict)) else None
            if target_paper is None:
                raise IngestionError("OMR_MCQ evaluation requires a TestPaper")
            return evaluate_omr_mcq_batch(
                paper=target_paper,
                roster=admissions,
                submissions=submissions,
                org_id=org_id,
            )
        if assessment.kind == AssessmentKind.MARKS_ENTRY_TOTALS:
            target_sheet = (
                submissions
                if isinstance(submissions, (MarksEntrySheet, list, tuple, dict))
                else (admissions if isinstance(admissions, (MarksEntrySheet, list, tuple, dict)) else None)
            )
            if target_sheet is None:
                raise IngestionError("MARKS_ENTRY_TOTALS evaluation requires MarksEntrySheet")
            return evaluate_marks_entry_totals_batch(
                sheet=target_sheet,
                roster=admissions if not isinstance(admissions, (MarksEntrySheet, list, tuple, dict)) else None,
                org_id=org_id,
            )
        if assessment.kind == AssessmentKind.MARKS_ENTRY_QUESTION_WISE:
            raise NotSupportedError(
                "Assessment kind 'MARKS_ENTRY_QUESTION_WISE' is not supported in Version 1 (ADR-0016)"
            )
        raise NotSupportedError(f"Unsupported assessment kind: {assessment.kind}")

    # 2. TestPaper passed as assessment
    if isinstance(assessment, TestPaper) or (
        isinstance(assessment, dict) and "questions" in assessment and "total_questions" in assessment
    ):
        if admissions is None or submissions is None:
            raise IngestionError("OMR_MCQ evaluation requires both admissions and submissions")
        return evaluate_omr_mcq_batch(
            paper=assessment,
            roster=admissions,
            submissions=submissions,
            org_id=org_id,
        )

    # 3. MarksEntrySheet or Sequence of sheets passed as assessment
    if isinstance(assessment, (MarksEntrySheet, list, tuple)) or (
        isinstance(assessment, dict) and "rows" in assessment and "max_marks" in assessment
    ):
        return evaluate_marks_entry_totals_batch(
            sheet=assessment,
            roster=admissions,
            org_id=org_id,
        )

    raise NotSupportedError(
        f"Unrecognized assessment format for evaluation: {type(assessment).__name__}"
    )
