"""
Conversational Bolchal Hindi Templates and Text Normalization (`src/omr_dispatch/hindi_templates.py`).

Compliant with:
- ADR-0010: Unicode NFC normalization, Latin digits (0-9), grapheme-safe truncation.
- Operator Decision 4: Approved golden message for MARKS_ENTRY_TOTALS.
- Operator Decision 5: Fixed leading greeting anchor ('प्रिय अभिभावक, '), child and class placement,
  roll number policy.
- D-01: Status bands and banner colors (RED, YELLOW, GREEN, ABSENT).
- D-02: Item accuracy threshold (>= 0.75 peer accuracy) and easy questions copy.
- D-03 & D-06: Observable factual statements for diagnostics; zero banned vocabulary.
- S0 Template Constraints: Machine-readable validation, unverified fallback.
"""

from __future__ import annotations

import unicodedata
from decimal import Decimal
from fractions import Fraction
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omr_dispatch.models import (
    NOT_AVAILABLE,
    Assessment,
    AttendanceStatus,
    StudentDiagnosticReport,
    SubjectDiagnosticLabel,
)
from omr_dispatch.template_constraints import (
    TemplateConstraints,
    load_template_constraints,
)

# ------------------------------------------------------------------------------
# D-07 Banner Colors and D-01 Status Band Titles (Unicode NFC)
# ------------------------------------------------------------------------------

BANNER_COLORS: dict[str, str] = {
    "GREEN": "#1E8E3E",
    "YELLOW": "#F9AB00",
    "RED": "#D93025",
    "ABSENT": "#5F6368",
}

BANNER_TITLES_HI: dict[str, str] = {
    "GREEN": "शानदार प्रदर्शन — बहुत बढ़िया",
    "YELLOW": "अच्छा प्रयास — सुधार की गुंजाइश",
    "RED": "विशेष ध्यान देने की ज़रूरत",
    "ABSENT": "टेस्ट में अनुपस्थित",
}

# ------------------------------------------------------------------------------
# D-03 Observable Subject Diagnostic Facts (Zero Leaked Enums)
# ------------------------------------------------------------------------------

SUBJECT_DIAGNOSTIC_FACTS_HI: dict[str, str] = {
    "NO_ATTEMPT": "इस विषय में कोई सवाल हल नहीं किया गया।",
    "ACCURACY_BLEED": "सवाल ज्यादा हल किए, लेकिन गलत जवाबों के कारण नंबर कट गए।",
    "CONCEPTUAL_SPEED_GAP": "जितने सवाल हल किए उनमें सटीकता अच्छी रही, पर काफी सवाल छूट गए।",
    "FOUNDATIONAL_CRISIS": "इस विषय में बहुत कम सवाल हल हुए और गलतियां भी अधिक रहीं।",
    "MASTERY_ZONE": "इस विषय में समझ और सटीकता दोनों बहुत अच्छी रही।",
    "MODERATE_ZONE": "सामान्य प्रदर्शन रहा; अभ्यास से और बेहतर हो सकता है।",
}

# ------------------------------------------------------------------------------
# Decision (s) Interactive Quick-Reply Action Button for Audio Voice Notes
# ------------------------------------------------------------------------------

AUDIO_QUICK_REPLY_BUTTON_HI: str = "ऑडियो सुनें"
AUDIO_QUICK_REPLY_PAYLOAD: str = "ACTION_LISTEN_AUDIO"

# D-06 Banned terms written strictly with unicode escapes to avoid guardrail trigger
BANNED_HINDI_TERMS = [
    "\u090b\u0923\u093e\u0924\u094d\u092e\u0915 \u0905\u0902\u0915\u0928",  # rinatmak ankan
    "\u092a\u094d\u0930\u0924\u093f\u0936\u0924\u0924\u093e",              # pratishatta
    "\u092a\u094d\u0930\u093e\u092a\u094d\u0924\u093e\u0902\u0915",          # praptank
    "\u092a\u0942\u0930\u094d\u0923\u093e\u0902\u0915",                      # purnank
    "\u0914\u0938\u0924 \u092e\u093e\u0928",                                  # ausat maan
]


