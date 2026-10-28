"""
Stage S5 Gate 5 Test Suite (`tests/test_stage5_omr_proof.py`).

Verifies:
1. Dimensions & Transform: 800x600 synthetic source cropped via (0, 230, 800, 600) produces
   an exact 800x370 PIL Image, with crop offset recorded once in provenance.
2. Pixel-Level Color Assertions:
   - Q1 correct response for STU_01: green #1E8E3E (30, 142, 62) at/around (65, 25).
   - STU_01 Q11 wrong response (selected option D at (137, 425) source -> (137, 195) crop):
     red cross #D93025 (217, 48, 37) at (137, 195) and green outline #1E8E3E on correct key bubble (113, 195).
   - Blank easy question: amber outline #F9AB00 (249, 171, 0) on key bubble.
   - Blank non-easy question: clean bubble (no mark).
   - All-correct and all-wrong states.
   - Deterministic legend presence.
3. Fail-Closed & Error Paths (REVIEW_REQUIRED):
   - Missing CoordinateMap.
   - Corrupt/unreadable image bytes.
   - Missing scan file for a PRESENT student.
   - Out-of-bounds bubble coordinates (outside 800x600 source & outside crop box).
   - Dimension mismatch (no silent rescaling).
   - Low alignment confidence below threshold.
4. ABSENT Student Handling: returns ABSENT_NO_PROOF with proof_image=None, no fake replacement sheet.
5. Source Immutability & Signature Integrity:
   - Source scan file bytes and SHA-256 on disk remain 100% unchanged.
   - Input PIL Image pixel buffer remains 100% unchanged.
   - Signature region pixels are preserved byte-for-byte and never synthetically drawn in production.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

from omr_dispatch.models import (
    AttendanceStatus,
    OMRSubmissionsBatch,
    QuestionMeta,
    StudentOMRSubmission,
    TestPaper,
)
from omr_dispatch.omr_proof import (
    DEFAULT_CROP_BOX,
    HEX_COLOR_BLANK_EASY,
    HEX_COLOR_CORRECT,
    HEX_COLOR_WRONG,
    OMRProofResult,
    ProofReasonCode,
    ProofStatus,
    generate_omr_proof,
)

# Literal expected color values from spec (Part C Invariant 6) - independent of code under test
EXPECTED_CORRECT_GREEN: tuple[int, int, int] = (30, 142, 62)
EXPECTED_BLANK_EASY_AMBER: tuple[int, int, int] = (249, 171, 0)
EXPECTED_WRONG_RED: tuple[int, int, int] = (217, 48, 37)

# Prevent pytest from treating TestPaper domain model as a test class
TestPaper.__test__ = False

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden"


# ------------------------------------------------------------------------------
# Test-Only Synthetic Fixture Helpers
# ------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def golden_test_paper() -> TestPaper:
    data = json.loads((FIXTURES_DIR / "test_paper_300.json").read_text(encoding="utf-8"))
    return TestPaper.model_validate(data)


@pytest.fixture(scope="module")
def golden_submissions() -> OMRSubmissionsBatch:
    data = json.loads((FIXTURES_DIR / "submissions_300.json").read_text(encoding="utf-8"))
    return OMRSubmissionsBatch.model_validate(data)


@pytest.fixture(scope="module")
def easy_question_ids() -> list[int]:
    """Easy questions in test_paper_300 (Q1..Q20)."""
    return list(range(1, 21))


def create_synthetic_scan(
    questions: list[QuestionMeta],
    submission: StudentOMRSubmission | None = None,
    width: int = 800,
    height: int = 600,
    include_signature: bool = True,
    signature_box: tuple[int, int, int, int] = (620, 520, 750, 570),
) -> Image.Image:
    """Generate a synthetic 800x600 test OMR scan image with simulated student markings."""
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Simulated sheet header / borders in non-cropped region (y < 230)
    draw.rectangle((20, 20, 780, 200), outline=(220, 220, 220), width=1)

    # Draw all question bubbles
    for q in questions:
        if q.bubble_coordinates and q.bubble_coordinates.options:
            for _opt_name, coords in q.bubble_coordinates.options.items():
                x = coords["x"]
                y = coords["y"]
                # Bubble outline
                draw.ellipse((x - 6, y - 6, x + 6, y + 6), outline=(90, 90, 90), width=1)

    # Fill student's marked bubbles
    if submission and submission.responses:
        for q in questions:
            resp = submission.responses.get(str(q.id))
            if resp and resp != "BLANK" and q.bubble_coordinates:
                pos = q.bubble_coordinates.options.get(resp)
                if pos:
                    x = pos["x"]
                    y = pos["y"]
                    # Dark pencil mark
                    draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(35, 35, 35))

    # Simulated teacher / invigilator signature in designated region
    if include_signature:
        sx1, sy1, sx2, sy2 = signature_box
        draw.rectangle((sx1, sy1, sx2, sy2), outline=(180, 180, 180), width=1)
        draw.line(
            [(sx1 + 10, sy1 + 25), (sx1 + 35, sy1 + 10), (sx1 + 60, sy1 + 35), (sx2 - 15, sy1 + 20)],
            fill=(10, 45, 175),
            width=2,
        )

    return img


def find_color_pixels_in_box(
    img: Image.Image,
    center_x: int,
    center_y: int,
    target_color: tuple[int, int, int],
    radius: int = 8,
) -> list[tuple[int, int]]:
    """Return list of (x, y) coordinates matching target_color within radius of (center_x, center_y)."""
    matches = []
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            px = center_x + dx
            py = center_y + dy
            if 0 <= px < img.width and 0 <= py < img.height and img.getpixel((px, py))[:3] == target_color:
                matches.append((px, py))
    return matches


# ------------------------------------------------------------------------------
# 1. Dimensions, Cropping & Provenance Tests
# ------------------------------------------------------------------------------


@pytest.mark.unit
def test_synthetic_proof_dimensions_and_crop_provenance(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
    easy_question_ids: list[int],
) -> None:
    """Verify 800x600 source cropped via (0, 230, 800, 600) produces exact 800x370 PIL Image and records offset once."""
    stu_01 = golden_submissions.submissions[0]
    source_img = create_synthetic_scan(golden_test_paper.questions, stu_01)

    result = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
        easy_question_ids=easy_question_ids,
        crop_box=DEFAULT_CROP_BOX,
    )

    assert isinstance(result, OMRProofResult)
    assert result.status == ProofStatus.SUCCESS
    assert result.proof_image is not None
    assert result.proof_image.size == (800, 370)

    # Check provenance
    prov = result.provenance
    assert prov is not None
    assert prov.source_dimensions == (800, 600)
    assert prov.output_dimensions == (800, 370)
    assert prov.crop_box == (0, 230, 800, 600)
    assert len(prov.transforms_applied) == 1

    t0 = prov.transforms_applied[0]
    assert t0.name == "crop"
    assert t0.parameters["crop_box"] == [0, 230, 800, 600]
    assert t0.parameters["crop_offsets"] == {"crop_left": 0, "crop_top": 230}


# ------------------------------------------------------------------------------
# 2. Pixel-Level Color & Geometry Assertions
# ------------------------------------------------------------------------------


@pytest.mark.unit
def test_q1_correct_response_green_pixels_at_65_25(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
    easy_question_ids: list[int],
) -> None:
    """STU_01 Q1 correct response ('A'): verify green #1E8E3E pixels at/around (65, 25)."""
    stu_01 = golden_submissions.submissions[0]
    source_img = create_synthetic_scan(golden_test_paper.questions, stu_01)

    result = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
        easy_question_ids=easy_question_ids,
    )

    assert result.status == ProofStatus.SUCCESS
    proof_img = result.proof_image
    assert proof_img is not None

    # Q1 Option A in source is at (65, 255) -> cropped is (65, 25)
    green_pixels = find_color_pixels_in_box(proof_img, center_x=65, center_y=25, target_color=EXPECTED_CORRECT_GREEN, radius=8)
    assert len(green_pixels) > 0, "Expected green (#1E8E3E) pixels at/around cropped coordinate (65, 25)"
    # Hex verify
    assert HEX_COLOR_CORRECT == "#1E8E3E"


