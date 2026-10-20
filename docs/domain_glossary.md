# Domain Glossary (`docs/domain_glossary.md`)

This document defines the authoritative vocabulary for the `omr_dispatch_engine`.
The **English Identifier Names** defined here serve as the canonical code identifiers across Pydantic models, database columns, and variable names.
The **Hindi Parent-Facing Wording** reflects respectful, non-judgmental conversational Bolchal Hindi compliant with frozen specification rules **D-06** (banned vocabulary: `ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, `औसत मान`) and observable indicators only.

---

## 1. Academic & Scoring Terms

| Term | English Code Identifier | Technical Definition & Invariants | Hindi Parent-Facing Wording (Bolchal) |
| :--- | :--- | :--- | :--- |
| **Gross Marks** | `gross_marks: int` | Sum of positive marks earned from all correctly answered questions. Non-negative integer. | "सही जवाबों से मिले नंबर" (e.g. "सही जवाबों से मिले 80 नंबर") |
| **Bleed Marks** | `bleed_marks: int` | Sum of mark deductions incurred from wrong answers (magnitude of negative marks). Non-negative integer. | "गलत जवाबों से कटे नंबर" (e.g. "गलत जवाबों से 25 नंबर कट गए") |
| **Net Marks** | `net_marks: int` | Final score after penalty deduction: `gross_marks - bleed_marks`. Can be negative. | "कुल नंबर" (e.g. "300 में से 55 नंबर आए हैं") |
| **Maximum Marks** | `max_positive_marks: int` | Total maximum attainable marks for the examination paper if all questions are answered correctly. | "कुल पूर्णांक" banned $\rightarrow$ "N में से" (e.g. "300 में से") |
| **Net Percentage** | `net_percentage: Decimal` | Exact ratio `Fraction(net_marks, max_positive_marks) * 100`, formatted with `ROUND_HALF_UP` to 1 decimal place. | Displayed alongside total score: "(18.3%)". "प्रतिशतता" banned. |
| **Attendance Status** | `attendance_status: AttendanceStatus` | Student presence at test: `PRESENT` or `ABSENT`. | `PRESENT`: उपस्थित<br>`ABSENT`: "टेस्ट में अनुपस्थित" |
| **Class Average** | `class_average_net: Decimal` | Arithmetic mean of net marks among all `PRESENT` students in the batch. Null if zero present. | "औसत मान" banned $\rightarrow$ "क्लास का औसत स्कोर" (e.g. "क्लास का औसत स्कोर: 142 नंबर") |
| **Class Topper Score** | `class_topper_net: int` | Highest net marks achieved by any `PRESENT` student in the batch. Null if zero present. | "क्लास का सबसे अधिक स्कोर" (e.g. "क्लास में सबसे ज्यादा 278 नंबर आए") |
| **Competition Rank** | `competition_rank: int \| None` | Standard competition rank: `1 + count(present students with strictly higher net)`. Ties share rank. Null for absent students. | "N उपस्थित बच्चों में से रैंक: X" (e.g. "16 उपस्थित बच्चों में से 14वीं रैंक") |

---

## 2. Status Bands & Colors (D-01, D-07)

| Band Name | Code Identifier | Evaluation Rule (Full Precision) | Banner Color Hex & Text | Parent-Facing Hindi Banner Text |
| :--- | :--- | :--- | :--- | :--- |
| **Green Band** | `StatusBand.GREEN` | `net * 100 > max_marks * 60` (> 60.0% net score) | `#1E8E3E` (White text) | "शानदार प्रदर्शन — बहुत बढ़िया" |
| **Yellow Band** | `StatusBand.YELLOW` | `30 * max_marks <= net * 100 <= 60 * max_marks` (30.0% to 60.0% inclusive) | `#F9AB00` (Dark text `#202124`) | "अच्छा प्रयास — सुधार की गुंजाइश" |
| **Red Band** | `StatusBand.RED` | `net * 100 < 30 * max_marks` (< 30.0% net score, or negative net) | `#D93025` (White text) | "विशेष ध्यान देने की ज़रूरत" |
| **Absent Band** | `StatusBand.ABSENT` | `attendance_status == AttendanceStatus.ABSENT` (Score/rank/percentage null) | `#5F6368` (White text) | "टेस्ट में अनुपस्थित" |

---

## 3. Diagnostics & Question Analysis (D-02, D-03)

| Term | English Code Identifier | Technical Definition & Invariants | Hindi Parent-Facing Copy |
| :--- | :--- | :--- | :--- |
| **Peer Accuracy** | `peer_accuracy: Fraction` | Ratio: `correct_count_among_present / present_count`. Evaluated as exact fraction. | "कम-से-कम 75% बच्चों ने सही किया" |
| **Easy Question** | `is_easy_question: bool` | True iff `peer_accuracy >= Fraction(3, 4)` ($\ge 75\%$). Exactly 75% qualifies per D-02. | "सरल सवाल" / "ज्यादातर बच्चों द्वारा सही किए गए सवाल" |
| **Easy Missed Questions (Low-Hanging Fruit)** | `easy_missed_question_ids: list[int]` | Questions that are easy (`accuracy >= 0.75`) but the student left blank or answered wrong. | "ऐसे सवाल जो अधिकांश बच्चों ने सही किए, लेकिन आपके बच्चे से छूट गए या गलत हो गए" |
| **Marks Not Earned** | `positive_marks_not_earned: int` | Sum of positive marks of easy questions missed: $\sum positive\_marks$ of easy questions wrong/blank. Never described as "marks gained if fixed". | "छूटे हुए सरल सवालों के कुल N नंबर" (e.g. "40 नंबर और मिल सकते थे") |
| **Attempt Ratio** | `attempt_ratio: Fraction` | Ratio: `attempted_questions / total_subject_questions`. | Observable: "N में से M सवाल हल किए" |
| **Accuracy Ratio** | `accuracy_ratio: Fraction` | Ratio: `correct_questions / attempted_questions`. Null if 0 attempted. | Observable: "हल किए गए सवालों में से K सही रहे" |

### Subject Classification Labels (Internal Diagnostic Codes)
*Parent-facing copy describes observable facts only; internal labels are never shown to parents.*

| Internal Subject Label | Code Identifier | Mathematical Threshold Rule | Parent-Facing Factual Hindi Copy |
| :--- | :--- | :--- | :--- |
| **No Attempt** | `SubjectDiagnostic.NO_ATTEMPT` | `attempted == 0` | "इस विषय में कोई सवाल हल नहीं किया गया।" |
| **Accuracy Bleed** | `SubjectDiagnostic.ACCURACY_BLEED` | `attempt_ratio >= 0.60 and accuracy_ratio < 0.65` | "सवाल ज्यादा हल किए, लेकिन गलत जवाबों के कारण नंबर कट गए।" |
| **Conceptual Speed Gap** | `SubjectDiagnostic.CONCEPTUAL_SPEED_GAP` | `attempt_ratio < 0.50 and accuracy_ratio >= 0.75` | "जितने सवाल हल किए उनमें सटीकता अच्छी रही, पर काफी सवाल छूट गए।" |
| **Foundational Crisis** | `SubjectDiagnostic.FOUNDATIONAL_CRISIS` | `attempt_ratio < 0.50 and accuracy_ratio < 0.65` | "इस विषय में बहुत कम सवाल हल हुए और गलतियां भी अधिक रहीं।" |
| **Mastery Zone** | `SubjectDiagnostic.MASTERY_ZONE` | `attempt_ratio >= 0.60 and accuracy_ratio >= 0.75` | "इस विषय में समझ और सटीकता दोनों बहुत अच्छी रही।" |
| **Moderate Zone** | `SubjectDiagnostic.MODERATE_ZONE` | Fallback (otherwise) | "सामान्य प्रदर्शन रहा; अभ्यास से और बेहतर हो सकता है।" |

---

## 4. Consultation & Parent-Teacher Meeting (D-04)

| Term | English Code Identifier | Technical Definition & Invariants | Parent-Facing Wording |
| :--- | :--- | :--- | :--- |
| **PTM Eligible / Slip Required** | `requires_ptm_slip: bool` | True iff `ABSENT`, or `band == RED`, or `competition_rank > floor(0.75 * present_count)`. Required for bottom quartile even in all-GREEN batches (`OWNER-CONFIRM`). | "अभिभावक-शिक्षक बैठक (PTM) में चर्चा आवश्यक" |
| **A4 PTM Consultation Slip** | `ptm_slip_pdf_path: str` | A4 printable PDF generated for guardian consultation containing bubble proofs and diagnostic review. | "पीटीएम परामर्श पर्ची" |

---

## 5. Contact Hygiene & Safety Quarantine (Rules 9, 10, S3, S8)

| Term | English Code Identifier | Technical Definition | Operational Handling |
| :--- | :--- | :--- | :--- |
| **Normalized Phone** | `normalized_phone: str` | E.164 formatted Indian mobile string: `+91XXXXXXXXXX`. Format `^[6-9]\d{9}$`. | Masked in all logs as `+91 98*** **321`. |
| **Interception Risk (Same Number)** | `ContactQuarantine.INTERCEPTION_RISK_SAME_NUMBER` | Student contact number and guardian contact number are identical. | **QUARANTINED**. High risk of child self-intercepting report card. Auto-dispatch blocked. |
| **Duplicate Parent Unverified** | `ContactQuarantine.DUPLICATE_PARENT_UNVERIFIED` | Same guardian phone number appears for multiple students without confirmed sibling relationship. | **QUARANTINED**. Prevents cross-student data leakage. Blocked until operator verifies sibling status. |
| **Quarantine Status** | `is_quarantined: bool` | Contact has one or more unresolved safety flags. | **HARD GATE**. Quarantined contacts are never dispatched. |
| **Parental Consent Status** | `consent_status: ConsentStatus` | Verified record of guardian consent: `OPT_IN`, `OPT_OUT`, `REVOKED`, `UNKNOWN`. | A non-empty phone number is NOT consent (Rule 9). `OPT_IN` required for send. |
| **Customer Service Window** | `service_window_open: bool` | 24 hours from the last user inbound message. Within window, free-form text is permitted. Outside window, approved templates are mandatory. | Monitored before any send attempt. |

---

## 6. Dispatch Pipeline & State Machine (S8, S9, S12)

| Dispatch State | Code Identifier | Definition & Next Transition |
| :--- | :--- | :--- |
| **Pending** | `DispatchStatus.PENDING` | Dispatch intent created; awaiting policy evaluation. |
| **Blocked (Consent)** | `DispatchStatus.BLOCKED_CONSENT` | No valid `OPT_IN` consent on record; dispatch aborted. |
| **Blocked (Hygiene)** | `DispatchStatus.BLOCKED_HYGIENE` | Contact quarantined (interception risk or unverified sibling); dispatch aborted. |
| **Blocked (Policy)** | `DispatchStatus.BLOCKED_POLICY` | Outside 24h window without approved template, or account restricted; dispatch aborted. |
| **Scheduled** | `DispatchStatus.SCHEDULED` | Passed policy checks; waiting for target dispatch time (e.g. Sunday 20:30 IST). |
| **Uploading Media** | `DispatchStatus.UPLOADING_MEDIA` | Uploading scorecard PNG / audio OGG to Meta Cloud API (`POST /{phone-id}/media`). |
| **Submitted** | `DispatchStatus.SUBMITTED` | Intent durably committed and request accepted by Meta Cloud API (`POST /messages`). Returns `wamid`. |
| **Delivered** | `DispatchStatus.DELIVERED` | Confirmed by Meta webhook delivery receipt (`status: "delivered"`). |
| **Read** | `DispatchStatus.READ` | Confirmed by Meta webhook read receipt (`status: "read"`). Implicitly satisfies `DELIVERED`. |
| **Failed** | `DispatchStatus.FAILED` | Terminal rejection by provider (PERMANENT error code or max retries exceeded). |
| **Retry Pending** | `DispatchStatus.RETRY_PENDING` | Request rejected with `RETRY_SAFE` code (rate limit/throttle); queued for backoff retry. |
| **Unknown Needs Review** | `DispatchStatus.UNKNOWN_NEEDS_REVIEW` | HTTP 5xx, timeout, or connection drop (`OUTCOME_UNKNOWN`). Auto-retry prohibited. Awaits webhook reconciliation or operator review. |
| **Cancelled** | `DispatchStatus.CANCELLED` | Job cancelled via emergency kill-switch or consent revocation. |

---

## 7. Error Classification Scheme (ADR-0008, Provider Contract v2.1.0)

| Error Class | Code Identifier | Operational Definition |
| :--- | :--- | :--- |
| **Retry Safe** | `ErrorClass.RETRY_SAFE` | The documented behaviour shows the request was rejected and the message was NOT accepted (rate limit). Auto-retry with backoff and jitter. |
| **Outcome Unknown** | `ErrorClass.OUTCOME_UNKNOWN` | HTTP 5xx or network timeout. Acceptance uncertain. Never auto-retry. Reconcile via webhook receipts. |
| **Operator Action** | `ErrorClass.OPERATOR_ACTION` | Auth failure, expired token, WABA maintenance, payment issue, paused template. Requires human intervention. |
| **Permanent** | `ErrorClass.PERMANENT` | Malformed request, invalid recipient number, expired window, unsupported media. Drop and log. |
| **Unknown** | `ErrorClass.UNKNOWN` | Unclassified error code. Defaults strictly to `OUTCOME_UNKNOWN` behaviour. |