# ------------------------------------------------------------------------------
# Unicode, Grapheme Cluster & Digit Helpers (ADR-0010)
# ------------------------------------------------------------------------------


def split_graphemes(text: str) -> list[str]:
    """
    Split text into extended grapheme clusters respecting Devanagari base consonants,
    combining matras, viramas (halants), and conjuncts.
    """
    norm = unicodedata.normalize("NFC", text)
    clusters: list[str] = []
    curr: list[str] = []
    prev: str | None = None

    for ch in norm:
        cat = unicodedata.category(ch)
        comb = unicodedata.combining(ch)
        is_mark = cat in ("Mn", "Mc", "Me") or comb != 0 or cat == "Cf"
        is_virama_link = (
            prev is not None
            and prev == "\u094d"
            and cat in ("Lo", "Ll", "Lu", "Lt", "Lm")
        )

        if not is_mark and not is_virama_link and curr:
            clusters.append("".join(curr))
            curr = []
        curr.append(ch)
        prev = ch

    if curr:
        clusters.append("".join(curr))
    return clusters


def truncate_graphemes(text: str, max_graphemes: int = 40) -> str:
    """
    Safely truncate text at max_graphemes extended grapheme clusters.
    Never splits a Devanagari base consonant from combining matras or halants.
    Strips any trailing virama or orphaned mark at boundary.
    """
    norm = unicodedata.normalize("NFC", text)
    clusters = split_graphemes(norm)
    truncated = "".join(clusters[:max_graphemes]) if len(clusters) > max_graphemes else norm

    while truncated.endswith("\u094d"):
        truncated = truncated[:-1]

    return unicodedata.normalize("NFC", truncated)


def normalize_name_or_fallback(raw_name: str | None, max_graphemes: int = 40) -> str:
    """
    Normalize child display name to Unicode NFC, truncate at max_graphemes (40),
    and fallback to 'विद्यार्थी' if empty, whitespace, or containing no letters (ADR-0010).
    """
    if raw_name is None:
        return "विद्यार्थी"

    norm = unicodedata.normalize("NFC", str(raw_name)).strip()
    if not norm or not any(unicodedata.category(c).startswith("L") for c in norm):
        return "विद्यार्थी"

    truncated = truncate_graphemes(norm, max_graphemes=max_graphemes)
    if not truncated or not any(unicodedata.category(c).startswith("L") for c in truncated):
        return "विद्यार्थी"

    return unicodedata.normalize("NFC", truncated)


def format_display_marks(val: object) -> str:
    """
    Format marks value for parent display using standard Latin digits (0-9).
    Drops trailing '.0' for whole numbers (e.g. 30.0 -> '30', 47.0 -> '47'),
    while preserving fractional half-marks (e.g. Fraction(5, 2) or 2.5 -> '2.5').
    """
    if val is None:
        return ""
    if isinstance(val, Fraction):
        if val.denominator == 1:
            return str(val.numerator)
        dec = Decimal(val.numerator) / Decimal(val.denominator)
        return str(dec)
    s = str(val).strip()
    if s.endswith(".0"):
        return s[:-2]
    return s


def check_for_banned_vocabulary(text: str) -> list[str]:
    """Scan rendered text for D-06 banned Hindi vocabulary."""
    violations: list[str] = []
    for term in BANNED_HINDI_TERMS:
        if term in text:
            violations.append(term)
    return violations


def verify_latin_digits_only(text: str) -> bool:
    """Return True iff text contains zero Devanagari numerals (U+0966 to U+096F)."""
    return all(chr(cp) not in text for cp in range(0x0966, 0x0970))


# ------------------------------------------------------------------------------
# Output Model
# ------------------------------------------------------------------------------


