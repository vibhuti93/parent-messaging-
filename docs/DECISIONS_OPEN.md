# Open Architectural & Business Decisions (DECISIONS_OPEN.md)

This document tracks items tagged `OWNER-CONFIRM`, requirement ambiguities, and deferred pre-deployment checklists per Part C Rule 3. No unapproved business-rule changes are permitted.

---

# Part 1: Active Decisions Awaiting Owner Confirmation

## 1. D-04: Bottom-Quarter PTM Rule for All-Green Batches (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  D-04 states: `PTM slip required iff ABSENT, or RED, or rank > floor(0.75 * present_count). OWNER-CONFIRM: bottom-quarter rule applies even when a whole batch is GREEN.`  
  In a high-performing batch where every student achieves > 60% net score (GREEN status), does the bottom quartile still receive a mandatory PTM summons?
* **Minimum Safe Resolution (Current Proposal):**  
  Apply the mathematical rule `rank > floor(0.75 * present_count)` strictly to all present students, ensuring deterministic behavior identical to the golden contract. PTM slips are generated for the bottom quartile regardless of status band unless explicitly disabled in batch policy.
* **Status:** Pending Owner Confirmation before S1 freeze.

---

## 2. D-11: Parent Confirmation (QR) Token TTL (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  D-11 proposes a default TTL of 72 hours for the single-use QR acknowledgment token. Parents receiving reports Sunday night at 20:30 IST would see the token expire Wednesday evening at 20:30 IST.
* **Minimum Safe Resolution (Current Proposal):**  
  Implement token TTL as an environment configuration parameter `QR_TOKEN_TTL_HOURS`, defaulting to 72 hours, with hard minimum of 12 hours and hard maximum of 168 hours (7 days).
* **Status:** Pending Owner Confirmation before S1 freeze.

---

## 3. D-11: Guardian OTP Delivery Channel (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  D-11 requires OTP challenge to the already verified guardian number, with channel tagged `OWNER-CONFIRM (WhatsApp authentication template vs SMS; deferred to pre-deployment checklist)`.
* **Minimum Safe Resolution (Current Proposal):**  
  Primary OTP delivery channel: WhatsApp Authentication Template (`category: "authentication"`, `otp_type: "copy_code"`). Carrier SMS adapter is treated as an optional secondary plugin that remains dormant unless explicit `TRAI_DLT_PE_ID` and `TRAI_DLT_TEMPLATE_ID` credentials are provided. Carrier registration verification is deferred to pre-deployment.
* **Status:** Pending Owner Confirmation before S1 freeze.

---

## 4. D-12: Disclosure of Topper Score to Parents (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  D-12 states: `Own child's report + class average + topper score + rank "X out of N present". No other student's response-level data. OWNER-CONFIRM: topper score may be shown.`  
  Some educational institutions prefer displaying only class average to avoid excessive peer comparison.
* **Minimum Safe Resolution (Current Proposal):**  
  Include topper score as documented in golden fixtures (`expected_reports.json`), configurable via batch report template flag `show_topper_score` (defaulting to true for golden consistency).
* **Status:** Pending Owner Confirmation before S1 freeze.

---

## 5. D-09 / Architecture: Pinned Meta Graph API Version Upgrade (STALE v21.0) (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  The engine currently pins Meta Graph API `v21.0` via configuration (`WHATSAPP_CLOUD_API_VERSION=v21.0`). Official source verification on 2026-10-20 shows:
  - Graph API `v21.0` was released on 2024-10-02.
  - The 2-year base guarantee expired on 2026-10-02 (18 days ago).
  - On the official Meta Graph API changelog, `v21.0` availability is stated as ending on **January 21, 2027** (~93 days from 2026-10-20).
  - Calling an expired version causes Meta to automatically default requests to the next oldest available version, creating breaking change risks.
  - The official WhatsApp Cloud API documentation now references `v26.0` in its primary examples.
  - S9 contract fixtures must record the exact version used.
* **Candidate Versions from Official Documentation:**
  1. **`v21.0` (Current Pin):** Status: `STALE`. Retains current development baseline. Sunsets 2027-01-21 (~3 months remaining). Low immediate change, but requires forced migration shortly after deployment.
  2. **`v24.0`:** Released 2025-10-08; available until 2028-02-18 (~16 months remaining). Intermediate stable baseline.
  3. **`v25.0`:** Released 2026-02-18; available until 2028-07-29 (~21 months remaining). Stable and widely deployed.
  4. **`v26.0` (Recommended):** Released 2026-07-29; latest version referenced across current WhatsApp Cloud API documentation. Active for full 2+ year support lifecycle (until mid-2028).
* **Effect of Unpinning vs. Pinning:**
  - **Pinning (Recommended):** Keeps contracts predictable, ensures reproducible unit and contract test mocks, and shields the engine from unexpected breaking changes when Meta updates platform defaults. The version is configuration-driven (`WHATSAPP_CLOUD_API_VERSION`).
  - **Unpinning:** Floating versions or omitting the version in request URLs causes Meta to fall back to the oldest active version permitted for the app, creating silent failures when legacy versions sunset.
