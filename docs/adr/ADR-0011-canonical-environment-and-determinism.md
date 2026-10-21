# ADR-0011: Canonical Environment and Determinism

## Status
`ACCEPTED`

## Context
Visual asset generation (HTML-to-image via Playwright Chromium) and audio transcoding (FFmpeg Ogg Opus) are notoriously sensitive to operating system environments, font rendering engines (FreeType vs Windows DirectWrite), and platform-specific audio codec libraries.
If developers run tests on Windows while production executes on Linux containers, pixel diffs and audio header lengths diverge, causing spurious test failures or uninspected visual regressions.
We need a clear canonical execution definition that supports multi-platform local development without compromising test determinism.

## Options Considered

### Option 1: Require Identical Local Operating Systems
- *Description*: Mandate that all developers run the same native Linux distribution locally.
- *Pros*: Eliminates cross-platform divergence.
- *Cons*: Restrictive and impractical for developers working on Windows/macOS workstations.

### Option 2: Linux Docker Image as Canonical Environment, Windows Supported for Non-Render Tests
- *Description*:
  - **Canonical Environment:** A standardized Docker container based on `python:3.12-slim` (Debian) with pinned font packages (`fonts-deva`, `fonts-noto-core`) and pinned FFmpeg is the sole **canonical baseline** for visual scorecard rendering, PDF slip generation, and audio duration tests.
  - **Cross-Platform Dev:** Windows local development is fully supported for all non-render and non-audio tests (scoring, diagnostics, contact hygiene, policy rules, template text, store, webhooks).
  - **Determinism Controls:** `PYTHONHASHSEED=0` enforced in CI/test runs; all JSON dumps emit sorted keys; tool versions (Python, Playwright, Chromium, FFmpeg) are recorded in run manifests.
  - **Visual Mismatch Policy:** If a visual render generated on Windows diverges from the golden baseline, the test is marked non-canonical on Windows; golden visual diff comparisons are evaluated and enforced strictly inside the canonical Docker container.
- *Pros*: Developer ergonomics preserved; absolute determinism in CI and production.
- *Cons*: Requires running Docker when verifying visual PNG/PDF golden diffs.

## Proposed Decision
We propose **Option 2 (Canonical Linux Docker Image, Cross-Platform Non-Render Dev, Strict Determinism Controls)**.

### Policy on Visual Mismatches
1. Golden snapshot assertions for scorecards (`tests/test_stage5_scorecard_render.py`) and PTM slips (`tests/test_stage6_ptm_slip_render.py`) require the `@pytest.mark.render` marker.
2. If run on a non-canonical host (e.g. native Windows without Docker), slight antialiasing or font metrics differences may trigger pixel-level diffs. In such cases:
   - The test issues a non-fatal warning on Windows.
   - The authoritative pass/fail gate is evaluated strictly in the Docker canonical environment (`docker run --rm omr_dispatch_runner pytest -m render`).
3. Audio transcoding duration checks (`@pytest.mark.audio`) similarly treat the Linux FFmpeg build as canonical.

## Consequences
- **Positive**: Eliminates "works on my machine" visual discrepancies; ensures pixel-perfect Hindi rendering in production.
- **Negative**: Visual tests require Docker on non-Linux workstations.
- **Neutral**: Fully documented in `docs/testing_strategy.md`.

## Revisit When
Revisit if headless browser-less canvas rendering (e.g. pure Python Skia) completely replaces Chromium.
