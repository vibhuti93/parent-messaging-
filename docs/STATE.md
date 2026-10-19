# Project State & Execution Log (`docs/STATE.md`)

## Current Status
- **Active Stage:** Stage S0-R2 (`Stage S0-R2 — Re-verify provider facts`) — **COMPLETED**
- **Next Stage:** Stage 1 (`S1 — Golden Dataset and Independent Contract`) — **AWAITING HUMAN GATE**
- **Live Dispatch:** **DISABLED** (`LIVE_DISPATCH_ENABLED=false` and `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`)
- **Legal/Compliance:** **DEFERRED** (fully collected and tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md`)
- **Fixture Manifest SHA-256:** `N/A` (Staged for S1 generation)
- **Stage Tag:** `stage-0-r2` (tagged commit on `agent-run`)

---

## Operator-Approved Additions to Allowed Files
Per operator instructions for S0-R, Stage D, and S0-R2, the following files outside the original S0 list are approved:
1. `scripts/guardrails.py`: Automated W3 invariant checker (pre-commit hook).
2. `scripts/split_prompt_pack.py`: Prompt pack splitter script.
3. `.gitignore`: Virtualenv, cache, and artifact exclusions.
4. `.python-version`: Local Python interpreter pin (`3.12`).
5. `.gitattributes`: Line ending normalization (`* text=auto eol=lf`).
6. `docs/PRE_DEPLOYMENT_CHECKLIST.md`: Deferred compliance, legal review, and carrier registration tracking list.
7. `docs/research/provider_contract.json`: Machine-readable provider specifications, classified error codes, and rate limits for S9.

---

## Stage S0-R2 Execution Evidence (Provider Fact Re-Verification)

### 1. Step 0 Preconditions
- **Network Access Status:** Active (verified via live search queries to Meta developer documentation on 2026-10-20).
- **Current Shell Date:** `2026-10-20` (command: `Get-Date -Format yyyy-MM-dd` -> output: `2026-10-20`).

### 2. T1: Meta Graph API Version & Lifecycle Verification (P1)
- **Release Date of v21.0:** `2024-10-02`
- **Base 2-Year Guarantee Expiry:** `2024-10-02` + 2 years = `2026-10-02`
- **Current Shell Date:** `2026-10-20` (18 days past the 2-year guarantee)
- **Stated End-of-Availability on Meta Changelog:** `2027-01-21` (2 years after v22.0 release date; ~93 days remaining)
- **Current Reference in WhatsApp Cloud API Documentation:** `v26.0` (released 2026-07-29)
- **Stated Expiration Rule:** Calls to an expired version automatically default to the next oldest available version, risking breaking changes.
- **Conclusion:** **`STALE`** (past its 2-year base guarantee of 2026-10-02, and within ~93 days of final platform sunset on 2027-01-21).
- **Action Taken:** Pinned value in configuration (`WHATSAPP_CLOUD_API_VERSION=v21.0`) is retained per instructions; added `OWNER-CONFIRM` item 5 in `docs/DECISIONS_OPEN.md` proposing candidate upgrade versions (`v24.0`, `v25.0`, `v26.0`).

### 3. T2: Removal of False Certainty (P2)
- Added two mandatory columns to every row of the verification table: `Volatility` (`STABLE` / `VOLATILE`) and `Confidence` (`HIGH` / `MEDIUM` / `LOW`).
- Eliminated all occurrences of "None" in unresolved uncertainties across all rows.
- Assigned explicit recheck cadences to all `VOLATILE` rows (pricing: quarterly; messaging limits/tiers: quarterly; template categories: monthly; throughput: quarterly; error codes: quarterly; API versions: monthly).
- Corrected Customer Service Window row (R-02): removed "must use Utility templates", recorded that any approved template can be used outside 24h window, noted automatic category reclassification, and noted transition to Per-Message Pricing (PMP).
- Corrected Opt-In and Messaging Limits row (R-03): verified that limits apply at the Business Portfolio level (starting at 250 unique recipients/24h for new portfolios; scaling to 2,000, 10,000, 100,000, Unlimited), and noted deprecation of `messaging_limit_tier` in favor of `whatsapp_business_manager_messaging_limit`.
- Corrected Template Constraints row (R-09) and `docs/research/template_constraints.json`: added quick reply button limits (max 3, 25 chars), call-to-action button limits (max 2, 25 chars), template name constraints (max 512 chars, `^[a-z0-9_]+$`), and header media constraints.
- Corrected Webhook row (R-14): removed engineering design choice "Idempotent deduplication on (wamid, status)" from source findings and relocated it to `docs/architecture_decisions.md`.

### 4. T3: Addition of Missing Provider Topics (P3)
- Added dedicated rows in Master Verification Table:
  1. Template approval categories, review statuses, rejection triggers, and automatic reclassification (R-06).
  2. Billing & Per-Message Pricing (PMP) model and payment method prerequisites (R-05).
  3. Phone display name approval and 7-day rolling quality rating impact on messaging tiers (R-04).
  4. Rate limits: 80 mps default phone throughput, portfolio messaging tiers (250..Unlimited), per-recipient pair rate limit error 131056, throughput error 130429 (R-10).
  5. Error codes: 13 documented sending/media codes classified (R-11).
  6. Retry guidance: exponential backoff with jitter, Retry-After header, and Meta webhook delivery retry policy (36h exponential retry, non-200 / >3s timeout criteria) (R-12).
  7. Idempotency: documented as "no documented guarantee"; Meta Cloud API does NOT support idempotency keys; client-side state machine required (R-13).
  8. Webhook status semantics: `sent`, `delivered`, `read`, `failed`; `read` implies `delivered`; non-FIFO delivery requiring timestamp sorting; duplicate webhook handling (R-14).
  9. Media upload limits (Image 5MB, Audio 16MB, Document 100MB, Video 16MB), 30-day media ID lifetime, and 5-minute download URL expiration (R-15).
- Created machine-readable contract `docs/research/provider_contract.json` with 13 classified error codes:
  - **`TRANSIENT` (5):** 190, 130429, 80007, 131000, 131056.
  - **`PERMANENT` (7):** 100, 131026, 131047, 131048, 131051, 131053, 130472.
  - **`UNKNOWN` (1):** 131052.

### 5. T4: Gap and Coverage Audit
- **Re-read S0 Verification Topics in `docs/prompt_pack/S0.md`:** 100% of required topics covered across rows R-01 through R-17.
- **Before vs After Counts:**
  - Table Rows: Before = 9, After = 17 (expanded by 8 topics).
  - Rows with Non-Empty Uncertainty: Before = 4, After = 17 (100% compliant, zero rows contain "None").
  - Rows UNVERIFIED: Before = 2, After = 2 (R-16 TRAI DLT, R-17 DPDP Act; both formally deferred to pre-deployment checklist by operator; institutional KYC in R-03 unverified pending school onboarding).

### 6. Files Changed in S0-R2
1. `docs/research/official_source_verification.md`: Complete re-verification, master table (17 rows), explicit uncertainties.
2. `docs/research/template_constraints.json`: Added button, name, and header media constraints.
3. `docs/research/provider_contract.json`: New machine-readable provider contract with 13 classified error codes.
4. `docs/architecture_decisions.md`: Documented webhook idempotency and deduplication design choice.
5. `docs/DECISIONS_OPEN.md`: Added item 5 for Graph API version upgrade; renumbered item 6.
6. `docs/STATE.md`: Recorded S0-R2 evidence, audit metrics, and stage status.

---

## Active Operator Decisions Awaiting Confirmation (`docs/DECISIONS_OPEN.md`)
1. **D-04:** PTM slip requirement for bottom quartile in all-GREEN batches (`OWNER-CONFIRM`).
2. **D-11:** Parent confirmation QR token TTL default 72h (`OWNER-CONFIRM`).
3. **D-11:** Primary guardian OTP challenge channel: WhatsApp Authentication Template vs Indian SMS (`OWNER-CONFIRM`).
4. **D-12:** Display of class topper score on parent-facing report card (`OWNER-CONFIRM`).
5. **D-09 / Architecture:** Pinned Meta Graph API Version Upgrade (`STALE v21.0` -> `v26.0` recommended) (`OWNER-CONFIRM`).
