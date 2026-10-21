# Data Inventory & Field-Level Privacy Map (`docs/data_map.md`)

This document enumerates every data field ingested, processed, stored, or logged by the `omr_dispatch_engine`.
It defines the PII classification, operational purpose, development retention lifecycle (per spec **D-13**), logger redaction policy, and automated deletion behavior.

> [!NOTE]
> All retention periods recorded herein represent **development defaults** per project specification D-13. Formal statutory legal compliance under the Digital Personal Data Protection Act, 2023 (DPDP) is deferred to the pre-deployment checklist ([docs/PRE_DEPLOYMENT_CHECKLIST.md](PRE_DEPLOYMENT_CHECKLIST.md)). This document contains technical engineering controls only and makes no formal legal claims.

---

## 1. PII Classification Tiers

- **`DIRECT_PII`**: Information that directly identifies an individual student or guardian (e.g. raw phone numbers, full names, unhashed tokens).
- **`INDIRECT_PII`**: Information that could identify a student when linked with external institutional datasets (e.g. roll numbers, section IDs, student ID).
- **`CONFIDENTIAL_EDUCATIONAL`**: Academic evaluation records, raw exam responses, diagnostic classifications, and scorecard assets.
- **`OPERATIONAL_SYSTEM`**: Machine-level technical telemetry, status codes, timestamps, and error categories containing zero personal information.

---

## 2. Field-Level Inventory

### 2.1 Student Roster & Admission Records (`StudentAdmissionRow`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `student_id` | `str (UUID)` | `INDIRECT_PII` | Opaque surrogate primary key for cross-module correlation. | Current academic year | `ALLOWED` | Deleted on student profile purge. |
| `org_id` | `str` | `OPERATIONAL_SYSTEM` | Institutional tenant isolation. | Current academic year | `ALLOWED` | Deleted on tenant purge. |
| `roll_number` | `str` | `INDIRECT_PII` | School-assigned identifier for student recognition on scorecards/slips. | Current academic year | `MASKED` | Deleted on academic year expiry. |
| `student_name` | `str` | `DIRECT_PII` | Official student name for archival records and PTM consultation slips. | Current academic year | `NEVER` in clear; `MASKED` in logs | Hard deleted on consent revocation. |
| `child_display_name`| `str` | `DIRECT_PII` | Personalization of parent WhatsApp messages and scorecards. NFC normalized. | Current academic year | `NEVER` in logs | Hard deleted on consent revocation. |
| `class_section` | `str` | `INDIRECT_PII` | Cohort descriptor appearing in message body and scorecard. | Current academic year | `NEVER` in logs (masked if linked) | Deleted on academic year expiry. |
| `guardian_salutation` | `str` | `DIRECT_PII` | Respectful Hindi Bolchal salutation (e.g. "श्री राजेश शर्मा जी"). | Current academic year | `NEVER` in clear; `MASKED` in logs | Hard deleted on consent revocation. |
| `section` | `str` | `INDIRECT_PII` | Batch grouping and classroom teacher consultation. | Current academic year | `ALLOWED` | Deleted on academic year expiry. |

---

### 2.2 Contact Coordinates & Quarantine (`ContactRecord`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `guardian_phone_raw` | `str` | `DIRECT_PII` | Ingested parent phone number before normalization. | Ephemeral (discarded after ingestion) | `NEVER` | Overwritten in memory immediately. |
| `guardian_phone_e164` | `str` | `DIRECT_PII` | Normalized E.164 mobile number (`+91XXXXXXXXXX`) for WhatsApp send. | Current academic year (or consent revocation) | `MASKED` (`+91 98*** **321`) | Purged on consent revocation; deleted post-year. |
| `student_phone_e164` | `str` | `DIRECT_PII` | Student contact number used exclusively for interception check. | Current academic year | `MASKED` | Deleted on academic year expiry. |
| `quarantine_flags` | `list[str]` | `OPERATIONAL_SYSTEM` | Safety flags (`INTERCEPTION_RISK_SAME_NUMBER`, `DUPLICATE_PARENT_UNVERIFIED`). | Current academic year | `ALLOWED` | Deleted when quarantine resolved. |
| `is_quarantined` | `bool` | `OPERATIONAL_SYSTEM` | Binary dispatch safety gatekeeper flag. | Current academic year | `ALLOWED` | Updated on resolution. |