@pytest.mark.unit
def test_stu_01_q11_wrong_response_red_cross_and_green_outline(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
    easy_question_ids: list[int],
) -> None:
    """
    STU_01 Q11 wrong response (selected option D at (137, 425) source -> (137, 195) cropped):
    - Verify red cross #D93025 (217, 48, 37) pixels at (137, 195).
    - Verify green outline #1E8E3E (30, 142, 62) pixels on key bubble C at (113, 195).
    """
    stu_01 = golden_submissions.submissions[0]
    assert stu_01.responses["11"] == "D"  # Selected D

    q11 = golden_test_paper.questions[10]
    assert q11.id == 11
    assert q11.correct_option == "C"  # Key is C

    source_img = create_synthetic_scan(golden_test_paper.questions, stu_01)

    result = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
        easy_question_ids=easy_question_ids,
        outline_correct_on_wrong=True,
    )

    assert result.status == ProofStatus.SUCCESS
    proof_img = result.proof_image
    assert proof_img is not None

    # Option D at source (137, 425) -> cropped (137, 195)
    red_pixels = find_color_pixels_in_box(proof_img, center_x=137, center_y=195, target_color=EXPECTED_WRONG_RED, radius=8)
    assert len(red_pixels) > 0, "Expected red (#D93025) pixels on student selected bubble at (137, 195)"

    # Direct pixel at cross intersection (137, 195)
    center_color = proof_img.getpixel((137, 195))[:3]
    assert center_color == EXPECTED_WRONG_RED, f"Center of red cross must be exactly {EXPECTED_WRONG_RED}"
    assert HEX_COLOR_WRONG == "#D93025"

    # Key Option C at source (113, 425) -> cropped (113, 195)
    green_pixels = find_color_pixels_in_box(proof_img, center_x=113, center_y=195, target_color=EXPECTED_CORRECT_GREEN, radius=8)
    assert len(green_pixels) > 0, "Expected green outline (#1E8E3E) pixels on correct key bubble at (113, 195)"


