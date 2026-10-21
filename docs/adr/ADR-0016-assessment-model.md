# ADR-0016: Assessment Entity, Multi-Kind Assessment Foundation, and Reporting Policy

## Status
`ACCEPTED`

## Context
The engine was initially conceived around single-batch optical mark recognition (`OMR_MCQ`) examinations. However, educational institutions assess students using multiple evaluation formats throughout an academic term:
1. High-stakes multiple-choice diagnostic tests with bubble sheets, negative marking, and question-level responses (`OMR_MCQ`).
2. Routine unit tests, weekly tests, and term assessments where subject teachers mark papers manually and enter a single total score per student per subject (`MARKS_ENTRY_TOTALS`).
3. Future detailed question-wise marks entry (`MARKS_ENTRY_QUESTION_WISE`), where item-level scores are keyed in by teachers.

If the engine's core models assume that every assessment has scanned sheets, bubble coordinates, answer keys, and negative marking, non-OMR evaluations cannot be processed without fabricating synthetic scan and bubble artifacts. Furthermore, student identities must persist across assessments across the academic year rather than being recreated per test batch.

## Options Considered

### Option 1: Separate Independent Engines / Forked Pipelines
- *Description*: Maintain `omr_dispatch_engine` exclusively for OMR MCQ, and build a separate `marks_dispatch_engine` for manual marks entry.
- *Pros*: Keeps the OMR pipeline completely untouched.
- *Cons*: Massive code duplication for messaging policies, contact hygiene, WhatsApp provider dispatch, audit logging, and parent delivery; splits the student identity across silos; unmaintainable.

### Option 2: Unified Assessment Entity with Polymorphic Assessment Kinds and Capability Flags
- *Description*:
  - Define an explicit `Assessment` domain entity with an immutable `kind: AssessmentKind` and capability flags.
  - Decouple student records (`StudentAdmissionRow`) from assessment submissions, persisting student identity across the academic year.
  - Introduce capability flags on assessment kind to declare available diagnostic capabilities (`has_attempt_data`, `has_negative_marking`, `has_question_level_data`).
  - Represent missing diagnostic dimensions as explicit `NOT_AVAILABLE` sentinels rather than zeros.
- *Pros*: Clean architectural abstraction; reuses the entire delivery, contact hygiene, audit, and messaging infrastructure; supports both OMR and marks entry natively; cleanly extensible.
- *Cons*: Diagnostic reporting and template rendering must branch on capability flags or handle `NOT_AVAILABLE` metrics cleanly.

## Proposed Decision
We propose **Option 2 (Unified Assessment Entity with Capability Flags and Persistent Student Roster)**.

### 1. Assessment Entity Schema
```python
class AssessmentKind(str, Enum):
    OMR_MCQ = "OMR_MCQ"                    # v1 supported
    MARKS_ENTRY_TOTALS = "MARKS_ENTRY_TOTALS"  # v1 supported
    MARKS_ENTRY_QUESTION_WISE = "MARKS_ENTRY_QUESTION_WISE"  # defined, post-v1

class AssessmentPurpose(str, Enum):
    WEEKLY_TEST = "WEEKLY_TEST"
    UNIT_TEST = "UNIT_TEST"
    MIDTERM = "MIDTERM"
    TERM_FINAL = "TERM_FINAL"
    PTM_LINKED = "PTM_LINKED"

class Assessment(BaseModel):
    schema_version: int = 1
    assessment_id: str                      # UUID
    org_id: str                             # Institutional tenant identifier
    kind: AssessmentKind
    name: str                               # e.g. "यूनिट टेस्ट 1", "Term 1 Diagnostic"
    date: date                              # Assessment administration date
    cohort_id: str                          # Cohort identifier (e.g. "GRADE_8_B")
    cohort_label: str                       # Human display label (e.g. "कक्षा 8-B")
    subjects: list[str]                     # e.g. ["Physics", "Chemistry", "Mathematics"]
    max_marks_per_subject: dict[str, int]   # e.g. {"Physics": 100, "Chemistry": 100, "Maths": 100} or {"English": 50}
    total_max_marks: int                    # Sum of subject max marks
    marking_scheme_version: int = 1
    purpose_flags: list[AssessmentPurpose]  # e.g. [UNIT_TEST, PTM_LINKED]
```

