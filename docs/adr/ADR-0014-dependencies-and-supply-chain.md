# ADR-0014: Dependency Justification and Supply Chain Hardening

## Status
`PROPOSED`

## Context
Modern software supply chains are vulnerable to malicious package updates, dependency confusion, license incompatibilities, and sudden breaking changes in upstream libraries.
Because `omr_dispatch_engine` handles sensitive student records, we must adopt an uncompromising, disciplined dependency policy.

## Options Considered

### Option 1: Unpinned, Permissive Dependencies
- *Description*: Allow flexible version ranges (e.g. `pydantic>=2.0`) without lockfiles or supply chain vetting.
- *Pros*: Low maintenance.
- *Cons*: Unreproducible builds; high vulnerability to compromised upstream package releases.

### Option 2: Strict Justification, Dependency Aging, and Sealed Adapters
- *Description*:
  - **Explicit Justification:** Every single direct dependency in `pyproject.toml` must be explicitly justified in this ADR.
  - **Lockfile Enforcement:** `uv.lock` is strictly tracked in version control; all builds install exact pinned hashes (`uv sync --frozen`).
  - **Dependency Aging Rule:** New dependencies or version upgrades must be at least **14 days old** in PyPI registry before adoption, mitigating "zero-day release" supply-chain attacks, unless an urgent security patch is required.
  - **Licensing:** Only permissive open-source licenses permitted (MIT, Apache-2.0, BSD-3-Clause). Copyleft licenses (GPL, AGPL) in direct runtime libraries are banned.
  - **Adapter Isolation:** Heavy external tools (Playwright, FFmpeg, TTS engines) are strictly isolated behind abstract adapter boundaries.
- *Pros*: Maximum supply chain security; reproducible builds across developer machines and CI; zero legal licensing hazards.
- *Cons*: Upgrades require deliberate review.

## Proposed Decision
We propose **Option 2 (Strict Justification, Dependency Aging, and Sealed Adapters)**.

### Direct Dependency Registry & Justification
| Package | License | Justification |
| :--- | :--- | :--- |
| `pydantic` (v2.x) | MIT | Core data modeling, strict schema validation, type safety. |
| `pydantic-settings` | MIT | Centralized environment variable management with `SecretStr`. |
| `httpx` / `requests` | BSD-3 / Apache-2 | HTTP client for Meta WhatsApp Cloud API and webhook simulation. |
| `jinja2` | BSD-3 | Template engine for HTML scorecard rendering and Hindi copy assembly. |
| `playwright` | Apache-2 | Headless Chromium automation for pixel-perfect scorecard PNG generation. |
| `reportlab` / `weasyprint` | BSD-3 / BSD-3 | High-fidelity A4 PTM slip PDF generation. |
| `pillow` | MIT | Image manipulation, OMR response bubble crop generation. |
| `hypothesis` (dev) | MPL-2.0 | Property-based testing for scoring arithmetic invariants. |
| `pytest` / `pytest-cov` (dev) | MIT / MIT | Test execution, marker filtering, and coverage enforcement. |
| `ruff` (dev) | MIT | Ultra-fast linting and code formatting. |
| `mypy` (dev) | MIT | Strict static type checking. |

## Consequences
- **Positive**: Fully audited dependency perimeter; zero unvetted packages; reliable builds.
- **Negative**: Adding a new package requires editing this ADR and justifying its inclusion.
- **Neutral**: Enforced via pre-commit and lockfile checks.

## Revisit When
Revisit quarterly during scheduled dependency security audits.

## Dependency log
- **2026-10-20**: Added `mypy` (2.4.0) and `pre-commit` (4.7.0) as dev dependencies via `uv add --dev`. Reason: type checking and pre-commit hooks configured in S0-R4 (ADR-0012, ADR-0014) could not run without them; found during the W2 review of S0-R4. Dev tools only, not imported by application code.