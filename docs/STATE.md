# Project State & Execution Log (`docs/STATE.md`)

## Current Status
- **Active Stage:** Stage 0 Remediation (`S0-R — Remediation of Stage 0`) — **COMPLETED**
- **Next Stage:** Stage 1 (`S1 — Golden Dataset and Independent Contract`) — **AWAITING HUMAN GATE**
- **Live Dispatch:** **DISABLED** (`LIVE_DISPATCH_ENABLED=false` safe default strictly preserved)
- **Fixture Manifest SHA-256:** `N/A` (Staged for S1 generation)
- **Stage Tag:** `stage-0` (tagged commit on `agent-run`)

---

## Operator-Approved Additions to S0 Allowed Files
Per operator instructions for Stage S0-R, the following files outside the original S0 list are approved:
1. `scripts/guardrails.py`: Automated W3 invariant checker (pre-commit hook).
2. `scripts/split_prompt_pack.py`: Prompt pack splitter script.
3. `.gitignore`: Virtualenv, cache, and artifact exclusions.
4. `.python-version`: Local Python interpreter pin (`3.12`).
5. `.gitattributes`: Line ending normalization (`* text=auto eol=lf`).

---

## Stage S0-R Execution Evidence

### 1. File Scope Audit & Diff vs Baseline
`template_constraints.py` was deleted from the repository root (deferred to Stage 4 ownership); `docs/research/template_constraints.json` is retained as the sole S0 machine-readable record.

All modified and untracked files compared against `stage-init` (`git status --porcelain`):
- `M  .env.example` (S0 allowed)
- `M  .gitignore` (Operator approved)
- `M  docs/DECISIONS_OPEN.md` (S0 allowed)
- `M  docs/STATE.md` (S0 allowed)
- `A  .gitattributes` (Operator approved)
- `A  .python-version` (Operator approved)
- `A  PROJECT_SPEC.md` (S0 allowed)
- `A  README.md` (S0 allowed)
- `A  docs/architecture_decisions.md` (S0 allowed)
- `A  docs/architecture_inventory.md` (S0 allowed)
- `A  docs/privacy_and_security.md` (S0 allowed)
- `A  docs/research/official_source_verification.md` (S0 allowed)
- `A  docs/research/template_constraints.json` (S0 allowed)
- `A  docs/testing_strategy.md` (S0 allowed)
- `A  pyproject.toml` (S0 allowed)
- `A  src/omr_dispatch/__init__.py` (S0 allowed empty scaffold)
- `A  tests/__init__.py` (S0 allowed empty scaffold)
- `A  uv.lock` (S0 allowed lockfile)

Zero unapproved files remain.

### 2. Python 3.12 Pinning Evidence
- Host System Interpreter: `Python 3.12.1` (`C:\Users\91933\AppData\Local\Programs\Python\Python312\python.exe`)
- `.python-version`: Contains `3.12`
- `pyproject.toml`: Contains `requires-python = ">=3.11,<3.14"`
- `uv lock` Output:
  `Using CPython 3.12.1 interpreter at: C:\Users\91933\AppData\Local\Programs\Python\Python312\python.exe`
  `Resolved 26 packages in 1.28s`
- `uv sync` Output:
  `Using CPython 3.12.1 interpreter at: C:\Users\91933\AppData\Local\Programs\Python\Python312\python.exe`
  `Installed 19 packages in 1.15s`
- `uv run python --version` Output:
  `Python 3.12.1`
- UTF-8 and Line Ending Settings:
  - `.gitattributes` configured with `* text=auto eol=lf`.
  - `README.md` documents `PYTHONUTF8=1` on Windows and `encoding="utf-8"` mandatory for all file operations.