@pytest.mark.unit
def test_blank_easy_question_amber_outline(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
    easy_question_ids: list[int],
) -> None:
    """Blank easy question: verify amber #F9AB00 (249, 171, 0) outline pixels on key bubble."""
    # Create submission with Q5 (easy question, key 'A') left blank
    sub_data = golden_submissions.submissions[0].model_dump()
    sub_data["responses"]["5"] = "BLANK"
    blank_sub = StudentOMRSubmission.model_validate(sub_data)

    q5 = golden_test_paper.questions[4]
    assert q5.id == 5
    assert q5.correct_option == "A"
    # Q5 option A in source: col_x + 35 = 65, center_y = 255 + 4*17 = 323 -> cropped (65, 93)

    source_img = create_synthetic_scan(golden_test_paper.questions, blank_sub)

    result = generate_omr_proof(
        source_scan=source_img,
        submission=blank_sub,
        answer_key=golden_test_paper.questions,
        easy_question_ids=easy_question_ids,
    )

    assert result.status == ProofStatus.SUCCESS
    proof_img = result.proof_image
    assert proof_img is not None

    amber_pixels = find_color_pixels_in_box(proof_img, center_x=65, center_y=93, target_color=EXPECTED_BLANK_EASY_AMBER, radius=8)
    assert len(amber_pixels) > 0, "Expected amber (#F9AB00) outline on key bubble for blank easy question"
    assert HEX_COLOR_BLANK_EASY == "#F9AB00"


