# Project State & Execution Log (`docs/STATE.md`)

## Current Status
- **Active Stage:** Stage S0-R3 (`Stage S0-R3 — Fix error classification and confidence ratings`) — **COMPLETED**
- **Next Stage:** Stage 1 (`S1 — Golden Dataset and Independent Contract`) — **AWAITING HUMAN GATE**
- **Live Dispatch:** **DISABLED** (`LIVE_DISPATCH_ENABLED=false` and `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`)
- **Legal/Compliance:** **DEFERRED** (fully collected and tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md`)
- **Fixture Manifest SHA-256:** `N/A` (Staged for S1 generation)
- **Stage Tag:** `stage-0-r3` (tagged commit on `agent-run`)

---

## Operator-Approved Additions to Allowed Files
Per operator instructions for S0-R, Stage D, S0-R2, and S0-R3, the following files outside the original S0 list are approved:
1. `scripts/guardrails.py`: Automated W3 invariant checker (pre-commit hook).
2. `scripts/split_prompt_pack.py`: Prompt pack splitter script.
3. `.gitignore`: Virtualenv, cache, and artifact exclusions.
4. `.python-version`: Local Python interpreter pin (`3.12`).
5. `.gitattributes`: Line ending normalization (`* text=auto eol=lf`).
6. `docs/PRE_DEPLOYMENT_CHECKLIST.md`: Deferred compliance, legal review, and carrier registration tracking list.
7. `docs/research/provider_contract.json`: Machine-readable provider specifications, 73 classified error codes, rate limits, and webhook retry contracts for S9.

---

## Stage S0-R3 Execution Evidence (Error Classes, Confidence Rubric, Full Coverage)

### 1. Step 0 Preconditions
- **Network Access Status:** Active (verified via live HTTP queries to Meta developer documentation on 2026-10-20).
- **Current Shell Date:** `2026-10-20 11:30:29 +05:30` (command: `Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"` -> output: `2026-10-20 11:30:29 +05:30`).

### 2. T1: Error-Handling Classes (P1)
- Replaced previous 3-way split (`TRANSIENT` / `PERMANENT` / `UNKNOWN`) with 5 non-overlapping operational classes tailored for a send path lacking native idempotency keys:
  1. **`RETRY_SAFE`:** The documented behaviour shows the request was rejected and the message was NOT accepted (rate limit / throttle rejections). Retry only with backoff/jitter and honouring `Retry-After`.
  2. **`OUTCOME_UNKNOWN`:** The message may or may not have been accepted (HTTP 5xx, timeouts, connection resets, any response the docs don't clearly describe as rejected). Never auto-retry. Recorded as `UNKNOWN_NEEDS_REVIEW` and reconciled through webhook delivery evidence.
  3. **`OPERATOR_ACTION`:** Cannot be fixed by retrying; needs human or configuration change (auth/token errors, payment, phone number state, quality/flagged state, template paused/rejected, missing permissions).
  4. **`PERMANENT`:** The request is invalid or the recipient/message can never succeed as sent (malformed payload, unsupported type, undeliverable, 24h window expired for freeform).
  5. **`UNKNOWN`:** The docs do not say. Default to `OUTCOME_UNKNOWN` behaviour.
- Added top-level `"default_class": "OUTCOME_UNKNOWN"` in `docs/research/provider_contract.json`.
- Updated retry section of `docs/prompt_pack/S9.md` to explicitly name these five classes and restrict automated retries strictly to `RETRY_SAFE`.
- Updated Master Table rows `R-11` and `R-12` and their detailed finding sections to reflect the new scheme.

### 3. T2: Confidence Rubric (P2)
- Added explicit Confidence Rubric above Master Table in `docs/research/official_source_verification.md`:
  - **`HIGH`:** Stated explicitly on an official page fetched/read in this session.
  - **`MEDIUM`:** Inferred from a page that does not address the claim directly, from absence of a feature in docs, or from a page only seen as a search snippet.
  - **`LOW`:** Ambiguous, conflicting, or only secondary sources.
  - **`N/A`:** Deferred or UNVERIFIED.
- Added mandatory **`Evidence Basis`** column to Master Table (one clear line per row).
- Honest Re-Rating across all 17 rows:
  - **HIGH (12):** R-01, R-02, R-04, R-05, R-06, R-07, R-09, R-10, R-11, R-12, R-14, R-15.
  - **MEDIUM (3):** R-03 (institutional KYC unverified), R-08 (mono explicit; 48 kHz inferred from RFC 7845 convention), R-13 (absence of idempotency key header).
  - **LOW (0):** None.
  - **N/A (2):** R-16, R-17 (deferred to pre-deployment checklist).

### 4. T3: Error-Code Coverage (P3)
- Opened and parsed the full official WhatsApp Cloud API error-codes reference (`https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes`).
- Enumerated **73 total codes** across all relevant categories (authorization, throttling, integrity, send-message, template, media, account/phone, payment):
  - **`RETRY_SAFE` (4):** `4`, `80007`, `130429`, `131056`.
  - **`OUTCOME_UNKNOWN` (7):** `1`, `2`, `131000`, `131016`, `131052`, `133004`, `134102`.
  - **`OPERATOR_ACTION` (39):** `0`, `3`, `10`, `33`, `190`, `200`, `299`, `368`, `130403`, `130497`, `131005`, `131031`, `131037`, `131042`, `131045`, `131048`, `131049`, `131057`, `131063`, `131064`, `132001`, `132007`, `132015`, `132016`, `132068`, `132069`, `133000`, `133005`, `133006`, `133008`, `133009`, `133010`, `133015`, `133016`, `134011`, `134101`, `1752041`, `2388019`, `2388039`.
  - **`PERMANENT` (23):** `100`, `130472`, `131008`, `131009`, `131021`, `131026`, `131047`, `131050`, `131051`, `131053`, `131055`, `132000`, `132005`, `132012`, `132018`, `134100`, `135000`, `2388040`, `2388047`, `2388072`, `2388073`, `2388293`, `2388299`.
  - **`UNKNOWN` (0):** Covered by default class `OUTCOME_UNKNOWN`.
- Verified specific audit categories:
  - Template codes: complete coverage across `132xxx` and `2388xxx` families.
  - Parameter count/format mismatches: `132000` (count mismatch), `132012` (format mismatch), `132018` (parameter validation).
  - Engagement & quality-based blocks: `131049` (ecosystem engagement), `131048` (spam restrictions), `131064` (template classification penalty), `132015` (template paused), `132016` (template disabled).
  - Re-engagement / window: `131047` (freeform blocked >24h).
  - Recipient allowlist: The official error codes page does not document a standalone "recipient not on allowlist" code; in development sandbox, unverified recipients trigger `131026` or `100`, while code `10` covers allowlisting for Flows public keys.

### 5. T4: Graph API Expiry Rule Verification (P4)
- Re-opened `https://developers.facebook.com/docs/graph-api/changelog` and `https://developers.facebook.com/docs/graph-api/guides/versioning`.
- **Exact Quotes Recorded:**
  - Changelog table availability row: `v21.0 | October 2, 2024 | January 21, 2027`.
  - Versioning guide lifecycle rule: `"Each version is guaranteed to operate for at least two years. A version will no longer be usable two years after the date that the subsequent version is released."`
- **Operative Rule:** The changelog table uses Rule 2 (two years after subsequent version `v22.0` release on January 21, 2025 -> January 21, 2027) as its operative sunset date.
- **Computed Dates Comparison:**
  - Rule 1 (2 years from own release 2024-10-02): `2026-10-02` (expired 18 days ago relative to 2026-10-20).
  - Rule 2 (2 years from subsequent release 2025-01-21): `2027-01-21` (~93 days remaining).
- **Conclusion:** `STALE` under both rules (expired past base guarantee; ~93 days to final sunset).

### 6. T5: Spot-Check Claims (P6)
1. **OGG/Opus Audio Constraints:** Fetched `https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media`. Stated constraint: `audio/ogg (OPUS codecs only; base audio/ogg not supported; mono input only)`. Channels ("mono input only") is **EXPLICITLY CONFIRMED**. Sampling rate ("48 kHz") is **NOT STATED** on Meta documentation (inferred from Opus RFC 7845 / FFmpeg convention); downgraded to `MEDIUM`.
2. **Webhook Retry Policy & Duration:** Fetched `https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks` (Section "Webhooks > Retries"). Stated policy: `"Meta retries delivery with decreasing frequency until the request succeeds, for up to 7 days... These retries can result in duplicate webhook notifications."` **CORRECTED** previous 36-hour claim (from generic Graph API) to **up to 7 days**.
3. **Messaging Tiers & Starting Limit:** Fetched `https://developers.facebook.com/docs/whatsapp/messaging-limits`. Stated: Newly created portfolios start at **250** unique users / 24h. Scaling progression: **2,000** (scaling path) -> **10,000** (automatic) -> **100,000** (automatic) -> **Unlimited** (automatic). Deprecation of `messaging_limit_tier` in favor of `whatsapp_business_manager_messaging_limit` **100% CONFIRMED**.
4. **Latest Graph API Version:** Fetched `https://developers.facebook.com/docs/graph-api/changelog`. Version `v26.0` released on `July 29, 2026` is **100% CONFIRMED**.

### 7. T6: Consistency & Decision Tracking (P5)
- **UNVERIFIED Inventory:** Listed every UNVERIFIED item by ID in one explicit section:
  1. `R-16`: Indian Carrier SMS via TRAI DLT Framework (deferred to `docs/PRE_DEPLOYMENT_CHECKLIST.md`, Item C-04).
  2. `R-17`: India DPDP Act, 2023 Section 9 parental consent & children's data compliance (deferred to `docs/PRE_DEPLOYMENT_CHECKLIST.md`, Items C-01, C-02, C-03).
  3. `R-03 (institutional part)`: Deploying school institutional KYC, Meta Business Manager account verification, and active payment method setup (unverified pending institution onboarding).
- **Row-Level Summary:** Total rows = 17 (12 HIGH, 3 MEDIUM, 0 LOW, 2 N/A). Total UNVERIFIED = 3.
- **Decision Tracking (`docs/DECISIONS_OPEN.md`):** Maintained Item 5 (`D-09 / Architecture: Pinned Meta Graph API Version Upgrade`) as an open `OWNER-CONFIRM` decision; added explicit timing note: "The choice of API version must be confirmed by the owner before Stage S9 execution begins, and S9 contract test fixtures (`tests/fixtures/provider_contract/**`) must record the exact API version used."

### 8. T7: Verification Commands & Artifact Hashes
- JSON Schema Validation:
  - Command: `python -c "import json; json.load(open('docs/research/provider_contract.json', encoding='utf-8'))"`
  - Exit Code: `0`
- Linter Check:
  - Command: `ruff check .`
  - Exit Code: `0`
- Guardrail Check:
  - Command: `python scripts/guardrails.py`
  - Exit Code: `0`
- Git Diff Scope Check:
  - Command: `git diff --name-status`
  - Exit Code: `0`
  - Files modified strictly within SCOPE:
    - `M docs/DECISIONS_OPEN.md`
    - `M docs/STATE.md`
    - `M docs/prompt_pack/S9.md`
    - `M docs/research/official_source_verification.md`
    - `M docs/research/provider_contract.json`

---

## Active Operator Decisions Awaiting Confirmation (`docs/DECISIONS_OPEN.md`)
1. **D-04:** PTM slip requirement for bottom quartile in all-GREEN batches (`OWNER-CONFIRM`).
2. **D-11:** Parent confirmation QR token TTL default 72h (`OWNER-CONFIRM`).
3. **D-11:** Primary guardian OTP challenge channel: WhatsApp Authentication Template vs Indian SMS (`OWNER-CONFIRM`).
4. **D-12:** Display of class topper score on parent-facing report card (`OWNER-CONFIRM`).
5. **D-09 / Architecture:** Pinned Meta Graph API Version Upgrade (`STALE v21.0` -> `v26.0` recommended; decision required before S9) (`OWNER-CONFIRM`).