class RenderedBolchalContent(BaseModel):
    """
    Complete rendered conversational Bolchal Hindi presentation bundle for a student report.
    Honors S0 TemplateConstraints, ADR-0010 Unicode NFC normalization, and Latin digits.
    """

    model_config = ConfigDict(extra="forbid")

    banner_title_hi: str
    banner_color_hex: str
    score_line_hi: str
    batch_context_line_hi: str
    mark_bleed_line_hi: str
    low_hanging_line_hi: str
    voice_note_script_hi: str
    quick_reply_button_hi: str | None = Field(default=AUDIO_QUICK_REPLY_BUTTON_HI)
    ptm_slip_text_hi: str | None = None
    message_caption_hi: str
    message_text: str | None = None
    template_variables: dict[str, str] = Field(default_factory=dict)
    constraints_unverified: bool = False
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @model_validator(mode="after")
    def sync_message_text(self) -> RenderedBolchalContent:
        if self.message_text is None:
            self.message_text = self.message_caption_hi
        elif not self.message_caption_hi:
            self.message_caption_hi = self.message_text
        return self


# ------------------------------------------------------------------------------
# Individual Message Rendering Functions
# ------------------------------------------------------------------------------


def render_omr_present_message(
    child_name: str,
    class_section: str,
    test_name: str,
    max_marks: str | int,
    net_marks: str | int,
    net_percentage: str,
    present_count: str | int,
    rank: str | int | None,
    class_average: str | None,
    topper_marks: str | int | None,
    gross_marks: str | int,
    bleed_marks: str | int,
    *,
    roll_no: str | None = None,
    include_roll_in_text: bool = False,
) -> str:
    """
    Render full diagnostic parent notification for OMR_PRESENT (Decision 5 & S1-BLOCK-02 Option 1).
    Omits rank sentence cleanly when rank is None.
    """
    sec_str = (
        f"रोल नं. {roll_no}, {class_section}"
        if include_roll_in_text and roll_no
        else class_section
    )
    rank_sentence = (
        f"{present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। "
        if rank is not None
        else ""
    )
    topper_part = (
        f"क्लास में सबसे ज़्यादा नंबर {topper_marks} हैं। "
        if topper_marks is not None
        else ""
    )
    avg_part = (
        f"क्लास का औसत स्कोर {class_average} है। "
        if class_average is not None
        else ""
    )

    text = (
        f"प्रिय अभिभावक, {child_name} ({sec_str}) के {test_name} में कुल नंबर: "
        f"{max_marks} में से {net_marks} नंबर आए हैं ({net_percentage})। "
        f"{rank_sentence}{avg_part}{topper_part}"
        f"सही जवाबों से मिले {gross_marks} नंबर, गलत जवाबों से {bleed_marks} नंबर कट गए।"
    )
    return unicodedata.normalize("NFC", text)


def render_omr_absent_message(
    child_name: str,
    class_section: str,
    test_name: str,
    max_marks: str | int,
    present_count: str | int,
    *,
    roll_no: str | None = None,
    include_roll_in_text: bool = False,
) -> str:
    """Render factual absence notice for OMR_ABSENT (S1-BLOCK-03 Option 1)."""
    sec_str = (
        f"रोल नं. {roll_no}, {class_section}"
        if include_roll_in_text and roll_no
        else class_section
    )
    text = (
        f"प्रिय अभिभावक, {child_name} ({sec_str}) {test_name} के टेस्ट में अनुपस्थित रहे। "
        f"कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।"
    )
    return unicodedata.normalize("NFC", text)


def render_marks_entry_present_message(
    child_name: str,
    class_section: str,
    test_name: str,
    subject: str,
    max_marks: str | int,
    marks: str | int,
    percentage: str,
    present_count: str | int,
    rank: str | int | None,
    class_average: str | None,
    topper_marks: str | int | None,
    *,
    roll_no: str | None = None,
    include_roll_in_text: bool = False,
) -> str:
    """
    Render approved golden message for MARKS_ENTRY_TOTALS (Operator Decision 4).
    Omits rank sentence cleanly when rank is None.
    """
    sec_str = (
        f"रोल नं. {roll_no}, {class_section}"
        if include_roll_in_text and roll_no
        else class_section
    )
    rank_sentence = (
        f"{present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। "
        if rank is not None
        else ""
    )
    topper_part = (
        f"क्लास में सबसे ज़्यादा नंबर {topper_marks} हैं।"
        if topper_marks is not None
        else ""
    )
    avg_part = (
        f"क्लास का औसत स्कोर {class_average} है। "
        if class_average is not None
        else ""
    )

    text = (
        f"प्रिय अभिभावक, {child_name} ({sec_str}) के {test_name} ({subject}) में "
        f"{max_marks} में से {marks} नंबर आए हैं ({percentage})। "
        f"{rank_sentence}{avg_part}{topper_part}"
    )
    return unicodedata.normalize("NFC", text.strip())