### 3. Source Verification Evidence
- **Network Access Status:** Active during session on 2026-10-20.
- All claims in `docs/research/official_source_verification.md` ground to official primary sources:
  1. Meta Graph API v21.0: Released October 2, 2024, supported under 2-year lifecycle (`https://developers.facebook.com/docs/graph-api/changelog/version21.0`).
  2. 24h Customer Service Window: Initial outbound messaging requires pre-approved Utility templates (`https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages`).
  3. Meta Business Account & Opt-In: Explicit user opt-in required; unverified accounts capped at 250 conversations/24h (`https://developers.facebook.com/docs/whatsapp/overview/business-opt-in`).
  4. Template Media Headers: Headers support Text, Image, Document, Video; **Audio headers are not supported** (`https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates/components`).
  5. Audio Payload Requirements: Ogg Opus only, mono, 48kHz, max 16MB; direct `.ogg` file renames prohibited (`https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#media-object`).
  6. Template Parameters: Max 1024 chars body, 60 chars header, no newlines in variables, no leading/trailing whitespace, no consecutive variables (`https://developers.facebook.com/docs/whatsapp/message-templates/guidelines`).
  7. Webhook Signature Verification: `X-Hub-Signature-256` HMAC SHA-256 computed over raw body with `APP_SECRET` (`https://developers.facebook.com/docs/graph-api/webhooks/getting-started`).
  8. Guardian Verification / OTP Channels: WhatsApp Authentication Templates (`category: "authentication"`) vs Indian Carrier SMS requiring TRAI DLT registration (TCCCPR 2018; Principal Entity ID, 6-char Header, Template ID) (`https://trai.gov.in`).
  9. India DPDP Framework: DPDP Act 2023 Section 9 mandates verifiable parental consent for minors (<18), prohibits tracking/behavioral profiling; DPDP Rules 2025 gazetted November 2025 with phased implementation timeline (`https://www.meity.gov.in`).
- Items remaining UNVERIFIED at institutional deployment level (institutional KYC, active DLT registration, formal legal clearance) keep live dispatch disabled (`LIVE_DISPATCH_ENABLED=false` in `.env.example`).

### 4. Spec Integrity & Contradiction Check
- `git diff --no-index docs/prompt_pack/PROJECT_SPEC.seed.md PROJECT_SPEC.md` shows only the added Product Boundary section; all decision text D-01 through D-14 is identical to the seed.
- Contradiction check: Completed cross-reference between `PROJECT_SPEC.md`, `AGENTS.md` (Rules 1–14), and `docs/prompt_pack/` (`S0.md`–`S13.md`). Result: **No contradictions found.** Recorded in `docs/DECISIONS_OPEN.md`.

### 5. Commands Executed & Exit Codes
1. `uv lock` -> Exit Code `0`
2. `uv sync` -> Exit Code `0`
3. `uv run python --version` -> Exit Code `0` (`Python 3.12.1`)
4. `ruff check .` -> Exit Code `0` (`All checks passed!`)
5. `python scripts/guardrails.py` -> Exit Code `0` (`[GUARDRAIL PASS] All pre-commit guardrails satisfied.`)
6. `uv run pytest` -> Exit Code `5` (`no tests ran in 0.01s`, expected `pytest.ExitCode.NO_TESTS_COLLECTED` for empty scaffold, not a test pass).

### 6. Open Decisions Awaiting Operator Confirmation (`docs/DECISIONS_OPEN.md`)
1. **D-04:** PTM slip requirement for bottom quartile in all-GREEN batches (`OWNER-CONFIRM`).
2. **D-11:** Parent confirmation QR token TTL default 72h (`OWNER-CONFIRM`).
3. **D-11:** Primary guardian OTP challenge channel: WhatsApp Authentication Template vs Indian SMS (`OWNER-CONFIRM`).
4. **D-12:** Display of class topper score on parent-facing report card (`OWNER-CONFIRM`).
5. **D-13:** Legal review under India's DPDP Act 2023 for 90-day log retention and children's data handling (`LEGAL REVIEW REQUIRED`).