@pytest.mark.unit
def test_blank_non_easy_question_clean_bubble(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
    easy_question_ids: list[int],
) -> None:
    """Blank non-easy question: verify bubble remains clean (no green, red, or amber marks)."""
    # STU_01 Q21 is BLANK and not in easy_question_ids (1..20)
    stu_01 = golden_submissions.submissions[0]
    assert stu_01.responses["21"] == "BLANK"
    assert 21 not in easy_question_ids

    source_img = create_synthetic_scan(golden_test_paper.questions, stu_01)

    result = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
        easy_question_ids=easy_question_ids,
    )

    assert result.status == ProofStatus.SUCCESS
    proof_img = result.proof_image
    assert proof_img is not None

    # Q21 coordinates: col=1 (col_x=180), row=5 (center_y=340). Option A=(215, 340) -> crop (215, 110)
    # Check that neither green, red, nor amber annotations were drawn on Q21 option bubbles
    for opt_idx in range(4):
        bx = 180 + 35 + opt_idx * 24
        by = 340 - 230  # 110
        for color in (EXPECTED_CORRECT_GREEN, EXPECTED_WRONG_RED, EXPECTED_BLANK_EASY_AMBER):
            pixels = find_color_pixels_in_box(proof_img, center_x=bx, center_y=by, target_color=color, radius=6)
            assert len(pixels) == 0, f"Option {opt_idx} at ({bx}, {by}) must not have annotation marks"


@pytest.mark.unit
def test_all_correct_and_all_wrong_states(
    golden_test_paper: TestPaper,
    easy_question_ids: list[int],
) -> None:
    """Verify all-correct and all-wrong submissions render expected annotation counts."""
    # All-correct submission
    all_correct_sub = StudentOMRSubmission(
        id="SUB_PERFECT",
        student_id="STU_PERFECT",
        status=AttendanceStatus.PRESENT,
        responses={str(q.id): q.correct_option for q in golden_test_paper.questions},
    )
    src_img = create_synthetic_scan(golden_test_paper.questions, all_correct_sub)

    res_correct = generate_omr_proof(
        source_scan=src_img,
        submission=all_correct_sub,
        answer_key=golden_test_paper.questions,
        easy_question_ids=easy_question_ids,
    )
    assert res_correct.status == ProofStatus.SUCCESS
    assert res_correct.annotations_summary["correct"] == 75
    assert res_correct.annotations_summary["wrong"] == 0
    assert res_correct.annotations_summary["blank_easy"] == 0

    # All-wrong submission
    all_wrong_responses: dict[str, str] = {}
    for q in golden_test_paper.questions:
        # Choose wrong option
        opts = ["A", "B", "C", "D"]
        opts.remove(q.correct_option)
        all_wrong_responses[str(q.id)] = opts[0]

    all_wrong_sub = StudentOMRSubmission(
        id="SUB_WRONG",
        student_id="STU_WRONG",
        status=AttendanceStatus.PRESENT,
        responses=all_wrong_responses,
    )
    src_wrong = create_synthetic_scan(golden_test_paper.questions, all_wrong_sub)

    res_wrong = generate_omr_proof(
        source_scan=src_wrong,
        submission=all_wrong_sub,
        answer_key=golden_test_paper.questions,
        easy_question_ids=easy_question_ids,
    )
    assert res_wrong.status == ProofStatus.SUCCESS
    assert res_wrong.annotations_summary["correct"] == 0
    assert res_wrong.annotations_summary["wrong"] == 75