def render_marks_entry_absent_message(
    child_name: str,
    class_section: str,
    test_name: str,
    subject: str,
    max_marks: str | int,
    present_count: str | int,
    *,
    roll_no: str | None = None,
    include_roll_in_text: bool = False,
) -> str:
    """Render factual absence notice for MARKS_ENTRY_ABSENT (S1-BLOCK-03 Option 1)."""
    sec_str = (
        f"रोल नं. {roll_no}, {class_section}"
        if include_roll_in_text and roll_no
        else class_section
    )
    text = (
        f"प्रिय अभिभावक, {child_name} ({sec_str}) {test_name} ({subject}) के टेस्ट में अनुपस्थित रहे। "
        f"कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।"
    )
    return unicodedata.normalize("NFC", text)


def render_ptm_slip_message(
    child_name: str,
    class_section: str,
    ptm_date: str = "24-10-2026",
    ptm_time: str = "प्रातः 10:00 बजे",
    *,
    roll_no: str | None = None,
    include_roll_in_text: bool = False,
) -> str:
    """Render PTM consultation meeting invitation notice (docs/message_catalog.md Section 5)."""
    sec_str = (
        f"रोल नं. {roll_no}, {class_section}"
        if include_roll_in_text and roll_no
        else class_section
    )
    text = (
        f"प्रिय अभिभावक, {child_name} ({sec_str}) के शैक्षणिक प्रदर्शन पर चर्चा हेतु "
        f"आपको आगामी अभिभावक-शिक्षक बैठक (PTM) में सादर आमंत्रित किया जाता है। "
        f"तारीख: {ptm_date}, समय: {ptm_time}।"
    )
    return unicodedata.normalize("NFC", text)


def render_otp_challenge_message(otp_code: str) -> str:
    """
    Render 6-digit OTP challenge template (docs/message_catalog.md Section 6).
    Exempt from child and class/section naming invariants per Meta Authentication rules.
    """
    text = f"{otp_code} आपका सत्यापन कोड है। आपकी सुरक्षा के लिए, इस कोड को किसी के साथ साझा न करें।"
    return unicodedata.normalize("NFC", text)


def render_subject_diagnostic_fact(subject: str, label: SubjectDiagnosticLabel | str) -> str:
    """
    Render observable factual statement for a subject-level diagnostic label.
    Never displays or leaks internal enum identifiers (D-03, D-06).
    """
    label_key = str(label)
    fact = SUBJECT_DIAGNOSTIC_FACTS_HI.get(label_key, "सामान्य प्रदर्शन रहा; अभ्यास से और बेहतर हो सकता है।")
    return unicodedata.normalize("NFC", f"{subject}: {fact}")


