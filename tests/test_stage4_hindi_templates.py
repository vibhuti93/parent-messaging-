"""
Stage S4 Test Suite: Conversational Bolchal Hindi Templates and Constraints.

Compliant with Gate 4 mandates:
1. Exact golden match across all 20 students in fixtures/golden/expected_reports.json (STU_01..STU_20).
2. Exact golden match across all 6 students in fixtures/golden/expected_marks_reports.json (ME_01..ME_06).
3. Exact character-for-character match against Decision 4 approved golden message.
4. Sibling distinctness test: STU_05 and STU_06 differ by child_display_name.
5. All behavioral branches:
   - Status bands (RED, YELLOW, GREEN, ABSENT) and banner colors (D-07).
   - Negative net score display (with minus sign '-').
   - Zero wrong answers (does not imply all questions attempted).
   - Exactly 75% item accuracy boundary and zero easy questions missed copy.
   - Missing rank (rank=None omits rank sentence cleanly).
   - NO_ATTEMPT and other subject lines use observable facts, zero leaked enums.
   - Roll number policy toggle (include_roll_in_text default False vs True).
   - Zero banned Hindi vocabulary across all rendered outputs (D-06).
   - Latin digits only across all parent copy (0-9).
6. Unicode, Grapheme & Constraint Edge Cases:
   - Odd names and salutations, empty name fallback to 'विद्यार्थी'.
   - Unicode NFC normalization (passing NFD yields strict NFC).
   - Grapheme-safe truncation at 40 grapheme clusters with multi-codepoint Devanagari conjuncts.
   - TemplateConstraints enforcement (newlines, whitespace, anchors, lengths, fixed-to-variable balance).
   - Conservative defaults fallback with constraints_unverified=True when UNVERIFIED.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pytest

from omr_dispatch.hindi_templates import (
    RenderedBolchalContent,
    check_for_banned_vocabulary,
    normalize_name_or_fallback,
    render_bolchal_templates,
    render_marks_entry_present_message,
    render_otp_challenge_message,
    render_subject_diagnostic_fact,
    split_graphemes,
    truncate_graphemes,
    verify_latin_digits_only,
)
from omr_dispatch.models import (
    AttendanceStatus,
    StudentDiagnosticReport,
    SubjectDiagnosticLabel,
)
from omr_dispatch.template_constraints import (
    TemplateConstraints,
    TemplateConstraintViolationError,
    get_conservative_defaults,
    load_template_constraints,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden"
REPO_ROOT = FIXTURES_DIR.parent.parent


@pytest.fixture(scope="module")
def expected_reports() -> dict[str, Any]:
    fpath = FIXTURES_DIR / "expected_reports.json"
    assert fpath.exists(), "expected_reports.json fixture missing"
    return json.loads(fpath.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def expected_marks_reports() -> dict[str, Any]:
    fpath = FIXTURES_DIR / "expected_marks_reports.json"
    assert fpath.exists(), "expected_marks_reports.json fixture missing"
    return json.loads(fpath.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def edge_cases() -> dict[str, Any]:
    fpath = FIXTURES_DIR / "edge_cases.json"
    assert fpath.exists(), "edge_cases.json fixture missing"
    return json.loads(fpath.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def verified_constraints() -> TemplateConstraints:
    return load_template_constraints()


# ==============================================================================
# 1. Golden Fixture Assertions (All 20 OMR Students & All 6 Marks Entry Students)
# ==============================================================================


class TestGoldenFixtureMatching:
    """Verify 100% character-for-character match against frozen golden fixture expectations."""

    def test_all_20_omr_student_messages_match_expected_reports(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """Every single student in STU_01..STU_20 matches expected_reports.json message_text."""
        batch_metrics = expected_reports["batch_metrics"]
        test_name = "टर्म 1 डायग्नोस्टिक टेस्ट"
        max_marks = 300

        for student_data in expected_reports["student_reports"]:
            sid = student_data["student_id"]
            expected_text = unicodedata.normalize("NFC", student_data["message_text"])

            # Render via facade using dictionary directly
            rendered = render_bolchal_templates(
                student_data,
                constraints=verified_constraints,
                test_name=test_name,
                max_marks=max_marks,
                present_count=batch_metrics["present_count"],
                class_average=batch_metrics["class_average"],
                topper_score=batch_metrics["topper_net_marks"],
            )

            assert rendered.message_caption_hi == expected_text, (
                f"OMR message mismatch for {sid}:\n"
                f"Expected: {expected_text}\n"
                f"Actual:   {rendered.message_caption_hi}"
            )
            assert rendered.message_text == expected_text
            assert unicodedata.is_normalized("NFC", rendered.message_caption_hi)
            assert verify_latin_digits_only(rendered.message_caption_hi)

    def test_stu_01_golden_assertions(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """
        STU_01 specific golden assertions:
        - Score line conveys 'कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)'
        - Enclosed by fixed greeting, child name, and class
        - Voice copy says 25 wrong answers deducted 25 marks and the final score is 55
        - Easy sentence: 10 missed questions, 40 marks not earned, at least 75% peer accuracy
        """
        reports = {r["student_id"]: r for r in expected_reports["student_reports"]}
        stu_01_data = reports["STU_01"]
        batch_metrics = expected_reports["batch_metrics"]

        rendered = render_bolchal_templates(
            stu_01_data,
            constraints=verified_constraints,
            test_name="टर्म 1 डायग्नोस्टिक टेस्ट",
            max_marks=300,
            present_count=batch_metrics["present_count"],
            class_average=batch_metrics["class_average"],
            topper_score=batch_metrics["topper_net_marks"],
        )

        caption = rendered.message_caption_hi
        # Greeting and identification anchor
        assert caption.startswith("प्रिय अभिभावक, आरव (कक्षा 10-A)")
        # Frozen score line
        assert "कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)" in caption
        # Score line component
        assert rendered.score_line_hi == "कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)"
        # Banner properties
        assert rendered.banner_color_hex == "#D93025"
        assert rendered.banner_title_hi == "विशेष ध्यान देने की ज़रूरत"

        # Voice script golden assertions
        voice = rendered.voice_note_script_hi
        assert "25 गलत जवाबों से 25 नंबर कट गए और अंतिम स्कोर 55 रहा।" in voice
        assert "कम-से-कम 75% बच्चों ने जो सवाल सही किए" in voice
        assert "10 सरल सवाल छूट गए जिनसे 40 नंबर नहीं मिल पाए।" in voice

    def test_stu_17_absent_golden_assertions(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """
        STU_17 specific golden assertions:
        - 300-mark test held, 16 students attended
        - Zero framing as a zero score, zero rank, zero performance band
        - Banner is neutral grey #5F6368 with text 'टेस्ट में अनुपस्थित'
        """
        reports = {r["student_id"]: r for r in expected_reports["student_reports"]}
        stu_17_data = reports["STU_17"]
        batch_metrics = expected_reports["batch_metrics"]

        rendered = render_bolchal_templates(
            stu_17_data,
            constraints=verified_constraints,
            test_name="टर्म 1 डायग्नोस्टिक टेस्ट",
            max_marks=300,
            present_count=batch_metrics["present_count"],
        )

        caption = rendered.message_caption_hi
        assert caption == (
            "प्रिय अभिभावक, रिया (कक्षा 10-A) टर्म 1 डायग्नोस्टिक टेस्ट के टेस्ट में अनुपस्थित रहे। "
            "कुल 300 नंबर का टेस्ट आयोजित किया गया था जिसमें 16 बच्चे उपस्थित रहे।"
        )
        assert rendered.banner_color_hex == "#5F6368"
        assert rendered.banner_title_hi == "टेस्ट में अनुपस्थित"
        assert rendered.score_line_hi == ""
        assert "नंबर आए" not in caption
        assert "रैंक" not in caption
        assert " 0 नंबर" not in caption
        assert "0 नंबर आए" not in caption

    def test_all_6_marks_entry_student_messages_match_expected_marks(
        self,
        expected_marks_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """Every single student in ME_01..ME_06 matches expected_marks_reports.json character-for-character."""
        batch_metrics = expected_marks_reports["batch_metrics"]
        test_name = expected_marks_reports["assessment_name"]
        subject = expected_marks_reports["subject"]
        max_marks = expected_marks_reports["max_marks"]

        for student_data in expected_marks_reports["student_reports"]:
            sid = student_data["student_id"]
            expected_text = unicodedata.normalize("NFC", student_data["message_text"])

            rendered = render_bolchal_templates(
                student_data,
                constraints=verified_constraints,
                test_name=test_name,
                subject=subject,
                max_marks=max_marks,
                present_count=batch_metrics["present_count"],
                class_average=batch_metrics["class_average"],
                topper_score=batch_metrics["topper_marks"],
            )

            assert rendered.message_caption_hi == expected_text, (
                f"Marks entry message mismatch for {sid}:\n"
                f"Expected: {expected_text}\n"
                f"Actual:   {rendered.message_caption_hi}"
            )
            assert rendered.message_text == expected_text
            assert unicodedata.is_normalized("NFC", rendered.message_caption_hi)

    def test_approved_decision_4_golden_message(self) -> None:
        """Dynamically load Decision 4 from docs/DECISIONS_OPEN.md and match character-for-character."""
        decisions_file = REPO_ROOT / "docs" / "DECISIONS_OPEN.md"
        assert decisions_file.exists(), "docs/DECISIONS_OPEN.md missing"
        decisions_content = decisions_file.read_text(encoding="utf-8")

        m_dec = re.search(
            r"### Decision 4: Approved Golden Message for `MARKS_ENTRY_TOTALS`.*?^\s*>\s*\"([^\"]+)\"",
            decisions_content,
            re.MULTILINE | re.DOTALL,
        )
        assert m_dec, "Could not extract approved golden message from docs/DECISIONS_OPEN.md Decision 4"
        approved_decision_4 = unicodedata.normalize("NFC", m_dec.group(1).strip())

        rendered = render_marks_entry_present_message(
            child_name="आरव",
            class_section="कक्षा 8-B",
            test_name="यूनिट टेस्ट 1",
            subject="अंग्रेज़ी",
            max_marks=50,
            marks="30",
            percentage="60.0%",
            present_count=18,
            rank=7,
            class_average="32.4",
            topper_marks=47,
        )

        assert rendered == approved_decision_4
        assert unicodedata.is_normalized("NFC", rendered)


# ==============================================================================
# 2. Sibling Distinctness & Fixed Leading Greeting Anchors
# ==============================================================================


class TestSiblingAndGreetingIdentity:
    """Verify child naming invariants, sibling differentiation, and roll number policy."""

    def test_sibling_distinctness_stu_05_and_stu_06(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """
        Sibling distinctness test: STU_05 (Kabir) and STU_06 (Ananya) share identical parent phone
        (9811122288) and identical scores (80/300, 26.7%), but must produce captions differing
        strictly by child_display_name.
        """
        reports = {r["student_id"]: r for r in expected_reports["student_reports"]}
        stu_05 = reports["STU_05"]
        stu_06 = reports["STU_06"]
        batch_metrics = expected_reports["batch_metrics"]

        rend_05 = render_bolchal_templates(
            stu_05,
            constraints=verified_constraints,
            present_count=batch_metrics["present_count"],
            class_average=batch_metrics["class_average"],
            topper_score=batch_metrics["topper_net_marks"],
        )
        rend_06 = render_bolchal_templates(
            stu_06,
            constraints=verified_constraints,
            present_count=batch_metrics["present_count"],
            class_average=batch_metrics["class_average"],
            topper_score=batch_metrics["topper_net_marks"],
        )

        assert rend_05.message_caption_hi != rend_06.message_caption_hi
        assert "कबीर" in rend_05.message_caption_hi
        assert "अनन्या" in rend_06.message_caption_hi

        # Excluding child_display_name, the remainder of their messages must be identical
        diff_05 = rend_05.message_caption_hi.replace("कबीर", "{NAME}")
        diff_06 = rend_06.message_caption_hi.replace("अनन्या", "{NAME}")
        assert diff_05 == diff_06

    def test_fixed_leading_greeting_anchor_always_first(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """Every parent notification begins with 'प्रिय अभिभावक, '; variable is never first token."""
        for rep in expected_reports["student_reports"]:
            rendered = render_bolchal_templates(rep, constraints=verified_constraints)
            caption = rendered.message_caption_hi
            assert caption.startswith("प्रिय अभिभावक, ")
            # Prove child name is NOT the first token
            name = rep["child_display_name"]
            assert not caption.startswith(name)

    def test_roll_number_policy_toggle(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """
        Default include_roll_in_text=False excludes roll number from text.
        Setting include_roll_in_text=True includes '(रोल नं. XX, ...)'.
        """
        reports = {r["student_id"]: r for r in expected_reports["student_reports"]}
        stu_01 = reports["STU_01"]

        # Default (False)
        rend_default = render_bolchal_templates(
            stu_01,
            constraints=verified_constraints,
            include_roll_in_text=False,
        )
        assert "रोल नं." not in rend_default.message_caption_hi
        assert "आरव (कक्षा 10-A)" in rend_default.message_caption_hi

        # Enabled (True)
        rend_with_roll = render_bolchal_templates(
            stu_01,
            constraints=verified_constraints,
            include_roll_in_text=True,
        )
        assert "आरव (रोल नं. 01, कक्षा 10-A)" in rend_with_roll.message_caption_hi


# ==============================================================================
# 3. Behavioral Branches, Boundaries & Negative Net Scores
# ==============================================================================


class TestBehavioralBranches:
    """Verify performance status bands, ties, negative nets, missing ranks, and easy questions."""

    def test_all_status_bands_and_colors(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """Verify GREEN, YELLOW, RED, and ABSENT bands produce exact D-07 banner colors and titles."""
        reports = {r["student_id"]: r for r in expected_reports["student_reports"]}

        # 1. GREEN (STU_02: 92.7%)
        g = render_bolchal_templates(reports["STU_02"], constraints=verified_constraints)
        assert g.banner_color_hex == "#1E8E3E"
        assert g.banner_title_hi == "शानदार प्रदर्शन — बहुत बढ़िया"
        assert g.ptm_slip_text_hi is None  # Green band without bottom quarter does not require PTM

        # 2. YELLOW (STU_03: 30.0%)
        y = render_bolchal_templates(reports["STU_03"], constraints=verified_constraints)
        assert y.banner_color_hex == "#F9AB00"
        assert y.banner_title_hi == "अच्छा प्रयास — सुधार की गुंजाइश"
        assert y.ptm_slip_text_hi is None

        # 3. RED (STU_01: 18.3%)
        r = render_bolchal_templates(reports["STU_01"], constraints=verified_constraints)
        assert r.banner_color_hex == "#D93025"
        assert r.banner_title_hi == "विशेष ध्यान देने की ज़रूरत"
        assert r.ptm_slip_text_hi is not None
        assert "अभिभावक-शिक्षक बैठक (PTM)" in r.ptm_slip_text_hi

        # 4. ABSENT (STU_17)
        a = render_bolchal_templates(reports["STU_17"], constraints=verified_constraints)
        assert a.banner_color_hex == "#5F6368"
        assert a.banner_title_hi == "टेस्ट में अनुपस्थित"
        assert a.ptm_slip_text_hi is not None

    def test_negative_net_score_displays_with_minus_sign(
        self,
        edge_cases: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """Negative net score (e.g. -75 net / -25.0%) displays with a standard minus sign '-'."""
        aw = edge_cases["all_wrong_student"]
        report = StudentDiagnosticReport(
            student_id="AW_01",
            roll_number="99",
            child_display_name="परीक्षार्थी",
            class_section="कक्षा 10-A",
            status=AttendanceStatus.PRESENT,
            attempted=75,
            correct=0,
            wrong=75,
            blank=0,
            gross_marks=0,
            bleed_marks=75,
            net_marks=aw["net_marks"],  # -75
            net_percentage=aw["net_percentage"],  # "-25.0%"
            status_band=aw["status_band"],  # "RED"
            requires_ptm_slip=aw["requires_ptm_slip"],
            present_count=16,
            competition_rank=16,
            class_average="82.7",
            topper_score=278,
            max_marks=300,
        )

        rendered = render_bolchal_templates(report, constraints=verified_constraints)
        assert "कुल नंबर: 300 में से -75 नंबर आए हैं (-25.0%)" in rendered.message_caption_hi
        assert rendered.score_line_hi == "कुल नंबर: 300 में से -75 नंबर आए हैं (-25.0%)"
        assert rendered.banner_color_hex == "#D93025"

    def test_zero_wrong_answers_does_not_imply_all_attempted(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """
        Students with zero wrong answers (e.g. STU_05: 20 attempted, 20 correct, 55 blank):
        mark_bleed_line_hi and voice script state that no marks were deducted without claiming
        all questions were attempted.
        """
        reports = {r["student_id"]: r for r in expected_reports["student_reports"]}
        stu_05 = reports["STU_05"]  # 20 correct, 0 wrong, 55 blank

        rendered = render_bolchal_templates(stu_05, constraints=verified_constraints)
        assert rendered.mark_bleed_line_hi == "सही जवाबों से मिले 80 नंबर, गलत जवाबों से कोई नंबर नहीं कटे।"
        assert "गलत जवाबों से कोई नंबर नहीं कटे हैं" in rendered.voice_note_script_hi
        # Prove it does not say all questions were solved
        assert "सभी सवाल हल" not in rendered.mark_bleed_line_hi
        assert "सारे सवाल" not in rendered.voice_note_script_hi

    def test_missing_rank_omits_rank_sentence_cleanly(
        self,
        verified_constraints: TemplateConstraints,
    ) -> None:
        """
        When competition_rank is None (e.g. multi-subject partial attendance),
        the 'rank X out of N' sentence is cleanly omitted without extra whitespace or orphan periods.
        """
        report = StudentDiagnosticReport(
            student_id="PARTIAL_01",
            roll_number="01",
            child_display_name="आरव",
            class_section="कक्षा 8-B",
            status=AttendanceStatus.PRESENT,
            marks="30",
            max_marks=50,
            net_percentage="60.0%",
            competition_rank=None,  # Missing rank!
            status_band="YELLOW",
            requires_ptm_slip=False,
            present_count=5,
            class_average="21.9",
            topper_score=47,
        )

        rendered = render_bolchal_templates(
            report,
            constraints=verified_constraints,
            test_name="यूनिट टेस्ट 1",
            subject="अंग्रेज़ी",
        )

        caption = rendered.message_caption_hi
        assert "रैंक" not in caption
        assert "उपस्थित बच्चों में" not in caption
        # Sentences flow cleanly
        assert "50 में से 30 नंबर आए हैं (60.0%)। क्लास का औसत स्कोर 21.9 है। क्लास में सबसे ज़्यादा नंबर 47 हैं।" in caption
        assert "  " not in caption

    def test_zero_easy_questions_missed(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """When 0 easy questions were missed (STU_02), explicitly state in Hindi that none were missed."""
        reports = {r["student_id"]: r for r in expected_reports["student_reports"]}
        stu_02 = reports["STU_02"]

        rendered = render_bolchal_templates(stu_02, constraints=verified_constraints)
        assert rendered.low_hanging_line_hi == "कम-से-कम 75% बच्चों द्वारा सही किया गया कोई भी सवाल नहीं छूटा।"
        assert "कम-से-कम 75% बच्चों द्वारा सही किया गया कोई भी सवाल नहीं छूटा।" in rendered.voice_note_script_hi


# ==============================================================================
# 4. Observables & Leaked Enums / Banned Vocabulary
# ==============================================================================


class TestObservablesAndHygiene:
    """Verify D-03 observable facts, zero leaked internal enums, and zero D-06 banned vocabulary."""

    def test_subject_diagnostics_observable_facts(self) -> None:
        """Verify all internal diagnostic enums map to observable facts and never leak enum names."""
        for label in SubjectDiagnosticLabel:
            fact_line = render_subject_diagnostic_fact("गणित", label)
            assert fact_line.startswith("गणित: ")
            # Ensure the enum name itself is NEVER in the parent line
            assert label.name not in fact_line
            assert label.value not in fact_line

        # Specific test for NO_ATTEMPT
        no_attempt_line = render_subject_diagnostic_fact("गणित", SubjectDiagnosticLabel.NO_ATTEMPT)
        assert no_attempt_line == "गणित: इस विषय में कोई सवाल हल नहीं किया गया।"

    def test_zero_leaked_internal_enums_across_all_20_reports(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """No internal enum names (NO_ATTEMPT, MASTERY_ZONE, RED, etc.) may appear in parent copy."""
        forbidden_tokens = [
            "NO_ATTEMPT",
            "ACCURACY_BLEED",
            "CONCEPTUAL_SPEED_GAP",
            "FOUNDATIONAL_CRISIS",
            "MASTERY_ZONE",
            "MODERATE_ZONE",
            "NOT_AVAILABLE",
            "SINGLE_CORRECT",
            "AttendanceStatus",
            "StatusBand",
        ]

        for rep in expected_reports["student_reports"]:
            rendered = render_bolchal_templates(rep, constraints=verified_constraints)
            for token in forbidden_tokens:
                assert token not in rendered.message_caption_hi, f"Leaked internal token {token} in caption"
                assert token not in rendered.voice_note_script_hi, f"Leaked internal token {token} in voice script"
                assert token not in rendered.score_line_hi
                assert token not in rendered.batch_context_line_hi

    def test_banned_hindi_vocabulary_zero_tolerance(
        self,
        expected_reports: dict[str, Any],
        expected_marks_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """
        Verify D-06 banned Hindi terms never appear in any parent output:
        ऋणात्मक अंकन, प्रतिशतता, प्राप्तांक, पूर्णांक, औसत मान.
        """
        all_rendered: list[RenderedBolchalContent] = []

        for rep in expected_reports["student_reports"]:
            all_rendered.append(render_bolchal_templates(rep, constraints=verified_constraints))

        for rep in expected_marks_reports["student_reports"]:
            all_rendered.append(
                render_bolchal_templates(
                    rep,
                    constraints=verified_constraints,
                    test_name="यूनिट टेस्ट 1",
                    subject="अंग्रेज़ी",
                )
            )

        for rend in all_rendered:
            for text_field in [
                rend.message_caption_hi,
                rend.score_line_hi,
                rend.batch_context_line_hi,
                rend.mark_bleed_line_hi,
                rend.low_hanging_line_hi,
                rend.voice_note_script_hi,
                rend.ptm_slip_text_hi or "",
            ]:
                violations = check_for_banned_vocabulary(text_field)
                assert violations == [], f"Found banned vocabulary in rendered output: {violations}"

    def test_latin_digits_policy_strictly_enforced(
        self,
        expected_reports: dict[str, Any],
        verified_constraints: TemplateConstraints,
    ) -> None:
        """All numbers in all rendered strings use standard Latin digits (0-9), never Devanagari numerals."""
        for rep in expected_reports["student_reports"]:
            rend = render_bolchal_templates(rep, constraints=verified_constraints)
            for text_field in [
                rend.message_caption_hi,
                rend.score_line_hi,
                rend.batch_context_line_hi,
                rend.mark_bleed_line_hi,
                rend.low_hanging_line_hi,
                rend.voice_note_script_hi,
            ]:
                assert verify_latin_digits_only(text_field), (
                    f"Forbidden Devanagari digit found in parent copy: {text_field}"
                )


# ==============================================================================
# 5. Unicode, Grapheme Truncation & Constraints Edge Cases
# ==============================================================================


class TestUnicodeGraphemesAndConstraints:
    """Verify Unicode NFC normalization, 40-grapheme safe truncation, and TemplateConstraints rules."""

    def test_odd_names_and_empty_name_fallback(self) -> None:
        """Empty, whitespace, or invalid names fallback to 'विद्यार्थी'."""
        assert normalize_name_or_fallback(None) == "विद्यार्थी"
        assert normalize_name_or_fallback("") == "विद्यार्थी"
        assert normalize_name_or_fallback("   ") == "विद्यार्थी"
        assert normalize_name_or_fallback("!@#$%^&*()") == "विद्यार्थी"
        assert normalize_name_or_fallback("123456") == "विद्यार्थी"
        assert normalize_name_or_fallback("आरव") == "आरव"

    def test_unicode_nfc_normalization_enforced(
        self,
        verified_constraints: TemplateConstraints,
    ) -> None:
        """Passing non-NFC un-normalized strings yields strict Unicode NFC output."""
        # U+0958 is the legacy precomposed Devanagari QA, which is non-NFC (NFC is U+0915 + U+093C)
        non_nfc_name = "\u0958ासिम"
        non_nfc_class = "कक्षा 10-A \u0041\u0301"  # A + combining acute (non-NFC)

        assert not unicodedata.is_normalized("NFC", non_nfc_name)
        assert not unicodedata.is_normalized("NFC", non_nfc_class)

        report = StudentDiagnosticReport(
            student_id="NFD_01",
            roll_number="01",
            child_display_name=non_nfc_name,
            class_section=non_nfc_class,
            status=AttendanceStatus.PRESENT,
            marks="50",
            max_marks=50,
            net_percentage="100.0%",
            competition_rank=1,
            status_band="GREEN",
            requires_ptm_slip=False,
            present_count=10,
            class_average="35.0",
            topper_score=50,
        )

        rendered = render_bolchal_templates(report, constraints=verified_constraints)
        assert unicodedata.is_normalized("NFC", rendered.message_caption_hi)
        assert unicodedata.is_normalized("NFC", rendered.score_line_hi)
        assert "प्रिय अभिभावक, " in rendered.message_caption_hi

    def test_grapheme_safe_truncation_at_40_graphemes(self) -> None:
        """
        Multi-codepoint Devanagari conjuncts (क्ष, त्र, ज्ञ, matras, halants):
        Truncation cuts at exactly 40 grapheme clusters and NEVER leaves a dangling halant or broken matra.
        """
        # Build a repetitive sequence of complex Indic grapheme clusters
        # Each cluster is a 3-codepoint conjunct: 'क्षि' = 'क' + '्' + 'ष' + 'ि' (4 codepoints, 1 grapheme cluster)
        unit = "क्षि"  # 1 grapheme cluster, 4 codepoints
        long_name = unit * 50  # 50 grapheme clusters, 200 codepoints

        clusters = split_graphemes(long_name)
        assert len(clusters) == 50

        truncated = truncate_graphemes(long_name, max_graphemes=40)
        assert len(split_graphemes(truncated)) == 40
        assert truncated == unit * 40
        assert not truncated.endswith("\u094d")  # No trailing halant

        # Test truncation with dangling halant at the boundary
        # If the input ends with a halant:
        test_with_halant = "विद्यार्थ" + "\u094d"
        clean = truncate_graphemes(test_with_halant, max_graphemes=40)
        assert not clean.endswith("\u094d")

    def test_template_constraints_reject_newlines_in_variables(
        self,
        verified_constraints: TemplateConstraints,
    ) -> None:
        """Variables containing \\n or \\r must trigger TemplateConstraintViolationError."""
        with pytest.raises(TemplateConstraintViolationError, match="newline character"):
            verified_constraints.validate_variable("child_name", "आरव\nवर्मा")

        with pytest.raises(TemplateConstraintViolationError, match="newline character"):
            verified_constraints.validate_variable("child_name", "आरव\rवर्मा")

    def test_template_constraints_reject_leading_trailing_whitespace(
        self,
        verified_constraints: TemplateConstraints,
    ) -> None:
        """Variables with leading or trailing whitespace must trigger TemplateConstraintViolationError."""
        with pytest.raises(TemplateConstraintViolationError, match="whitespace"):
            verified_constraints.validate_variable("child_name", " आरव")

        with pytest.raises(TemplateConstraintViolationError, match="whitespace"):
            verified_constraints.validate_variable("child_name", "आरव ")

    def test_template_constraints_fixed_anchors_and_length(
        self,
        verified_constraints: TemplateConstraints,
    ) -> None:
        """Must reject messages violating leading greeting anchor or ending with raw variable."""
        # 1. Missing leading greeting
        with pytest.raises(TemplateConstraintViolationError, match="fixed leading greeting anchor"):
            verified_constraints.validate_rendered_message("नमस्ते, आरव के 50 नंबर आए हैं।")

        # 2. Variable is first token
        with pytest.raises(TemplateConstraintViolationError, match="fixed leading greeting anchor"):
            verified_constraints.validate_rendered_message("आरव (कक्षा 10-A) के 50 नंबर आए हैं।")

        # 3. Ending with variable placeholder
        with pytest.raises(TemplateConstraintViolationError, match="trailing anchor"):
            verified_constraints.validate_rendered_message("प्रिय अभिभावक, आरव के नंबर हैं {{1}}")

        # 4. Length exceeding 1024 chars
        too_long = "प्रिय अभिभावक, " + ("क" * 1020)
        with pytest.raises(TemplateConstraintViolationError, match="exceeds max_body_length"):
            verified_constraints.validate_rendered_message(too_long)

    def test_unverified_constraints_fallback(self) -> None:
        """When constraints are UNVERIFIED, constraints_unverified is True on output."""
        conservative = get_conservative_defaults()
        assert conservative.constraints_unverified is True
        assert conservative.source_verified is False

        report = StudentDiagnosticReport(
            student_id="UNVERIFIED_01",
            roll_number="01",
            child_display_name="आरव",
            class_section="कक्षा 10-A",
            status=AttendanceStatus.PRESENT,
            marks="50",
            max_marks=50,
            net_percentage="100.0%",
            competition_rank=1,
            status_band="GREEN",
            requires_ptm_slip=False,
            present_count=10,
            class_average="35.0",
            topper_score=50,
        )

        rendered = render_bolchal_templates(report, constraints=conservative)
        assert rendered.constraints_unverified is True

    def test_otp_challenge_template_exemption(self) -> None:
        """Authentication OTP challenge is exempt from naming child/class."""
        otp_msg = render_otp_challenge_message("482910")
        assert "482910" in otp_msg
        assert "सत्यापन कोड" in otp_msg
        assert "प्रिय अभिभावक" not in otp_msg
        assert unicodedata.is_normalized("NFC", otp_msg)
