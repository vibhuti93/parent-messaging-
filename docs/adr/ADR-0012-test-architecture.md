# ADR-0012: Test Architecture, Strict Markers, and Coverage Floor

## Status
`PROPOSED`

## Context
The dispatch engine handles child educational data, calculates student competition ranks, and performs automated WhatsApp messaging where duplicate sends cost money and violate privacy rules.
Testing must be rigorous, granular, fast, and structured so that external dependencies (network, browsers, FFmpeg) can be run selectively without slowing down the core test loop.

## Options Considered

### Option 1: Flat Test Directory with Default Pytest Run
- *Description*: All tests in a single directory running everything on every invocation.
- *Pros*: Minimal setup.
- *Cons*: Slow runs; failure to isolate network or heavy browser tests; unclear coverage targets.

### Option 2: Categorized Pytest Markers, Strict Enforcement, and High Core Coverage Floor
- *Description*:
  - **Pytest Markers:** Explicit markers: `unit`, `integration`, `render`, `audio`, `network`.
  - **Strict Markers:** Enforce `--strict-markers` in `pyproject.toml` so typos in marker names immediately fail the test suite.
  - **Directory Layout:** Segregated test packages: `tests/unit/`, `tests/integration/`, `tests/contract/`, `tests/fixtures/`.
  - **Core Coverage Floor:** Propose **95% branch coverage floor** for pure core packages (`diagnostics`, `models`, `hindi_templates`, `messaging_policy`).
    - *Justification*: Core scoring and policy logic directly impacts student academic evaluations and carrier billing. A calculation or policy bug has immediate external consequences. High coverage ensures all boundary conditions are tested.
  - **Network Isolation:** Zero external network calls by default; any test requiring live provider simulation uses local mocks or synthetic contracts.
  - **Property-Based Testing:** Use Hypothesis to test arithmetic invariants (e.g. `attempted == correct + wrong`, `net == gross - bleed`).
- *Pros*: Sub-second unit test execution; total confidence in diagnostic accuracy; clear separation of heavy render suites.
- *Cons*: Enforcing 95% coverage requires thorough testing of edge cases and exceptions.

## Proposed Decision
We propose **Option 2 (Pytest Markers, Strict Enforcement, 95% Core Coverage Floor)**.

### Marker Definitions
- `unit`: Pure in-memory unit tests (executes in milliseconds, zero I/O).
- `integration`: Tests exercising local SQLite WAL store, file I/O, or pipeline coordination.
- `render`: Heavy tests requiring Playwright Chromium or PDF generation.
- `audio`: Tests invoking FFmpeg or audio token stitching.
- `network`: Tests exercising HTTP client adapters against local mock HTTP servers (never external endpoints).

## Consequences
- **Positive**: High test velocity; deterministic CI pipeline; zero accidental network calls.
- **Negative**: Tests must be explicitly tagged with markers.
- **Neutral**: Enforced via `pyproject.toml` configuration.

## Revisit When
Revisit coverage thresholds if non-critical exploratory UI modules are introduced.