---

### 2.3 Consent & Governance Records (`ConsentRecord`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `consent_status` | `str (Enum)` | `OPERATIONAL_SYSTEM` | Consent state: `OPT_IN`, `OPT_OUT`, `REVOKED`, `UNKNOWN`. | Current academic year + 90 days audit | `ALLOWED` | Preserved in audit tombstone upon revocation. |
| `consent_scope` | `str` | `OPERATIONAL_SYSTEM` | Scope of authorization (e.g. `EXAM_RESULTS_WHATSAPP`). | Current academic year + 90 days audit | `ALLOWED` | Retained with consent record. |
| `consent_timestamp_utc`| `datetime` | `OPERATIONAL_SYSTEM` | Proof of timestamp when guardian opted in. | Current academic year + 90 days audit | `ALLOWED` | Retained for audit proof. |
| `consent_source` | `str` | `OPERATIONAL_SYSTEM` | Channel of consent capture (e.g. `PHYSICAL_FORM`, `PORTAL`). | Current academic year + 90 days audit | `ALLOWED` | Retained for audit proof. |
| `consent_reference` | `str` | `INDIRECT_PII` | Form reference or physical document ID. | Current academic year + 90 days audit | `MASKED` | Retained for audit proof. |
| `revocation_timestamp` | `datetime \| None`| `OPERATIONAL_SYSTEM` | Timestamp when consent was revoked by parent. | 90 days post-revocation | `ALLOWED` | Triggers immediate downstream send cancellation. |

---

### 2.4 Examination Metadata & Marking Scheme (`TestPaper`, `QuestionMeta`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `test_id` | `str` | `OPERATIONAL_SYSTEM` | Unique identifier of the test paper. | Current academic year | `ALLOWED` | Deleted with academic year archive. |
| `question_id` | `int` | `OPERATIONAL_SYSTEM` | Sequential question index (1 to N). | Current academic year | `ALLOWED` | Deleted with test paper. |
| `subject` | `str` | `OPERATIONAL_SYSTEM` | Subject name (e.g. "Physics", "Mathematics"). | Current academic year | `ALLOWED` | Deleted with test paper. |
| `question_type` | `str (Enum)` | `OPERATIONAL_SYSTEM` | Question format (`SINGLE_CORRECT`). | Current academic year | `ALLOWED` | Deleted with test paper. |
| `correct_option` | `str` | `OPERATIONAL_SYSTEM` | Answer key value ("A", "B", "C", "D"). | Current academic year | `ALLOWED` | Deleted with test paper. |
| `positive_marks` | `int` | `OPERATIONAL_SYSTEM` | Mark weight awarded for correct response. | Current academic year | `ALLOWED` | Deleted with test paper. |
| `negative_marks` | `int` | `OPERATIONAL_SYSTEM` | Deduction magnitude subtracted for wrong response. | Current academic year | `ALLOWED` | Deleted with test paper. |
| `bubble_coordinates` | `dict` | `OPERATIONAL_SYSTEM` | Crop boundary coordinates for OMR proof overlays. | Current academic year | `ALLOWED` | Deleted with test paper. |

---

### 2.5 OMR Responses & Scans (`StudentOMRSubmission`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `submission_id` | `str (UUID)` | `OPERATIONAL_SYSTEM` | Opaque surrogate ID for the OMR submission. | Current academic year | `ALLOWED` | Deleted on purge. |
| `raw_responses` | `dict[int, str]`| `CONFIDENTIAL_EDUCATIONAL` | Decoded bubble responses per question ("A", "BLANK"). | Current academic year | `NEVER` in logs | Deleted on academic year expiry. |
| `scan_image_path` | `str` | `CONFIDENTIAL_EDUCATIONAL` | Local path to high-resolution scanned sheet image. | Current academic year | `ALLOWED` (path only) | File destroyed on academic year expiry. |
| `scan_hash_sha256` | `str` | `OPERATIONAL_SYSTEM` | Integrity checksum verifying source scan authenticity. | Current academic year | `ALLOWED` | Retained with submission record. |
| `scan_provenance` | `dict` | `OPERATIONAL_SYSTEM` | Ingestion scanner model, resolution, and timestamp. | Current academic year | `ALLOWED` | Deleted with submission. |

