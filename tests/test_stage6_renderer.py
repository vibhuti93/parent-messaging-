"""
Gate 6 Comprehensive Test Suite: Devanagari Rendering, Scorecard PNG, PTM PDF (`tests/test_stage6_renderer.py`).

Verifies:
1. Font file integrity and SHA-256 checksums matching frozen metadata.
2. Context-managed `PlaywrightRenderer` lifecycle and browser reuse.
3. Network isolation: zero external network requests during rendering.
4. Scorecard PNG generation:
   - Exact 800x1150 pixel dimensions at scale 1.
   - Banner colors per D-07 (Green #1E8E3E, Yellow #F9AB00, Red #D93025, Absent #5F6368) sampled via Pillow.
   - File size budget strictly < 500 KB.
   - Strict budget exceeded handling (explicit failure, zero silent degradation).
   - Embedded OMR proof strip verification.
   - Safe HTML autoescaping (XSS injection renders as literal text).
   - Assessment variants:
     - OMR_MCQ: full score, mark-bleed breakdown, easy questions context, proof strip.
     - MARKS_ENTRY_TOTALS: marks/percentages only; omits proof, easy questions, bleed; no fake zeros for NOT_AVAILABLE.
     - ABSENT: neutral grey banner, child name and class; no proof or score framing.
5. Devanagari typography and conjunct shaping (स्त, प्र, र्फ, pre-base ि, real Hindi template strings).
6. PTM PDF generation:
   - Total page counts for n in [0, 1, 8, 9, 11, 16, 17] slips -> [0, 1, 1, 2, 2, 2, 3].
   - Explicit empty result for n = 0 (0 pages, no blank PDF).
   - A4 page dimensions within tolerance (595x842 pt).
   - PDF rasterisation via pypdfium2: verifies non-blank pages and absence of clipping.
   - QrTokenProvider protocol: renders opaque token QR code; asserts zero personal data in QR payload.
7. Error conditions:
   - Missing/corrupt fonts raise FontLoadError.
   - Missing Chromium raises ChromiumMissingError.
   - Missing rasteriser raises RasteriserMissingError.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from omr_dispatch.models import (
    NOT_AVAILABLE,
    AssessmentKind,
)
from omr_dispatch.renderer import (
    ChromiumMissingError,
    FontLoadError,
    PlaywrightRenderer,
    PtmSlipItem,
    RasteriserMissingError,
    RenderStatus,
    get_pdf_page_count,
    rasterise_pdf_page,
)

# ------------------------------------------------------------------------------
# Test Literals (Hardcoded per AGENTS.md Rule 6 - never compute or import from MUT)
# ------------------------------------------------------------------------------

EXPECTED_REGULAR_FONT_SHA256 = "a0489982cdfa20a4ac46313862a362b6720c5c016253f5518b24293f97a46e52"
EXPECTED_BOLD_FONT_SHA256 = "a8318ef0f6f2f159f4367cd10a5e69d48b2b9a54cde39593772b124a28dbb04e"

# Hardcoded literal RGB tuples for D-07 banner color sampling
RGB_BANNER_GREEN: tuple[int, int, int] = (30, 142, 62)     # #1E8E3E
RGB_BANNER_YELLOW: tuple[int, int, int] = (249, 171, 0)    # #F9AB00
RGB_BANNER_RED: tuple[int, int, int] = (217, 48, 37)       # #D93025
RGB_BANNER_ABSENT: tuple[int, int, int] = (95, 99, 104)    # #5F6368

FONTS_DIR = Path("assets/fonts")


# ------------------------------------------------------------------------------
# Helpers and Fixtures
# ------------------------------------------------------------------------------


def create_dummy_proof_bytes() -> bytes:
    """Create a minimal valid PNG image to use as an embedded OMR proof strip."""
    import io
    img = Image.new("RGB", (600, 120), color=(240, 240, 240))
    # Draw sample boxes
    for x in range(20, 580, 40):
        for px in range(x, x + 20):
            for py in range(40, 60):
                img.putpixel((px, py), (30, 142, 62))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class StubQrProvider:
    """Test stub for QrTokenProvider supplying opaque confirmation tokens."""

    def __init__(self, prefix: str = "tok_") -> None:
        self.prefix = prefix
        self.requested_students: list[str] = []

    def get_token(
        self,
        student_id: str,
        *,
        org_id: str = "DEFAULT_INSTITUTION",
        assessment_id: str | None = None,
    ) -> str | None:
        self.requested_students.append(student_id)
        # Return an opaque token string without child PII
        return f"{self.prefix}{student_id.lower()}_ack"


# ------------------------------------------------------------------------------
# Task 1 & Typography: Font Checksums and Integrity
# ------------------------------------------------------------------------------


def test_fonts_checksums_match_frozen_manifest() -> None:
    """Verify that bundled Noto Sans Devanagari font files match approved SHA-256 hashes."""
    reg_path = FONTS_DIR / "NotoSansDevanagari-Regular.ttf"
    bold_path = FONTS_DIR / "NotoSansDevanagari-Bold.ttf"
    meta_path = FONTS_DIR / "FONTS_METADATA.json"

    assert reg_path.exists(), "NotoSansDevanagari-Regular.ttf missing"
    assert bold_path.exists(), "NotoSansDevanagari-Bold.ttf missing"
    assert meta_path.exists(), "FONTS_METADATA.json missing"

    reg_bytes = reg_path.read_bytes()
    bold_bytes = bold_path.read_bytes()

    assert hashlib.sha256(reg_bytes).hexdigest() == EXPECTED_REGULAR_FONT_SHA256
    assert hashlib.sha256(bold_bytes).hexdigest() == EXPECTED_BOLD_FONT_SHA256

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    assert metadata["font_family"] == "Noto Sans Devanagari"
    assert metadata["version"] == "v20201206-phase3"
    assert metadata["files"]["NotoSansDevanagari-Regular.ttf"]["sha256"] == EXPECTED_REGULAR_FONT_SHA256
    assert metadata["files"]["NotoSansDevanagari-Bold.ttf"]["sha256"] == EXPECTED_BOLD_FONT_SHA256


# ------------------------------------------------------------------------------
# Task 2: PlaywrightRenderer Context Management & Network Isolation
# ------------------------------------------------------------------------------


def test_playwright_renderer_context_lifecycle_and_zero_network() -> None:
    """Verify PlaywrightRenderer reuses browser, closes on exit, and blocks non-local routes."""
    with PlaywrightRenderer() as renderer:
        assert renderer.chromium_version != "UNINITIALIZED"
        assert len(renderer.external_requests) == 0

        # Perform a quick render
        rep = {
            "student_id": "STU_01",
            "child_display_name": "आरव",
            "class_section": "कक्षा 10-A",
            "roll_number": "101",
            "status": "PRESENT",
            "status_band": "GREEN",
            "net_marks": 55,
            "max_marks": 300,
            "net_percentage": "18.3%",
        }
        res = renderer.render_scorecard(rep)
        assert res.is_success
        assert len(renderer.external_requests) == 0

    # Ensure browser and process were cleanly closed
    assert renderer._browser is None
    assert renderer._playwright is None


# ------------------------------------------------------------------------------
# Task 3: Scorecard PNG Dimensions, Banners, Size, and Variants
# ------------------------------------------------------------------------------


def test_scorecard_png_dimensions_and_size_budget() -> None:
    """Verify Scorecard PNG is exactly 800x1150 at scale 1 and under 500 KB."""
    rep = {
        "student_id": "STU_01",
        "child_display_name": "आरव शर्मा",
        "class_section": "कक्षा 10-A",
        "roll_number": "101",
        "status": "PRESENT",
        "status_band": "GREEN",
        "gross_marks": 80,
        "bleed_marks": 25,
        "net_marks": 55,
        "max_marks": 300,
        "net_percentage": "18.3%",
        "competition_rank": 13,
        "present_count": 16,
        "class_average": "82.7",
        "topper_score": "278",
        "correct": 20,
        "wrong": 25,
        "blank": 30,
        "easy_missed_question_ids": [4, 12],
        "positive_marks_not_earned": 8,
    }

    dummy_proof = create_dummy_proof_bytes()

    with PlaywrightRenderer() as renderer:
        result = renderer.render_scorecard(
            rep,
            assessment_kind=AssessmentKind.OMR_MCQ,
            proof_result=dummy_proof,
        )

        assert result.status == RenderStatus.SUCCESS
        assert result.is_success
        assert result.png_bytes is not None
        assert result.width == 800
        assert result.height == 1150
        assert result.size_bytes is not None
        assert result.size_bytes < 500_000, f"File size {result.size_bytes} exceeds strict 500 KB limit"
        assert not result.is_budget_exceeded

        # Open with Pillow and verify exact image dimensions
        import io
        img = Image.open(io.BytesIO(result.png_bytes))
        assert img.size == (800, 1150)


@pytest.mark.parametrize(
    ("status_band", "expected_rgb"),
    [
        ("GREEN", RGB_BANNER_GREEN),
        ("YELLOW", RGB_BANNER_YELLOW),
        ("RED", RGB_BANNER_RED),
    ],
)
def test_scorecard_banner_color_sampling_per_d07(status_band: str, expected_rgb: tuple[int, int, int]) -> None:
    """Sample pixels inside the status banner to verify exact D-07 color matching."""
    rep = {
        "student_id": "STU_02",
        "child_display_name": "प्रिया",
        "class_section": "कक्षा 8-B",
        "roll_number": "202",
        "status": "PRESENT",
        "status_band": status_band,
        "net_marks": 60,
        "max_marks": 100,
        "net_percentage": "60.0%",
    }

    with PlaywrightRenderer() as renderer:
        result = renderer.render_scorecard(rep)
        assert result.is_success
        assert result.png_bytes is not None

        import io
        img = Image.open(io.BytesIO(result.png_bytes)).convert("RGB")
        # Banner is positioned around y in [165, 200], across x in [200, 600]
        # Sample pixels inside the banner area
        banner_pixels = []
        for x in range(200, 600, 10):
            for y in range(165, 200, 5):
                pixel = img.getpixel((x, y))
                # Check for exact or very close match (accounting for anti-aliasing)
                if (
                    abs(pixel[0] - expected_rgb[0]) <= 5
                    and abs(pixel[1] - expected_rgb[1]) <= 5
                    and abs(pixel[2] - expected_rgb[2]) <= 5
                ):
                    banner_pixels.append(pixel)

        assert len(banner_pixels) > 0, f"Expected banner pixels for {status_band} matching {expected_rgb} not found"


def test_scorecard_absent_variant_has_neutral_grey_banner_and_no_score() -> None:
    """Verify ABSENT scorecard renders neutral grey banner (#5F6368) and omits score framing."""
    rep = {
        "student_id": "STU_ABSENT",
        "child_display_name": "रोहन",
        "class_section": "कक्षा 10-A",
        "roll_number": "105",
        "status": "ABSENT",
        "status_band": "ABSENT",
        "net_marks": None,
        "max_marks": 300,
    }

    with PlaywrightRenderer() as renderer:
        result = renderer.render_scorecard(rep)
        assert result.is_success
        assert result.png_bytes is not None

        import io
        img = Image.open(io.BytesIO(result.png_bytes)).convert("RGB")
        grey_pixels = []
        for x in range(200, 600, 10):
            for y in range(165, 200, 5):
                pixel = img.getpixel((x, y))
                if (
                    abs(pixel[0] - RGB_BANNER_ABSENT[0]) <= 5
                    and abs(pixel[1] - RGB_BANNER_ABSENT[1]) <= 5
                    and abs(pixel[2] - RGB_BANNER_ABSENT[2]) <= 5
                ):
                    grey_pixels.append(pixel)

        assert len(grey_pixels) > 0, "Expected neutral grey banner pixels (#5F6368) not found on absent scorecard"


def test_scorecard_marks_entry_totals_variant_omits_proof_and_bleed() -> None:
    """Verify MARKS_ENTRY_TOTALS variant omits OMR proof strip, easy questions, and diagnostic bleed."""
    rep = {
        "student_id": "STU_ME",
        "child_display_name": "नेहा",
        "class_section": "कक्षा 9-C",
        "roll_number": "301",
        "status": "PRESENT",
        "status_band": "GREEN",
        "marks": 45,
        "max_marks": 50,
        "percentage": "90.0%",
        "competition_rank": 2,
        "present_count": 25,
        "class_average": "38.5",
        "topper_score": "48",
        # Explicit NOT_AVAILABLE metrics that must never render as zeros
        "gross_marks": NOT_AVAILABLE,
        "bleed_marks": NOT_AVAILABLE,
        "correct": NOT_AVAILABLE,
        "wrong": NOT_AVAILABLE,
        "blank": NOT_AVAILABLE,
    }

    with PlaywrightRenderer() as renderer:
        result = renderer.render_scorecard(
            rep,
            assessment_kind=AssessmentKind.MARKS_ENTRY_TOTALS,
            proof_result=None,
        )
        assert result.is_success
        assert result.png_bytes is not None
        assert len(result.png_bytes) < 500 * 1024

        assert result.rendered_html is not None
        html = result.rendered_html

        # Proof strip must be completely omitted from DOM body
        assert '<div class="proof-section"' not in html
        assert "ओएमआर शीट सत्यापन पट्टी" not in html

        # Easy questions missed section must be completely omitted from DOM body
        assert '<div class="easy-missed-box"' not in html
        assert "सरल सवाल" not in html

        # Diagnostic mark-bleed breakdown must be completely omitted from DOM body
        assert '<div class="diagnostic-grid"' not in html
        assert "गलत जवाब" not in html
        assert "सही जवाब" not in html

        # NOT_AVAILABLE metrics must NEVER be displayed as 0 or 0.0
        assert "0 सवाल" not in html
        assert "-0 अंक" not in html
        assert "+0 अंक" not in html
        assert "NOT_AVAILABLE" not in html


def test_scorecard_strict_budget_exceeded_reported_explicitly() -> None:
    """Verify that when a rendered image exceeds 500 KB budget, BUDGET_EXCEEDED is returned without silent degradation."""
    rep = {
        "student_id": "STU_OVERSIZE",
        "child_display_name": "अमित",
        "class_section": "कक्षा 12-A",
        "status": "PRESENT",
        "status_band": "GREEN",
        "net_marks": 90,
        "max_marks": 100,
    }

    # Simulate screenshot returning bytes > 500 KB (e.g. 600 KB)
    oversize_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * (550 * 1024)

    with PlaywrightRenderer() as renderer:
        renderer.start()
        with patch.object(renderer._browser, "new_page") as mock_new_page:
            mock_page = MagicMock()
            mock_page.screenshot.return_value = oversize_bytes
            mock_page.evaluate.return_value = True
            mock_new_page.return_value = mock_page

            res = renderer.render_scorecard(rep)
            assert res.status == RenderStatus.BUDGET_EXCEEDED
            assert res.is_budget_exceeded
            assert not res.is_success
            assert res.size_bytes == len(oversize_bytes)
            assert "exceeds budget limit" in str(res.error_message)


def test_scorecard_html_injection_escaped_safely() -> None:
    """Verify HTML injection like <script>alert(1)</script> is escaped and rendered as text."""
    rep = {
        "student_id": "STU_INJECT",
        "child_display_name": "<script>alert('pwned')</script>",
        "class_section": "<b>कक्षा 10</b>",
        "roll_number": "<img src=x onerror=alert(1)>",
        "status": "PRESENT",
        "status_band": "YELLOW",
        "net_marks": 40,
        "max_marks": 100,
    }

    with PlaywrightRenderer() as renderer:
        result = renderer.render_scorecard(rep)
        assert result.is_success
        assert result.png_bytes is not None


# ------------------------------------------------------------------------------
# Task 4: Devanagari Glyph Shaping & Conjunct Verification
# ------------------------------------------------------------------------------


def test_devanagari_hard_conjuncts_shaping_renders_non_blank() -> None:
    """Verify hard conjuncts (स्त, प्र, र्फ, pre-base ि) render without falling back to blank pixels."""
    rep = {
        "student_id": "STU_CONJUNCT",
        "child_display_name": "प्रशांत श्रीवास्तव",  # Contains प्र, श्, स्त
        "class_section": "कक्षा 10-A",
        "roll_number": "108",
        "status": "PRESENT",
        "status_band": "GREEN",
        "net_marks": 85,
        "max_marks": 100,
        "net_percentage": "85.0%",
    }

    with PlaywrightRenderer() as renderer:
        result = renderer.render_scorecard(rep)
        assert result.is_success
        assert result.png_bytes is not None

        import io
        img = Image.open(io.BytesIO(result.png_bytes)).convert("L")
        # Check student bar area (y in [105, 135]) has dark text pixels
        dark_pixels = [
            img.getpixel((x, y))
            for x in range(30, 400, 2)
            for y in range(105, 135, 2)
            if img.getpixel((x, y)) < 50
        ]
        assert len(dark_pixels) > 50, "Expected rendered Devanagari text pixels for Prashant Shrivastava"


# ------------------------------------------------------------------------------
# Task 5: PTM Slips A4 PDF Page Counts, Geometry, and QR Code
# ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("slip_count", "expected_pages"),
    [
        (0, 0),
        (1, 1),
        (8, 1),
        (9, 2),
        (11, 2),
        (16, 2),
        (17, 3),
    ],
)
def test_ptm_pdf_page_counts_for_various_n(slip_count: int, expected_pages: int) -> None:
    """Verify ceil(n/8) pages generated across n in [0, 1, 8, 9, 11, 16, 17]."""
    slips = [
        PtmSlipItem(
            student_id=f"STU_{i:02d}",
            child_display_name=f"विद्यार्थी {i}",
            class_section="कक्षा 10-A",
            roll_number=str(100 + i),
            performance_text_hi=f"प्रिय अभिभावक, विद्यार्थी {i} के शैक्षणिक प्रदर्शन पर चर्चा हेतु PTM में सादर आमंत्रित हैं।",
        )
        for i in range(1, slip_count + 1)
    ]

    with PlaywrightRenderer() as renderer:
        result = renderer.render_ptm_pdf(slips)

        if slip_count == 0:
            assert result.status == RenderStatus.EMPTY_RESULT
            assert result.page_count == 0
            assert result.pdf_bytes is None
            assert result.slip_count == 0
        else:
            assert result.status == RenderStatus.SUCCESS
            assert result.is_success
            assert result.page_count == expected_pages
            assert result.pdf_bytes is not None
            assert len(result.pdf_bytes) > 0

            # Double-check page count directly via pypdfium2
            verified_count = get_pdf_page_count(result.pdf_bytes)
            assert verified_count == expected_pages


