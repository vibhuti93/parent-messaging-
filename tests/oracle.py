"""
Minimal test-local oracle for omr_dispatch_engine.

Used exclusively in tests for independent cross-checking of arithmetic,
ranking, diagnostics, and template rendering invariants.
Shares ZERO code with src/. All calculations use exact integer arithmetic,
fractions.Fraction, and decimal.Decimal (ROUND_HALF_UP). Zero float.
"""

from __future__ import annotations

import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction


def format_percentage_display(net: int | Fraction, max_marks: int) -> str:
    """Format net / max_marks as a percentage string with 1 decimal place using ROUND_HALF_UP."""
    if isinstance(net, Fraction):
        pct = (Decimal(net.numerator) * Decimal(100)) / (Decimal(net.denominator) * Decimal(max_marks))
    else:
        pct = (Decimal(net) * Decimal(100)) / Decimal(max_marks)
    rounded = pct.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded}%"


def format_decimal_display(value: int | Fraction, divisor: int = 1) -> str:
    """Format value / divisor as decimal string with 1 decimal place using ROUND_HALF_UP."""
    if isinstance(value, Fraction):
        num = Decimal(value.numerator)
        den = Decimal(value.denominator) * Decimal(divisor)
        val = num / den
    else:
        val = Decimal(value) / Decimal(divisor)
    rounded = val.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded}"


def classify_status_band(net: int | Fraction | None, max_marks: int, is_present: bool = True) -> str:
    """
    D-01 Status bands.
    PRESENT: < 30.0% RED; 30.0%–60.0% inclusive YELLOW; > 60.0% GREEN.
    ABSENT: band ABSENT.
    Uses exact integer cross-multiplication (zero float).
    """
    if not is_present or net is None:
        return "ABSENT"

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
        return "RED"
    if lhs <= rhs_yellow:
        return "YELLOW"
    return "GREEN"


def classify_subject_label(attempted: int, correct: int, total_subject_questions: int) -> str:
    """
    D-03 Subject diagnostic labels evaluated in priority order via exact cross-multiplication:
    1. attempted == 0 -> NO_ATTEMPT
    2. attempt_ratio >= 0.60 and accuracy_ratio < 0.65 -> ACCURACY_BLEED
    3. attempt_ratio < 0.50 and accuracy_ratio >= 0.75 -> CONCEPTUAL_SPEED_GAP
    4. attempt_ratio < 0.50 and accuracy_ratio < 0.65 -> FOUNDATIONAL_CRISIS
    5. attempt_ratio >= 0.60 and accuracy_ratio >= 0.75 -> MASTERY_ZONE
    6. otherwise -> MODERATE_ZONE
    """
    if attempted == 0:
        return "NO_ATTEMPT"

    # attempt_ratio = attempted / total_subject_questions
    # accuracy_ratio = correct / attempted
    # attempt_ratio >= 0.60 <=> attempted * 10 >= total_subject_questions * 6
    # attempt_ratio < 0.50  <=> attempted * 2 < total_subject_questions
    # accuracy_ratio >= 0.75 <=> correct * 4 >= attempted * 3 (or correct * 100 >= attempted * 75)
    # accuracy_ratio < 0.65  <=> correct * 100 < attempted * 65

    attempt_ge_60 = attempted * 10 >= total_subject_questions * 6
    attempt_lt_50 = attempted * 2 < total_subject_questions
    accuracy_ge_75 = correct * 4 >= attempted * 3
    accuracy_lt_65 = correct * 100 < attempted * 65

    if attempt_ge_60 and accuracy_lt_65:
        return "ACCURACY_BLEED"
    if attempt_lt_50 and accuracy_ge_75:
        return "CONCEPTUAL_SPEED_GAP"
    if attempt_lt_50 and accuracy_lt_65:
        return "FOUNDATIONAL_CRISIS"
    if attempt_ge_60 and accuracy_ge_75:
        return "MASTERY_ZONE"
    return "MODERATE_ZONE"


def check_requires_ptm_slip(is_present: bool, status_band: str, rank: int | None, present_count: int) -> bool:
    """
    D-04 Rank and PTM.
    PTM slip required iff ABSENT, or RED, or rank > floor(0.75 * present_count).
    floor(0.75 * present_count) == (present_count * 3) // 4 in exact integer arithmetic.
    """
    if not is_present:
        return True
    if status_band == "RED":
        return True
    if rank is not None:
        threshold = (present_count * 3) // 4
        if rank > threshold:
            return True
    return False


