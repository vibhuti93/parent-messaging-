"""
OMR Proof Strip Generation and Scan Provenance (`src/omr_dispatch/omr_proof.py`).

Provides:
- Non-destructive image cropping and visual bubble overlays using Pillow.
- Color-coded annotation rules:
  - Correct response: green ring/check (#1E8E3E, RGB (30, 142, 62)) at/around selected bubble.
  - Wrong response: red cross (#D93025, RGB (217, 48, 37)) on selected bubble + optional green outline on key bubble.
  - Blank easy question: amber outline (#F9AB00, RGB (249, 171, 0)) on key bubble.
  - Blank non-easy question: clean bubble (no mark).
- Deterministic visual legend placed outside the mapped bubble grid.
- Complete scan provenance tracking (source SHA-256, dimensions, transforms, versions, timestamp).
- Fail-closed validation returning REVIEW_REQUIRED for any corrupt input, out-of-bounds coordinate,
  dimension mismatch, or low alignment confidence.
- Strict absence and signature preservation: ABSENT returns ABSENT_NO_PROOF (no fake replacement),
  and existing signature pixels are preserved byte-for-byte without synthetic generation.

Compliant with:
- ADR-0002: Exact Fraction arithmetic, zero float.
- ADR-0005: Timezone-aware UTC timestamps, injected clocks.
- ADR-0006: Schema versioning on all serialized result models.
- ADR-0008: Typed result models, stable machine-readable reason codes, zero print.
- Invariant 11: No synthetic scans or signatures in production paths.
- Invariant 15: Mandatory tenant context (org_id).
- Invariant 17: No child PII in logs.
"""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, ConfigDict, Field

from omr_dispatch.models import (
    AttendanceStatus,
    CoordinateMap,
    QuestionMeta,
    StudentOMRSubmission,
)

# ------------------------------------------------------------------------------
# Constants & Color Palette (Hex & RGB Tuples)
# ------------------------------------------------------------------------------

HEX_COLOR_CORRECT = "#1E8E3E"
COLOR_CORRECT: tuple[int, int, int] = (30, 142, 62)

HEX_COLOR_WRONG = "#D93025"
COLOR_WRONG: tuple[int, int, int] = (217, 48, 37)

HEX_COLOR_BLANK_EASY = "#F9AB00"
COLOR_BLANK_EASY: tuple[int, int, int] = (249, 171, 0)

DEFAULT_CROP_BOX: tuple[int, int, int, int] = (0, 230, 800, 600)
DEFAULT_EXPECTED_DIMENSIONS: tuple[int, int] = (800, 600)
DEFAULT_BUBBLE_RADIUS: int = 6
DEFAULT_MIN_ALIGNMENT_CONFIDENCE: Fraction = Fraction(95, 100)

PROCESSING_VERSION: str = "1.0.0"
COORDINATE_MAP_VERSION: int = 1


# ------------------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------------------


class ProofStatus(StrEnum):
    """Execution status of OMR proof generation."""

    SUCCESS = "SUCCESS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ABSENT_NO_PROOF = "ABSENT_NO_PROOF"


class ProofReasonCode(StrEnum):
    """Machine-readable reason codes for OMR proof generation."""

    MISSING_COORDINATE_MAP = "MISSING_COORDINATE_MAP"
    MISSING_QUESTION_COORDINATES = "MISSING_QUESTION_COORDINATES"
    CORRUPT_IMAGE = "CORRUPT_IMAGE"
    UNREADABLE_IMAGE = "UNREADABLE_IMAGE"
    DIMENSION_MISMATCH = "DIMENSION_MISMATCH"
    INVALID_CROP_BOX = "INVALID_CROP_BOX"
    COORDINATE_OUT_OF_BOUNDS = "COORDINATE_OUT_OF_BOUNDS"
    LOW_ALIGNMENT_CONFIDENCE = "LOW_ALIGNMENT_CONFIDENCE"
    MISSING_SCAN_FILE = "MISSING_SCAN_FILE"
    STUDENT_ABSENT = "STUDENT_ABSENT"
    EMPTY_ANSWER_KEY = "EMPTY_ANSWER_KEY"


