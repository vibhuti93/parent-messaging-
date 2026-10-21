# Pre-Deployment Regulatory & Compliance Checklist

**Status:** Deferred by the operator. The project is NOT cleared for deployment or for real student/parent data until every item is closed.
**Date Deferred:** 2026-10-20
**Governing Rule:** Development and automated testing proceed exclusively using synthetic test fixtures. All legal reviews, regulatory registrations, and production account clearances are strictly gated behind this pre-deployment checklist.

---

## 1. Compliance & Legal Review Items

| # | Item Description | Status | Verification Requirement & Primary Source Criteria |
| :- | :--- | :---: | :--- |
| **C-01** | **India DPDP Act & Rules Legal Review** | `NOT STARTED (deferred by operator, 2026-10-20)` | Formal legal counsel review of India's Digital Personal Data Protection Act, 2023 (Act No. 22 of 2023) and notified DPDP Rules, 2025 specifically addressing: (a) processing of children's data (<18 years), (b) technical mechanism for verifiable parental/guardian consent, (c) applicable exemptions (if any) for recognized educational institutions, (d) statutory retention limits, (e) verified deletion protocols, and (f) data fiduciary / data processor contracts. Official sources to cite: Gazette of India Act texts and MeitY notifications. |
| **C-02** | **Privacy Notice & Consent Formulation** | `NOT STARTED (deferred by operator, 2026-10-20)` | Plain-language Hindi and English privacy notice, consent capture mechanisms, and opt-in / revocation wording formally reviewed and approved by qualified legal counsel. |
| **C-03** | **Data Retention Schedule Confirmation** | `NOT STARTED (deferred by operator, 2026-10-20)` | Legal counsel review confirming the data retention schedule in D-13 (current academic year for student scans and scorecards; 90-day masked audit and dispatch logs). |
| **C-04** | **Carrier SMS Regulatory Prerequisites (TRAI DLT)** | `NOT STARTED (deferred by operator, 2026-10-20)` | If carrier SMS is used as a secondary OTP fallback channel under D-11: complete Principal Entity (PE) registration on an Indian telecom DLT portal under TRAI TCCCPR 2018; register institutional 6-character Header (Sender ID); submit and approve SMS content templates with explicit `{#var#}` placeholders; execute PE-TM binding with SMS gateway. (Remains dormant if WhatsApp Authentication Templates are used exclusively). |

---

## 2. Platform & Production Account Prerequisites

| # | Item Description | Status | Verification Requirement & Primary Source Criteria |
| :- | :--- | :---: | :--- |
| **P-01** | **Meta Business Verification & WhatsApp Phone ID** | `NOT STARTED (deferred by operator, 2026-10-20)` | Institutional Meta Business Manager account verification completed; official institutional phone number registered and assigned a live Phone Number ID; payment method attached to establish production messaging tier. |
| **P-02** | **Message Template Approval** | `NOT STARTED (deferred by operator, 2026-10-20)` | Utility category message templates for scorecards, PTM notifications, and Authentication templates for OTP verification submitted to Meta and approved in the WhatsApp Business Manager. |
| **P-03** | **Official-Source Re-Verification (W5)** | `NOT STARTED (deferred by operator, 2026-10-20)` | Prior to deployment, re-run official-source verification across Meta developer endpoints, TRAI regulations, and MeitY notices. All items marked `UNVERIFIED` in `docs/research/official_source_verification.md` must be resolved with current URLs, retrieval dates, and documentation. |
| **P-04** | **Signed Launch Checklist & Canary Rollout (W8)** | `NOT STARTED (deferred by operator, 2026-10-20)` | Human sign-off of the complete pre-deployment verification report; execution of a phased canary dispatch batch under live supervision; confirmation that `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=true` is set only after all checklist items are closed. |

---

## 3. Items Moved Out of Development Path in Stage D

The following items were removed from active development gates and transferred to this checklist per operator authorization:

1. **PROJECT_SPEC.md (Line 44, D-13):**
   - *Original text:* `**D-13 Retention (proposal only, needs legal review).**`
   - *Transferred item:* Legal review of retention schedules transferred to Item **C-03** above.
2. **PROJECT_SPEC.md (Line 40, D-11):**
   - *Original text:* `S0 must verify prerequisites, including any Indian SMS registration requirements`
   - *Transferred item:* Indian carrier SMS TRAI DLT verification transferred to Item **C-04** above.
