"""
Input Contracts, Data Ingestion, and Schema Validation (`src/omr_dispatch/ingestion.py`).

Provides robust, fail-closed importers for:
  - Student rosters (CSV and JSON)
  - Examination answer keys and test papers (CSV and JSON)
  - Decoded OMR student submissions (CSV and JSON)
  - Teacher manual marks entry totals (CSV, JSON, and Excel .xlsx)

Invariants:
  - Strict ADR-0002 exact Fraction arithmetic; zero float.
  - Strict ADR-0003 and ADR-0017 tenancy: org_id is required; stamped onto all models;
    if file carries org_id it must equal the argument or import fails (ORG_ID_MISMATCH).
  - No partial imports: if any row/field has an error, records is None.
  - Machine-readable structured error tracking (row, field, reason_code).
  - Missing records are never treated as zero (S2 Task 2).
  - Preserves links to source scan images and provenance.
  - Invariant 17: Never logs child names or class/section.
"""

from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from omr_dispatch.models import (
    AttendanceStatus,
    ImportResult,
    IngestionErrorDetail,
    IngestionReasonCode,
    MarksEntryRow,
    MarksEntrySheet,
    MarksValidationError,
    NotSupportedError,
    QuestionMeta,
    ScanProvenance,
    StudentAdmissionRow,
    StudentOMRSubmission,
    TestPaper,
    parse_marks_decimal,
)

# ------------------------------------------------------------------------------
# Allowed and Required Field Definitions
# ------------------------------------------------------------------------------

ROSTER_ALLOWED_FIELDS = {
    "student_id",
    "id",
    "roll_number",
    "roll",
    "roll_no",
    "child_display_name",
    "class_section",
    "guardian_salutation",
    "student_name",
    "raw_student_phone",
    "student_phone",
    "raw_guardian_phone",
    "guardian_phone",
    "verified_sibling",
    "guardian_verification",
    "consent_status",
    "consent_scope",
    "consent_timestamp_utc",
    "consent_source",
    "consent_reference",
    "revocation_timestamp",
    "marks",
    "max_marks",
    "org_id",
    "schema_version",
}

ROSTER_REQUIRED_FIELDS = {"student_id", "roll_number", "child_display_name", "class_section"}

ANSWER_KEY_ALLOWED_FIELDS = {
    "question_id",
    "id",
    "subject",
    "question_type",
    "correct_option",
    "positive_marks",
    "negative_marks",
    "blank_marks",
    "bubble_coordinates",
    "org_id",
    "schema_version",
}

ANSWER_KEY_REQUIRED_FIELDS = {"question_id", "subject", "correct_option", "positive_marks", "negative_marks"}

SUBMISSIONS_ALLOWED_FIELDS = {
    "submission_id",
    "id",
    "student_id",
    "status",
    "responses",
    "scan_image_path",
    "scan_provenance",
    "org_id",
    "schema_version",
}

MARKS_ENTRY_ALLOWED_FIELDS = {
    "roll_no",
    "roll_number",
    "roll",
    "student_id",
    "id",
    "child_display_name",
    "status",
    "marks",
    "max_marks",
    "subject",
    "assessment_name",
    "assessment",
    "cohort_label",
    "org_id",
    "schema_version",
}

MARKS_ENTRY_REQUIRED_FIELDS = {"roll_no", "status", "marks"}

VALID_OPTIONS = {"A", "B", "C", "D", "BLANK"}


# ------------------------------------------------------------------------------
# Helper Utilities
# ------------------------------------------------------------------------------


