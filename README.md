# OMR Dispatch Engine (`omr_dispatch_engine`)

A high-assurance, deterministic diagnostics and parent notification engine for Indian educational institutions.

The engine processes student roster data, exam answer keys, raw OMR scans, and decoded responses. It computes rigorous academic diagnostics, generates respectful conversational Bolchal Hindi notifications, renders mobile-optimized scorecard PNGs and A4 PTM slips, stitches natural Hindi voice notes, and manages WhatsApp Business Cloud API dispatches with contact hygiene and quarantine safeguards.

---

## 1. Product Boundaries & Philosophy

* **What it does:**
  - Ingests and validates roster, answer key, decoded OMR responses, and raw student scan images.
  - Computes deterministic scores (gross, bleed, net, percentage), competition ranks, status bands (`RED`, `YELLOW`, `GREEN`, `ABSENT`), easy question identification (≥ 75% accuracy among present peers), and subject diagnostic classifications.
  - Produces parent-facing assets: conversational Bolchal Hindi text, scorecard PNGs, A4 PTM slip PDFs, and stitched audio voice notes.
  - Performs contact hygiene: normalizes numbers to E.164, detects interception risk (student number == parent number), resolves shared parent numbers, and quarantines unverified contacts.
  - Dispatches via WhatsApp Cloud API under verified template rules.
  - Ingests delivery receipts via signed webhooks (`sent`, `delivered`, `read`, `failed`).
  - Supports optional parent acknowledgment via single-use cryptographic QR tokens and guardian OTP challenge.
  - Maintains append-only masked audit trails and automated 90-day retention purging.
* **What it does not do:**
  - Optical bubble detection, sheet corner detection, or scanner deskew. Decoded bubble answers are provided by an upstream OMR scanning service (contract defined in S2).

---

## 2. Deployment Status & Compliance Safeguards

> [!IMPORTANT]
> **Development Mode: Synthetic Data Only.**  
> Development and automated testing proceed exclusively using synthetic student data. Deployment to real parents and processing of real student records are strictly blocked until all items in [docs/PRE_DEPLOYMENT_CHECKLIST.md](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_pareent_messaging/docs/PRE_DEPLOYMENT_CHECKLIST.md) are completed and signed off.
> 
> **Enforced Dual-Switch Gate:**  
> Any live dispatch command (`send`) refuses to execute unless **both** environment flags are explicitly set:
> 1. `LIVE_DISPATCH_ENABLED=true`
> 2. `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=true` (must remain `false` until the checklist is fully closed).

---

## 3. Offline vs. Network Features

| Feature Category | Execution Mode | Default State | Description |
| :--- | :--- | :--- | :--- |
| **Ingestion & Validation** | **Offline** | Enabled | Ingests JSON rosters, answer keys, decoded responses, and image files. |
| **Diagnostic Scoring** | **Offline** | Enabled | Pure arithmetic calculation of scores, ranks, bands, and subject labels. |
| **Hindi Copy Generation** | **Offline** | Enabled | Generates natural Bolchal Hindi adhering to D-06 vocabulary rules. |
| **Asset Rendering** | **Offline** | Enabled | Renders PNG scorecards via Playwright and A4 PTM PDFs locally. |
| **Audio Note Stitching** | **Offline** | Enabled | Concatenates recorded Hindi audio tokens and transcodes via local FFmpeg. |
| **Contact Hygiene** | **Offline** | Enabled | Normalizes numbers and enforces quarantine rules without network lookup. |
| **Live WhatsApp Dispatch** | **Network** | **DISABLED** | Live messaging requires explicit opt-in and `LIVE_DISPATCH_ENABLED=true`. |
| **Inbound Webhooks** | **Network** | Standby | Receives Meta delivery receipts, validating HMAC SHA-256 signatures. |
| **Network TTS Adapter** | **Network** | **DISABLED** | Secondary cloud TTS adapter, disabled by default in favor of local stitch. |

---

## 4. Environment Setup & Requirements

### 4.1 System Prerequisites & UTF-8 Configuration
- **Python:** Pinned to Python 3.12 (`.python-version` holds `3.12`, `requires-python = ">=3.11,<3.14"` in `pyproject.toml`).
- **UTF-8 & Encoding Invariant:** All file reads and writes across the engine must strictly specify `encoding="utf-8"`. On Windows hosts, set `PYTHONUTF8=1` (PowerShell: `$env:PYTHONUTF8="1"`) to ensure standard UTF-8 mode and avoid Windows cp1252 Devanagari corruption.
- **Line Endings:** `.gitattributes` enforces `* text=auto eol=lf` across all text files.
- **FFmpeg:** Required for transcoding audio into Ogg Opus format (mono, 48kHz).
- **Poppler & Fonts:** Required for PDF rendering and Devanagari script display (`fonts-noto-core`).

### 4.2 Installation

Using `uv` (recommended):
```bash
# Clone the repository
git clone <repo-url>
cd new_pareent_messaging

# Sync dependencies from lockfile
uv sync

# Install Playwright browser binaries
uv run playwright install chromium
```

Using standard `pip`:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

### 4.3 Docker Support
A hermetic Debian Bookworm container is provided:
```bash
docker build -t omr-dispatch-engine .
docker run -it --rm omr-dispatch-engine pytest
```

---

## 5. Configuration & Security

All runtime settings are read from environment variables. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### Safety Flags:
- `LIVE_DISPATCH_ENABLED=false`: Safe-by-default switch. No external WhatsApp messages will be sent unless explicitly flipped to `true`.
- `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`: Compliance switch. Must remain `false` until all pre-deployment checklist items are satisfied.
- `WHATSAPP_CLOUD_API_VERSION=v21.0`: Pinned Meta Graph API version. Floating versions are strictly prohibited.
- `DATA_RETENTION_DAYS_LOGS=90`: Rolling retention window for operational audit logs.

### Privacy Invariants (AGENTS.md):
- Never log full phone numbers, student names, scores, QR tokens, or raw audio payloads (all masked per Rule 10).
- Never infer consent, guardian identity, or sibling status from spreadsheet data or surnames (Rule 9).
- A non-empty phone number does not constitute consent; explicit opt-in is mandatory.

---

## 6. Development & Verification

### Running Automated Tests
```bash
# Run test suite
pytest -q

# Run specific stage test (e.g. Stage 1 golden contract)
pytest -q tests/test_stage1_golden_contract.py
```

### Pre-commit Guardrails
Pre-commit checks are enforced automatically via `.git/hooks/pre-commit` or can be run manually:
```bash
python scripts/guardrails.py
```
Checks performed:
1. Secrets scanner (detects API keys, tokens, private keys).
2. Forbidden pattern checks (bans `voice: true`, hardcoded API versions, direct `.ogg` file renames, unmasked mobile numbers, localhost in production).
3. Banned Hindi vocabulary checker (enforces D-06).
4. Fixture hash integrity against `manifest.json`.
5. Monotonically non-decreasing test count validation.