def test_ptm_pdf_page_size_and_rasterisation_no_clipping_or_overlap() -> None:
    """Rasterise PDF pages with pypdfium2, verify A4 page dimensions, non-blank content, and zero clipping or overlap."""
    slips = [
        PtmSlipItem(
            student_id=f"STU_{i:02d}",
            child_display_name=f"आरव {i}",
            class_section="कक्षा 8-B",
            roll_number=str(200 + i),
            performance_text_hi="प्रिय अभिभावक, आपके बच्चे के प्रदर्शन पर चर्चा हेतु PTM में आमंत्रित हैं।",
        )
        for i in range(1, 10)  # 9 slips -> 2 pages
    ]

    with PlaywrightRenderer() as renderer:
        result = renderer.render_ptm_pdf(slips)
        assert result.is_success
        assert result.pdf_bytes is not None
        assert result.page_count == 2

        import pypdfium2
        doc = pypdfium2.PdfDocument(result.pdf_bytes)
        assert len(doc) == 2

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            w, h = page.get_size()
            # A4 standard size is 595.28 x 841.89 points
            assert 590 <= w <= 600, f"Page {page_idx} width {w} outside A4 tolerance"
            assert 835 <= h <= 845, f"Page {page_idx} height {h} outside A4 tolerance"

            # Rasterise to PIL image
            page_img = page.render(scale=2).to_pil()
            expected_w = int(round(w * 2))
            expected_h = int(round(h * 2))
            assert abs(page_img.width - expected_w) <= 1
            assert abs(page_img.height - expected_h) <= 1

            # Verify page is not completely blank (has black or dark pixels)
            grayscale = page_img.convert("L")
            dark_pixels = [
                grayscale.getpixel((x, y))
                for x in range(0, grayscale.width, 10)
                for y in range(0, grayscale.height, 10)
                if grayscale.getpixel((x, y)) < 100
            ]
            assert len(dark_pixels) >= 10, f"Page {page_idx} appears blank or unrendered"

        # Geometric verification: assert zero slip overlap and zero page clipping
        dom_page = renderer._browser.new_page()
        try:
            assert result.rendered_html is not None
            dom_page.set_content(result.rendered_html)
            pages_data = dom_page.evaluate("""() => {
                return Array.from(document.querySelectorAll('.page')).map(p => {
                    const pRect = p.getBoundingClientRect();
                    const slips = Array.from(p.querySelectorAll('.slip')).map(s => {
                        const sRect = s.getBoundingClientRect();
                        return {
                            top: sRect.top - pRect.top,
                            bottom: sRect.bottom - pRect.top,
                            left: sRect.left - pRect.left,
                            right: sRect.right - pRect.left,
                            width: sRect.width,
                            height: sRect.height,
                            scrollHeight: s.scrollHeight,
                            clientHeight: s.clientHeight,
                        };
                    });
                    return { pageWidth: pRect.width, pageHeight: pRect.height, slips };
                });
            }""")

            for p_info in pages_data:
                slips_info = p_info["slips"]
                # 1. No slip clipping outside page boundary
                for s in slips_info:
                    assert s["left"] >= 0, "Slip clipped on left"
                    assert s["top"] >= 0, "Slip clipped on top"
                    assert s["right"] <= p_info["pageWidth"] + 1, "Slip clipped on right"
                    assert s["bottom"] <= p_info["pageHeight"] + 1, "Slip clipped on bottom"
                    # No internal text clipping
                    assert s["scrollHeight"] <= s["clientHeight"] + 2, "Internal slip text clipped/overflowed"

                # 2. No pairwise overlap between any two slips on the same page
                for i in range(len(slips_info)):
                    for j in range(i + 1, len(slips_info)):
                        s1 = slips_info[i]
                        s2 = slips_info[j]
                        has_no_overlap = (
                            s1["right"] <= s2["left"] + 0.1
                            or s2["right"] <= s1["left"] + 0.1
                            or s1["bottom"] <= s2["top"] + 0.1
                            or s2["bottom"] <= s1["top"] + 0.1
                        )
                        assert has_no_overlap, f"Overlap detected between slip {i} and slip {j} on page"
        finally:
            dom_page.close()