def _read_file_text(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def _col2num(col: str) -> int:
    num = 0
    for c in col.upper():
        if "A" <= c <= "Z":
            num = num * 26 + (ord(c) - ord("A") + 1)
    return num


def _read_xlsx_rows(file_path: Path) -> list[dict[str, str]]:
    """
    Zero-dependency stdlib Excel (.xlsx) reader using zipfile and xml.etree.ElementTree.
    Extracts tabular rows from sheet1.xml and resolves shared strings.
    Strictly handles sparse cell coordinates (missing cells via cell 'r' attribute)
    and rejects malformed XML / zip packages safely.
    """
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                try:
                    tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
                    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                    for si in tree.findall(f".//{{{ns}}}si"):
                        t = si.find(f"{{{ns}}}t")
                        shared_strings.append(t.text if t is not None and t.text is not None else "")
                except ET.ParseError as exc:
                    raise ValueError(f"Malformed or entity-expanded sharedStrings.xml: {exc}") from exc

            sheet_path = "xl/worksheets/sheet1.xml"
            if sheet_path not in z.namelist():
                raise ValueError(f"Invalid Excel file: {sheet_path} not found in zip archive")

            try:
                tree = ET.fromstring(z.read(sheet_path))
            except ET.ParseError as exc:
                raise ValueError(f"Malformed or entity-expanded {sheet_path}: {exc}") from exc

            ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

            raw_grid: list[dict[str, str]] = []
            all_cols: set[str] = set()

            for row_elem in tree.findall(f".//{{{ns}}}row"):
                row_dict: dict[str, str] = {}
                for c_elem in row_elem.findall(f"{{{ns}}}c"):
                    ref = c_elem.attrib.get("r", "")
                    col_letters = "".join(filter(str.isalpha, ref)).upper()
                    if not col_letters:
                        continue
                    cell_type = c_elem.attrib.get("t")
                    v_elem = c_elem.find(f"{{{ns}}}v")
                    val = v_elem.text if v_elem is not None and v_elem.text is not None else ""

                    if cell_type == "s" and val.isdigit():
                        idx = int(val)
                        val = shared_strings[idx] if idx < len(shared_strings) else val
                    elif cell_type == "inlineStr":
                        t_elem = c_elem.find(f".//{{{ns}}}t")
                        if t_elem is not None and t_elem.text is not None:
                            val = t_elem.text

                    row_dict[col_letters] = val.strip()
                    all_cols.add(col_letters)
                if row_dict:
                    raw_grid.append(row_dict)

            if not raw_grid:
                return []

            sorted_cols = sorted(all_cols, key=_col2num)
            header_row = raw_grid[0]
            header_map = {col: header_row.get(col, "").strip() for col in sorted_cols if header_row.get(col, "").strip()}

            result_rows: list[dict[str, str]] = []
            for r_dict in raw_grid[1:]:
                mapped: dict[str, str] = {}
                for col, h in header_map.items():
                    # Sparse cell safe: missing cells in row return empty string
                    mapped[h] = r_dict.get(col, "")
                result_rows.append(mapped)

            return result_rows
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid or corrupted zip archive for Excel file: {exc}") from exc


def _read_csv_rows(file_path: Path) -> list[dict[str, str]]:
    with file_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _read_tabular_file(file_path: Path) -> list[dict[str, str]]:
    ext = file_path.suffix.lower()
    if ext == ".csv":
        return _read_csv_rows(file_path)
    if ext == ".xlsx":
        return _read_xlsx_rows(file_path)
    raise ValueError(f"Unsupported tabular file extension: {ext}")


# ------------------------------------------------------------------------------
# Importer 1: Student Roster
# ------------------------------------------------------------------------------


def import_roster(file_path: str | Path, org_id: str) -> ImportResult[StudentAdmissionRow]:
    """
    Import student admissions / roster records from CSV or JSON.
    Enforces tenant match, rejects unknown columns and duplicates, stamps org_id.
    """
    path = Path(file_path)
    errors: list[IngestionErrorDetail] = []

    if not path.exists():
        errors.append(
            IngestionErrorDetail(
                row=None,
                field=None,
                reason_code=IngestionReasonCode.CORRUPTED_FILE,
                message=f"File not found: {path}",
            )
        )
        return ImportResult(records=None, errors=errors, org_id=org_id)

    raw_students: list[dict[str, Any]] = []

    if path.suffix.lower() == ".json":
        try:
            data = json.loads(_read_file_text(path))
        except Exception as exc:
            errors.append(
                IngestionErrorDetail(
                    row=None,
                    field=None,
                    reason_code=IngestionReasonCode.CORRUPTED_FILE,
                    message=f"Invalid JSON in {path}: {exc}",
                )
            )
            return ImportResult(records=None, errors=errors, org_id=org_id)

        matched_org_data = None
        if isinstance(data, dict):
            for _k, v in data.items():
                if isinstance(v, dict) and v.get("org_id") == org_id:
                    matched_org_data = v
                    break

        if matched_org_data is not None:
            raw_students = matched_org_data.get("students", [])
        elif isinstance(data, dict) and any(
            isinstance(v, dict) and "org_id" in v for v in data.values()
        ):
            errors.append(
                IngestionErrorDetail(
                    row=None,
                    field="org_id",
                    reason_code=IngestionReasonCode.ORG_ID_MISMATCH,
                    message=f"Organization '{org_id}' not found in multi-tenant file {path}",
                )
            )
            return ImportResult(records=None, errors=errors, org_id=org_id)
        elif isinstance(data, dict):
            file_org = data.get("org_id")
            if file_org is not None and file_org != org_id:
                errors.append(
                    IngestionErrorDetail(
                        row=None,
                        field="org_id",
                        reason_code=IngestionReasonCode.ORG_ID_MISMATCH,
                        message=f"File org_id '{file_org}' does not match context org_id '{org_id}'",
                    )
                )
                return ImportResult(records=None, errors=errors, org_id=org_id)

            top_allowed = {"org_id", "schema_version", "test_id", "cohort_label", "school_name", "students"}
            for k in data:
                if k not in top_allowed:
                    errors.append(
                        IngestionErrorDetail(
                            row=None,
                            field=k,
                            reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                            message=f"Unknown top-level attribute '{k}' in roster JSON",
                        )
                    )

            raw_students = data.get("students", [])
        elif isinstance(data, list):
            raw_students = data
    else:
        try:
            raw_students = _read_tabular_file(path)
        except Exception as exc:
            errors.append(
                IngestionErrorDetail(
                    row=None,
                    field=None,
                    reason_code=IngestionReasonCode.CORRUPTED_FILE,
                    message=f"Could not parse tabular roster file {path}: {exc}",
                )
            )
            return ImportResult(records=None, errors=errors, org_id=org_id)

    seen_ids: set[str] = set()
    seen_rolls: set[tuple[str, str]] = set()
    records: list[StudentAdmissionRow] = []

    for idx, raw in enumerate(raw_students, start=1):
        for k in raw:
            if k not in ROSTER_ALLOWED_FIELDS:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field=k,
                        reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                        message=f"Unknown column/field '{k}' in roster",
                    )
                )

        row_org = raw.get("org_id")
        if row_org is not None and row_org != org_id:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="org_id",
                    reason_code=IngestionReasonCode.ORG_ID_MISMATCH,
                    message=f"Row {idx} org_id '{row_org}' does not match context org_id '{org_id}'",
                )
            )

        stu_id = raw.get("student_id") or raw.get("id")
        roll_num = raw.get("roll_number") or raw.get("roll") or raw.get("roll_no")
        child_name = raw.get("child_display_name")
        class_sec = raw.get("class_section")

        if not stu_id:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="student_id",
                    reason_code=IngestionReasonCode.MISSING_REQUIRED_FIELD,
                    message=f"Row {idx} missing required field 'student_id'",
                )
            )
        if not roll_num:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="roll_number",
                    reason_code=IngestionReasonCode.MISSING_REQUIRED_FIELD,
                    message=f"Row {idx} missing required field 'roll_number'",
                )
            )
        if not child_name:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="child_display_name",
                    reason_code=IngestionReasonCode.MISSING_REQUIRED_FIELD,
                    message=f"Row {idx} missing required field 'child_display_name'",
                )
            )
        if not class_sec:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="class_section",
                    reason_code=IngestionReasonCode.MISSING_REQUIRED_FIELD,
                    message=f"Row {idx} missing required field 'class_section'",
                )
            )

        if stu_id:
            stu_id_str = str(stu_id).strip()
            if stu_id_str in seen_ids:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="student_id",
                        reason_code=IngestionReasonCode.DUPLICATE_ID,
                        message=f"Duplicate student_id '{stu_id_str}' at row {idx}",
                    )
                )
            else:
                seen_ids.add(stu_id_str)

        if roll_num and class_sec:
            roll_key = (str(class_sec).strip(), str(roll_num).strip())
            if roll_key in seen_rolls:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="roll_number",
                        reason_code=IngestionReasonCode.DUPLICATE_ROW,
                        message=f"Duplicate roll_number '{roll_num}' in cohort '{class_sec}' at row {idx}",
                    )
                )
            else:
                seen_rolls.add(roll_key)

        if not errors:
            clean_dict = dict(raw)
            clean_dict["id"] = str(stu_id)
            clean_dict["roll"] = str(roll_num)
            clean_dict["org_id"] = org_id
            clean_dict["schema_version"] = 1
            clean_dict.pop("student_id", None)
            clean_dict.pop("roll_number", None)
            clean_dict.pop("roll_no", None)

            try:
                row_model = StudentAdmissionRow.model_validate(clean_dict)
                records.append(row_model)
            except Exception as exc:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field=None,
                        reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                        message=f"Schema validation error on row {idx}: {exc}",
                    )
                )

    if errors:
        return ImportResult(records=None, errors=errors, org_id=org_id)

    return ImportResult(records=records, errors=[], org_id=org_id)