3. **docs/prompt_pack/S0.md (Line 20):**
   - *Original text:* `India's DPDP framework: current legal texts, commencement/rules status, children's-data and guardian-consent requirements. Treat as release-blocking, needing documented legal review. Do not claim compliance.`
   - *Transferred item:* DPDP legal review requirement transferred to Item **C-01** above.
4. **docs/prompt_pack/S0.md (Line 19):**
   - *Original text:* `OTP delivery options for guardian verification (authentication templates vs SMS) and any Indian SMS registration prerequisites;`
   - *Transferred item:* SMS registration verification transferred to Item **C-04** above.
5. **docs/prompt_pack/S13.md (Line 8, W8):**
   - *Original text:* Release blocker gate on legal/DPDP review recorded.
   - *Transferred item:* Development blocker replaced by pre-deployment checklist closure verification (Item **P-04**).
6. **docs/DECISIONS_OPEN.md (Section 5):**
   - *Original text:* `D-13: Retention Policy & DPDP Alignment (LEGAL REVIEW REQUIRED)`
   - *Transferred item:* Moved to "Deferred to pre-deployment" section in `docs/DECISIONS_OPEN.md`.
7. **docs/research/official_source_verification.md (Sections 8 & 9):**
   - *Original text:* Active development release blockers for TRAI DLT readiness and DPDP institutional sign-off.
   - *Transferred item:* Marked `UNVERIFIED — DEFERRED to pre-deployment (see checklist)`.

---

## 4. Multi-Tenant Service & School Governance Prerequisites (Stage S0-R5 Additions)

The following operational, legal, and security items govern the hosted multi-school deployment and must be completed prior to production launch:

| # | Item Description | Status | Verification Requirement & Primary Source Criteria |
| :- | :--- | :---: | :--- |
| **P-05** | **Data-Processing Agreements (DPA) & Defined Roles** | `NOT STARTED` | Formal Data Processing Agreement executed with each participating educational institution, explicitly defining statutory roles under India's DPDP Act, 2023 (School = Data Fiduciary / Controller; SaaS Platform = Data Processor), specifying data processing purposes, security safeguards, sub-processor disclosures, and mandatory breach notification timelines. |
| **P-06** | **Per-School WhatsApp Business Setup & Template Approval** | `NOT STARTED` | Provisioning and verification of dedicated WhatsApp Business Account (WABA), official phone number ID, verified institutional display name (`VERIFIED_NAME`), and pre-approval of utility templates for each onboarded school in Meta Business Manager. |
| **P-07** | **Meta Multi-Business Onboarding Architecture (UNVERIFIED)** | `NOT STARTED` | Official verification and legal resolution of Meta multi-business onboarding architecture (R-03, ADR-0019): confirm whether schools onboard via Meta Tech Provider / Partner Onboarding API, whether a single Meta App can receive webhooks from multiple distinct client WABAs, and determine token issuance/refresh lifecycles. |
| **P-08** | **Meta Billing Responsibility & Liability (Who Pays Meta)** | `NOT STARTED` | Formal operational resolution of WhatsApp Per-Message Pricing (PMP) payment responsibility: confirm whether each school attaches its own institutional credit card directly in its Meta Business Manager account, or if the platform acts as an authorized WhatsApp solution provider managing consolidated billing with appropriate liability agreements. |
| **P-09** | **Per-School Cost Allocation & Metering** | `NOT STARTED` | Implementation and verification of automated per-school message metering and cost allocation reports reconciling monthly platform-delivered template counts against Meta billing invoices. |
| **P-10** | **Multi-Tenant Hosting, Backups, and Incident Response** | `NOT STARTED` | Production deployment on managed PostgreSQL with automated point-in-time recovery (PITR), off-site encrypted backups, tenant-filtered logical restore tooling, 99.9% uptime SLA monitoring, and a 24/7 security incident response runbook. |
| **P-11** | **Pre-Launch Cross-Tenant Isolation Test with External Review** | `NOT STARTED` | Independent third-party security audit and penetration test validating: (a) PostgreSQL Row-Level Security (RLS) enforcement, (b) repository-level tenant context gating, (c) webhook routing isolation by `phone_number_id`, and (d) zero cross-tenant data leakage under concurrent batch execution (ADR-0017). |
