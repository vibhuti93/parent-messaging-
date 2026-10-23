# Input Contracts and Ingestion Specification (`docs/input_contracts.md`)

This document defines the formal data input contracts, file schemas, validation rules, and structured error codes for the `omr_dispatch_engine` (Stage S2).

---

## 1. Scope & Product Boundary: Bubble Detection is Out of Scope

> [!IMPORTANT]
> **Explicit Architectural Boundary:**
> Optical bubble detection, sheet corner detection, fiducial alignment, image thresholding, and scanner deskew are **strictly OUT OF SCOPE** for `omr_dispatch_engine`.
> The engine does not process raw pixel grids to decide which bubble is marked. Decoded student responses, coordinate maps, and confidence indicators must be provided by an upstream OMR scanning service or pre-materialized input files compliant with the contracts defined below.

---

## 2. Ingestion Contracts Summary

| Artifact | Supported Formats | Primary Model | Mandatory Tenancy & Versioning |
| :--- | :--- | :--- | :--- |
| **Student Roster** | CSV, JSON | `StudentAdmissionRow`, `StudentRoster` | `org_id: str`, `schema_version: int` |
| **Answer Key / Test Paper** | CSV, JSON | `QuestionMeta`, `TestPaper` | `org_id: str`, `schema_version: int` |
| **Decoded OMR Responses** | CSV, JSON | `StudentOMRSubmission`, `OMRSubmissionsBatch` | `org_id: str`, `schema_version: int` |
| **Manual Marks Entry Totals**| CSV, JSON, Excel (`.xlsx`) | `MarksEntryRow`, `MarksEntrySheet` | `org_id: str`, `schema_version: int` |

---

## 3. OMR Decoded Response Contract

External OMR scanning services deliver decoded response batches either as JSON payloads or CSV spreadsheets.

### 3.1 JSON Payload Specification (`OMRSubmissionsBatch`)
```json
{
  "org_id": "DEFAULT_INSTITUTION",
  "schema_version": 1,
  "test_id": "TEST_300",
  "submissions": [
    {
      "submission_id": "SUB_300_01",
      "student_id": "STU_01",
      "status": "PRESENT",
      "responses": {
        "1": "A",
        "2": "B",
        "3": "C",
        "4": "BLANK"
      },
      "scan_image_path": "scans/STU_01_raw.png",
      "scan_provenance": {
        "scanner_model": "Fujitsu fi-7160",
        "scan_timestamp_utc": "2026-10-18T10:15:00Z",
        "resolution_dpi": 300,
        "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
      }
    },
    {
      "submission_id": "SUB_300_02",
      "student_id": "STU_02",
      "status": "ABSENT",
      "responses": {},
      "scan_image_path": null,
      "scan_provenance": null
    }
  ]
}
```

### 3.2 Required Fields and Invariants
- `org_id`: Institutional tenant identifier. Must match the caller's active `org_id` context.
- `schema_version`: Serialization version integer (defaults to `1`).
- `test_id`: Alphanumeric test identifier linking to the answer key.
- `status`: Attendance status, strictly `PRESENT` or `ABSENT`.
- `responses`: Dictionary mapping question number (`1` to `N` as string) to marked option.
  - Allowed options: `"A"`, `"B"`, `"C"`, `"D"`, or `"BLANK"`.
  - For `ABSENT` students, `responses` must be empty (`{}`).
  - If an answer key is provided, all question IDs must be within the answer key range. Missing questions for present students are rejected; **a missing record is never treated as zero**.
- `scan_image_path`: Path or URI to the source scan image. Preserved for downstream bubble proof cropping.
- `scan_provenance`: Optional dictionary recording scanner hardware model, scan timestamp, DPI resolution, and SHA-256 integrity hash.

---

## 4. Student Roster Contract

The roster defines the student cohort, demographic identifiers, parental contacts, and consent status.