# ------------------------------------------------------------------------------
# Importer 2: Answer Key & Test Paper
# ------------------------------------------------------------------------------


def import_answer_key(file_path: str | Path, org_id: str) -> ImportResult[QuestionMeta]:
    """
    Import examination answer key / question definitions from CSV or JSON.
    Enforces SINGLE_CORRECT question type per ADR-0004.
    """
    path = Path(file_path)
    errors: list[IngestionErrorDetail] = []

    if not path.exists():
        errors.append(
            IngestionErrorDetail(
                row=None,
                field=None,
                reason_code=IngestionReasonCode.CORRUPTED_FILE,
                message=f"File not found: {path}",
            )
        )
        return ImportResult(records=None, errors=errors, org_id=org_id)

    raw_questions: list[dict[str, Any]] = []

    if path.suffix.lower() == ".json":
        try:
            data = json.loads(_read_file_text(path))
        except Exception as exc:
            errors.append(
                IngestionErrorDetail(
                    row=None,
                    field=None,
                    reason_code=IngestionReasonCode.CORRUPTED_FILE,
                    message=f"Invalid JSON in {path}: {exc}",
                )
            )
            return ImportResult(records=None, errors=errors, org_id=org_id)

        if isinstance(data, dict):
            file_org = data.get("org_id")
            if file_org is not None and file_org != org_id:
                errors.append(
                    IngestionErrorDetail(
                        row=None,
                        field="org_id",
                        reason_code=IngestionReasonCode.ORG_ID_MISMATCH,
                        message=f"File org_id '{file_org}' does not match context org_id '{org_id}'",
                    )
                )
                return ImportResult(records=None, errors=errors, org_id=org_id)

            top_allowed = {
                "org_id",
                "schema_version",
                "test_id",
                "name",
                "subjects",
                "max_marks_per_subject",
                "total_max_marks",
                "total_questions",
                "questions",
            }
            for k in data:
                if k not in top_allowed:
                    errors.append(
                        IngestionErrorDetail(
                            row=None,
                            field=k,
                            reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                            message=f"Unknown top-level attribute '{k}' in answer key JSON",
                        )
                    )

            raw_questions = data.get("questions", [])
        elif isinstance(data, list):
            raw_questions = data
    else:
        try:
            raw_questions = _read_tabular_file(path)
        except Exception as exc:
            errors.append(
                IngestionErrorDetail(
                    row=None,
                    field=None,
                    reason_code=IngestionReasonCode.CORRUPTED_FILE,
                    message=f"Could not parse tabular answer key file {path}: {exc}",
                )
            )
            return ImportResult(records=None, errors=errors, org_id=org_id)

    seen_q_ids: set[int] = set()
    records: list[QuestionMeta] = []

    for idx, raw in enumerate(raw_questions, start=1):
        for k in raw:
            if k not in ANSWER_KEY_ALLOWED_FIELDS:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field=k,
                        reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                        message=f"Unknown column/field '{k}' in answer key",
                    )
                )

        q_id = raw.get("question_id") or raw.get("id")
        subject = raw.get("subject")
        correct = raw.get("correct_option")
        pos_m = raw.get("positive_marks")
        neg_m = raw.get("negative_marks", 0)
        blank_m = raw.get("blank_marks", 0)
        q_type = raw.get("question_type", "SINGLE_CORRECT")

        if q_id is None:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="question_id",
                    reason_code=IngestionReasonCode.MISSING_REQUIRED_FIELD,
                    message=f"Row {idx} missing required field 'question_id'",
                )
            )
        else:
            try:
                int_qid = int(q_id)
                if int_qid in seen_q_ids:
                    errors.append(
                        IngestionErrorDetail(
                            row=idx,
                            field="question_id",
                            reason_code=IngestionReasonCode.DUPLICATE_ID,
                            message=f"Duplicate question_id '{int_qid}' at row {idx}",
                        )
                    )
                else:
                    seen_q_ids.add(int_qid)
            except ValueError:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="question_id",
                        reason_code=IngestionReasonCode.INVALID_MARK_VALUE,
                        message=f"Question ID '{q_id}' must be an integer",
                    )
                )

        if not subject:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="subject",
                    reason_code=IngestionReasonCode.MISSING_REQUIRED_FIELD,
                    message=f"Row {idx} missing required field 'subject'",
                )
            )

        if not correct:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="correct_option",
                    reason_code=IngestionReasonCode.MISSING_REQUIRED_FIELD,
                    message=f"Row {idx} missing required field 'correct_option'",
                )
            )
        elif str(correct).strip() not in ("A", "B", "C", "D"):
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="correct_option",
                    reason_code=IngestionReasonCode.INVALID_OPTION,
                    message=f"Correct option '{correct}' is invalid; must be A, B, C, or D",
                )
            )

        if q_type != "SINGLE_CORRECT":
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="question_type",
                    reason_code=IngestionReasonCode.UNSUPPORTED_QUESTION_TYPE,
                    message=f"Question type '{q_type}' is not supported in Version 1 (ADR-0004)",
                )
            )

        try:
            if pos_m is not None and int(pos_m) < 0:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="positive_marks",
                        reason_code=IngestionReasonCode.MARK_BELOW_ZERO,
                        message="Positive marks must be non-negative integer",
                    )
                )
            if neg_m is not None and int(neg_m) < 0:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="negative_marks",
                        reason_code=IngestionReasonCode.MARK_BELOW_ZERO,
                        message="Negative marks deduction must be non-negative integer",
                    )
                )
        except ValueError:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="positive_marks",
                    reason_code=IngestionReasonCode.INVALID_MARK_VALUE,
                    message="Marks weights must be integer values",
                )
            )

        if not errors:
            clean_q = dict(raw)
            clean_q["id"] = int(q_id) if q_id is not None else 0
            clean_q["positive_marks"] = int(pos_m) if pos_m is not None else 0
            clean_q["negative_marks"] = int(neg_m) if neg_m is not None else 0
            clean_q["blank_marks"] = int(blank_m) if blank_m is not None else 0
            clean_q["org_id"] = org_id
            clean_q["schema_version"] = 1
            clean_q.pop("question_id", None)

            try:
                q_model = QuestionMeta.model_validate(clean_q)
                records.append(q_model)
            except NotSupportedError as nse:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="question_type",
                        reason_code=IngestionReasonCode.UNSUPPORTED_QUESTION_TYPE,
                        message=str(nse),
                    )
                )
            except Exception as exc:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field=None,
                        reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                        message=f"Schema validation error on row {idx}: {exc}",
                    )
                )

    if errors:
        return ImportResult(records=None, errors=errors, org_id=org_id)

    return ImportResult(records=records, errors=[], org_id=org_id)


