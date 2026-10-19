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
* **Status:** Pending Owner Confirmation before S9 provider implementation.

---

# Part 2: Deferred to Pre-Deployment (see docs/PRE_DEPLOYMENT_CHECKLIST.md)

## 6. D-13: Retention Policy & Statutory Compliance (`DEFERRED`)
* **Background:**  
  D-13 establishes the development default: student scans and reports for the active academic year; message/audit logs for 90 days (masked). Deletion on verified request.
* **Status:**  
  **DEFERRED TO PRE-DEPLOYMENT.** Tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md` (Items C-01 and C-03). Development and testing continue using synthetic data only. Prior to production deployment or handling real parent/student data, qualified legal counsel must confirm retention schedules and statutory consent mechanisms under India's DPDP Act, 2023.

---

# Part 3: Contradiction Check Result (Gate 0)

* **Status:** **No contradictions found.**
* **Methodology:** Systematic cross-comparison of `PROJECT_SPEC.md` clauses D-01 through D-14 against:
  1. Global Invariants in `AGENTS.md` (Rules 1–14);
  2. Stage specifications in `docs/prompt_pack/` (`S0.md` through `S13.md`).
* **Verification Details:**
  - Status bands (D-01), easy question thresholds (D-02), subject diagnosis priority ordering (D-03), and rank arithmetic (D-04, D-05) align exactly with S1 golden contract and S2 diagnostics.
  - Hindi wording rules and banned terms (D-06) align with Rule 14, S4, and `scripts/guardrails.py`.
  - Palette colors and contrast (D-07) align with S7 scorecard renderer.
  - Audio duration (<45s) and token-stitch hierarchy (D-08) align with S8 audio engine.
  - Scheduling (D-10) and live messaging default off (D-09) align with Rule 8, S0, and S9 messaging policy.
  - Scale limit (D-14: <=200 students/batch) aligns with SQLite durable store concurrency limits in `docs/architecture_decisions.md`.