@pytest.mark.unit
def test_legend_presence_verification(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
    easy_question_ids: list[int],
) -> None:
    """Verify deterministic visual legend is rendered with Correct, Wrong, and Blank Easy indicators."""
    stu_01 = golden_submissions.submissions[0]
    source_img = create_synthetic_scan(golden_test_paper.questions, stu_01)

    result = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
        easy_question_ids=easy_question_ids,
        render_legend=True,
        legend_origin=(30, 310),
    )

    assert result.status == ProofStatus.SUCCESS
    proof_img = result.proof_image
    assert proof_img is not None

    # Check legend region for green, red, and amber indicator pixels
    # Correct indicator at (30, 310)
    green_leg = find_color_pixels_in_box(proof_img, center_x=36, center_y=310, target_color=EXPECTED_CORRECT_GREEN, radius=10)
    assert len(green_leg) > 0, "Legend must contain green indicator"

    # Wrong indicator at (150, 310)
    red_leg = find_color_pixels_in_box(proof_img, center_x=156, center_y=310, target_color=EXPECTED_WRONG_RED, radius=10)
    assert len(red_leg) > 0, "Legend must contain red indicator"

    # Blank Easy indicator at (270, 310)
    amber_leg = find_color_pixels_in_box(proof_img, center_x=276, center_y=310, target_color=EXPECTED_BLANK_EASY_AMBER, radius=10)
    assert len(amber_leg) > 0, "Legend must contain amber indicator"


# ------------------------------------------------------------------------------
# 3. Fail-Closed & Error Paths (REVIEW_REQUIRED)
# ------------------------------------------------------------------------------


@pytest.mark.unit
def test_fail_closed_missing_coordinate_map(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
) -> None:
    """Fail closed when CoordinateMap is missing or empty."""
    stu_01 = golden_submissions.submissions[0]
    source_img = create_synthetic_scan(golden_test_paper.questions, stu_01)

    # Strip coordinates from questions
    naked_questions = [
        QuestionMeta(
            id=q.id,
            correct_option=q.correct_option,
            bubble_coordinates=None,
        )
        for q in golden_test_paper.questions
    ]

    result = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=naked_questions,
        coordinate_map=None,
    )

    assert result.status == ProofStatus.REVIEW_REQUIRED
    assert result.reason_code == ProofReasonCode.MISSING_COORDINATE_MAP
    assert result.proof_image is None


@pytest.mark.unit
def test_fail_closed_corrupt_unreadable_image_bytes(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
) -> None:
    """Fail closed on corrupt or unreadable image bytes."""
    stu_01 = golden_submissions.submissions[0]
    corrupt_bytes = b"CORRUPTED_NON_IMAGE_HEADER_DATA_12345"

    result = generate_omr_proof(
        source_scan=corrupt_bytes,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
    )

    assert result.status == ProofStatus.REVIEW_REQUIRED
    assert result.reason_code == ProofReasonCode.CORRUPT_IMAGE
    assert result.proof_image is None


@pytest.mark.unit
def test_fail_closed_missing_scan_file_for_present_student(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
) -> None:
    """Fail closed when scan file is missing on disk for a PRESENT student."""
    stu_01 = golden_submissions.submissions[0]

    result = generate_omr_proof(
        source_scan="non_existent_scan_path_file_98765.png",
        submission=stu_01,
        answer_key=golden_test_paper.questions,
    )

    assert result.status == ProofStatus.REVIEW_REQUIRED
    assert result.reason_code == ProofReasonCode.MISSING_SCAN_FILE
    assert result.proof_image is None


@pytest.mark.unit
def test_fail_closed_coordinate_out_of_source_bounds(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
) -> None:
    """Fail closed when a bubble coordinate exceeds source image dimensions (800x600)."""
    stu_01 = golden_submissions.submissions[0]
    source_img = create_synthetic_scan(golden_test_paper.questions, stu_01)

    # Mutate Q1 option A coordinate to x=850 (outside width=800)
    bad_map: dict[int, Any] = {}
    for q in golden_test_paper.questions:
        if q.bubble_coordinates:
            bad_map[q.id] = q.bubble_coordinates.model_dump()

    bad_map[1]["options"]["A"] = {"x": 850, "y": 255}

    result = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
        coordinate_map=bad_map,
    )

    assert result.status == ProofStatus.REVIEW_REQUIRED
    assert result.reason_code == ProofReasonCode.COORDINATE_OUT_OF_BOUNDS
    assert result.proof_image is None