---

### 2.6 Diagnostic Evaluations (`StudentDiagnosticReport`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `gross_marks` | `int` | `CONFIDENTIAL_EDUCATIONAL` | Marks earned from correct answers. | Current academic year | `MASKED` | Deleted on academic year expiry. |
| `bleed_marks` | `int` | `CONFIDENTIAL_EDUCATIONAL` | Negative mark deductions from wrong answers. | Current academic year | `MASKED` | Deleted on academic year expiry. |
| `net_marks` | `int` | `CONFIDENTIAL_EDUCATIONAL` | Final examination score. | Current academic year | `MASKED` | Deleted on academic year expiry. |
| `net_percentage` | `Decimal` | `CONFIDENTIAL_EDUCATIONAL` | Net score percentage to 1 decimal place. | Current academic year | `MASKED` | Deleted on academic year expiry. |
| `status_band` | `str (Enum)` | `CONFIDENTIAL_EDUCATIONAL` | Performance categorization (`RED`, `YELLOW`, `GREEN`, `ABSENT`). | Current academic year | `ALLOWED` | Deleted on academic year expiry. |
| `competition_rank` | `int \| None` | `CONFIDENTIAL_EDUCATIONAL` | Batch rank among present students. | Current academic year | `MASKED` | Deleted on academic year expiry. |
| `easy_missed_ids` | `list[int]` | `CONFIDENTIAL_EDUCATIONAL` | High-accuracy questions missed by student. | Current academic year | `ALLOWED` | Deleted on academic year expiry. |
| `marks_not_earned` | `int` | `CONFIDENTIAL_EDUCATIONAL` | Potential marks missed on easy questions. | Current academic year | `MASKED` | Deleted on academic year expiry. |
| `subject_diagnostics`| `dict` | `CONFIDENTIAL_EDUCATIONAL` | Diagnostic label per subject. | Current academic year | `ALLOWED` | Deleted on academic year expiry. |
| `requires_ptm_slip`| `bool` | `CONFIDENTIAL_EDUCATIONAL` | Mandatory guardian consultation indicator. | Current academic year | `ALLOWED` | Deleted on academic year expiry. |

---

### 2.7 Generated Parent Assets (`RenderedAssets`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `hindi_body_text` | `str` | `CONFIDENTIAL_EDUCATIONAL` | Conversational Bolchal Hindi template text. | Current academic year | `NEVER` in clear; `MASKED` in logs | Deleted on academic year expiry. |
| `scorecard_png_path`| `str` | `CONFIDENTIAL_EDUCATIONAL` | File path to rendered scorecard PNG image. | Current academic year | `ALLOWED` (path only) | File destroyed on academic year expiry. |
| `ptm_slip_pdf_path` | `str` | `CONFIDENTIAL_EDUCATIONAL` | File path to rendered A4 consultation slip PDF. | Current academic year | `ALLOWED` (path only) | File destroyed on academic year expiry. |
| `audio_opus_path` | `str` | `CONFIDENTIAL_EDUCATIONAL` | File path to stitched Ogg Opus audio voice note. | Current academic year | `ALLOWED` (path only) | File destroyed on academic year expiry. |
| `audio_duration_sec`| `Decimal` | `OPERATIONAL_SYSTEM` | Audio playback duration guard (hard max 45s). | Current academic year | `ALLOWED` | Deleted on academic year expiry. |

---