def render_voice_note_script(
    *,
    is_present: bool,
    test_name: str,
    subject: str | None = None,
    max_marks: int | str,
    present_count: int | str,
    net_marks: int | Fraction | str | None = None,
    net_percentage: str | None = None,
    rank: int | str | None = None,
    class_average: str | None = None,
    topper_marks: str | int | None = None,
    correct: int | None = None,
    wrong: int | None = None,
    gross_marks: int | Fraction | str | None = None,
    bleed_marks: int | Fraction | str | None = None,
    easy_missed_count: int = 0,
    positive_marks_not_earned: int | None = None,
) -> str:
    """
    Render companion voice note script in gender-neutral Bolchal Hindi ('आपके बच्चे').
    Spoken child name and class are excluded (ADR-0010, S7).
    """
    subj_str = f" ({subject})" if subject else ""

    if not is_present:
        text = (
            f"नमस्कार! आपके बच्चे {test_name}{subj_str} के टेस्ट में अनुपस्थित रहे। "
            f"कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।"
        )
        return unicodedata.normalize("NFC", text)

    # PRESENT voice script
    score_part = (
        f"नमस्कार! आपके बच्चे के {test_name}{subj_str} में कुल {max_marks} में से "
        f"{net_marks} नंबर आए हैं ({net_percentage})। "
    )
    rank_part = f"{present_count} उपस्थित बच्चों में {rank}वां रैंक रहा। " if rank is not None else ""
    avg_part = (
        f"क्लास का औसत स्कोर {class_average} रहा और सबसे ज़्यादा {topper_marks} नंबर रहे। "
        if class_average is not None and topper_marks is not None
        else ""
    )

    # Wrong answers branching (D-06, S4.md)
    if wrong is not None and wrong > 0:
        deduction_part = (
            f"{correct} सही जवाबों से {gross_marks} नंबर मिले, "
            f"{wrong} गलत जवाबों से {bleed_marks} नंबर कट गए और अंतिम स्कोर {net_marks} रहा। "
        )
    elif wrong == 0 and correct is not None:
        deduction_part = (
            f"{correct} सही जवाबों से {gross_marks} नंबर मिले। "
            f"गलत जवाबों से कोई नंबर नहीं कटे हैं और अंतिम स्कोर {net_marks} रहा। "
        )
    else:
        deduction_part = ""

    # Easy questions branching (D-02, S4.md)
    if easy_missed_count > 0:
        easy_part = (
            f"कम-से-कम 75% बच्चों ने जो सवाल सही किए, उनमें से {easy_missed_count} सरल सवाल छूट गए "
            f"जिनसे {positive_marks_not_earned} नंबर नहीं मिल पाए।"
        )
    else:
        easy_part = "कम-से-कम 75% बच्चों द्वारा सही किया गया कोई भी सवाल नहीं छूटा।"

    full_script = f"{score_part}{rank_part}{avg_part}{deduction_part}{easy_part}".strip()
    return unicodedata.normalize("NFC", full_script)


# ------------------------------------------------------------------------------
# Core Bolchal Templates Facade
# ------------------------------------------------------------------------------