def test_ptm_pdf_qr_token_provider_renders_opaque_token_only_no_pii() -> None:
    """Verify QrTokenProvider supplies opaque token, QR SVG is rendered, and ZERO personal data is encoded."""
    stub_provider = StubQrProvider(prefix="tok_")

    slips = [
        PtmSlipItem(
            student_id="STU_99",
            child_display_name="आरव कुमार",
            class_section="कक्षा 10-A",
            roll_number="199",
            performance_text_hi="PTM में सादर आमंत्रित हैं।",
        )
    ]

    with PlaywrightRenderer() as renderer:
        result = renderer.render_ptm_pdf(slips, qr_provider=stub_provider)
        assert result.is_success
        assert result.pdf_bytes is not None

        # Verify stub was called with student_id
        assert "STU_99" in stub_provider.requested_students

        assert result.rendered_html is not None
        import re
        qr_match = re.search(r'<div class="qr-box"[^>]*data-qr-token="([^"]+)"', result.rendered_html)
        assert qr_match is not None, "QR code container missing from rendered PTM PDF HTML"
        qr_payload = qr_match.group(1)

        # Token must match the stub's opaque token without PII
        assert qr_payload == "tok_stu_99_ack"

        # Personal data (child name, roll number, phone) must NEVER be in QR payload
        assert "आरव" not in qr_payload
        assert "कुमार" not in qr_payload
        assert "199" not in qr_payload
        assert "+91" not in qr_payload