### 2.8 Dispatch, Delivery, & Provider Telemetry (`DispatchRecord`, `DispatchEvent`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `dispatch_id` | `str (UUID)` | `OPERATIONAL_SYSTEM` | Primary key for dispatch tracking. | 90 days | `ALLOWED` | Purged by CLI `purge` after 90 days. |
| `idempotency_key` | `str` | `OPERATIONAL_SYSTEM` | Composite deduplication key (zero PII). | 90 days | `ALLOWED` | Purged after 90 days. |
| `dispatch_status` | `str (Enum)` | `OPERATIONAL_SYSTEM` | Current lifecycle state (`SUBMITTED`, `DELIVERED`, etc.). | 90 days | `ALLOWED` | Purged after 90 days. |
| `provider_wamid` | `str` | `OPERATIONAL_SYSTEM` | WhatsApp message identifier returned by Meta. | 90 days | `ALLOWED` | Purged after 90 days. |
| `media_id` | `str` | `OPERATIONAL_SYSTEM` | Meta temporary media handle (30-day lifetime). | 30 days | `ALLOWED` | Purged after 30 days. |
| `error_class` | `str (Enum)` | `OPERATIONAL_SYSTEM` | Classified error type (`RETRY_SAFE`, etc.). | 90 days | `ALLOWED` | Purged after 90 days. |
| `error_code` | `int` | `OPERATIONAL_SYSTEM` | Numeric error code from Meta Cloud API. | 90 days | `ALLOWED` | Purged after 90 days. |
| `attempt_count` | `int` | `OPERATIONAL_SYSTEM` | Total retry attempts executed. | 90 days | `ALLOWED` | Purged after 90 days. |

---

### 2.9 Confirmation & Verification Tokens (`ConfirmationRecord`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `raw_qr_token` | `str` | `DIRECT_PII` | Ephemeral 256-bit random token in QR link. | Ephemeral (never persisted) | `NEVER` | Handed to renderer, never stored. |
| `token_hash_sha256`| `str` | `OPERATIONAL_SYSTEM` | Cryptographic hash of QR token for verification. | 72 hours (or single-use consumption) | `MASKED` (`tok_***`) | Deleted upon token consumption or expiry. |
| `otp_challenge_hash`| `str` | `DIRECT_PII` | Hash of 6-digit guardian challenge OTP. | 10 minutes | `NEVER` | Deleted upon verification or 5 failed tries. |
| `otp_attempts_count`| `int` | `OPERATIONAL_SYSTEM` | Brute-force throttle guard (max 5 attempts). | 72 hours | `ALLOWED` | Deleted with token. |
| `confirmed_at_utc` | `datetime \| None`| `OPERATIONAL_SYSTEM` | Timestamp when parent acknowledged report. | Current academic year + 90 days audit | `ALLOWED` | Retained with student archive. |

---

### 2.10 Structured Audit Trail (`AuditRecord`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `audit_id` | `str (UUID)` | `OPERATIONAL_SYSTEM` | Unique audit log entry identifier. | 90 days | `ALLOWED` | Purged after 90 days. |
| `run_correlation_id`| `str (UUID)`| `OPERATIONAL_SYSTEM` | Trace ID linking all actions in a single CLI run. | 90 days | `ALLOWED` | Purged after 90 days. |
| `action` | `str` | `OPERATIONAL_SYSTEM` | Executed operation (`INGEST`, `DISPATCH`, `PURGE`). | 90 days | `ALLOWED` | Purged after 90 days. |
| `actor` | `str` | `OPERATIONAL_SYSTEM` | User or automated service initiating the action. | 90 days | `ALLOWED` | Purged after 90 days. |
| `details_json` | `str (JSON)` | `OPERATIONAL_SYSTEM` | Structured action details (all PII pre-masked). | 90 days | `MASKED` | Purged after 90 days. |
| `timestamp_utc` | `datetime` | `OPERATIONAL_SYSTEM` | Tamper-evident audit timestamp. | 90 days | `ALLOWED` | Purged after 90 days. |

---