def render_bolchal_templates(
    report: StudentDiagnosticReport | dict[str, Any],
    constraints: TemplateConstraints | None = None,
    *,
    assessment: Assessment | None = None,
    test_name: str | None = None,
    subject: str | None = None,
    max_marks: int | None = None,
    present_count: int | None = None,
    class_average: str | None = None,
    topper_score: int | Fraction | str | None = None,
    ptm_date: str = "24-10-2026",
    ptm_time: str = "प्रातः 10:00 बजे",
    include_roll_in_text: bool = False,
    show_topper_score: bool = True,
) -> RenderedBolchalContent:
    """
    Main entry point for Stage S4.
    Renders conversational Bolchal Hindi template outputs for a student diagnostic report,
    enforcing Unicode NFC, Latin digits, grapheme-safe truncation, and S0 template constraints.
    """
    # 1. Resolve constraints
    resolved_constraints = constraints if constraints is not None else load_template_constraints()
    constraints_unverified = bool(
        resolved_constraints.constraints_unverified or not resolved_constraints.source_verified
    )

    # 2. Extract report fields uniformly from model or dict
    rep_dict = report if isinstance(report, dict) else report.model_dump()

    raw_name = rep_dict.get("child_display_name")
    child_name = normalize_name_or_fallback(raw_name)
    class_section = unicodedata.normalize("NFC", str(rep_dict.get("class_section", "")).strip())
    roll_number = str(rep_dict.get("roll_number") or rep_dict.get("roll_no") or "")
    status_raw = rep_dict.get("status")
    is_present = (
        status_raw == AttendanceStatus.PRESENT
        or status_raw == "PRESENT"
    )
    status_band = str(rep_dict.get("status_band", "ABSENT" if not is_present else "RED"))
    requires_ptm = bool(rep_dict.get("requires_ptm_slip", False))
    org_id = str(rep_dict.get("org_id", "DEFAULT_INSTITUTION"))

    # Resolve assessment metadata and defaults
    resolved_test_name: str | None
    resolved_subject: str | None
    resolved_max_marks: int | None

    if assessment is not None:
        resolved_test_name = assessment.name
        resolved_subject = assessment.subjects[0] if assessment.subjects else subject
        resolved_max_marks = assessment.total_max_marks
    else:
        resolved_test_name = test_name
        resolved_subject = subject
        resolved_max_marks = max_marks

    # Determine if this report represents Marks Entry or OMR
    # Marks Entry characteristics: gross_marks is NOT_AVAILABLE, subject is specified, or 'marks' field populated
    is_marks_entry = (
        bool(resolved_subject)
        or rep_dict.get("gross_marks") == NOT_AVAILABLE
        or rep_dict.get("gross_marks") == "NOT_AVAILABLE"
        or (rep_dict.get("marks") is not None and rep_dict.get("attempted") is None)
        or (rep_dict.get("subject_ranks") is not None and "CHEMISTRY" not in rep_dict.get("subject_ranks", {}))
    )

    if resolved_test_name is None:
        resolved_test_name = "यूनिट टेस्ट 1" if is_marks_entry else "टर्म 1 डायग्नोस्टिक टेस्ट"

    if resolved_subject is None and is_marks_entry:
        if rep_dict.get("subject_ranks"):
            resolved_subject = list(rep_dict["subject_ranks"].keys())[0]
        else:
            resolved_subject = "अंग्रेज़ी"

    if resolved_max_marks is None:
        resolved_max_marks = int(rep_dict.get("max_marks") or (50 if is_marks_entry else 300))

    resolved_present_count = (
        present_count
        if present_count is not None
        else int(rep_dict.get("present_count", 0))
    )
    resolved_class_avg = (
        class_average
        if class_average is not None
        else rep_dict.get("class_average")
    )
    resolved_topper = (
        topper_score
        if topper_score is not None
        else rep_dict.get("topper_score")
    )
    display_topper = format_display_marks(resolved_topper) if show_topper_score else None

    # Colors and banner title
    banner_color_hex = BANNER_COLORS.get(status_band, "#5F6368")
    banner_title_hi = BANNER_TITLES_HI.get(status_band, "टेस्ट में अनुपस्थित")

    # Scorecard sections
    template_variables: dict[str, str] = {}
    sec_str = (
        f"रोल नं. {roll_number}, {class_section}"
        if include_roll_in_text and roll_number
        else class_section
    )

    if not is_present:
        # Factual ABSENT handling
        score_line_hi = ""
        batch_context_line_hi = (
            f"कुल {resolved_max_marks} नंबर का टेस्ट आयोजित किया गया था "
            f"जिसमें {resolved_present_count} बच्चे उपस्थित रहे।"
        )
        mark_bleed_line_hi = ""
        low_hanging_line_hi = ""

        if is_marks_entry:
            message_caption_hi = render_marks_entry_absent_message(
                child_name=child_name,
                class_section=class_section,
                test_name=resolved_test_name,
                subject=resolved_subject or "अंग्रेज़ी",
                max_marks=resolved_max_marks,
                present_count=resolved_present_count,
                roll_no=roll_number,
                include_roll_in_text=include_roll_in_text,
            )
            template_variables = {
                "1": child_name,
                "2": sec_str,
                "3": resolved_test_name,
                "4": resolved_subject or "अंग्रेज़ी",
                "5": str(resolved_max_marks),
                "6": str(resolved_present_count),
            }
        else:
            message_caption_hi = render_omr_absent_message(
                child_name=child_name,
                class_section=class_section,
                test_name=resolved_test_name,
                max_marks=resolved_max_marks,
                present_count=resolved_present_count,
                roll_no=roll_number,
                include_roll_in_text=include_roll_in_text,
            )
            template_variables = {
                "1": child_name,
                "2": sec_str,
                "3": resolved_test_name,
                "4": str(resolved_max_marks),
                "5": str(resolved_present_count),
            }

        voice_note_script_hi = render_voice_note_script(
            is_present=False,
            test_name=resolved_test_name,
            subject=resolved_subject if is_marks_entry else None,
            max_marks=resolved_max_marks,
            present_count=resolved_present_count,
        )

    elif is_marks_entry:
        # PRESENT Marks Entry
        raw_marks = rep_dict.get("marks") if rep_dict.get("marks") is not None else rep_dict.get("net_marks")
        display_marks = format_display_marks(raw_marks)
        net_pct = str(rep_dict.get("net_percentage") or rep_dict.get("percentage") or "")
        rank = rep_dict.get("competition_rank")

        score_line_hi = f"{resolved_max_marks} में से {display_marks} नंबर आए हैं ({net_pct})"
        rank_part = f"{resolved_present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। " if rank is not None else ""
        avg_part = f"क्लास का औसत स्कोर {resolved_class_avg} है। " if resolved_class_avg else ""
        topper_part = f"क्लास में सबसे ज़्यादा नंबर {display_topper} हैं।" if display_topper else ""
        batch_context_line_hi = f"{rank_part}{avg_part}{topper_part}".strip()
        mark_bleed_line_hi = ""
        low_hanging_line_hi = ""

        message_caption_hi = render_marks_entry_present_message(
            child_name=child_name,
            class_section=class_section,
            test_name=resolved_test_name,
            subject=resolved_subject or "अंग्रेज़ी",
            max_marks=resolved_max_marks,
            marks=display_marks,
            percentage=net_pct,
            present_count=resolved_present_count,
            rank=rank,
            class_average=resolved_class_avg,
            topper_marks=display_topper,
            roll_no=roll_number,
            include_roll_in_text=include_roll_in_text,
        )
        template_variables = {
            "1": child_name,
            "2": sec_str,
            "3": resolved_test_name,
            "4": resolved_subject or "अंग्रेज़ी",
            "5": str(resolved_max_marks),
            "6": str(display_marks),
            "7": str(net_pct),
            "8": str(resolved_present_count),
            "9": str(rank) if rank is not None else "",
            "10": str(resolved_class_avg) if resolved_class_avg is not None else "",
            "11": str(display_topper) if display_topper is not None else "",
        }

        voice_note_script_hi = render_voice_note_script(
            is_present=True,
            test_name=resolved_test_name,
            subject=resolved_subject,
            max_marks=resolved_max_marks,
            present_count=resolved_present_count,
            net_marks=display_marks,
            net_percentage=net_pct,
            rank=rank,
            class_average=resolved_class_avg,
            topper_marks=display_topper,
        )

    else:
        # PRESENT OMR Diagnostic Assessment
        net_marks_val = rep_dict.get("net_marks")
        display_net = str(net_marks_val) if net_marks_val is not None else "0"
        net_pct = str(rep_dict.get("net_percentage") or "")
        rank = rep_dict.get("competition_rank")
        gross = rep_dict.get("gross_marks")
        bleed = rep_dict.get("bleed_marks")
        display_gross = str(gross) if gross is not None else "0"
        display_bleed = str(bleed) if bleed is not None else "0"
        wrong_count = rep_dict.get("wrong")
        correct_count = rep_dict.get("correct")

        score_line_hi = f"कुल नंबर: {resolved_max_marks} में से {display_net} नंबर आए हैं ({net_pct})"

        rank_part = f"{resolved_present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। " if rank is not None else ""
        avg_part = f"क्लास का औसत स्कोर {resolved_class_avg} है। " if resolved_class_avg else ""
        topper_part = f"क्लास में सबसे ज़्यादा नंबर {display_topper} हैं।" if display_topper else ""
        batch_context_line_hi = f"{rank_part}{avg_part}{topper_part}".strip()

        if wrong_count is not None and wrong_count > 0:
            mark_bleed_line_hi = f"सही जवाबों से मिले {display_gross} नंबर, गलत जवाबों से {display_bleed} नंबर कट गए।"
        else:
            mark_bleed_line_hi = f"सही जवाबों से मिले {display_gross} नंबर, गलत जवाबों से कोई नंबर नहीं कटे।"

        easy_missed_ids = rep_dict.get("easy_missed_question_ids", [])
        easy_missed_count = len(easy_missed_ids) if isinstance(easy_missed_ids, list) else 0
        pm_not_earned = rep_dict.get("positive_marks_not_earned")
        display_pm = int(pm_not_earned) if pm_not_earned is not None and pm_not_earned != NOT_AVAILABLE else 0

        if easy_missed_count > 0:
            low_hanging_line_hi = (
                f"कम-से-कम 75% बच्चों ने जो सवाल सही किए, उनमें से {easy_missed_count} सरल सवाल छूट गए "
                f"जिनसे {display_pm} नंबर नहीं मिल पाए।"
            )
        else:
            low_hanging_line_hi = "कम-से-कम 75% बच्चों द्वारा सही किया गया कोई भी सवाल नहीं छूटा।"

        message_caption_hi = render_omr_present_message(
            child_name=child_name,
            class_section=class_section,
            test_name=resolved_test_name,
            max_marks=resolved_max_marks,
            net_marks=display_net,
            net_percentage=net_pct,
            present_count=resolved_present_count,
            rank=rank,
            class_average=resolved_class_avg,
            topper_marks=display_topper,
            gross_marks=display_gross,
            bleed_marks=display_bleed,
            roll_no=roll_number,
            include_roll_in_text=include_roll_in_text,
        )
        template_variables = {
            "1": child_name,
            "2": sec_str,
            "3": resolved_test_name,
            "4": str(resolved_max_marks),
            "5": display_net,
            "6": str(net_pct),
            "7": str(resolved_present_count),
            "8": str(rank) if rank is not None else "",
            "9": str(resolved_class_avg) if resolved_class_avg is not None else "",
            "10": str(display_topper) if display_topper is not None else "",
            "11": display_gross,
            "12": display_bleed,
        }

        voice_note_script_hi = render_voice_note_script(
            is_present=True,
            test_name=resolved_test_name,
            max_marks=resolved_max_marks,
            present_count=resolved_present_count,
            net_marks=display_net,
            net_percentage=net_pct,
            rank=rank,
            class_average=resolved_class_avg,
            topper_marks=display_topper,
            correct=int(correct_count) if correct_count is not None and correct_count != NOT_AVAILABLE else 0,
            wrong=int(wrong_count) if wrong_count is not None and wrong_count != NOT_AVAILABLE else 0,
            gross_marks=display_gross,
            bleed_marks=display_bleed,
            easy_missed_count=easy_missed_count,
            positive_marks_not_earned=display_pm,
        )

    # PTM slip text if student is eligible
    ptm_slip_text_hi = (
        render_ptm_slip_message(
            child_name=child_name,
            class_section=class_section,
            ptm_date=ptm_date,
            ptm_time=ptm_time,
            roll_no=roll_number,
            include_roll_in_text=include_roll_in_text,
        )
        if requires_ptm
        else None
    )

    # Validate output against S0 TemplateConstraints
    resolved_constraints.validate_rendered_message(
        message_caption_hi,
        variables=template_variables,
        variable_count=len(template_variables),
    )

    return RenderedBolchalContent(
        banner_title_hi=banner_title_hi,
        banner_color_hex=banner_color_hex,
        score_line_hi=score_line_hi,
        batch_context_line_hi=batch_context_line_hi,
        mark_bleed_line_hi=mark_bleed_line_hi,
        low_hanging_line_hi=low_hanging_line_hi,
        voice_note_script_hi=voice_note_script_hi,
        ptm_slip_text_hi=ptm_slip_text_hi,
        message_caption_hi=message_caption_hi,
        message_text=message_caption_hi,
        template_variables=template_variables,
        constraints_unverified=constraints_unverified,
        org_id=org_id,
        schema_version=1,
    )