def import_test_paper(file_path: str | Path, org_id: str) -> ImportResult[TestPaper]:
    """Import full TestPaper container object from JSON."""
    path = Path(file_path)
    errors: list[IngestionErrorDetail] = []

    if not path.exists():
        errors.append(
            IngestionErrorDetail(
                row=None,
                field=None,
                reason_code=IngestionReasonCode.CORRUPTED_FILE,
                message=f"File not found: {path}",
            )
        )
        return ImportResult(records=None, errors=errors, org_id=org_id)

    try:
        data = json.loads(_read_file_text(path))
    except Exception as exc:
        errors.append(
            IngestionErrorDetail(
                row=None,
                field=None,
                reason_code=IngestionReasonCode.CORRUPTED_FILE,
                message=f"Invalid JSON in {path}: {exc}",
            )
        )
        return ImportResult(records=None, errors=errors, org_id=org_id)

    file_org = data.get("org_id")
    if file_org is not None and file_org != org_id:
        errors.append(
            IngestionErrorDetail(
                row=None,
                field="org_id",
                reason_code=IngestionReasonCode.ORG_ID_MISMATCH,
                message=f"File org_id '{file_org}' does not match context org_id '{org_id}'",
            )
        )
        return ImportResult(records=None, errors=errors, org_id=org_id)

    try:
        data["org_id"] = org_id
        paper = TestPaper.model_validate(data)
        return ImportResult(records=[paper], errors=[], org_id=org_id)
    except Exception as exc:
        errors.append(
            IngestionErrorDetail(
                row=None,
                field=None,
                reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                message=f"Failed to validate TestPaper: {exc}",
            )
        )
        return ImportResult(records=None, errors=errors, org_id=org_id)