### 2. Capability Flags per Assessment Kind
| Capability Flag | `OMR_MCQ` (v1) | `MARKS_ENTRY_TOTALS` (v1) | `MARKS_ENTRY_QUESTION_WISE` (Future) |
| :--- | :---: | :---: | :---: |
| `has_attempt_data` | `True` | `False` | `True` |
| `has_negative_marking` | `True` (configurable per paper) | `False` | `False` (or configurable) |
| `has_question_level_data` | `True` | `False` | `True` |

### 3. Student Roster Persistence
Students (`StudentAdmissionRow`) persist across assessments within an institution (`org_id`). They are enrolled once per academic year and referenced by `student_id`. A test batch links existing student profiles to new assessment submissions rather than recreating student profiles per run.

### 4. Diagnostics Availability Matrix (D-01 to D-05)
For each core diagnostic metric, availability is defined per kind:

| Metric / Rule | Technical Identifier | `OMR_MCQ` | `MARKS_ENTRY_TOTALS` | Sentinel / Handling when Unavailable |
| :--- | :--- | :---: | :---: | :--- |
| **D-01: Net Score** | `net_marks` | Available | Available | Exact marks obtained. |
| **D-01: Net Percentage** | `net_percentage` | Available | Available | `Fraction(net_marks, total_max_marks) * 100` |
| **D-01: Status Band** | `status_band` | Available | Available | RED (<30%), YELLOW (30–60%), GREEN (>60%), ABSENT. |
| **D-02: Easy Question Detection** | `is_easy_question` | Available | `NOT_AVAILABLE` | Omitted from models and templates; never reported as 0. |
| **D-02: Easy Questions Missed** | `easy_missed_ids` | Available | `NOT_AVAILABLE` | Omitted from templates; never reported as empty list or 0. |
| **D-02 / D-05: Marks Not Earned** | `positive_marks_not_earned`| Available | `NOT_AVAILABLE` | Omitted from templates; never reported as 0. |
| **D-03: Attempt Ratio** | `attempt_ratio` | Available | `NOT_AVAILABLE` | Omitted; no question attempt tracking in totals entry. |
| **D-03: Subject Diagnostic Labels**| `subject_diagnostics` | Available | `NOT_AVAILABLE` | Omitted; observable totals only. |
| **D-04: Competition Rank** | `competition_rank` | Available | Available | Standard competition rank within cohort among present students. |
| **D-04: Class Average** | `class_average_net` | Available | Available | Arithmetic mean of present students in cohort. |
| **D-04: Class Topper Score** | `class_topper_net` | Available | Available | Maximum score among present students in cohort. |
| **D-04: PTM Slip Requirement** | `requires_ptm_slip` | Available | Available | PTM eligibility under D-04 applies to every assessment type. |
| **D-05: Gross Marks** | `gross_marks` | Available | `NOT_AVAILABLE` | Equal to net marks in non-negative marking; omitted from copy. |
| **D-05: Bleed Marks (Deductions)**| `bleed_marks` | Available | `NOT_AVAILABLE` | Zero deduction concept; omitted from copy (never shown as 0). |

*Strict Invariant:* An unavailable metric must be marked `NOT_AVAILABLE` (or `None` in nullable typed models) and omitted from parent-facing copy. It must **never** be coerced to zero or presented as 0 marks lost.

### 5. Rank, Average, and Cohort Definitions for Marks Entry
1. **Cohort Scope:**
   - Both OMR and marks entry compute competition rank, class average, and topper score over the assessment's **cohort**: the group of students sitting the assessment together.
   - A cohort is defined on the `Assessment` entity (e.g. a specific section such as "8-B", or all sections across Grade 8).
   - The cohort's human-readable label (`cohort_label`, e.g. `"कक्षा 8-B"`) is passed as the "class" placeholder in parent-facing messages.
   - Frozen OMR golden values (`expected_reports.json`) are unaffected because the golden batch forms a single cohort of 20 enrolled students (16 present).
2. **Subject Rank:**
   - Rank is computed per subject within the assessment among `PRESENT` students:
     `rank = 1 + count(present students in cohort with strictly higher marks in subject)`.
   - Tied students share rank; subsequent ranks skip accordingly (standard competition rank).