### 4.1 Schema Specification (`StudentAdmissionRow`)
```json
{
  "org_id": "DEFAULT_INSTITUTION",
  "schema_version": 1,
  "cohort_label": "कक्षा 10-A",
  "test_id": "TEST_300",
  "students": [
    {
      "student_id": "STU_01",
      "roll_number": "01",
      "child_display_name": "आरव",
      "class_section": "कक्षा 10-A",
      "guardian_salutation": "श्री राजेश शर्मा जी",
      "student_name": "आरव शर्मा",
      "raw_student_phone": "+91 98111-22201",
      "raw_guardian_phone": "+91 98111-22202",
      "verified_sibling": false,
      "guardian_verification": "VERIFIED",
      "consent_status": "OPT_IN",
      "consent_scope": "EXAM_RESULTS_WHATSAPP",
      "consent_timestamp_utc": "2026-08-01T09:00:00Z",
      "consent_source": "PHYSICAL_FORM",
      "consent_reference": "ADM-2026-001"
    }
  ]
}
```

### 4.2 Tabular / CSV Roster Columns
| Column Name | Required | Description |
| :--- | :--- | :--- |
| `student_id` (or `id`) | **Yes** | Opaque surrogate student identifier. |
| `roll_number` (or `roll`, `roll_no`) | **Yes** | School-assigned roll number (unique within section). |
| `child_display_name` | **Yes** | Given name for personalized parent copy (Unicode NFC). |
| `class_section` | **Yes** | Cohort descriptor (e.g. "कक्षा 10-A"). |
| `raw_student_phone` | No | Student contact number (raw string). |
| `raw_guardian_phone` (or `guardian_phone`) | No | Parent contact number (raw string). |
| `guardian_salutation` | No | Formal Hindi Bolchal salutation. |
| `student_name` | No | Full legal student name. |
| `verified_sibling` | No | Boolean indicating confirmed multi-child household. |
| `guardian_verification` | No | `VERIFIED` or `UNVERIFIED`. |
| `consent_status` | No | `OPT_IN`, `OPT_OUT`, `REVOKED`, or `UNKNOWN`. |
| `consent_scope` | No | Authorization scope string. |

*Note: S2 preserves contact numbers as raw, un-normalized string fields. Contact hygiene and quarantine rules (ADR-0008, Rules 9 & 10) are executed in Stage S3.*

---

## 5. Examination Answer Key Contract

Defines the correct options, marking weights, and bubble coordinate maps for automated diagnostic scoring.

### 5.1 Question Specification (`QuestionMeta`)
```json
{
  "question_id": 1,
  "subject": "PHYSICS",
  "question_type": "SINGLE_CORRECT",
  "correct_option": "A",
  "positive_marks": 4,
  "negative_marks": 1,
  "blank_marks": 0,
  "bubble_coordinates": {
    "center_y": 255,
    "col": 0,
    "col_x": 30,
    "row": 0,
    "options": {
      "A": { "x": 65, "y": 255 },
      "B": { "x": 89, "y": 255 },
      "C": { "x": 113, "y": 255 },
      "D": { "x": 137, "y": 255 }
    }
  }
}
```

### 5.2 Rules & Invariants
- `question_type`: Version 1 strictly supports `SINGLE_CORRECT`. Any other question type (`MULTI_CORRECT`, `NUMERICAL`, `MATRIX_MATCH`) raises `NotSupportedError` / `UNSUPPORTED_QUESTION_TYPE`.
- `correct_option`: Must be `"A"`, `"B"`, `"C"`, or `"D"`.
- `positive_marks`: Non-negative integer (marks awarded for correct bubble).
- `negative_marks`: Non-negative integer (magnitude subtracted for wrong bubble).
- `blank_marks`: Non-negative integer (marks awarded for unattempted question; default 0).

---

## 6. Manual Teacher Marks Entry Contract (`MarksEntrySheet`, `MarksEntryRow`)

Supports single-mark total entry per student, per subject, per assessment (ADR-0016).

### 6.1 Supported Formats
1. **JSON (`marks_entry_50.json`)**
2. **CSV (`marks_entry.csv`)**
3. **Excel (`.xlsx`)** (zero-dependency stdlib parser)

