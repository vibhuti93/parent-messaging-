# Privacy & Security Architecture

**System:** `omr_dispatch_engine`  
**Classification:** Educational Minor Data (DPDP Act, 2023 Section 9 Scope)  
**Date:** 2026-10-20  
**Stage:** S0 (Discovery, Contracts, Source Verification)

---

## 1. Regulatory Context & Threat Model

### 1.1 Regulatory Scope
Under Section 9 of India's Digital Personal Data Protection (DPDP) Act, 2023, personal data of individuals under 18 years of age requires verifiable parental consent before processing. Data fiduciaries are prohibited from engaging in tracking, behavioural monitoring, or harmful processing.

### 1.2 Core Threats & Mitigations
1. **Interception by Minor:** A student provides their own phone number as the parent's contact to intercept negative exam reports.  
   *Mitigation:* Pre-dispatch contact hygiene flags identical student/parent numbers (`INTERCEPTION_RISK_SAME_NUMBER`) and blocks dispatch.
2. **Unauthorized Disclosure:** Sibling numbers or shared family numbers receive unrelated student reports.  
   *Mitigation:* Multiple students sharing a parent number without verified sibling status are flagged `DUPLICATE_PARENT_UNVERIFIED` and quarantined.
3. **Log Exposure:** Cloud log collectors or developers view student phone numbers, marks, or audio notes.  
   *Mitigation:* Automatic sanitization masks phone numbers, names, scores, tokens, and audio binaries across all log handlers.
4. **Token Hijacking & QR Tampering:** Physical PTM slips with QR codes are photographed or intercepted by peers.  
   *Mitigation:* QR tokens are high-entropy random secrets, stored hashed in SQLite, single-use, rate-limited to 5 attempts, and require OTP challenge to the registered guardian.
5. **Webhook Spoofing:** Rogue actors send fake delivery or read confirmations.  
   *Mitigation:* Webhook endpoint enforces constant-time HMAC SHA-256 signature verification (`X-Hub-Signature-256`) against Meta's `APP_SECRET`.

---

## 2. Data Minimization & Consent Invariants

* **Rule 9 (AGENTS.md):**  
  > "Never infer consent, guardian identity, or sibling status from a spreadsheet value or surname. A non-empty phone number is not consent."
* **Rules Enforced in Code:**
  1. A contact number alone does not permit dispatch. Consent must be explicitly recorded as `OPT_IN`. Any other value (`UNKNOWN`, `REVOKED`) blocks dispatch.
  2. Guardian relationship must be explicitly `VERIFIED`. An unverified guardian record blocks dispatch.
  3. Shared surnames or shared addresses do not constitute verified sibling status; `verified_sibling=true` must be explicitly authenticated in student admissions data.

---

## 3. Masking & Redaction Standards (Rule 10)

All console output, file logs, and telemetry must mask sensitive fields before emission. Raw sensitive values must never appear in production logs.

| Sensitive Field | Raw Example | Masked Log Representation | Masking Rule |
| :--- | :--- | :--- | :--- |
| **Indian Phone Number** | `+919811122201` | `+91 98*** **201` | Keep country code, first 2 digits, last 3 digits; mask middle 5 digits. |
| **Student Name** | `Aarav Sharma` | `Aa*** Sh***` | First 2 letters of each token, remaining masked with asterisks. |
| **Test Scores & Marks** | `55 / 300` | `[SCORE_MASKED]` | Omit raw numerical scores from operational logs. |
| **QR Acknowledgment Token**| `tok_8f93a...` | `sha256:d4e7...` | Log only first 8 chars of SHA-256 hash. |
| **Audio Note Payload** | Binary / Base64 | `[AUDIO_OPUS_18s_SHA256:ab12...]` | Log duration and audio hash; never dump payload bytes. |

---

## 4. Retention Policy & Automated Purging (D-13)

* **Student Scans & Scorecards:** Retained for the duration of the active academic year. At year end, an archival purge permanently removes rendered PNGs, cropped OMR bubbles, and PTM PDFs.
* **Dispatch Logs & Webhook Events:** Retained for a rolling **90 days** in masked format.
* **Automated TTL Purge:** A background worker runs weekly to delete audit records older than 90 days and unlink orphaned media files.
* **Right to Erasure (Verified Deletion):** Upon receipt of an authenticated guardian deletion request, all records matching the student ID are purged within 72 hours, unless an explicit statutory legal hold applies.

---

## 5. Secret Management & Access Controls

* **Zero Secrets in Code:** `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `FACEBOOK_APP_SECRET`, and `QR_HMAC_SECRET` are read exclusively from environment variables.
* **Git Guardrails:** `scripts/guardrails.py` runs on pre-commit to reject private keys, access tokens, or API key assignments.
* **Least Privilege:** Production dispatches run under a non-root system account with read-only access to source code and write access restricted to SQLite database and temporary render directories.

---

## 6. Incident Response & Emergency Procedures

1. **Emergency Kill-Switch:** Setting `LIVE_DISPATCH_ENABLED=false` in the runtime environment immediately stops all outbound WhatsApp API requests. The engine shifts to offline queuing mode.
2. **Credential Revocation:** If an API token or App Secret is compromised, the operator revokes the token in Meta App Dashboard, updates environment variables, and restarts the engine.
3. **Data Spill Remediation:** If unmasked personal data is inadvertently logged, the log file is immediately rotated, scrubbed, and audited. An incident report is recorded in `docs/reviews/`.