* **Current Research Status:** `v21.0` is past its two-year base guarantee (which expired October 2, 2026). Per the official Meta Graph API changelog table, `v21.0` remains usable until its stated end date of **`January 21, 2027`** (~93 days remaining). Any deployment after January 21, 2027 would break because retired versions fall back to the next oldest available version, risking breaking schema changes. The latest version on the changelog is `v26.0` (released July 29, 2026).
* **Status:** Pending Owner Confirmation before Stage S9 provider implementation. **Decision Timing:** The choice of API version must be confirmed by the owner before Stage S9 execution begins, and S9 contract test fixtures (`tests/fixtures/provider_contract/**`) must record the exact API version used.

---

## 6. ADR-0003: Institutional Tenancy Scope (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  The engine is initially commissioned for a single school batch. Should data models, schemas, and idempotency keys include an `org_id` / institutional tenant identifier from Day 1, or remain strictly single-tenant?
* **Minimum Safe Resolution (Current Proposal):**  
  Include `org_id: str` (defaulting to `"DEFAULT_INSTITUTION"` or school code) across all database models, dispatch tables, and composite idempotency keys from inception. Adding an institutional tenant identifier later requires migrating every table, foreign key, and unique constraint across the database.
* **Status:** Pending Owner Confirmation before Stage S1 / S2 freeze.

---

## 7. ADR-0007: Database Encryption at Rest (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  Sensitive student scores, PTM consultation requests, and masked contact records are stored in local SQLite WAL databases. Does development require application-level cryptographic database encryption (e.g. SQLCipher), or is host-level volume encryption sufficient?
* **Minimum Safe Resolution (Current Proposal):**  
  Rely on host operating system disk encryption (BitLocker on Windows, LUKS on Linux) for local development and offline test suites. Application-level database encryption (SQLCipher) is formally deferred to the pre-deployment compliance checklist (`docs/PRE_DEPLOYMENT_CHECKLIST.md`, Item P-04).
* **Status:** Pending Owner Confirmation before Stage S8 database implementation.

---

## 8. ADR-0010: Script Digit Policy in Hindi Parent Communications (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  Parent-facing messages, scorecards, and consultation slips are rendered in conversational Bolchal Hindi. Should numeric representations (scores, percentages, dates, ranks) display in standard Latin digits (`0, 1, 2, ... 9`) or Devanagari numerals (`०, १, २, ... ९`)?
* **Minimum Safe Resolution (Current Proposal):**  
  Use **Latin digits (`0-9`)** across all parent-facing Hindi text, scorecards, and PTM consultation slips (e.g. `"कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)"`). In modern Indian education, Latin numerals are universally recognized across all state and central boards, whereas Devanagari numerals cause misinterpretation among parents of varying literacy levels.
* **Status:** Pending Owner Confirmation before Stage S4 template freeze.

---

# Part 2: Deferred to Pre-Deployment (see docs/PRE_DEPLOYMENT_CHECKLIST.md)

## 9. D-13: Retention Policy & Statutory Compliance (`DEFERRED`)
* **Background:**  
  D-13 establishes the development default: student scans and reports for the active academic year; message/audit logs for 90 days (masked). Deletion on verified request.
* **Status:**  
  **DEFERRED TO PRE-DEPLOYMENT.** Tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md` (Items C-01 and C-03). Development and testing continue using synthetic data only. Prior to production deployment or handling real parent/student data, qualified legal counsel must confirm retention schedules and statutory consent mechanisms under India's DPDP Act, 2023.

---

# Part 3: Contradiction Check Result (Gate 0 / S0-R4)

* **Status:** **No contradictions found.**
* **Methodology:** Systematic cross-comparison of `PROJECT_SPEC.md` clauses D-01 through D-14, `AGENTS.md` (Rules 1–14), `docs/prompt_pack/` (`S0.md`–`S13.md`), and Foundation ADRs (ADR-0001 through ADR-0015).
* **Verification Details:**
  - Status bands (D-01), easy question thresholds (D-02), subject diagnosis priority ordering (D-03), and rank arithmetic (D-04, D-05) align exactly with ADR-0002 (integer marks, Fraction ratios, cross-multiplication, Decimal ROUND_HALF_UP).
  - Hindi wording rules and banned terms (D-06) align with Rule 14, S4, ADR-0010, and `scripts/guardrails.py`.
  - Palette colors and contrast (D-07) align with S5/S6 renderers and ADR-0011.
  - Audio duration (<45s) and token-stitch hierarchy (D-08) align with S7 audio engine and ADR-0011.
  - Scheduling (D-10) and live messaging default off (D-09) align with Rule 8, S0, S8, S9, ADR-0005 (Asia/Kolkata presentation, UTC storage), and ADR-0009.
  - Scale limit (D-14: <=200 students/batch) aligns with SQLite WAL concurrency limits in ADR-0007.