### 6.2 Numeric Semantics & Rules (ADR-0002)
- **Zero Float:** Marks must be parsed directly from decimal text as exact rational `fractions.Fraction`. Native `float` values are strictly prohibited in core numerics.
- **Latin Digits Only:** Accepted input format: `^[0-9]+(?:\.[0-9]+)?$`. Signs (`+`, `-`), exponent notation (`1e2`), thousands separators (`,`), Devanagari numerals (U+0966 to U+096F), and blank text are strictly rejected.
- **Whole and Half Marks Only:** Allowed fractional marks are multiples of `0.5` (e.g. `0.5`, `1.0`, `1.5`, `2.5`). Denominator in reduced `Fraction` must be `1` or `2`. Values like `2.25` or `2.3` are rejected with `FRACTIONAL_MARK_NOT_HALF`.
- **Range Constraints:** `0 <= marks <= max_marks`.
  - Negative marks are rejected with `MARK_BELOW_ZERO`.
  - Marks exceeding the subject total are rejected with `MARK_EXCEEDS_MAX`.
- **Attendance Rules:**
  - `status == PRESENT`: Marks cannot be blank or null (`PRESENT_WITH_BLANK_MARKS`).
  - `status == ABSENT`: Marks must be blank or null. Any recorded mark is rejected with `ABSENT_WITH_MARKS`.
  - **Blanks are never read as zero.**
- **Duplicate Prevention:** Duplicate roll numbers within an assessment sheet are rejected with `DUPLICATE_ROW`.
- **Subject Max Marks Consistency:** All rows within an assessment must have consistent `max_marks`. Conflicting rows are rejected with `INCONSISTENT_MAX_MARKS`.

---

## 7. Stable Machine-Readable Reason Codes (`IngestionReasonCode`)

Every importer returns structured errors `(row, field, reason_code, message)`:

| Reason Code | Category | Operational Description |
| :--- | :--- | :--- |
| `ORG_ID_MISMATCH` | Tenancy | File or row `org_id` does not equal the active repository context. |
| `UNKNOWN_COLUMN` | Schema | Unrecognized column header or JSON attribute found. |
| `MISSING_REQUIRED_FIELD` | Schema | Mandatory attribute missing on row or document header. |
| `DUPLICATE_ID` | Identity | Duplicate `student_id`, `question_id`, or `submission_id`. |
| `DUPLICATE_ROW` | Integrity | Duplicate student/roll entry in roster or marks sheet. |
| `INVALID_MARK_FORMAT` | Numeric | Non-decimal string, exponent, signs, comma, or Devanagari digits. |
| `INVALID_MARK_VALUE` | Numeric | Unparseable integer or non-numeric mark weight. |
| `FRACTIONAL_MARK_NOT_HALF`| Numeric | Mark fraction has denominator other than 1 or 2 (e.g. `2.25`, `2.3`). |
| `MARK_EXCEEDS_MAX` | Boundary | Student marks strictly exceed `max_marks`. |
| `MARK_BELOW_ZERO` | Boundary | Negative marks entered for a student. |
| `PRESENT_WITH_BLANK_MARKS`| Attendance| PRESENT student has blank/null marks. (Blanks are never zero). |
| `ABSENT_WITH_MARKS` | Attendance| ABSENT student has a recorded score. |
| `INCONSISTENT_MAX_MARKS` | Assessment | Different rows declare conflicting maximum attainable marks. |
| `UNKNOWN_ROLL_NUMBER` | Roster | Marks entry roll number does not exist in enrolled cohort roster. |
| `INVALID_ATTENDANCE_STATUS`| Attendance| Status string is not `PRESENT` or `ABSENT`. |
| `INVALID_OPTION` | Evaluation | Response or key option is not in `{"A", "B", "C", "D", "BLANK"}`. |
| `OUT_OF_RANGE_QUESTION_ID`| Evaluation | Response references question ID not present in answer key. |
| `MISSING_RECORD` | Completeness| Student or question missing from submission or marks sheet. |
| `UNSUPPORTED_QUESTION_TYPE`| Scope | Question type is not `SINGLE_CORRECT` (ADR-0004). |
| `CORRUPTED_FILE` | I/O | File missing, unreadable, or invalid JSON/CSV/XLSX structure. |

### No-Partial-Import Guarantee
If a file contains even a single error, **zero records are imported** (`records is None`). Partial or silent imports are strictly prohibited to prevent data corruption.
