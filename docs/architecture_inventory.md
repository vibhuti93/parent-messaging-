# Architecture Inventory & Workspace Baseline

**Date:** 2026-10-20  
**Stage:** S0 (Discovery, Contracts, Source Verification)  
**Branch:** `agent-run`  
**Git Baseline Tag:** `stage-init` (`8ec672d`)

---

## 1. Repository & System State
- **OS Platform:** Windows 11 (PowerShell environment), with Linux container support via `Dockerfile`.
- **Python Version:** 3.12.1 local runtime (Python 3.11+ requirement satisfied); container targets Python 3.11-slim-bookworm.
- **Package Management:** `uv` 0.13.1 available locally; `pip` available.
- **Git State:** Clean working tree at initialization tag `stage-init`.

---

## 2. Inventory of Existing Files & Artifacts

| Path | Status | Purpose & Handling Rule |
| :--- | :--- | :--- |
| `AGENTS.md` | Pre-existing | Global invariants and agent instructions. **Frozen / must not be weakened or deleted.** |
| `Dockerfile` | Pre-existing | Docker container specification with OS packages: FFmpeg, Poppler, Noto Devanagari fonts, and Playwright Chromium. Reused for hermetic builds and rendering tests. |
| `requirements.txt` | Pre-existing | Minimal base dependencies (`playwright`, `pillow`, `pydantic`, `pytest`). Maintained alongside `pyproject.toml`. |
| `scripts/guardrails.py` | Pre-existing | Pre-commit guardrail checker enforcing W3 rules (secrets, banned patterns, banned Hindi terms, fixture hashes, monotonic test counts). **Must not be bypassed.** |
| `scripts/split_prompt_pack.py` | Pre-existing | Prompt pack splitter script. Completed execution, retained for audit. |
| `.git/hooks/pre-commit` | Pre-existing | Active pre-commit hook enforcing `scripts/guardrails.py`. |
| `.env.example` | Pre-existing | Baseline runtime configuration placeholders (`LIVE_DISPATCH_ENABLED=false`). |
| `docs/DECISIONS_OPEN.md` | Pre-existing | Open decisions and `OWNER-CONFIRM` proposals tracking log. |
| `docs/STATE.md` | Pre-existing | State tracking file updated at the conclusion of each stage. |
| `docs/prompt_pack/` | Pre-existing | Contains 16 stage specifications (`00_global_invariants.md`, `PROJECT_SPEC.seed.md`, `S0.md` through `S13.md`). **Frozen reference.** |

---

## 3. Gap Analysis (What is Missing vs Stage Targets)

1. **Contracts & Specifications:**
   - `PROJECT_SPEC.md`: Required verbatim copy of Part B plus clear product boundaries (created in S0).
   - `docs/DECISIONS_OPEN.md`: Required documentation of all `OWNER-CONFIRM` proposals and ambiguities (populated in S0).
2. **Official Source Research & Pre-Deployment Checklist:**
   - `docs/research/official_source_verification.md`: Verification of Meta Cloud API, audio constraints, and parameter limits (created in S0; DPDP and TRAI reviews deferred to pre-deployment checklist).
   - `docs/PRE_DEPLOYMENT_CHECKLIST.md`: Deferred compliance, legal review, and carrier registration items (created in Stage D).
   - Machine-readable `template_constraints.json`: Specification for WhatsApp template limits (created in S0).
3. **Architecture & Governance:**
   - `docs/architecture_decisions.md`: High-level module architecture and durable state planning (created in S0).
   - `docs/privacy_and_security.md`: Data minimization, masking, retention, DPDP alignment (created in S0).
   - `docs/testing_strategy.md`: Oracle separation, frozen fixture validation, boundary-only mocking (created in S0).
4. **Project Configuration & Tooling:**
   - `pyproject.toml`: Modern Python packaging, ruff, mypy, and pytest configuration (created in S0).
   - Lockfile: Generated via `uv` (created in S0).
   - `README.md`: Setup, architecture, offline vs network feature explanation (created in S0).
5. **Code & Test Scaffold:**
   - `src/omr_dispatch/`: Empty package structure without business logic (created in S0).
   - `tests/`: Empty test suite structure (created in S0).

---

## 4. Protected Files & Anti-Tampering Rules

The following files represent hard project guardrails and must **never** be arbitrarily modified or overwritten:
1. `AGENTS.md` — Enforces strict Part C global invariants across all sessions.
2. `scripts/guardrails.py` — The pre-commit automated validator for secrets, banned Hindi terms, hardcoded API versions, and test count monotonicity.
3. Frozen Fixtures (`fixtures/golden/*`, staged for S1) — May only be generated in S1 and must match `manifest.json` SHA-256 hashes thereafter.