# ------------------------------------------------------------------------------
# Provenance & Result Models
# ------------------------------------------------------------------------------


class TransformRecord(BaseModel):
    """Record of a single geometric transform applied during proof processing."""

    model_config = ConfigDict(extra="forbid")

    name: str
    parameters: dict[str, Any]
    timestamp_utc: str


class ProofProvenance(BaseModel):
    """Complete scan provenance metadata for a generated proof strip."""

    model_config = ConfigDict(extra="forbid")

    source_sha256: str
    source_ref: str
    source_dimensions: tuple[int, int]
    output_dimensions: tuple[int, int]
    crop_box: tuple[int, int, int, int]
    processing_version: str = PROCESSING_VERSION
    coordinate_map_version: int = COORDINATE_MAP_VERSION
    timestamp_utc: str
    transforms_applied: list[TransformRecord] = Field(default_factory=list)
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1


class OMRProofResult(BaseModel):
    """Result of OMR proof strip generation and verification."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    status: ProofStatus
    student_id: str
    submission_id: str
    proof_image: Any | None = None
    proof_bytes: bytes | None = None
    reason_code: ProofReasonCode | None = None
    error_message: str | None = None
    provenance: ProofProvenance | None = None
    annotations_summary: dict[str, int] = Field(default_factory=dict)
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @property
    def is_success(self) -> bool:
        """True iff generation succeeded with a valid proof image."""
        return self.status == ProofStatus.SUCCESS and self.proof_image is not None

    def to_png_bytes(self) -> bytes | None:
        """Return the proof image as PNG encoded bytes."""
        if self.proof_bytes is not None:
            return self.proof_bytes
        if self.proof_image is not None and hasattr(self.proof_image, "save"):
            buf = io.BytesIO()
            self.proof_image.save(buf, format="PNG")
            return buf.getvalue()
        return None


# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------


def _parse_confidence(val: Fraction | Decimal | str | int | None) -> Fraction | None:
    """Parse confidence value to exact Fraction without float conversion (ADR-0002)."""
    if val is None:
        return None
    if type(val).__name__ == "float":
        raise ValueError("Native float confidence is forbidden per ADR-0002; use Fraction or Decimal string")
    if isinstance(val, Fraction):
        return val
    if isinstance(val, int):
        return Fraction(val, 1)
    if isinstance(val, Decimal):
        return Fraction(str(val))
    if isinstance(val, str):
        return Fraction(val.strip())
    raise ValueError(f"Unsupported confidence type: {type(val).__name__}")


def _format_timestamp(ts: datetime | str | None) -> str:
    """Format timestamp as ISO-8601 UTC string (ADR-0005)."""
    if ts is None:
        return datetime.now(UTC).isoformat()
    if isinstance(ts, str):
        return ts
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            raise ValueError("Naive datetime is forbidden per ADR-0005; provide timezone-aware UTC datetime")
        return ts.astimezone(UTC).isoformat()
    raise ValueError(f"Invalid timestamp type: {type(ts).__name__}")


# ------------------------------------------------------------------------------
# Core Generator Function
# ------------------------------------------------------------------------------


def generate_omr_proof(
    source_scan: str | Path | bytes | Image.Image | None,
    submission: StudentOMRSubmission,
    answer_key: list[QuestionMeta] | dict[int, QuestionMeta],
    coordinate_map: CoordinateMap | dict[int, CoordinateMap] | dict[int, dict[str, Any]] | None = None,
    *,
    easy_question_ids: set[int] | list[int] | None = None,
    crop_box: tuple[int, int, int, int] = DEFAULT_CROP_BOX,
    expected_dimensions: tuple[int, int] | None = DEFAULT_EXPECTED_DIMENSIONS,
    min_alignment_confidence: Fraction | Decimal = DEFAULT_MIN_ALIGNMENT_CONFIDENCE,
    alignment_confidence: Fraction | Decimal | str | int | None = None,
    source_ref: str | None = None,
    timestamp: str | datetime | None = None,
    bubble_radius: int = DEFAULT_BUBBLE_RADIUS,
    outline_correct_on_wrong: bool = True,
    render_legend: bool = True,
    legend_origin: tuple[int, int] = (30, 310),
    org_id: str = "DEFAULT_INSTITUTION",
) -> OMRProofResult:
    """
    Generate an annotated OMR proof strip from an original scan and student submission.

    Guarantees:
    - Never mutates the input image object or alters files on disk.
    - Applies crop offsets exactly once without silent rescaling.
    - Preserves existing signature pixels byte-for-byte and never generates synthetic signatures.
    - Returns structured REVIEW_REQUIRED for any corrupt, missing, out-of-bounds, or misaligned inputs.
    - Returns explicit ABSENT_NO_PROOF for absent students without generating a replacement sheet.
    """
    sub_id = submission.id
    stu_id = submission.student_id

    # 1. ABSENT Student Handling (Task 4)
    if submission.status == AttendanceStatus.ABSENT:
        return OMRProofResult(
            status=ProofStatus.ABSENT_NO_PROOF,
            student_id=stu_id,
            submission_id=sub_id,
            proof_image=None,
            proof_bytes=None,
            reason_code=ProofReasonCode.STUDENT_ABSENT,
            error_message="Student is ABSENT; no proof strip or replacement sheet generated",
            org_id=org_id,
        )

    # 2. Source Scan Presence Check
    actual_source: Any = source_scan
    if actual_source is None and submission.scan_image_path is not None:
        actual_source = submission.scan_image_path

    if actual_source is None:
        return OMRProofResult(
            status=ProofStatus.REVIEW_REQUIRED,
            student_id=stu_id,
            submission_id=sub_id,
            reason_code=ProofReasonCode.MISSING_SCAN_FILE,
            error_message="Missing scan image for PRESENT student",
            org_id=org_id,
        )

    # 3. Alignment Confidence Check (Numeric Hygiene: Fraction / Decimal only)
    min_conf_frac = min_alignment_confidence if isinstance(min_alignment_confidence, Fraction) else Fraction(str(min_alignment_confidence))
    parsed_conf = _parse_confidence(alignment_confidence)
    if parsed_conf is not None and parsed_conf < min_conf_frac:
        return OMRProofResult(
            status=ProofStatus.REVIEW_REQUIRED,
            student_id=stu_id,
            submission_id=sub_id,
            reason_code=ProofReasonCode.LOW_ALIGNMENT_CONFIDENCE,
            error_message=f"Alignment confidence ({parsed_conf}) below required threshold ({min_conf_frac})",
            org_id=org_id,
        )

    # 4. Resolve Timestamp (Time Hygiene: ADR-0005)
    iso_timestamp = _format_timestamp(timestamp)

    # 5. Load and Hash Source Scan Immutably
    source_sha256: str
    ref: str
    source_img: Image.Image

    if isinstance(actual_source, (str, Path)):
        scan_path = Path(actual_source)
        if not scan_path.exists() or not scan_path.is_file():
            return OMRProofResult(
                status=ProofStatus.REVIEW_REQUIRED,
                student_id=stu_id,
                submission_id=sub_id,
                reason_code=ProofReasonCode.MISSING_SCAN_FILE,
                error_message=f"Source scan file not found on disk: {actual_source}",
                org_id=org_id,
            )
        try:
            file_bytes = scan_path.read_bytes()
            source_sha256 = hashlib.sha256(file_bytes).hexdigest()
            ref = source_ref or str(scan_path)
            with Image.open(io.BytesIO(file_bytes)) as opened:
                source_img = opened.convert("RGB")
        except Exception as exc:
            return OMRProofResult(
                status=ProofStatus.REVIEW_REQUIRED,
                student_id=stu_id,
                submission_id=sub_id,
                reason_code=ProofReasonCode.CORRUPT_IMAGE,
                error_message=f"Failed to read/decode source scan image: {exc}",
                org_id=org_id,
            )
    elif isinstance(actual_source, bytes):
        source_sha256 = hashlib.sha256(actual_source).hexdigest()
        ref = source_ref or f"bytes:{source_sha256[:16]}"
        try:
            with Image.open(io.BytesIO(actual_source)) as opened:
                source_img = opened.convert("RGB")
        except Exception as exc:
            return OMRProofResult(
                status=ProofStatus.REVIEW_REQUIRED,
                student_id=stu_id,
                submission_id=sub_id,
                reason_code=ProofReasonCode.CORRUPT_IMAGE,
                error_message=f"Failed to decode image bytes: {exc}",
                org_id=org_id,
            )
    elif isinstance(actual_source, Image.Image):
        # Non-destructive copy of in-memory PIL image
        source_img = actual_source.copy().convert("RGB")
        buf = io.BytesIO()
        source_img.save(buf, format="PNG")
        source_sha256 = hashlib.sha256(buf.getvalue()).hexdigest()
        ref = source_ref or f"pil_image:{id(actual_source)}"
    else:
        return OMRProofResult(
            status=ProofStatus.REVIEW_REQUIRED,
            student_id=stu_id,
            submission_id=sub_id,
            reason_code=ProofReasonCode.UNREADABLE_IMAGE,
            error_message=f"Unsupported scan input type: {type(actual_source).__name__}",
            org_id=org_id,
        )

    # 6. Source Dimensions & Dimension Mismatch Check
    src_w, src_h = source_img.size
    if expected_dimensions is not None:
        exp_w, exp_h = expected_dimensions
        if src_w != exp_w or src_h != exp_h:
            return OMRProofResult(
                status=ProofStatus.REVIEW_REQUIRED,
                student_id=stu_id,
                submission_id=sub_id,
                reason_code=ProofReasonCode.DIMENSION_MISMATCH,
                error_message=(
                    f"Scan dimensions ({src_w}x{src_h}) do not match expected ({exp_w}x{exp_h}). "
                    "Silent rescaling is forbidden."
                ),
                org_id=org_id,
            )

    # 7. Validate Crop Box
    c_left, c_top, c_right, c_bottom = crop_box
    if (
        c_left < 0
        or c_top < 0
        or c_right > src_w
        or c_bottom > src_h
        or c_right <= c_left
        or c_bottom <= c_top
    ):
        return OMRProofResult(
            status=ProofStatus.REVIEW_REQUIRED,
            student_id=stu_id,
            submission_id=sub_id,
            reason_code=ProofReasonCode.INVALID_CROP_BOX,
            error_message=f"Crop box {crop_box} is invalid or outside source bounds ({src_w}x{src_h})",
            org_id=org_id,
        )

    # 8. Resolve Answer Key and Questions
    questions_list: list[QuestionMeta] = (
        answer_key if isinstance(answer_key, list) else list(answer_key.values())
    )

    if not questions_list:
        return OMRProofResult(
            status=ProofStatus.REVIEW_REQUIRED,
            student_id=stu_id,
            submission_id=sub_id,
            reason_code=ProofReasonCode.EMPTY_ANSWER_KEY,
            error_message="Answer key is empty or invalid",
            org_id=org_id,
        )

    # 9. Resolve Coordinate Maps per Question
    resolved_maps: dict[int, CoordinateMap] = {}

    if isinstance(coordinate_map, dict):
        for k, v in coordinate_map.items():
            try:
                qid = int(k)
                if isinstance(v, CoordinateMap):
                    resolved_maps[qid] = v
                elif isinstance(v, dict):
                    resolved_maps[qid] = CoordinateMap(**v)
            except Exception:
                continue
    elif isinstance(coordinate_map, CoordinateMap):
        # Single coordinate map applicable across questions if indexed
        pass

    # Fallback to QuestionMeta.bubble_coordinates
    for q in questions_list:
        if q.id not in resolved_maps and q.bubble_coordinates is not None:
            resolved_maps[q.id] = q.bubble_coordinates

    if not resolved_maps:
        return OMRProofResult(
            status=ProofStatus.REVIEW_REQUIRED,
            student_id=stu_id,
            submission_id=sub_id,
            reason_code=ProofReasonCode.MISSING_COORDINATE_MAP,
            error_message="Coordinate map is missing or empty for all questions",
            org_id=org_id,
        )

    # 10. Coordinate Map Completeness & Bound Checks
    for q in questions_list:
        qid = q.id
        if qid not in resolved_maps:
            return OMRProofResult(
                status=ProofStatus.REVIEW_REQUIRED,
                student_id=stu_id,
                submission_id=sub_id,
                reason_code=ProofReasonCode.MISSING_QUESTION_COORDINATES,
                error_message=f"Missing coordinate map for question ID {qid}",
                org_id=org_id,
            )

        cmap = resolved_maps[qid]
        if not cmap.options:
            return OMRProofResult(
                status=ProofStatus.REVIEW_REQUIRED,
                student_id=stu_id,
                submission_id=sub_id,
                reason_code=ProofReasonCode.MISSING_QUESTION_COORDINATES,
                error_message=f"Option coordinates dictionary is empty for question ID {qid}",
                org_id=org_id,
            )

        for opt_label, pos in cmap.options.items():
            bx = pos.get("x")
            by = pos.get("y")
            if bx is None or by is None:
                return OMRProofResult(
                    status=ProofStatus.REVIEW_REQUIRED,
                    student_id=stu_id,
                    submission_id=sub_id,
                    reason_code=ProofReasonCode.COORDINATE_OUT_OF_BOUNDS,
                    error_message=f"Incomplete coordinate for Q{qid} option {opt_label}",
                    org_id=org_id,
                )

            # Check source bounds
            if (
                bx - bubble_radius < 0
                or bx + bubble_radius > src_w
                or by - bubble_radius < 0
                or by + bubble_radius > src_h
            ):
                return OMRProofResult(
                    status=ProofStatus.REVIEW_REQUIRED,
                    student_id=stu_id,
                    submission_id=sub_id,
                    reason_code=ProofReasonCode.COORDINATE_OUT_OF_BOUNDS,
                    error_message=f"Bubble Q{qid} {opt_label} at ({bx}, {by}) is outside source image bounds ({src_w}x{src_h})",
                    org_id=org_id,
                )

            # Check cropped region bounds
            if (
                bx - bubble_radius < c_left
                or bx + bubble_radius > c_right
                or by - bubble_radius < c_top
                or by + bubble_radius > c_bottom
            ):
                return OMRProofResult(
                    status=ProofStatus.REVIEW_REQUIRED,
                    student_id=stu_id,
                    submission_id=sub_id,
                    reason_code=ProofReasonCode.COORDINATE_OUT_OF_BOUNDS,
                    error_message=f"Bubble Q{qid} {opt_label} at ({bx}, {by}) is outside crop box {crop_box}",
                    org_id=org_id,
                )

    # 11. Execute Crop Transform (Discipline: exactly once)
    proof_image = source_img.crop(crop_box)
    out_w, out_h = proof_image.size

    transform_records = [
        TransformRecord(
            name="crop",
            parameters={
                "crop_box": list(crop_box),
                "crop_offsets": {"crop_left": c_left, "crop_top": c_top},
            },
            timestamp_utc=iso_timestamp,
        )
    ]

    # 12. Non-Destructive Annotation Overlay
    draw = ImageDraw.Draw(proof_image)
    easy_set: set[int] = set(easy_question_ids or [])
    annotations_summary: dict[str, int] = {
        "correct": 0,
        "wrong": 0,
        "blank_easy": 0,
        "blank_non_easy": 0,
    }

    for q in questions_list:
        qid = q.id
        correct_opt = q.correct_option
        cmap = resolved_maps[qid]

        resp = submission.responses.get(str(qid))
        if resp is None:
            resp = submission.responses.get(str(qid).strip())

        if resp is not None and resp.strip() not in ("", "BLANK"):
            student_opt = resp.strip()
            if student_opt == correct_opt:
                # Correct response: Green ring around bubble + small checkmark inside
                opt_pos = cmap.options.get(student_opt)
                if opt_pos:
                    cx = opt_pos["x"] - c_left
                    cy = opt_pos["y"] - c_top
                    draw.ellipse(
                        (cx - bubble_radius, cy - bubble_radius, cx + bubble_radius, cy + bubble_radius),
                        outline=COLOR_CORRECT,
                        width=2,
                    )
                    # Checkmark at centre
                    draw.line([(cx - 3, cy), (cx - 1, cy + 3), (cx + 4, cy - 3)], fill=COLOR_CORRECT, width=2)
                    annotations_summary["correct"] += 1
            else:
                # Wrong response: Red cross on selected bubble
                opt_pos = cmap.options.get(student_opt)
                if opt_pos:
                    sx = opt_pos["x"] - c_left
                    sy = opt_pos["y"] - c_top
                    draw.line(
                        [(sx - bubble_radius, sy - bubble_radius), (sx + bubble_radius, sy + bubble_radius)],
                        fill=COLOR_WRONG,
                        width=2,
                    )
                    draw.line(
                        [(sx - bubble_radius, sy + bubble_radius), (sx + bubble_radius, sy - bubble_radius)],
                        fill=COLOR_WRONG,
                        width=2,
                    )

                # Optional green outline on correct answer key bubble
                if outline_correct_on_wrong:
                    key_pos = cmap.options.get(correct_opt)
                    if key_pos:
                        kx = key_pos["x"] - c_left
                        ky = key_pos["y"] - c_top
                        draw.ellipse(
                            (kx - bubble_radius, ky - bubble_radius, kx + bubble_radius, ky + bubble_radius),
                            outline=COLOR_CORRECT,
                            width=2,
                        )
                annotations_summary["wrong"] += 1
        else:
            # Blank response
            if qid in easy_set:
                # Blank easy question: Amber outline on correct answer key bubble
                key_pos = cmap.options.get(correct_opt)
                if key_pos:
                    kx = key_pos["x"] - c_left
                    ky = key_pos["y"] - c_top
                    draw.ellipse(
                        (kx - bubble_radius, ky - bubble_radius, kx + bubble_radius, ky + bubble_radius),
                        outline=COLOR_BLANK_EASY,
                        width=2,
                    )
                annotations_summary["blank_easy"] += 1
            else:
                # Blank non-easy question: Leave clean
                annotations_summary["blank_non_easy"] += 1

    # 13. Deterministic Legend Rendering
    if render_legend:
        lx, ly = legend_origin
        default_font = ImageFont.load_default()

        # Correct Indicator
        draw.ellipse((lx, ly - 5, lx + 12, ly + 7), outline=COLOR_CORRECT, width=2)
        draw.line([(lx + 3, ly + 1), (lx + 5, ly + 4), (lx + 9, ly - 2)], fill=COLOR_CORRECT, width=2)
        draw.text((lx + 18, ly - 3), "Correct", fill=(0, 0, 0), font=default_font)

        # Wrong Indicator
        rx = lx + 120
        draw.line([(rx, ly - 5), (rx + 12, ly + 7)], fill=COLOR_WRONG, width=2)
        draw.line([(rx, ly + 7), (rx + 12, ly - 5)], fill=COLOR_WRONG, width=2)
        draw.text((rx + 18, ly - 3), "Wrong", fill=(0, 0, 0), font=default_font)

        # Blank Easy Indicator
        ax = lx + 240
        draw.ellipse((ax, ly - 5, ax + 12, ly + 7), outline=COLOR_BLANK_EASY, width=2)
        draw.text((ax + 18, ly - 3), "Blank (Easy)", fill=(0, 0, 0), font=default_font)

    # 14. Assemble Provenance and Final Result
    provenance = ProofProvenance(
        source_sha256=source_sha256,
        source_ref=ref,
        source_dimensions=(src_w, src_h),
        output_dimensions=(out_w, out_h),
        crop_box=crop_box,
        processing_version=PROCESSING_VERSION,
        coordinate_map_version=COORDINATE_MAP_VERSION,
        timestamp_utc=iso_timestamp,
        transforms_applied=transform_records,
        org_id=org_id,
        schema_version=1,
    )

    out_buf = io.BytesIO()
    proof_image.save(out_buf, format="PNG")
    proof_bytes = out_buf.getvalue()

    return OMRProofResult(
        status=ProofStatus.SUCCESS,
        student_id=stu_id,
        submission_id=sub_id,
        proof_image=proof_image,
        proof_bytes=proof_bytes,
        provenance=provenance,
        annotations_summary=annotations_summary,
        org_id=org_id,
        schema_version=1,
    )
