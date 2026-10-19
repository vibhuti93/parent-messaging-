# Project State & Execution Log (`docs/STATE.md`)

## Current Status
- **Active Stage:** Stage D (`Stage D — Defer legal/compliance gates to pre-deployment`) — **COMPLETED**
- **Next Stage:** Stage 1 (`S1 — Golden Dataset and Independent Contract`) — **AWAITING HUMAN GATE**
- **Live Dispatch:** **DISABLED** (`LIVE_DISPATCH_ENABLED=false` and `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`)
- **Legal/Compliance:** **DEFERRED** (fully collected and tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md`)
- **Fixture Manifest SHA-256:** `N/A` (Staged for S1 generation)
- **Stage Tag:** `stage-d` (tagged release on `agent-run`)

---

## Operator-Approved Additions to Allowed Files
Per operator instructions for S0-R and Stage D, the following files outside the original S0 list are approved:
1. `scripts/guardrails.py`: Automated W3 invariant checker (pre-commit hook).
2. `scripts/split_prompt_pack.py`: Prompt pack splitter script.
3. `.gitignore`: Virtualenv, cache, and artifact exclusions.
4. `.python-version`: Local Python interpreter pin (`3.12`).
5. `.gitattributes`: Line ending normalization (`* text=auto eol=lf`).
6. `docs/PRE_DEPLOYMENT_CHECKLIST.md`: Deferred compliance, legal review, and carrier registration tracking list.

---

## Stage D Execution Evidence

### 1. Summary of Stage D Edits
1. **Created `docs/PRE_DEPLOYMENT_CHECKLIST.md`:**
   - Status of all items: `NOT STARTED (deferred by operator, 2026-10-20)`.
   - Collects DPDP Act & Rules legal review (C-01), counsel-approved privacy notice and consent wording (C-02), retention period confirmation (C-03), carrier SMS TRAI DLT registration (C-04), Meta business verification & phone setup (P-01), template approvals (P-02), official-source re-verification W5 (P-03), and signed launch checklist W8 (P-04).
   - Top banner clearly states project is NOT cleared for deployment or real data until every item is closed.
2. **Updated `PROJECT_SPEC.md`:**
   - D-11: Dropped SMS registration verification from development path, added `(deferred to pre-deployment checklist)`. Tagged `OWNER-CONFIRM` preserved.
   - D-13: Updated from `(proposal only, needs legal review)` to `(development default; legal review deferred, see docs/PRE_DEPLOYMENT_CHECKLIST.md)`.
   - All other decisions, numbers, and thresholds preserved verbatim.
3. **Updated `docs/research/official_source_verification.md`:**
   - Section 8 (TRAI DLT) and Section 9 (DPDP Framework) marked `UNVERIFIED — DEFERRED to pre-deployment (see checklist)`. Research text and citations preserved.
4. **Updated `docs/DECISIONS_OPEN.md`:**
   - D-13 retention legal review moved to Part 2 ("Deferred to Pre-Deployment").
   - Four active `OWNER-CONFIRM` items (D-04 all-green PTM rule, D-11 QR TTL, D-11 OTP delivery channel, D-12 topper score disclosure) remain open for operator confirmation in Part 1.
5. **Updated `docs/prompt_pack/S0.md`:**
   - DPDP and carrier SMS registration verification items marked `deferred, record in checklist only`.
   - Removed `release-blocking, needing documented legal review` from development stage.
6. **Updated `docs/prompt_pack/S12.md`:**
   - Added requirement that CLI `send` and any live provider call refuse to run unless BOTH `LIVE_DISPATCH_ENABLED=true` AND `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=true`.
7. **Updated `docs/prompt_pack/S13.md`:**
   - Replaced development release blocker on legal review with requirement: `Before any real deployment, close every item in docs/PRE_DEPLOYMENT_CHECKLIST.md.`
8. **Updated `.env.example`:**
   - Added `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false` with comment `# must stay false until docs/PRE_DEPLOYMENT_CHECKLIST.md is fully closed`.
9. **Updated `README.md`:**
   - Added Section 2 "Deployment Status & Compliance Safeguards" documenting that development uses synthetic data only, deployment is blocked until the checklist is closed, and explaining the dual-switch technical gate.
10. **Updated `docs/privacy_and_security.md` & `docs/architecture_inventory.md`:**
    - Documented deferral of legal review to `docs/PRE_DEPLOYMENT_CHECKLIST.md` while keeping engineering safeguards active.

### 2. Technical Safeguards Kept Active (Non-Negotiable)
- `LIVE_DISPATCH_ENABLED=false` default preserved.
- `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false` dual-switch enforced.
- Contact hygiene and quarantine logic (Rule 9, S8).
- Log masking across console, logs, and traces (Rule 10).
- Pure synthetic data only for development and testing (Rule 11).
- Pinned Meta API version (`WHATSAPP_CLOUD_API_VERSION=v21.0`), hardcoded versions banned.
- Monotonically non-decreasing test count and fixture hash integrity guardrails.

### 3. Open Decisions Awaiting Operator Confirmation (`docs/DECISIONS_OPEN.md`)
1. **D-04:** PTM slip requirement for bottom quartile in all-GREEN batches (`OWNER-CONFIRM`).
2. **D-11:** Parent confirmation QR token TTL default 72h (`OWNER-CONFIRM`).
3. **D-11:** Primary guardian OTP challenge channel: WhatsApp Authentication Template vs Indian SMS (`OWNER-CONFIRM`).
4. **D-12:** Display of class topper score on parent-facing report card (`OWNER-CONFIRM`).