### 2.11 Multi-Kind Assessment Metadata (`AssessmentRecord`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `assessment_id` | `str (UUID)` | `OPERATIONAL_SYSTEM` | Unique identifier for the assessment. | Current academic year | `ALLOWED` | Deleted on academic year purge. |
| `org_id` | `str` | `OPERATIONAL_SYSTEM` | Institutional tenant owner. | Current academic year | `ALLOWED` | Deleted on tenant purge. |
| `kind` | `str (Enum)` | `OPERATIONAL_SYSTEM` | `OMR_MCQ`, `MARKS_ENTRY_TOTALS`, `MARKS_ENTRY_QUESTION_WISE`. | Current academic year | `ALLOWED` | Deleted on purge. |
| `name` | `str` | `OPERATIONAL_SYSTEM` | Assessment display name (e.g. "यूनिट टेस्ट 1"). | Current academic year | `ALLOWED` | Deleted on purge. |
| `date` | `date` | `OPERATIONAL_SYSTEM` | Administration date of the test. | Current academic year | `ALLOWED` | Deleted on purge. |
| `cohort_id` | `str` | `OPERATIONAL_SYSTEM` | Cohort identifier (e.g. "GRADE_8_B"). | Current academic year | `ALLOWED` | Deleted on purge. |
| `cohort_label` | `str` | `OPERATIONAL_SYSTEM` | Human display class label (e.g. "कक्षा 8-B"). | Current academic year | `ALLOWED` | Deleted on purge. |
| `subjects` | `list[str]` | `OPERATIONAL_SYSTEM` | Subject list assessed. | Current academic year | `ALLOWED` | Deleted on purge. |
| `max_marks_per_subject`| `dict[str, int]`| `OPERATIONAL_SYSTEM`| Maximum marks per subject. | Current academic year | `ALLOWED` | Deleted on purge. |
| `purpose_flags` | `list[str]` | `OPERATIONAL_SYSTEM` | Purpose categorization (`UNIT_TEST`, `PTM_LINKED`). | Current academic year | `ALLOWED` | Deleted on purge. |

---

### 2.12 Per-School Sender Identity & Credentials Reference (`SenderIdentityRecord`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `sender_id` | `str (UUID)` | `OPERATIONAL_SYSTEM` | Unique sender configuration identifier. | Active tenant lifetime | `ALLOWED` | Deleted on tenant offboarding. |
| `org_id` | `str` | `OPERATIONAL_SYSTEM` | Institutional tenant owner. | Active tenant lifetime | `ALLOWED` | Deleted on tenant offboarding. |
| `waba_id` | `str` | `OPERATIONAL_SYSTEM` | Meta WhatsApp Business Account ID. | Active tenant lifetime | `ALLOWED` | Deleted on tenant offboarding. |
| `phone_number_id` | `str` | `OPERATIONAL_SYSTEM` | Meta registered Phone Number ID. | Active tenant lifetime | `ALLOWED` | Deleted on tenant offboarding. |
| `display_phone_number`| `str` | `OPERATIONAL_SYSTEM`| E.164 business number displayed to parents. | Active tenant lifetime | `MASKED` | Deleted on tenant offboarding. |
| `verified_display_name`| `str`| `OPERATIONAL_SYSTEM`| Meta-approved institutional display name. | Active tenant lifetime | `ALLOWED` | Deleted on tenant offboarding. |
| `credential_secret_ref`| `str`| `OPERATIONAL_SYSTEM`| Opaque pointer to access token secret. | Active tenant lifetime | `ALLOWED` (pointer only) | Deleted on tenant offboarding. |
| `app_secret_ref` | `str` | `OPERATIONAL_SYSTEM` | Opaque pointer to webhook app secret. | Active tenant lifetime | `ALLOWED` (pointer only) | Deleted on tenant offboarding. |
| `template_registry` | `dict`| `OPERATIONAL_SYSTEM` | Approved template statuses for this sender. | Active tenant lifetime | `ALLOWED` | Deleted on tenant offboarding. |

---