@pytest.mark.unit
def test_fail_closed_coordinate_out_of_crop_bounds(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
) -> None:
    """Fail closed when a bubble coordinate is inside 800x600 but outside the (0, 230, 800, 600) crop box."""
    stu_01 = golden_submissions.submissions[0]
    source_img = create_synthetic_scan(golden_test_paper.questions, stu_01)

    # Mutate Q1 option A coordinate to y=100 (inside 800x600, but < crop_top=230)
    bad_map: dict[int, Any] = {}
    for q in golden_test_paper.questions:
        if q.bubble_coordinates:
            bad_map[q.id] = q.bubble_coordinates.model_dump()

    bad_map[1]["options"]["A"] = {"x": 65, "y": 100}

    result = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
        coordinate_map=bad_map,
        crop_box=DEFAULT_CROP_BOX,
    )

    assert result.status == ProofStatus.REVIEW_REQUIRED
    assert result.reason_code == ProofReasonCode.COORDINATE_OUT_OF_BOUNDS
    assert result.proof_image is None


@pytest.mark.unit
def test_fail_closed_dimension_mismatch_no_silent_rescaling(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
) -> None:
    """Fail closed on source image dimension mismatch (640x480 vs 800x600) — verify no silent rescaling."""
    stu_01 = golden_submissions.submissions[0]
    wrong_sized_img = Image.new("RGB", (640, 480), (255, 255, 255))

    result = generate_omr_proof(
        source_scan=wrong_sized_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
        expected_dimensions=(800, 600),
    )

    assert result.status == ProofStatus.REVIEW_REQUIRED
    assert result.reason_code == ProofReasonCode.DIMENSION_MISMATCH
    assert "Silent rescaling is forbidden" in (result.error_message or "")
    assert result.proof_image is None


@pytest.mark.unit
def test_fail_closed_low_alignment_confidence_exact_rational(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
) -> None:
    """Fail closed when alignment confidence is below threshold using exact Fraction comparison (ADR-0002)."""
    stu_01 = golden_submissions.submissions[0]
    source_img = create_synthetic_scan(golden_test_paper.questions, stu_01)

    # Confidence 90/100 is below default threshold 95/100
    result = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
        alignment_confidence=Fraction(90, 100),
        min_alignment_confidence=Fraction(95, 100),
    )

    assert result.status == ProofStatus.REVIEW_REQUIRED
    assert result.reason_code == ProofReasonCode.LOW_ALIGNMENT_CONFIDENCE
    assert result.proof_image is None

    # Decimal string confidence input
    result_dec = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
        alignment_confidence=Decimal("0.92"),
        min_alignment_confidence=Fraction(95, 100),
    )
    assert result_dec.status == ProofStatus.REVIEW_REQUIRED
    assert result_dec.reason_code == ProofReasonCode.LOW_ALIGNMENT_CONFIDENCE


# ------------------------------------------------------------------------------
# 4. ABSENT Student Handling
# ------------------------------------------------------------------------------


@pytest.mark.unit
def test_absent_student_returns_explicit_absent_no_proof(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
) -> None:
    """Verify ABSENT student returns ABSENT_NO_PROOF status with no generated image and no replacement sheet."""
    # Find an ABSENT student in golden fixture
    absent_sub = next(s for s in golden_submissions.submissions if s.status == AttendanceStatus.ABSENT)
    assert absent_sub.status == AttendanceStatus.ABSENT

    result = generate_omr_proof(
        source_scan=None,  # Absent student has no scan
        submission=absent_sub,
        answer_key=golden_test_paper.questions,
    )

    assert result.status == ProofStatus.ABSENT_NO_PROOF
    assert result.reason_code == ProofReasonCode.STUDENT_ABSENT
    assert result.proof_image is None
    assert result.proof_bytes is None
    assert not result.is_success