# ------------------------------------------------------------------------------
# Importer 3: Decoded OMR Submissions
# ------------------------------------------------------------------------------


def import_submissions(
    file_path: str | Path,
    org_id: str,
    answer_key: list[QuestionMeta] | None = None,
    roster: list[StudentAdmissionRow] | None = None,
) -> ImportResult[StudentOMRSubmission]:
    """
    Import decoded OMR responses and scan links from CSV or JSON.
    Validates attendance status, valid response options, question ID bounds, and missing records.
    """
    path = Path(file_path)
    errors: list[IngestionErrorDetail] = []

    if not path.exists():
        errors.append(
            IngestionErrorDetail(
                row=None,
                field=None,
                reason_code=IngestionReasonCode.CORRUPTED_FILE,
                message=f"File not found: {path}",
            )
        )
        return ImportResult(records=None, errors=errors, org_id=org_id)

    raw_submissions: list[dict[str, Any]] = []

    if path.suffix.lower() == ".json":
        try:
            data = json.loads(_read_file_text(path))
        except Exception as exc:
            errors.append(
                IngestionErrorDetail(
                    row=None,
                    field=None,
                    reason_code=IngestionReasonCode.CORRUPTED_FILE,
                    message=f"Invalid JSON in {path}: {exc}",
                )
            )
            return ImportResult(records=None, errors=errors, org_id=org_id)

        if isinstance(data, dict):
            file_org = data.get("org_id")
            if file_org is not None and file_org != org_id:
                errors.append(
                    IngestionErrorDetail(
                        row=None,
                        field="org_id",
                        reason_code=IngestionReasonCode.ORG_ID_MISMATCH,
                        message=f"File org_id '{file_org}' does not match context org_id '{org_id}'",
                    )
                )
                return ImportResult(records=None, errors=errors, org_id=org_id)

            top_allowed = {"org_id", "schema_version", "test_id", "submissions"}
            for k in data:
                if k not in top_allowed:
                    errors.append(
                        IngestionErrorDetail(
                            row=None,
                            field=k,
                            reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                            message=f"Unknown top-level attribute '{k}' in submissions JSON",
                        )
                    )

            raw_submissions = data.get("submissions", [])
        elif isinstance(data, list):
            raw_submissions = data
    else:
        try:
            raw_submissions = _read_tabular_file(path)
        except Exception as exc:
            errors.append(
                IngestionErrorDetail(
                    row=None,
                    field=None,
                    reason_code=IngestionReasonCode.CORRUPTED_FILE,
                    message=f"Could not parse tabular submissions file {path}: {exc}",
                )
            )
            return ImportResult(records=None, errors=errors, org_id=org_id)

    seen_sub_ids: set[str] = set()
    seen_stu_ids: set[str] = set()
    records: list[StudentOMRSubmission] = []

    ak_qids: set[str] = {str(q.id) for q in answer_key} if answer_key else set()

    for idx, raw in enumerate(raw_submissions, start=1):
        responses: dict[str, str] = {}
        sub_id = raw.get("submission_id") or raw.get("id")
        stu_id = raw.get("student_id")
        raw_status = raw.get("status")
        scan_path = raw.get("scan_image_path")
        provenance = raw.get("scan_provenance")

        if isinstance(raw.get("responses"), dict):
            responses = {str(k): str(v).strip() for k, v in raw["responses"].items()}
            for k in raw:
                if k not in SUBMISSIONS_ALLOWED_FIELDS:
                    errors.append(
                        IngestionErrorDetail(
                            row=idx,
                            field=k,
                            reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                            message=f"Unknown field '{k}' in submission",
                        )
                    )
        else:
            for k, v in raw.items():
                if k in SUBMISSIONS_ALLOWED_FIELDS:
                    continue
                q_match = re.match(r"^Q?([0-9]+)$", k, re.IGNORECASE)
                if q_match:
                    qid_str = q_match.group(1)
                    responses[qid_str] = str(v).strip()
                else:
                    errors.append(
                        IngestionErrorDetail(
                            row=idx,
                            field=k,
                            reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                            message=f"Unknown column '{k}' in submissions sheet",
                        )
                    )

        if not sub_id:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="submission_id",
                    reason_code=IngestionReasonCode.MISSING_REQUIRED_FIELD,
                    message=f"Row {idx} missing required field 'submission_id'",
                )
            )
        else:
            sub_id_str = str(sub_id).strip()
            if sub_id_str in seen_sub_ids:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="submission_id",
                        reason_code=IngestionReasonCode.DUPLICATE_ID,
                        message=f"Duplicate submission_id '{sub_id_str}' at row {idx}",
                    )
                )
            else:
                seen_sub_ids.add(sub_id_str)

        if not stu_id:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="student_id",
                    reason_code=IngestionReasonCode.MISSING_REQUIRED_FIELD,
                    message=f"Row {idx} missing required field 'student_id'",
                )
            )
        else:
            stu_id_str = str(stu_id).strip()
            if stu_id_str in seen_stu_ids:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="student_id",
                        reason_code=IngestionReasonCode.DUPLICATE_ID,
                        message=f"Duplicate submission for student_id '{stu_id_str}' at row {idx}",
                    )
                )
            else:
                seen_stu_ids.add(stu_id_str)

        if not raw_status or raw_status not in ("PRESENT", "ABSENT"):
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="status",
                    reason_code=IngestionReasonCode.INVALID_ATTENDANCE_STATUS,
                    message=f"Invalid attendance status '{raw_status}'; must be PRESENT or ABSENT",
                )
            )

        status_enum = AttendanceStatus.PRESENT if raw_status == "PRESENT" else AttendanceStatus.ABSENT

        if status_enum == AttendanceStatus.PRESENT:
            for q_str, opt_str in responses.items():
                if opt_str not in VALID_OPTIONS:
                    errors.append(
                        IngestionErrorDetail(
                            row=idx,
                            field=f"response_{q_str}",
                            reason_code=IngestionReasonCode.INVALID_OPTION,
                            message=f"Invalid response option '{opt_str}' for Q{q_str}. Must be in {sorted(VALID_OPTIONS)}",
                        )
                    )

                if ak_qids and q_str not in ak_qids:
                    errors.append(
                        IngestionErrorDetail(
                            row=idx,
                            field=f"response_{q_str}",
                            reason_code=IngestionReasonCode.OUT_OF_RANGE_QUESTION_ID,
                            message=f"Question ID '{q_str}' is outside the valid answer key",
                        )
                    )

            if ak_qids:
                missing_qs = ak_qids - set(responses.keys())
                if missing_qs:
                    errors.append(
                        IngestionErrorDetail(
                            row=idx,
                            field="responses",
                            reason_code=IngestionReasonCode.MISSING_RECORD,
                            message=f"Present student missing responses for questions: {sorted(missing_qs)}. Missing records are never zero",
                        )
                    )

        if not errors:
            records.append(
                StudentOMRSubmission(
                    id=str(sub_id),
                    student_id=str(stu_id),
                    status=status_enum,
                    responses=responses,
                    scan_image_path=str(scan_path) if scan_path else None,
                    scan_provenance=ScanProvenance.model_validate(provenance) if provenance else None,
                    org_id=org_id,
                    schema_version=1,
                )
            )

    if roster:
        for s in roster:
            if s.id not in seen_stu_ids:
                errors.append(
                    IngestionErrorDetail(
                        row=None,
                        field="student_id",
                        reason_code=IngestionReasonCode.MISSING_RECORD,
                        message=f"Missing submission record for enrolled student '{s.id}'",
                    )
                )

    if errors:
        return ImportResult(records=None, errors=errors, org_id=org_id)

    return ImportResult(records=records, errors=[], org_id=org_id)