### 2.13 Resumable Asynchronous Job Records (`JobRecord`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `job_id` | `str (UUID)` | `OPERATIONAL_SYSTEM` | Unique background job identifier. | 90 days | `ALLOWED` | Purged after 90 days. |
| `org_id` | `str` | `OPERATIONAL_SYSTEM` | Institutional tenant owner. | 90 days | `ALLOWED` | Purged after 90 days. |
| `kind` | `str (Enum)` | `OPERATIONAL_SYSTEM` | Job type (`BATCH_EVALUATE`, `DISPATCH_BATCH`).| 90 days | `ALLOWED` | Purged after 90 days. |
| `state` | `str (Enum)` | `OPERATIONAL_SYSTEM` | Lifecycle state (`QUEUED`, `RUNNING`, etc.). | 90 days | `ALLOWED` | Purged after 90 days. |
| `progress_current` | `int` | `OPERATIONAL_SYSTEM` | Processed items count for progress bar. | 90 days | `ALLOWED` | Purged after 90 days. |
| `progress_total` | `int` | `OPERATIONAL_SYSTEM` | Total batch size. | 90 days | `ALLOWED` | Purged after 90 days. |
| `last_processed_id` | `str \| None`| `OPERATIONAL_SYSTEM` | Cursor checkpoint for crash recovery. | 90 days | `ALLOWED` | Purged after 90 days. |
| `error_code` | `str \| None`| `OPERATIONAL_SYSTEM` | Classified failure code if failed. | 90 days | `ALLOWED` | Purged after 90 days. |

---

### 2.14 Tenant Settings & Administrative Controls (`TenantSettingsRecord`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `org_id` | `str` | `OPERATIONAL_SYSTEM` | Institutional tenant identifier. | Active tenant lifetime | `ALLOWED` | Deleted on tenant offboarding. |
| `school_name` | `str` | `OPERATIONAL_SYSTEM` | Official school name. | Active tenant lifetime | `ALLOWED` | Deleted on tenant offboarding. |
| `emergency_kill_switch`| `bool` | `OPERATIONAL_SYSTEM` | Tenant-level pause switch. | Active tenant lifetime | `ALLOWED` | Updated on toggle. |
| `daily_message_quota` | `int` | `OPERATIONAL_SYSTEM` | Maximum dispatches allowed per 24 hours. | Active tenant lifetime | `ALLOWED` | Updated on configuration. |
| `include_roll_in_text`| `bool` | `OPERATIONAL_SYSTEM` | Whether roll number is appended in text copy. | Active tenant lifetime | `ALLOWED` | Updated on configuration. |
| `default_send_window` | `str` | `OPERATIONAL_SYSTEM` | Standard dispatch window schedule. | Active tenant lifetime | `ALLOWED` | Updated on configuration. |

---

### 2.15 Opaque Artifact Metadata (`ArtifactMetadataRecord`)

| Field Name | Data Type | PII Class | Business Purpose | Retention Policy (D-13 Dev Default) | Logging Policy | Deletion / Purge Behaviour |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `artifact_id` | `str` | `OPERATIONAL_SYSTEM` | Opaque handle (`v1:{org}:{assessment}:{stu}:{type}`). | Current academic year | `ALLOWED` | Destroyed with student profile purge. |
| `org_id` | `str` | `OPERATIONAL_SYSTEM` | Institutional tenant owner. | Current academic year | `ALLOWED` | Destroyed on tenant purge. |
| `artifact_type` | `str (Enum)` | `OPERATIONAL_SYSTEM` | `SCORECARD_PNG`, `PTM_PDF`, `AUDIO_OGG`. | Current academic year | `ALLOWED` | Destroyed on purge. |
| `mime_type` | `str` | `OPERATIONAL_SYSTEM` | `image/png`, `application/pdf`, `audio/ogg`.| Current academic year | `ALLOWED` | Destroyed on purge. |
| `size_bytes` | `int` | `OPERATIONAL_SYSTEM` | File byte length. | Current academic year | `ALLOWED` | Destroyed on purge. |
| `sha256_hash` | `str` | `OPERATIONAL_SYSTEM` | Cryptographic integrity checksum. | Current academic year | `ALLOWED` | Destroyed on purge. |