def score_single_omr_submission(test_paper: dict, submission: dict) -> dict:
    """Score a single student OMR submission against the test paper."""
    if submission.get("status") == "ABSENT":
        return {
            "status": "ABSENT",
            "attempted": None,
            "correct": None,
            "wrong": None,
            "blank": None,
            "gross_marks": None,
            "bleed_marks": None,
            "net_marks": None,
            "net_percentage": None,
            "status_band": "ABSENT",
            "subject_breakdown": None,
            "subject_diagnostics": None,
        }

    responses = submission.get("responses", {})
    questions = test_paper.get("questions", [])

    correct_count = 0
    wrong_count = 0
    blank_count = 0

    subject_counts: dict[str, dict[str, int]] = {}

    for q in questions:
        q_id = str(q["question_id"])
        subj = q["subject"]
        if subj not in subject_counts:
            subject_counts[subj] = {"total": 0, "attempted": 0, "correct": 0, "wrong": 0, "blank": 0}
        subject_counts[subj]["total"] += 1

        key = q["correct_option"]
        resp = responses.get(q_id)

        if resp is None or resp == "BLANK" or resp == "":
            blank_count += 1
            subject_counts[subj]["blank"] += 1
        elif resp == key:
            correct_count += 1
            subject_counts[subj]["attempted"] += 1
            subject_counts[subj]["correct"] += 1
        else:
            wrong_count += 1
            subject_counts[subj]["attempted"] += 1
            subject_counts[subj]["wrong"] += 1

    attempted_count = correct_count + wrong_count
    gross = correct_count * 4
    bleed = wrong_count * 1
    net = gross - bleed
    total_max = test_paper.get("total_max_marks", 300)

    # Subject diagnostics
    diagnostics: dict[str, str] = {}
    for subj, cnts in subject_counts.items():
        diagnostics[subj] = classify_subject_label(cnts["attempted"], cnts["correct"], cnts["total"])

    return {
        "status": "PRESENT",
        "attempted": attempted_count,
        "correct": correct_count,
        "wrong": wrong_count,
        "blank": blank_count,
        "gross_marks": gross,
        "bleed_marks": bleed,
        "net_marks": net,
        "net_percentage": format_percentage_display(net, total_max),
        "status_band": classify_status_band(net, total_max, is_present=True),
        "subject_breakdown": subject_counts,
        "subject_diagnostics": diagnostics,
    }


def find_easy_questions(test_paper: dict, submissions: list[dict]) -> set[int]:
    """
    D-02 Easy questions.
    accuracy = correct among PRESENT / PRESENT count; easy iff accuracy >= 0.75.
    Exact comparison: correct * 4 >= present_count * 3.
    """
    present_subs = [s for s in submissions if s.get("status") == "PRESENT"]
    present_count = len(present_subs)
    if present_count == 0:
        return set()

    questions = test_paper.get("questions", [])
    easy_set: set[int] = set()

    for q in questions:
        q_id = str(q["question_id"])
        key = q["correct_option"]
        correct_for_q = 0
        for s in present_subs:
            resp = s.get("responses", {}).get(q_id)
            if resp == key:
                correct_for_q += 1

        if correct_for_q * 4 >= present_count * 3:
            easy_set.add(q["question_id"])

    return easy_set