3. **Overall Rank:**
   - An overall assessment rank is computed **only** when an assessment consists of multiple subjects and every present student has a recorded score for all subjects. If students take disjoint optional subjects, overall rank is `NOT_AVAILABLE`.
4. **Class Average:**
   - Arithmetic mean over `PRESENT` students in the cohort: $\sum marks_{present} / N_{present}$.
   - Stored and evaluated at full precision (`Fraction`); formatted with `ROUND_HALF_UP` to exactly one decimal place on display (e.g. `32.4`).

### 6. Input Contract for Marks Import (CSV / Excel)
The marks entry ingestion pipeline accepts tabular data with the following contract:

| Column Name | Type / Format | Allowed Values & Validation Rules |
| :--- | :--- | :--- |
| `assessment` | `str` | Must match a declared `Assessment.name` or `assessment_id` in the institution. |
| `subject` | `str` | Must match one of the declared subjects in the assessment definition. |
| `max_marks` | `int \| Decimal` | Must be consistent for all rows of the same subject within the assessment. |
| `roll_no` | `str` | Must resolve to a valid enrolled student in the institution's roster. Unknown roll numbers are rejected per row with a structured error. |
| `status` | `str (Enum)` | Strictly `PRESENT` or `ABSENT`. |
| `marks` | `Decimal \| Fraction \| None` | When `PRESENT`: Mandatory, numeric, $0 \le marks \le max\_marks$. Half marks allowed ($marks \pmod{0.5} == 0$). Blank marks are **strictly rejected**. A blank is never read as zero.<br>When `ABSENT`: Must be blank / null. Non-blank marks for absent students are **strictly rejected**. |

**Validation Invariants:**
1. Zero silent coercions: Missing marks never default to zero; missing status never defaults to `PRESENT`.
2. Duplicate row rejection: Duplicate `(assessment, subject, roll_no)` pairs are rejected with a conflict error.
3. Batch atomicity: Input errors are collected and reported per row and column; partial imports are prohibited.

### 7. Reporting Policy by Purpose (Weekly, Midterm, PTM-Linked)
Assessments carry purpose flags that govern parent communication:
1. **PTM Eligibility:**
   - PTM eligibility under D-04 applies to every assessment type (per S1-BLOCK-01 Option 1). Any student who is ABSENT, RED, or bottom-quarter rank (`rank > floor(0.75 * present_count)`) has `requires_ptm_slip = true`, with no `is_ptm_linked` gating condition.
2. **Consent Scope Alignment:**
   - The existing consent model (`docs/data_map.md`, Section 2.3) specifies `consent_scope: str`.
   - The engine validates that guardian consent covers the assessment purpose:
     - `EXAM_RESULTS_ALL`: Authorizes all assessment dispatches.
     - `EXAM_RESULTS_PTM`: Authorizes only PTM-linked assessments.
     - `EXAM_RESULTS_WEEKLY`: Authorizes routine weekly progress messages.
   - If consent scope does not encompass the assessment purpose, dispatch is blocked with `BLOCKED_CONSENT`.
3. **Cadence & Weekly-Digest Mode:**
   - Routine weekly assessments create delivery risks if multiple tests are dispatched individually (parent notification fatigue and spam flagging risk under research row **R-04**).
   - Institutions may enable a weekly-digest mode (`WEEKLY_DIGEST`), consolidating multiple subject marks into a single summary template.
4. **Cost and Platform Quality Risks:**
   - Meta Per-Message Pricing (**R-05**) applies to every delivered template message.
   - Sending multiple single-subject notifications per week increases messaging expenditure and increases the risk of parent blocks or spam reports, degrading the phone number's Quality Rating (**R-04**).
   - All high-frequency dispatch schedules must respect per-sender daily portfolio limits (**R-10**).

## Consequences
- **Positive**: Cleanly supports both OMR diagnostic tests and manual teacher marks entry without fabricating OMR artifacts; maintains mathematical rigor and deterministic reporting.
- **Negative**: Adds validation rules and ingestion branching based on `AssessmentKind`.
- **Neutral**: Does not modify existing golden OMR values or change any frozen specification rules (D-01 to D-14).

## Revisit When
Revisit when implementing `MARKS_ENTRY_QUESTION_WISE` to add question-level rubric definitions.
