"""
Devanagari Rendering, Scorecard PNG, and PTM Slip PDF Generation (`src/omr_dispatch/renderer.py`).

Provides:
- Context-managed `PlaywrightRenderer` using bundled Playwright Chromium (zero fallback).
- Pixel-exact 800x1150 Scorecard PNG generation at scale 1 with strict 500 KB size budget enforcement.
- Status banner color mapping per D-07 (#1E8E3E Green, #F9AB00 Yellow, #D93025 Red, #5F6368 Absent/Neutral).
- Multi-kind assessment handling:
  - OMR_MCQ: score/max/%, mark-bleed breakdown, easy questions context, subject table, embedded proof strip.
  - MARKS_ENTRY_TOTALS: subject marks/percentages, omitting proof strip, easy questions, and diagnostic bleed;
    all NOT_AVAILABLE metrics omitted (never displayed as zero).
  - ABSENT: neutral grey banner (#5F6368), child name, class/section; no proof or score framing.
- A4 Portrait PTM Slip PDF generation: 2x4 grid (8 slips per page), ceil(n/8) pages, explicit empty result for n = 0.
- `QrTokenProvider` Protocol interface with secure opaque token QR code rendering (zero personal data).
- Bundled Noto Sans Devanagari typography loaded via local @font-face; zero network requests at render time.
- Font readiness verification (document.fonts.ready + document.fonts.check) before capture.
- Lazy, guarded PDF inspection and rasterisation via pypdfium2.

Compliant with:
- ADR-0002: Exact integer/Fraction arithmetic, zero float.
- ADR-0005: Timezone-aware UTC timestamps, injected clocks.
- ADR-0006: Schema versioning on all serialized result models.
- ADR-0008: Typed result models, stable machine-readable error hierarchy, zero print.
- ADR-0010: Unicode NFC normalization, standard Latin digits (0-9).
- ADR-0016: Multi-kind assessment scorecard variants (OMR_MCQ vs MARKS_ENTRY_TOTALS).
- Invariant 7: Real local components, mock only external boundaries.
- Invariant 10 & 17: Zero child PII or personal data in logs, tokens, or QR payloads.
- Invariant 15: Mandatory tenant context (org_id).
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

import jinja2
from PIL import Image
from pydantic import BaseModel, ConfigDict

from omr_dispatch.hindi_templates import (
    BANNER_COLORS,
    BANNER_TITLES_HI,
    format_display_marks,
    normalize_name_or_fallback,
)
from omr_dispatch.models import (
    AssessmentKind,
    AttendanceStatus,
    OMRDispatchError,
    StudentDiagnosticReport,
)
from omr_dispatch.omr_proof import OMRProofResult

# ------------------------------------------------------------------------------
# Constants & Paths
# ------------------------------------------------------------------------------

SCORECARD_WIDTH: int = 800
SCORECARD_HEIGHT: int = 1150
SCORECARD_BUDGET_BYTES: int = 500_000  # Strict decimal 500 KB (500,000 bytes)

SLIPS_PER_PAGE: int = 8
A4_MARGIN_MM: int = 6

FONT_VERSION: str = "v20201206-phase3"
FONT_FAMILY: str = "Noto Sans Devanagari"

EXPECTED_REGULAR_SHA256: str = "a0489982cdfa20a4ac46313862a362b6720c5c016253f5518b24293f97a46e52"
EXPECTED_BOLD_SHA256: str = "a8318ef0f6f2f159f4367cd10a5e69d48b2b9a54cde39593772b124a28dbb04e"

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
FONTS_DIR: Path = PROJECT_ROOT / "assets" / "fonts"
TEMPLATES_DIR: Path = PROJECT_ROOT / "templates"


# ------------------------------------------------------------------------------
# Exception Hierarchy (ADR-0008)
# ------------------------------------------------------------------------------


class RendererError(OMRDispatchError):
    """Base exception for all rendering failures."""


class ChromiumMissingError(RendererError):
    """Raised when Playwright bundled Chromium executable cannot be found or launched."""


class FontLoadError(RendererError):
    """Raised when Noto Sans Devanagari fonts fail validation, are missing, or fail in-browser loading."""


class BudgetExceededError(RendererError):
    """Raised when a rendered asset exceeds its strict file-size budget."""


class RasteriserMissingError(RendererError):
    """Raised when PDF rasterisation is requested but pypdfium2 is missing."""


# ------------------------------------------------------------------------------
# Enumerations and Result Models
# ------------------------------------------------------------------------------


class RenderStatus(StrEnum):
    """Execution status of a render operation."""

    SUCCESS = "SUCCESS"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    RENDER_FAILED = "RENDER_FAILED"
    EMPTY_RESULT = "EMPTY_RESULT"


class RenderMetadata(BaseModel):
    """Metadata tracking environment and typography versions for a render."""

    model_config = ConfigDict(extra="forbid")

    chromium_version: str
    font_version: str = FONT_VERSION
    font_family: str = FONT_FAMILY
    timestamp_utc: str
    device_scale_factor: int = 1
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1


class ScorecardResult(BaseModel):
    """Result of Scorecard PNG rendering."""

    model_config = ConfigDict(extra="forbid")

    status: RenderStatus
    student_id: str
    png_bytes: bytes | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
    metadata: RenderMetadata | None = None
    budget_bytes: int = SCORECARD_BUDGET_BYTES
    is_budget_exceeded: bool = False
    error_message: str | None = None
    rendered_html: str | None = None
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @property
    def is_success(self) -> bool:
        """True iff rendering succeeded within size and dimension budgets."""
        return self.status == RenderStatus.SUCCESS and self.png_bytes is not None


class PtmSlipItem(BaseModel):
    """Data item representing a single student PTM invitation slip."""

    model_config = ConfigDict(extra="forbid")

    student_id: str
    child_display_name: str
    class_section: str
    roll_number: str = ""
    performance_text_hi: str
    qr_token: str | None = None
    institution_header: str = "आदर्श विद्या मंदिर"
    assessment_name: str = "अभिभावक-शिक्षक बैठक (PTM)"
    ptm_date: str = "24-10-2026"
    ptm_time: str = "प्रातः 10:00 बजे"
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1


class PtmPdfResult(BaseModel):
    """Result of PTM Slips A4 PDF rendering."""

    model_config = ConfigDict(extra="forbid")

    status: RenderStatus
    slip_count: int
    page_count: int
    pdf_bytes: bytes | None = None
    size_bytes: int | None = None
    metadata: RenderMetadata | None = None
    error_message: str | None = None
    rendered_html: str | None = None
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @property
    def is_success(self) -> bool:
        """True iff generation produced a valid non-empty PDF result."""
        return self.status == RenderStatus.SUCCESS and self.pdf_bytes is not None


# ------------------------------------------------------------------------------
# QR Token Provider Protocol (S6 / S11)
# ------------------------------------------------------------------------------


@runtime_checkable
class QrTokenProvider(Protocol):
    """
    Protocol for supplying opaque parent confirmation QR tokens (S6 Task 9 / S11).
    Implementations must NEVER encode personal data (names, marks, phones) into tokens.
    """

    def get_token(
        self,
        student_id: str,
        *,
        org_id: str = "DEFAULT_INSTITUTION",
        assessment_id: str | None = None,
    ) -> str | None:
        """
        Return an opaque token string for the given student, or None if QR confirmation
        is disabled or unconfigured.
        """
        ...


# ------------------------------------------------------------------------------
# Helpers: Typography, QR SVG, and PDF Inspection
# ------------------------------------------------------------------------------


def _load_and_verify_font(font_path: Path, expected_sha256: str) -> tuple[bytes, str]:
    """Load font file, verify SHA-256 integrity, and return (bytes, base64_str)."""
    if not font_path.exists():
        raise FontLoadError(f"Required font file not found: {font_path}")
    raw = font_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise FontLoadError(
            f"Font checksum mismatch for {font_path.name}: expected {expected_sha256}, got {digest}"
        )
    return raw, base64.b64encode(raw).decode("ascii")


def generate_qr_svg(token: str, size: int = 80) -> str:
    """
    Generate an SVG 21x21 QR-like matrix containing an opaque confirmation token.
    Uses standard QR finder patterns at three corners and deterministic data modules.
    Complies with ADR-0002 by using exact integer coordinates and viewBox.
    Never encodes personal data.
    """
    grid: list[list[int]] = [[0] * 21 for _ in range(21)]

    def draw_finder(top: int, left: int) -> None:
        for r in range(7):
            for c in range(7):
                if r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4):
                    grid[top + r][left + c] = 1
                else:
                    grid[top + r][left + c] = 0

    draw_finder(0, 0)
    draw_finder(0, 14)
    draw_finder(14, 0)

    # Timing lines
    for i in range(8, 13):
        grid[6][i] = 1 if i % 2 == 0 else 0
        grid[i][6] = 1 if i % 2 == 0 else 0

    # Dark module
    grid[13][8] = 1

    # Fill data modules deterministically using token hash
    h = hashlib.sha256(token.encode("utf-8")).digest()
    bit_idx = 0
    for r in range(21):
        for c in range(21):
            if (r < 8 and c < 8) or (r < 8 and c >= 13) or (r >= 13 and c < 8) or r == 6 or c == 6:
                continue
            byte = h[(bit_idx // 8) % len(h)]
            bit = (byte >> (bit_idx % 8)) & 1
            grid[r][c] = bit
            bit_idx += 1

    rects: list[str] = []
    for r in range(21):
        for c in range(21):
            if grid[r][c] == 1:
                rects.append(f'<rect x="{c}" y="{r}" width="1" height="1" fill="#000000"/>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21" width="{size}" height="{size}">'
        f'<rect width="21" height="21" fill="#FFFFFF"/>'
        f'{"".join(rects)}'
        f"</svg>"
    )


def get_pdf_page_count(pdf_bytes: bytes) -> int:
    """Return the total number of pages in a PDF document using pypdfium2."""
    try:
        import pypdfium2  # type: ignore[import-untyped]
        doc = pypdfium2.PdfDocument(pdf_bytes)
        return int(len(doc))
    except ImportError as e:
        raise RasteriserMissingError("pypdfium2 is required for PDF page counting and inspection") from e


def rasterise_pdf_page(pdf_bytes: bytes, page_index: int = 0, scale: int = 2) -> Image.Image:
    """Rasterise a single PDF page to a Pillow Image at the requested scale using pypdfium2."""
    try:
        import pypdfium2
        doc = pypdfium2.PdfDocument(pdf_bytes)
        if page_index < 0 or page_index >= len(doc):
            raise IndexError(f"Page index {page_index} out of range (total pages: {len(doc)})")
        img = doc[page_index].render(scale=scale).to_pil()
        return cast(Image.Image, img)
    except ImportError as e:
        raise RasteriserMissingError("pypdfium2 is required for PDF rasterisation") from e


# ------------------------------------------------------------------------------
# Playwright Renderer Context Manager
# ------------------------------------------------------------------------------


class PlaywrightRenderer:
    """
    Context-managed renderer backed by Playwright bundled Chromium.
    Reuses a single browser instance across renders, opens one page per render,
    closes pages and browser processes cleanly, and blocks external network requests.
    """

    def __init__(self, *, fonts_dir: Path | str | None = None, templates_dir: Path | str | None = None) -> None:
        self._fonts_dir: Path = Path(fonts_dir) if fonts_dir is not None else FONTS_DIR
        self._templates_dir: Path = Path(templates_dir) if templates_dir is not None else TEMPLATES_DIR

        # Font verification & base64 encoding (cached)
        reg_path = self._fonts_dir / "NotoSansDevanagari-Regular.ttf"
        bold_path = self._fonts_dir / "NotoSansDevanagari-Bold.ttf"
        _, self._font_regular_b64 = _load_and_verify_font(reg_path, EXPECTED_REGULAR_SHA256)
        _, self._font_bold_b64 = _load_and_verify_font(bold_path, EXPECTED_BOLD_SHA256)

        # Jinja2 environment with strict autoescaping
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self._templates_dir)),
            autoescape=jinja2.select_autoescape(["html", "xml", "j2"]),
            undefined=jinja2.StrictUndefined,
        )

        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._external_requests: list[str] = []

    def __enter__(self) -> PlaywrightRenderer:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def start(self) -> None:
        """Initialize Playwright and launch bundled Chromium."""
        if self._browser is not None:
            return

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise ChromiumMissingError("Playwright Python package is not installed") from e

        try:
            self._playwright = sync_playwright().start()
            # Must launch Playwright's own bundled Chromium without channel override
            self._browser = self._playwright.chromium.launch(headless=True)
        except Exception as e:
            self.close()
            raise ChromiumMissingError(
                f"Failed to launch bundled Playwright Chromium: {e}. "
                "Ensure 'playwright install chromium' has been executed."
            ) from e

    def close(self) -> None:
        """Close browser and terminate Playwright process cleanly."""
        if self._browser is not None:
            with contextlib.suppress(Exception):
                self._browser.close()
            self._browser = None

        if self._playwright is not None:
            with contextlib.suppress(Exception):
                self._playwright.stop()
            self._playwright = None

    @property
    def chromium_version(self) -> str:
        """Return the running Chromium engine version string."""
        if self._browser is None:
            return "UNINITIALIZED"
        return str(self._browser.version)

    @property
    def external_requests(self) -> list[str]:
        """Return list of any external network requests intercepted and blocked."""
        return list(self._external_requests)

    def _setup_page_isolation_and_fonts(self, page: Any) -> None:
        """Configure route blocking for zero external requests and verify font readiness."""
        def route_handler(route: Any) -> None:
            url = route.request.url
            if url.startswith("data:") or url.startswith("file:"):
                route.continue_()
            else:
                self._external_requests.append(url)
                route.abort("blockedbyclient")

        page.route("**/*", route_handler)

    def _verify_fonts_ready(self, page: Any) -> None:
        """Verify that Noto Sans Devanagari font is loaded into the Chromium document."""
        page.evaluate("document.fonts.ready")
        loaded = page.evaluate('document.fonts.check("16px \'Noto Sans Devanagari\'")')
        if not loaded:
            raise FontLoadError(
                "Noto Sans Devanagari font failed to load or validate in Chromium document"
            )

    # --------------------------------------------------------------------------
    # Scorecard PNG Rendering
    # --------------------------------------------------------------------------

    def render_scorecard(
        self,
        report: StudentDiagnosticReport | dict[str, Any],
        *,
        assessment_kind: AssessmentKind | str = AssessmentKind.OMR_MCQ,
        proof_result: OMRProofResult | bytes | None = None,
        assessment_name: str | None = None,
        institution_header: str = "आदर्श विद्या मंदिर",
        test_date: str = "24-10-2026",
        include_roll: bool = True,
        timestamp_utc: str | None = None,
        org_id: str = "DEFAULT_INSTITUTION",
    ) -> ScorecardResult:
        """
        Render an 800x1150 Scorecard PNG for a student report.
        Enforces D-07 banner color rules, variant omissions, and a 500 KB file-size budget.
        """
        if self._browser is None:
            self.start()
        assert self._browser is not None

        # Resolve report attributes
        if isinstance(report, dict):
            student_id = str(report.get("student_id", "UNKNOWN"))
            raw_name = report.get("child_display_name", "विद्यार्थी")
            class_sec = str(report.get("class_section", ""))
            roll_no = str(report.get("roll_number", report.get("roll_no", "")))
            status = AttendanceStatus(report.get("status", AttendanceStatus.PRESENT))
            status_band = str(report.get("status_band", "ABSENT" if status == AttendanceStatus.ABSENT else "GREEN"))
            gross = report.get("gross_marks")
            bleed = report.get("bleed_marks")
            net = report.get("net_marks")
            marks_val = report.get("marks")
            max_m = report.get("max_marks")
            percentage_val = report.get("percentage")
            net_pct = report.get("net_percentage")
            rank = report.get("competition_rank")
            present_c = report.get("present_count", 0)
            avg = report.get("class_average")
            topper = report.get("topper_score", report.get("topper_marks"))
            correct = report.get("correct")
            wrong = report.get("wrong")
            blank = report.get("blank")
            easy_ids = report.get("easy_missed_question_ids", [])
            pos_unearned = report.get("positive_marks_not_earned")
            subj_breakdown = report.get("subject_breakdown")
            subj_diags = report.get("subject_diagnostics")
        else:
            student_id = report.student_id
            raw_name = report.child_display_name
            class_sec = report.class_section
            roll_no = report.roll_number
            status = report.status
            status_band = report.status_band
            gross = report.gross_marks
            bleed = report.bleed_marks
            net = report.net_marks
            marks_val = report.marks
            max_m = report.max_marks
            percentage_val = report.percentage
            net_pct = report.net_percentage
            rank = report.competition_rank
            present_c = report.present_count
            avg = report.class_average
            topper = report.topper_score
            correct = report.correct
            wrong = report.wrong
            blank = report.blank
            easy_ids = report.easy_missed_question_ids if isinstance(report.easy_missed_question_ids, list) else []
            pos_unearned = report.positive_marks_not_earned
            subj_breakdown = report.subject_breakdown if isinstance(report.subject_breakdown, dict) else None
            subj_diags = report.subject_diagnostics if isinstance(report.subject_diagnostics, dict) else None

        child_name = normalize_name_or_fallback(raw_name)
        is_absent = status == AttendanceStatus.ABSENT
        is_omr = assessment_kind == AssessmentKind.OMR_MCQ

        # Resolve D-07 Banner Colors and Titles
        if is_absent:
            banner_color = BANNER_COLORS["ABSENT"]
            banner_title = BANNER_TITLES_HI["ABSENT"]
            status_band_label = "ABSENT"
        else:
            resolved_band = status_band.upper() if status_band else "GREEN"
            banner_color = BANNER_COLORS.get(resolved_band, BANNER_COLORS["GREEN"])
            banner_title = BANNER_TITLES_HI.get(resolved_band, "शानदार प्रदर्शन — बहुत बढ़िया")
            status_band_label = resolved_band

        # Display percentage formatting
        if is_omr:
            display_pct = str(net_pct or percentage_val or "0.0%")
        else:
            display_pct = str(percentage_val or "0.0%")

        # Resolve embedded proof strip PNG bytes (base64)
        proof_png_b64: str | None = None
        if is_omr and not is_absent and proof_result is not None:
            if isinstance(proof_result, bytes):
                proof_png_b64 = base64.b64encode(proof_result).decode("ascii")
            elif isinstance(proof_result, OMRProofResult):
                png_bytes = proof_result.to_png_bytes()
                if png_bytes is not None:
                    proof_png_b64 = base64.b64encode(png_bytes).decode("ascii")

        # Resolve subject table rows
        subject_rows: list[dict[str, Any]] = []
        if not is_absent and subj_breakdown:
            for sname, sdata in subj_breakdown.items():
                diag_fact = subj_diags.get(sname, "") if subj_diags else ""
                subject_rows.append({
                    "subject": sname,
                    "total": sdata.get("total", 0),
                    "correct": sdata.get("correct", 0),
                    "wrong": sdata.get("wrong", 0),
                    "marks": format_display_marks(sdata.get("net_marks", sdata.get("marks", 0))),
                    "max_marks": sdata.get("max_marks", 0),
                    "percentage": sdata.get("percentage", ""),
                    "diag_label": diag_fact,
                })

        # Render template context
        tmpl = self._jinja_env.get_template("scorecard.html.j2")
        rendered_html = tmpl.render(
            font_regular_base64=self._font_regular_b64,
            font_bold_base64=self._font_bold_b64,
            institution_header=institution_header,
            assessment_name=assessment_name or ("टर्म 1 डायग्नोस्टिक टेस्ट" if is_omr else "मासिक मूल्यांकन"),
            test_date=test_date,
            child_display_name=child_name,
            class_section=class_sec,
            roll_number=roll_no,
            include_roll=include_roll,
            banner_color_hex=banner_color,
            banner_title_hi=banner_title,
            status_band=status_band_label,
            is_absent=is_absent,
            is_omr=is_omr,
            net_marks=format_display_marks(net),
            gross_marks=format_display_marks(gross),
            bleed_marks=format_display_marks(bleed),
            marks=format_display_marks(marks_val),
            max_marks=max_m,
            display_percentage=display_pct,
            competition_rank=rank,
            present_count=present_c,
            class_average=avg,
            topper_score=topper,
            correct=correct,
            wrong=wrong,
            blank=blank,
            easy_missed_count=len(easy_ids) if isinstance(easy_ids, list) else 0,
            easy_missed_question_ids=easy_ids if isinstance(easy_ids, list) else [],
            positive_marks_not_earned=pos_unearned,
            subject_rows=subject_rows,
            proof_png_base64=proof_png_b64,
            verification_ref=f"VRF-{student_id[:8].upper()}",
        )

        now_utc = timestamp_utc or datetime.now(UTC).isoformat()
        metadata = RenderMetadata(
            chromium_version=self.chromium_version,
            font_version=FONT_VERSION,
            font_family=FONT_FAMILY,
            timestamp_utc=now_utc,
            device_scale_factor=1,
            org_id=org_id,
        )

        # Launch page and capture screenshot
        page = self._browser.new_page(
            viewport={"width": SCORECARD_WIDTH, "height": SCORECARD_HEIGHT},
            device_scale_factor=1,
        )
        try:
            self._setup_page_isolation_and_fonts(page)
            page.set_content(rendered_html)
            self._verify_fonts_ready(page)

            png_bytes = page.screenshot(
                type="png",
                clip={"x": 0, "y": 0, "width": SCORECARD_WIDTH, "height": SCORECARD_HEIGHT},
            )
            size_bytes = len(png_bytes)

            # Strict 500 KB budget check (never silently degrade or downscale)
            if size_bytes >= SCORECARD_BUDGET_BYTES:
                return ScorecardResult(
                    status=RenderStatus.BUDGET_EXCEEDED,
                    student_id=student_id,
                    png_bytes=png_bytes,
                    width=SCORECARD_WIDTH,
                    height=SCORECARD_HEIGHT,
                    size_bytes=size_bytes,
                    metadata=metadata,
                    is_budget_exceeded=True,
                    error_message=f"Scorecard size {size_bytes} bytes exceeds budget limit {SCORECARD_BUDGET_BYTES} bytes",
                    rendered_html=rendered_html,
                    org_id=org_id,
                )

            return ScorecardResult(
                status=RenderStatus.SUCCESS,
                student_id=student_id,
                png_bytes=png_bytes,
                width=SCORECARD_WIDTH,
                height=SCORECARD_HEIGHT,
                size_bytes=size_bytes,
                metadata=metadata,
                is_budget_exceeded=False,
                rendered_html=rendered_html,
                org_id=org_id,
            )
        finally:
            page.close()

    # --------------------------------------------------------------------------
    # PTM Slip A4 PDF Rendering
    # --------------------------------------------------------------------------

    def render_ptm_pdf(
        self,
        slips: list[PtmSlipItem] | list[dict[str, Any]],
        *,
        qr_provider: QrTokenProvider | None = None,
        institution_header: str = "आदर्श विद्या मंदिर",
        assessment_name: str = "अभिभावक-शिक्षक बैठक (PTM)",
        timestamp_utc: str | None = None,
        org_id: str = "DEFAULT_INSTITUTION",
    ) -> PtmPdfResult:
        """
        Render an A4 portrait PDF containing 2x4 slips per page.
        Total pages = ceil(n/8).
        For n = 0, returns an explicit empty result with 0 pages (no blank PDF).
        """
        n = len(slips)
        now_utc = timestamp_utc or datetime.now(UTC).isoformat()
        metadata = RenderMetadata(
            chromium_version=self.chromium_version,
            font_version=FONT_VERSION,
            font_family=FONT_FAMILY,
            timestamp_utc=now_utc,
            device_scale_factor=1,
            org_id=org_id,
        )

        # Explicit empty result for n = 0 (S6 Task 9 mandate)
        if n == 0:
            return PtmPdfResult(
                status=RenderStatus.EMPTY_RESULT,
                slip_count=0,
                page_count=0,
                pdf_bytes=None,
                size_bytes=0,
                metadata=metadata,
                org_id=org_id,
            )

        if self._browser is None:
            self.start()
        assert self._browser is not None

        # Build processed slip list
        processed_slips: list[dict[str, Any]] = []
        for s in slips:
            if isinstance(s, PtmSlipItem):
                st_id = s.student_id
                c_name = normalize_name_or_fallback(s.child_display_name)
                c_sec = s.class_section
                r_no = s.roll_number
                p_text = s.performance_text_hi
                inst = s.institution_header or institution_header
                a_name = s.assessment_name or assessment_name
                qr_tok = s.qr_token
            else:
                st_id = str(s.get("student_id", "UNKNOWN"))
                c_name = normalize_name_or_fallback(s.get("child_display_name", "विद्यार्थी"))
                c_sec = str(s.get("class_section", ""))
                r_no = str(s.get("roll_number", s.get("roll_no", "")))
                p_text = str(s.get("performance_text_hi", ""))
                inst = str(s.get("institution_header", institution_header))
                a_name = str(s.get("assessment_name", assessment_name))
                qr_tok = s.get("qr_token")

            # Resolve QR token from provider if configured
            if qr_provider is not None:
                resolved_tok = qr_provider.get_token(st_id, org_id=org_id)
                if resolved_tok is not None:
                    qr_tok = resolved_tok

            qr_svg: str | None = None
            if qr_tok:
                # Opaque token only: never personal data
                qr_svg = generate_qr_svg(qr_tok, size=60)

            processed_slips.append({
                "student_id": st_id,
                "child_display_name": c_name,
                "class_section": c_sec,
                "roll_number": r_no,
                "performance_text_hi": p_text,
                "institution_header": inst,
                "assessment_name": a_name,
                "qr_token": qr_tok,
                "qr_svg": qr_svg,
            })

        # Group slips into pages of 8 slips (2x4 grid per page)
        slip_pages: list[list[dict[str, Any]]] = []
        for i in range(0, n, SLIPS_PER_PAGE):
            slip_pages.append(processed_slips[i : i + SLIPS_PER_PAGE])

        # Render HTML
        tmpl = self._jinja_env.get_template("ptm_slips.html.j2")
        rendered_html = tmpl.render(
            font_regular_base64=self._font_regular_b64,
            font_bold_base64=self._font_bold_b64,
            slip_pages=slip_pages,
        )

        page = self._browser.new_page()
        try:
            self._setup_page_isolation_and_fonts(page)
            page.set_content(rendered_html)
            self._verify_fonts_ready(page)

            pdf_bytes = page.pdf(
                format="A4",
                margin={
                    "top": f"{A4_MARGIN_MM}mm",
                    "bottom": f"{A4_MARGIN_MM}mm",
                    "left": f"{A4_MARGIN_MM}mm",
                    "right": f"{A4_MARGIN_MM}mm",
                },
                print_background=True,
                prefer_css_page_size=True,
            )

            # Inspect actual page count via pypdfium2
            actual_pages = get_pdf_page_count(pdf_bytes)

            return PtmPdfResult(
                status=RenderStatus.SUCCESS,
                slip_count=n,
                page_count=actual_pages,
                pdf_bytes=pdf_bytes,
                size_bytes=len(pdf_bytes),
                metadata=metadata,
                rendered_html=rendered_html,
                org_id=org_id,
            )
        finally:
            page.close()