def compute_standard_competition_ranks(scores: list[int | Fraction | None]) -> list[int | None]:
    """
    D-04 Standard competition rank: 1 + count(present students with strictly higher net).
    None for absent students.
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


def render_marks_entry_present_message(
    child_name: str,
    class_section: str,
    test_name: str,
    subject: str,
    max_marks: str | int,
    marks: str | int,
    percentage: str,
    present_count: str | int,
    rank: str | int,
    class_average: str,
    topper_marks: str | int,
) -> str:
    """Render approved golden message for MARKS_ENTRY_TOTALS (Operator Decision 4)."""
    text = (
        f"प्रिय अभिभावक, {child_name} ({class_section}) के {test_name} ({subject}) में "
        f"{max_marks} में से {marks} नंबर आए हैं ({percentage})। "
        f"{present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। "
        f"क्लास का औसत स्कोर {class_average} है। क्लास में सबसे ज़्यादा नंबर {topper_marks} हैं।"
    )
    return unicodedata.normalize("NFC", text)


def render_omr_present_message(
    child_name: str,
    class_section: str,
    test_name: str,
    max_marks: str | int,
    net_marks: str | int,
    net_percentage: str,
    present_count: str | int,
    rank: str | int,
    class_average: str,
    topper_marks: str | int,
    gross_marks: str | int,
    bleed_marks: str | int,
) -> str:
    """Render full diagnostic parent message for OMR_PRESENT (S1-BLOCK-02 Option 1)."""
    text = (
        f"प्रिय अभिभावक, {child_name} ({class_section}) के {test_name} में कुल नंबर: "
        f"{max_marks} में से {net_marks} नंबर आए हैं ({net_percentage})। "
        f"{present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। "
        f"क्लास का औसत स्कोर {class_average} है। क्लास में सबसे ज़्यादा नंबर {topper_marks} हैं। "
        f"सही जवाबों से मिले {gross_marks} नंबर, गलत जवाबों से {bleed_marks} नंबर कट गए।"
    )
    return unicodedata.normalize("NFC", text)


def render_omr_absent_message(
    child_name: str,
    class_section: str,
    test_name: str,
    max_marks: str | int,
    present_count: str | int,
) -> str:
    """Render factual absence notice for OMR_ABSENT (S1-BLOCK-03 Option 1)."""
    text = (
        f"प्रिय अभिभावक, {child_name} ({class_section}) {test_name} के टेस्ट में अनुपस्थित रहे। "
        f"कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।"
    )
    return unicodedata.normalize("NFC", text)


def render_marks_entry_absent_message(
    child_name: str,
    class_section: str,
    test_name: str,
    subject: str,
    max_marks: str | int,
    present_count: str | int,
) -> str:
    """Render factual absence notice for MARKS_ENTRY_ABSENT (S1-BLOCK-03 Option 1)."""
    text = (
        f"प्रिय अभिभावक, {child_name} ({class_section}) {test_name} ({subject}) के टेस्ट में अनुपस्थित रहे। "
        f"कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।"
    )
    return unicodedata.normalize("NFC", text)


# ==============================================================================
# Contact Classification Oracle (Operator Decision 2026-10-22)
# ==============================================================================

def normalize_indian_phone(raw_phone: str) -> tuple[str, bool]:
    """
    Normalize and validate Indian mobile phone number.
    Operator decision (2026-10-22) pending recording in spec:
    - Strip all non-digits.
    - If 12 digits starting with '91', drop '91'.
    - If 11 digits starting with '0', drop '0'.
    - Remaining national number must be exactly 10 digits starting with 6, 7, 8, or 9;
      otherwise INVALID_PHONE_NUMBER.
    Two numbers are 'the same' when their normalised 10-digit values are equal.
    """
    digits = "".join(c for c in raw_phone if c.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        national = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        national = digits[1:]
    else:
        national = digits

    is_valid = len(national) == 10 and len(national) > 0 and national[0] in "6789"
    return national, is_valid


def classify_contacts_oracle(admissions: dict) -> dict:
    """
    Minimal contact classifier oracle for admissions_300.json.
    Evaluates phone normalization, validity, student==parent same number,
    duplicate parent with verified_sibling false, consent not OPT_IN,
    and guardian verification not VERIFIED.

    Operator Ratified Exclusion Reason Precedence (2026-10-23):
      1. INVALID_PHONE_NUMBER
      2. INTERCEPTION_RISK_SAME_NUMBER
      3. DUPLICATE_PARENT_UNVERIFIED
      4. CONSENT_<STATUS> (CONSENT_UNKNOWN, CONSENT_REVOKED)
      5. GUARDIAN_<STATUS> (GUARDIAN_UNVERIFIED)

    Reproduces expected_contacts.json for all students.
    """
    students = admissions["students"]

    # Pre-normalize phones
    stu_norm_map: dict[str, tuple[str, bool]] = {}
    guard_norm_map: dict[str, tuple[str, bool]] = {}

    for s in students:
        sid = s["student_id"]
        stu_norm_map[sid] = normalize_indian_phone(s.get("raw_student_phone", ""))
        guard_norm_map[sid] = normalize_indian_phone(s.get("raw_guardian_phone", ""))

    # Count guardian phone occurrences across cohort
    guard_phone_counts: dict[str, int] = {}
    for norm_g, valid_g in guard_norm_map.values():
        if valid_g:
            guard_phone_counts[norm_g] = guard_phone_counts.get(norm_g, 0) + 1

    contacts = []
    for s in students:
        sid = s["student_id"]
        norm_s, valid_s = stu_norm_map[sid]
        norm_g, valid_g = guard_norm_map[sid]

        quarantine_flags: list[str] = []

        # 1. Phone validity check
        if not valid_g:
            quarantine_flags.append("INVALID_PHONE_NUMBER")

        # 2. Student == parent interception risk check
        # Two numbers are the same when their normalized 10-digit values are equal
        if valid_s and valid_g and norm_s == norm_g:
            quarantine_flags.append("INTERCEPTION_RISK_SAME_NUMBER")

        # 3. Duplicate parent check
        # If parent number shared by multiple students and verified_sibling is False
        if valid_g and guard_phone_counts.get(norm_g, 0) > 1 and not s.get("verified_sibling", False):
            quarantine_flags.append("DUPLICATE_PARENT_UNVERIFIED")

        is_quarantined = len(quarantine_flags) > 0

        # 4. Dispatch eligibility and exclusion reason
        dispatch_eligible = True
        exclusion_reason: str | None = None

        if is_quarantined:
            dispatch_eligible = False
            exclusion_reason = quarantine_flags[0]
        elif s.get("consent_status") != "OPT_IN":
            dispatch_eligible = False
            exclusion_reason = f"CONSENT_{s.get('consent_status')}"
        elif s.get("guardian_verification") != "VERIFIED":
            dispatch_eligible = False
            exclusion_reason = f"GUARDIAN_{s.get('guardian_verification')}"

        contacts.append({
            "dispatch_eligible": dispatch_eligible,
            "exclusion_reason": exclusion_reason,
            "is_quarantined": is_quarantined,
            "quarantine_flags": quarantine_flags,
            "student_id": sid,
        })

    return {
        "contacts": contacts,
        "org_id": admissions.get("org_id", "DEFAULT_INSTITUTION"),
        "schema_version": admissions.get("schema_version", 1),
        "test_id": admissions.get("test_id", "TEST_300"),
    }