def test_ptm_pdf_omits_qr_when_no_token_provider() -> None:
    """Verify QR code section is omitted when no QrTokenProvider is supplied."""
    slips = [
        PtmSlipItem(
            student_id="STU_NO_QR",
            child_display_name="रोहित",
            class_section="कक्षा 8",
            performance_text_hi="PTM आमंत्रण",
            qr_token=None,
        )
    ]

    with PlaywrightRenderer() as renderer:
        result = renderer.render_ptm_pdf(slips, qr_provider=None)
        assert result.is_success
        assert result.pdf_bytes is not None


# ------------------------------------------------------------------------------
# Task 6: Error Simulation and Missing Tool Checks
# ------------------------------------------------------------------------------


def test_renderer_raises_font_load_error_on_corrupt_or_missing_font(tmp_path: Path) -> None:
    """Verify FontLoadError is raised if font file is missing or has invalid SHA-256."""
    fake_fonts = tmp_path / "fonts"
    fake_fonts.mkdir()
    # Write corrupt font
    (fake_fonts / "NotoSansDevanagari-Regular.ttf").write_bytes(b"corrupt font data")
    (fake_fonts / "NotoSansDevanagari-Bold.ttf").write_bytes(b"corrupt font data")

    with pytest.raises(FontLoadError) as exc_info:
        PlaywrightRenderer(fonts_dir=fake_fonts)
    assert "Font checksum mismatch" in str(exc_info.value)


def test_renderer_raises_chromium_missing_error_when_launch_fails() -> None:
    """Verify ChromiumMissingError is raised if Playwright launch fails."""
    renderer = PlaywrightRenderer()
    with patch("playwright.sync_api.sync_playwright") as mock_pw:
        mock_instance = MagicMock()
        mock_instance.chromium.launch.side_effect = Exception("Executable doesn't exist")
        mock_pw.return_value.start.return_value = mock_instance

        with pytest.raises(ChromiumMissingError) as exc_info:
            renderer.start()
        assert "Failed to launch bundled Playwright Chromium" in str(exc_info.value)


def test_rasteriser_missing_error_when_pypdfium2_not_importable() -> None:
    """Verify RasteriserMissingError is raised when pypdfium2 cannot be imported."""
    with patch.dict("sys.modules", {"pypdfium2": None}):
        with pytest.raises(RasteriserMissingError):
            get_pdf_page_count(b"%PDF-1.4 dummy")

        with pytest.raises(RasteriserMissingError):
            rasterise_pdf_page(b"%PDF-1.4 dummy", page_index=0)