# ------------------------------------------------------------------------------
# Importer 4: Teacher Manual Marks Entry Totals
# ------------------------------------------------------------------------------


def import_marks_entry(
    file_path: str | Path,
    org_id: str,
    roster: list[StudentAdmissionRow] | None = None,
) -> ImportResult[MarksEntryRow]:
    """
    Import manual marks entry totals from CSV, JSON, or Excel (.xlsx).

    Rules:
      - Validates 0 <= marks <= max_marks.
      - Half marks allowed (parsed directly as exact Fraction from decimal text, never float per ADR-0002).
      - Blank marks rejected when PRESENT.
      - Marks forbidden when ABSENT.
      - Blanks never read as zero.
      - Duplicate rows rejected.
      - Unknown roll numbers reported per row if roster provided.
      - Subject max_marks consistent within an assessment.
      - Unknown columns rejected.
      - No partial import on error.
    """
    path = Path(file_path)
    errors: list[IngestionErrorDetail] = []

    if not path.exists():
        errors.append(
            IngestionErrorDetail(
                row=None,
                field=None,
                reason_code=IngestionReasonCode.CORRUPTED_FILE,
                message=f"File not found: {path}",
            )
        )
        return ImportResult(records=None, errors=errors, org_id=org_id)

    raw_rows: list[dict[str, Any]] = []
    header_max_marks: int | None = None
    header_subject: str | None = None
    header_assessment: str | None = None

    if path.suffix.lower() == ".json":
        try:
            data = json.loads(_read_file_text(path))
        except Exception as exc:
            errors.append(
                IngestionErrorDetail(
                    row=None,
                    field=None,
                    reason_code=IngestionReasonCode.CORRUPTED_FILE,
                    message=f"Invalid JSON in {path}: {exc}",
                )
            )
            return ImportResult(records=None, errors=errors, org_id=org_id)

        matched_org_data = None
        if isinstance(data, dict):
            for _k, v in data.items():
                if isinstance(v, dict) and v.get("org_id") == org_id:
                    matched_org_data = v
                    break

        if matched_org_data is not None:
            raw_rows = matched_org_data.get("students", [])
            for r in raw_rows:
                r["status"] = "PRESENT"
        elif isinstance(data, dict) and any(
            isinstance(v, dict) and "org_id" in v for v in data.values()
        ):
            errors.append(
                IngestionErrorDetail(
                    row=None,
                    field="org_id",
                    reason_code=IngestionReasonCode.ORG_ID_MISMATCH,
                    message=f"Organization '{org_id}' not found in multi-tenant file {path}",
                )
            )
            return ImportResult(records=None, errors=errors, org_id=org_id)
        elif isinstance(data, dict):
            file_org = data.get("org_id")
            if file_org is not None and file_org != org_id:
                errors.append(
                    IngestionErrorDetail(
                        row=None,
                        field="org_id",
                        reason_code=IngestionReasonCode.ORG_ID_MISMATCH,
                        message=f"File org_id '{file_org}' does not match context org_id '{org_id}'",
                    )
                )
                return ImportResult(records=None, errors=errors, org_id=org_id)

            top_allowed = {
                "org_id",
                "schema_version",
                "assessment_name",
                "subject",
                "max_marks",
                "cohort_label",
                "rows",
            }
            for k in data:
                if k not in top_allowed:
                    errors.append(
                        IngestionErrorDetail(
                            row=None,
                            field=k,
                            reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                            message=f"Unknown top-level attribute '{k}' in marks entry JSON",
                        )
                    )

            header_max_marks = data.get("max_marks")
            header_subject = data.get("subject")
            header_assessment = data.get("assessment_name")
            raw_rows = data.get("rows", [])
        elif isinstance(data, list):
            raw_rows = data
    else:
        try:
            raw_rows = _read_tabular_file(path)
        except Exception as exc:
            errors.append(
                IngestionErrorDetail(
                    row=None,
                    field=None,
                    reason_code=IngestionReasonCode.CORRUPTED_FILE,
                    message=f"Could not parse tabular marks entry file {path}: {exc}",
                )
            )
            return ImportResult(records=None, errors=errors, org_id=org_id)

    seen_rolls: set[str] = set()
    records: list[MarksEntryRow] = []
    detected_max_marks: int | None = header_max_marks

    roster_roll_map: dict[str, StudentAdmissionRow] = {}
    if roster:
        for s in roster:
            roster_roll_map[s.roll] = s

    for idx, raw in enumerate(raw_rows, start=1):
        for k in raw:
            if k not in MARKS_ENTRY_ALLOWED_FIELDS:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field=k,
                        reason_code=IngestionReasonCode.UNKNOWN_COLUMN,
                        message=f"Unknown column/field '{k}' in marks entry row {idx}",
                    )
                )

        roll = raw.get("roll_no") or raw.get("roll_number") or raw.get("roll")
        stu_id = raw.get("student_id") or raw.get("id")
        raw_status = raw.get("status")
        raw_mark = raw.get("marks")
        child_name = raw.get("child_display_name")
        sub = raw.get("subject", header_subject)
        asmt = raw.get("assessment_name", header_assessment)
        row_max = raw.get("max_marks", header_max_marks)

        row_org = raw.get("org_id")
        if row_org is not None and row_org != org_id:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="org_id",
                    reason_code=IngestionReasonCode.ORG_ID_MISMATCH,
                    message=f"Row {idx} org_id '{row_org}' does not match context org_id '{org_id}'",
                )
            )

        if not roll:
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="roll_no",
                    reason_code=IngestionReasonCode.MISSING_REQUIRED_FIELD,
                    message=f"Row {idx} missing required field 'roll_no'",
                )
            )
        else:
            roll_str = str(roll).strip()
            if roll_str in seen_rolls:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="roll_no",
                        reason_code=IngestionReasonCode.DUPLICATE_ROW,
                        message=f"Duplicate row for roll number '{roll_str}' at row {idx}",
                    )
                )
            else:
                seen_rolls.add(roll_str)

            if roster and roll_str not in roster_roll_map:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="roll_no",
                        reason_code=IngestionReasonCode.UNKNOWN_ROLL_NUMBER,
                        message=f"Roll number '{roll_str}' is not enrolled in cohort roster",
                    )
                )

        if row_max is not None:
            try:
                row_max_int = int(row_max)
                if detected_max_marks is None:
                    detected_max_marks = row_max_int
                elif detected_max_marks != row_max_int:
                    errors.append(
                        IngestionErrorDetail(
                            row=idx,
                            field="max_marks",
                            reason_code=IngestionReasonCode.INCONSISTENT_MAX_MARKS,
                            message=f"Row {idx} max_marks {row_max_int} inconsistent with earlier max_marks {detected_max_marks}",
                        )
                    )
            except ValueError:
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="max_marks",
                        reason_code=IngestionReasonCode.INVALID_MARK_VALUE,
                        message=f"max_marks '{row_max}' must be an integer",
                    )
                )

        if not raw_status or raw_status not in ("PRESENT", "ABSENT"):
            errors.append(
                IngestionErrorDetail(
                    row=idx,
                    field="status",
                    reason_code=IngestionReasonCode.INVALID_ATTENDANCE_STATUS,
                    message=f"Invalid attendance status '{raw_status}'; must be PRESENT or ABSENT",
                )
            )
            continue

        status_enum = AttendanceStatus.PRESENT if raw_status == "PRESENT" else AttendanceStatus.ABSENT
        parsed_mark: Fraction | None = None

        if status_enum == AttendanceStatus.ABSENT:
            if raw_mark is not None and str(raw_mark).strip() != "":
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="marks",
                        reason_code=IngestionReasonCode.ABSENT_WITH_MARKS,
                        message=f"ABSENT student at row {idx} cannot have marks recorded ('{raw_mark}')",
                    )
                )
        else:
            if raw_mark is None or (isinstance(raw_mark, str) and raw_mark.strip() == ""):
                errors.append(
                    IngestionErrorDetail(
                        row=idx,
                        field="marks",
                        reason_code=IngestionReasonCode.PRESENT_WITH_BLANK_MARKS,
                        message=f"PRESENT student at row {idx} cannot have blank marks. Blanks never read as zero",
                    )
                )
            else:
                try:
                    parsed_mark = parse_marks_decimal(raw_mark)
                except MarksValidationError as mve:
                    msg = str(mve)
                    if "not a whole or half mark" in msg or "not a valid whole or half mark" in msg:
                        code = IngestionReasonCode.FRACTIONAL_MARK_NOT_HALF
                    else:
                        code = IngestionReasonCode.INVALID_MARK_FORMAT
                    errors.append(
                        IngestionErrorDetail(
                            row=idx,
                            field="marks",
                            reason_code=code,
                            message=msg,
                        )
                    )
                except Exception as exc:
                    errors.append(
                        IngestionErrorDetail(
                            row=idx,
                            field="marks",
                            reason_code=IngestionReasonCode.INVALID_MARK_FORMAT,
                            message=f"Could not parse mark '{raw_mark}': {exc}",
                        )
                    )

                if parsed_mark is not None:
                    if parsed_mark < 0:
                        errors.append(
                            IngestionErrorDetail(
                                row=idx,
                                field="marks",
                                reason_code=IngestionReasonCode.MARK_BELOW_ZERO,
                                message=f"Marks cannot be negative, got {parsed_mark}",
                            )
                        )
                    if detected_max_marks is not None and parsed_mark > detected_max_marks:
                        errors.append(
                            IngestionErrorDetail(
                                row=idx,
                                field="marks",
                                reason_code=IngestionReasonCode.MARK_EXCEEDS_MAX,
                                message=f"Marks {parsed_mark} exceeds maximum attainable {detected_max_marks}",
                            )
                        )

        if not errors:
            records.append(
                MarksEntryRow(
                    roll_no=str(roll),
                    student_id=str(stu_id) if stu_id else None,
                    child_display_name=str(child_name) if child_name else None,
                    status=status_enum,
                    marks=parsed_mark,
                    assessment_name=str(asmt) if asmt else None,
                    subject=str(sub) if sub else None,
                    max_marks=detected_max_marks,
                    org_id=org_id,
                    schema_version=1,
                )
            )

    if roster:
        for s in roster:
            if s.roll not in seen_rolls:
                errors.append(
                    IngestionErrorDetail(
                        row=None,
                        field="roll_no",
                        reason_code=IngestionReasonCode.MISSING_RECORD,
                        message=f"Missing marks entry for enrolled student roll '{s.roll}'. Missing records are never zero",
                    )
                )

    if errors:
        return ImportResult(records=None, errors=errors, org_id=org_id)

    return ImportResult(records=records, errors=[], org_id=org_id)


def import_marks_entry_sheet(
    file_path: str | Path,
    org_id: str,
    roster: list[StudentAdmissionRow] | None = None,
) -> ImportResult[MarksEntrySheet]:
    """Import full MarksEntrySheet container object."""
    res = import_marks_entry(file_path=file_path, org_id=org_id, roster=roster)
    if not res.is_success or res.records is None:
        return ImportResult(records=None, errors=res.errors, org_id=org_id)

    asmt = res.records[0].assessment_name or "Assessment"
    subj = res.records[0].subject or "Subject"
    max_m = res.records[0].max_marks or 100

    sheet = MarksEntrySheet(
        assessment_name=asmt,
        subject=subj,
        max_marks=max_m,
        rows=res.records,
        org_id=org_id,
        schema_version=1,
    )
    return ImportResult(records=[sheet], errors=[], org_id=org_id)