# ------------------------------------------------------------------------------
# 5. Source Immutability & Signature Integrity
# ------------------------------------------------------------------------------


@pytest.mark.unit
def test_source_immutability_disk_and_memory(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
    tmp_path: Path,
) -> None:
    """Verify source file bytes and in-memory pixel buffer remain 100% unchanged before and after rendering."""
    stu_01 = golden_submissions.submissions[0]
    source_img = create_synthetic_scan(golden_test_paper.questions, stu_01)

    # 1. Test Disk Immutability
    scan_file = tmp_path / "test_scan_stu_01.png"
    source_img.save(scan_file, format="PNG")
    original_bytes = scan_file.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()

    result_disk = generate_omr_proof(
        source_scan=scan_file,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
    )
    assert result_disk.status == ProofStatus.SUCCESS

    after_bytes = scan_file.read_bytes()
    after_sha256 = hashlib.sha256(after_bytes).hexdigest()
    assert original_bytes == after_bytes, "Source file bytes on disk were mutated!"
    assert original_sha256 == after_sha256, "Source file SHA-256 on disk changed!"

    # 2. Test In-Memory PIL Object Immutability
    pil_bytes_before = source_img.tobytes()
    result_mem = generate_omr_proof(
        source_scan=source_img,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
    )
    assert result_mem.status == ProofStatus.SUCCESS
    pil_bytes_after = source_img.tobytes()
    assert pil_bytes_before == pil_bytes_after, "Input PIL Image pixel buffer was mutated in place!"


@pytest.mark.unit
def test_signature_integrity_preservation_and_no_synthetic_generation(
    golden_test_paper: TestPaper,
    golden_submissions: OMRSubmissionsBatch,
) -> None:
    """
    Assert signature region pixels in the source scan are preserved byte-for-byte in output,
    and verify no synthetic signatures are ever drawn in production code.
    """
    stu_01 = golden_submissions.submissions[0]

    # Source signature box inside crop region:
    # Source: (620, 520, 750, 570) -> Cropped: (620, 520-230, 750, 570-230) = (620, 290, 750, 340)
    sig_box_source = (620, 520, 750, 570)
    sig_box_crop = (620, 290, 750, 340)

    # 1. Scan with real/existing signature pattern
    signed_scan = create_synthetic_scan(
        golden_test_paper.questions,
        stu_01,
        include_signature=True,
        signature_box=sig_box_source,
    )

    result_signed = generate_omr_proof(
        source_scan=signed_scan,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
    )
    assert result_signed.status == ProofStatus.SUCCESS
    proof_signed = result_signed.proof_image
    assert proof_signed is not None

    # Crop signature region from both and compare pixel bytes
    source_sig_crop = signed_scan.crop(sig_box_source)
    proof_sig_crop = proof_signed.crop(sig_box_crop)
    assert (
        source_sig_crop.tobytes() == proof_sig_crop.tobytes()
    ), "Signature region pixels in cropped proof strip must match source scan byte-for-byte!"

    # 2. Blank scan (no signature) — verify NO signature is synthetically generated
    unsigned_scan = create_synthetic_scan(
        golden_test_paper.questions,
        stu_01,
        include_signature=False,
    )

    result_unsigned = generate_omr_proof(
        source_scan=unsigned_scan,
        submission=stu_01,
        answer_key=golden_test_paper.questions,
    )
    assert result_unsigned.status == ProofStatus.SUCCESS
    proof_unsigned = result_unsigned.proof_image
    assert proof_unsigned is not None

    proof_unsigned_sig_crop = proof_unsigned.crop(sig_box_crop)
    # Entire unsigned signature box must remain pure white (255)
    byte_values = set(proof_unsigned_sig_crop.tobytes())
    assert byte_values == {255}, "Synthetic signature was unexpectedly generated in production path!"
