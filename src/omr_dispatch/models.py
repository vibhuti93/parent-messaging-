"""
Domain Models, Ingestion Contracts, and Error Hierarchy (`src/omr_dispatch/models.py`).

Compliant with:
- ADR-0002: Exact Fraction arithmetic, zero float.
- ADR-0003: Opaque surrogate IDs, institutional tenancy (mandatory org_id).
- ADR-0004: Marking scheme as data, SINGLE_CORRECT supported in v1.
- ADR-0006: Explicit schema_version on all serialized models.
- ADR-0008: Typed exception hierarchy, stable machine-readable error codes.
- ADR-0017: Multi-school isolation, fail-closed tenant context.
"""

from __future__ import annotations

import re
from enum import StrEnum
from fractions import Fraction
from typing import Annotated, Any, Generic, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

# ------------------------------------------------------------------------------
# Exception Hierarchy (ADR-0008)
# ------------------------------------------------------------------------------


class OMRDispatchError(Exception):
    """Root domain exception for omr_dispatch_engine."""


class IngestionError(OMRDispatchError):
    """Base exception for input contract and ingestion failures."""


class SchemaValidationError(IngestionError):
    """Raised when an ingested record violates Pydantic schema constraints."""


class DuplicateRecordError(IngestionError):
    """Raised when duplicate entity IDs or duplicate rows are encountered."""


class NotSupportedError(IngestionError):
    """Raised when an unsupported question type or format is specified."""


class OrgIdMismatchError(IngestionError):
    """Raised when an ingested artifact's org_id does not match the active context."""


class MarksValidationError(IngestionError):
    """Raised when marks values violate scoring boundaries or numeric rules."""


# ------------------------------------------------------------------------------
# Enumerations
# ------------------------------------------------------------------------------


class AttendanceStatus(StrEnum):
    """Student examination attendance status (D-01)."""

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


class QuestionType(StrEnum):
    """
    Question format classification (ADR-0004).
    Version 1 strictly supports SINGLE_CORRECT.
    Other types raise NotSupportedError.
    """

    SINGLE_CORRECT = "SINGLE_CORRECT"
    MULTI_CORRECT = "MULTI_CORRECT"
    NUMERICAL = "NUMERICAL"
    MATRIX_MATCH = "MATRIX_MATCH"


class IngestionReasonCode(StrEnum):
    """
    Stable machine-readable ingestion rejection reason codes (S2 Task 4).
    Documented in docs/input_contracts.md.
    """

    ORG_ID_MISMATCH = "ORG_ID_MISMATCH"
    UNKNOWN_COLUMN = "UNKNOWN_COLUMN"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    DUPLICATE_ID = "DUPLICATE_ID"
    DUPLICATE_ROW = "DUPLICATE_ROW"
    INVALID_MARK_FORMAT = "INVALID_MARK_FORMAT"
    INVALID_MARK_VALUE = "INVALID_MARK_VALUE"
    FRACTIONAL_MARK_NOT_HALF = "FRACTIONAL_MARK_NOT_HALF"
    MARK_EXCEEDS_MAX = "MARK_EXCEEDS_MAX"
    MARK_BELOW_ZERO = "MARK_BELOW_ZERO"
    PRESENT_WITH_BLANK_MARKS = "PRESENT_WITH_BLANK_MARKS"
    ABSENT_WITH_MARKS = "ABSENT_WITH_MARKS"
    INCONSISTENT_MAX_MARKS = "INCONSISTENT_MAX_MARKS"
    UNKNOWN_ROLL_NUMBER = "UNKNOWN_ROLL_NUMBER"
    INVALID_ATTENDANCE_STATUS = "INVALID_ATTENDANCE_STATUS"
    INVALID_OPTION = "INVALID_OPTION"
    OUT_OF_RANGE_QUESTION_ID = "OUT_OF_RANGE_QUESTION_ID"
    MISSING_RECORD = "MISSING_RECORD"
    UNSUPPORTED_QUESTION_TYPE = "UNSUPPORTED_QUESTION_TYPE"
    CORRUPTED_FILE = "CORRUPTED_FILE"


# ------------------------------------------------------------------------------
# Marks Numeric Parsing (ADR-0002, S2 Task 2)
# ------------------------------------------------------------------------------

# Strict Latin digit pattern: digits with optional single decimal point.
# Rejects exponents (1e2), signs (+/-), thousands separators (,),
# Devanagari digits (०-९), blanks, NaN, inf.
LATIN_DECIMAL_MARKS_REGEX = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")


def parse_marks_decimal(val: Any) -> Fraction:
    """
    Parse marks directly from decimal text as an exact Fraction.
    Never passes through floating-point representation (ADR-0002).

    Rules:
      - Accepts only Latin digits in form: digits with optional single decimal point.
      - Rejects exponent notation, signs, thousands separators, NaN/inf, Devanagari digits, blank.
      - Disallows any standard float instance to prevent precision loss.
      - Allows only whole or half marks (Fraction denominator must be 1 or 2 per ADR-0002).
    """
    # Reject native float instances immediately
    if type(val).__name__ == "float":
        raise MarksValidationError("Native float marks are forbidden per ADR-0002; provide decimal text or Fraction")

    if isinstance(val, Fraction):
        if val.denominator not in (1, 2):
            raise MarksValidationError(
                f"Fractional mark {val} is not a valid whole or half mark; denominator must be 1 or 2 (ADR-0002)"
            )
        return val

    if isinstance(val, int):
        return Fraction(val, 1)

    if not isinstance(val, str):
        raise MarksValidationError(f"Invalid mark input type: {type(val).__name__}")

    text = val.strip() if isinstance(val, str) else ""
    if not text or not LATIN_DECIMAL_MARKS_REGEX.match(val):
        raise MarksValidationError(
            f"Invalid mark format '{val}'. Must be Latin digits with optional single decimal point, no signs or exponents"
        )

    try:
        frac = Fraction(val)
    except Exception as exc:
        raise MarksValidationError(f"Could not parse mark string '{val}' as exact rational: {exc}") from exc

    if frac.denominator not in (1, 2):
        raise MarksValidationError(
            f"Fractional mark '{val}' (exact {frac}) is not a whole or half mark. Denominator must be 1 or 2 per ADR-0002"
        )

    return frac


def _pydantic_validate_marks(val: Any) -> Fraction | None:
    if val is None or val == "":
        return None
    return parse_marks_decimal(val)


MarksFractionType = Annotated[
    Fraction | None,
    BeforeValidator(_pydantic_validate_marks),
    PlainSerializer(lambda x: str(x) if x is not None else None),
]


# ------------------------------------------------------------------------------
# Ingestion Result and Error Detail Models
# ------------------------------------------------------------------------------


class IngestionErrorDetail(BaseModel):
    """
    Structured error detail for an ingestion failure (S2 Task 4).
    Guarantees machine-readable row, field, and reason_code tracking.
    """

    model_config = ConfigDict(extra="forbid")

    row: int | None = None
    field: str | None = None
    reason_code: IngestionReasonCode
    message: str

    def as_tuple(self) -> tuple[int | None, str | None, str]:
        """Return (row, field, reason_code) tuple for assertion comparison."""
        return (self.row, self.field, self.reason_code.value)


T = TypeVar("T")


class ImportResult(BaseModel, Generic[T]):
    """
    Result container for an import operation.
    Enforces no-partial-import: if errors is non-empty, records is None.
    """

    model_config = ConfigDict(extra="forbid")

    records: list[T] | None = None
    errors: list[IngestionErrorDetail] = Field(default_factory=list)
    org_id: str
    schema_version: int = 1

    @property
    def is_success(self) -> bool:
        """True iff there are zero errors and records is populated."""
        return len(self.errors) == 0 and self.records is not None


# ------------------------------------------------------------------------------
# Core Ingestion Models
# ------------------------------------------------------------------------------

SubjectName = str


class CoordinateMap(BaseModel):
    """
    Bubble crop coordinate map on scanned sheet (ADR-0004, S2 Task 1).
    All models require org_id and schema_version per ADR-0006 and ADR-0017.
    """

    model_config = ConfigDict(extra="forbid")

    center_y: int | None = None
    col: int | None = None
    col_x: int | None = None
    row: int | None = None
    options: dict[str, dict[str, int]] = Field(default_factory=dict)
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1


class QuestionMeta(BaseModel):
    """
    Question metadata and marking scheme specification (ADR-0004, S2 Task 1).
    Version 1 strictly supports SINGLE_CORRECT; all other types raise NotSupportedError.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    subject: SubjectName = "General"
    question_type: QuestionType = QuestionType.SINGLE_CORRECT
    correct_option: str
    positive_marks: int = 4
    negative_marks: int = 1
    blank_marks: int = 0
    bubble_coordinates: CoordinateMap | None = None
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @property
    def question_id(self) -> int:
        return self.id

    @property
    def question_number(self) -> int:
        return self.id

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "question_id" in d:
                if "id" not in d:
                    d["id"] = d.pop("question_id")
                else:
                    d.pop("question_id")
            if "question_number" in d:
                if "id" not in d:
                    d["id"] = d.pop("question_number")
                else:
                    d.pop("question_number")
            return d
        return data

    @field_validator("question_type")
    @classmethod
    def validate_question_type(cls, v: QuestionType) -> QuestionType:
        if v != QuestionType.SINGLE_CORRECT:
            raise NotSupportedError(f"Question type '{v}' is not supported in Version 1 (ADR-0004)")
        return v

    @field_validator("positive_marks", "negative_marks", "blank_marks")
    @classmethod
    def validate_marks_weights(cls, v: int) -> int:
        if v < 0:
            raise IngestionError(f"Mark weight must be non-negative integer, got {v}")
        return v


class TestPaper(BaseModel):
    """
    Canonical examination test paper metadata (ADR-0004, ADR-0016).
    """

    model_config = ConfigDict(extra="forbid")

    test_id: str
    name: str
    subjects: list[str]
    max_marks_per_subject: dict[str, int]
    total_max_marks: int
    total_questions: int
    questions: list[QuestionMeta]
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @property
    def max_marks(self) -> int:
        return self.total_max_marks

    @model_validator(mode="before")
    @classmethod
    def stamp_org_id_and_version(cls, data: Any) -> Any:
        if isinstance(data, dict):
            parent_org = data.get("org_id", "DEFAULT_INSTITUTION")
            parent_ver = data.get("schema_version", 1)
            raw_q = data.get("questions", [])
            if isinstance(raw_q, list):
                new_q = []
                for q in raw_q:
                    if isinstance(q, dict):
                        qd = dict(q)
                        if "org_id" not in qd:
                            qd["org_id"] = parent_org
                        if "schema_version" not in qd:
                            qd["schema_version"] = parent_ver
                        new_q.append(qd)
                    else:
                        new_q.append(q)
                data["questions"] = new_q
        return data


class StudentAdmissionRow(BaseModel):
    """
    Roster admission input row (S2 Task 1, docs/data_map.md Section 2.1).
    All contacts stay raw un-normalized fields; quarantine is not executed here.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    id: str
    roll: str
    child_display_name: str
    class_section: str
    guardian_salutation: str | None = None
    student_name: str | None = None
    raw_student_phone: str | None = None
    raw_guardian_phone: str | None = None
    verified_sibling: bool = False
    guardian_verification: str = "UNVERIFIED"
    consent_status: str = "UNKNOWN"
    consent_scope: str | None = None
    consent_timestamp_utc: str | None = None
    consent_source: str | None = None
    consent_reference: str | None = None
    revocation_timestamp: str | None = None
    marks: MarksFractionType = None
    max_marks: int | None = None
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @property
    def student_id(self) -> str:
        return self.id

    @property
    def roll_number(self) -> str:
        return self.roll

    @property
    def roll_no(self) -> str:
        return self.roll

    @property
    def guardian_phone(self) -> str | None:
        return self.raw_guardian_phone

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "student_id" in d:
                d.setdefault("id", d.pop("student_id"))
            if "roll_number" in d:
                d.setdefault("roll", d.pop("roll_number"))
            elif "roll_no" in d:
                d.setdefault("roll", d.pop("roll_no"))
            if "guardian_phone" in d:
                d.setdefault("raw_guardian_phone", d.pop("guardian_phone"))
            if "student_phone" in d:
                d.setdefault("raw_student_phone", d.pop("student_phone"))
            if "first_name" in d:
                if "child_display_name" not in d:
                    d["child_display_name"] = d.pop("first_name")
                else:
                    d.pop("first_name")
            if "phone" in d:
                if "raw_guardian_phone" not in d:
                    d["raw_guardian_phone"] = d.pop("phone")
                else:
                    d.pop("phone")
            return d
        return data


class StudentRoster(BaseModel):
    """
    Complete cohort student roster batch (S2 Task 1).
    """

    model_config = ConfigDict(extra="forbid")

    org_id: str
    schema_version: int = 1
    test_id: str | None = None
    cohort_label: str | None = None
    school_name: str | None = None
    students: list[StudentAdmissionRow]

    @model_validator(mode="before")
    @classmethod
    def stamp_org_id_and_version(cls, data: Any) -> Any:
        if isinstance(data, dict):
            parent_org = data.get("org_id", "DEFAULT_INSTITUTION")
            parent_ver = data.get("schema_version", 1)
            raw_s = data.get("students", [])
            if isinstance(raw_s, list):
                new_s = []
                for s in raw_s:
                    if isinstance(s, dict):
                        sd = dict(s)
                        if "org_id" not in sd:
                            sd["org_id"] = parent_org
                        if "schema_version" not in sd:
                            sd["schema_version"] = parent_ver
                        new_s.append(sd)
                    else:
                        new_s.append(s)
                data["students"] = new_s
        return data


class ScanProvenance(BaseModel):
    """
    Physical OMR sheet scanner provenance metadata (S2 Task 1).
    """

    model_config = ConfigDict(extra="forbid")

    scanner_model: str | None = None
    scan_timestamp_utc: str | None = None
    resolution_dpi: int | None = None
    sha256_hash: str | None = None
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1


class StudentOMRSubmission(BaseModel):
    """
    Decoded OMR response submission per student (S2 Task 1).
    Preserves connection to source scan image and provenance.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    student_id: str
    status: AttendanceStatus
    responses: dict[str, str] = Field(default_factory=dict)
    scan_image_path: str | None = None
    scan_provenance: ScanProvenance | None = None
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @property
    def submission_id(self) -> str:
        return self.id

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases_and_responses(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "submission_id" in d:
                d.setdefault("id", d.pop("submission_id"))
            raw_r = d.get("responses")
            if isinstance(raw_r, dict):
                d["responses"] = {str(k): str(v) for k, v in raw_r.items()}
            return d
        return data


class OMRSubmissionsBatch(BaseModel):
    """
    Batch of OMR submissions for a test paper (S2 Task 1).
    """

    model_config = ConfigDict(extra="forbid")

    test_id: str
    submissions: list[StudentOMRSubmission]
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @model_validator(mode="before")
    @classmethod
    def stamp_org_id_and_version(cls, data: Any) -> Any:
        if isinstance(data, dict):
            parent_org = data.get("org_id", "DEFAULT_INSTITUTION")
            parent_ver = data.get("schema_version", 1)
            raw_sub = data.get("submissions", [])
            if isinstance(raw_sub, list):
                new_sub = []
                for sub in raw_sub:
                    if isinstance(sub, dict):
                        sd = dict(sub)
                        if "org_id" not in sd:
                            sd["org_id"] = parent_org
                        if "schema_version" not in sd:
                            sd["schema_version"] = parent_ver
                        new_sub.append(sd)
                    else:
                        new_sub.append(sub)
                data["submissions"] = new_sub
        return data


class MarksEntryRow(BaseModel):
    """
    Single row in a teacher manual marks entry sheet (ADR-0016, S2 Task 1).
    Marks are parsed as exact Fraction, never float.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    roll_no: str
    student_id: str | None = None
    child_display_name: str | None = None
    status: AttendanceStatus
    marks: MarksFractionType = None
    assessment_name: str | None = None
    subject: SubjectName | None = None
    max_marks: int | None = None
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @property
    def roll_number(self) -> str:
        return self.roll_no

    @property
    def roll(self) -> str:
        return self.roll_no

    @property
    def assessment(self) -> str | None:
        return self.assessment_name

    @property
    def id(self) -> str | None:
        return self.student_id

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "roll_number" in d:
                d.setdefault("roll_no", d.pop("roll_number"))
            elif "roll" in d:
                d.setdefault("roll_no", d.pop("roll"))
            if "id" in d:
                d.setdefault("student_id", d.pop("id"))
            if "assessment" in d:
                d.setdefault("assessment_name", d.pop("assessment"))
            return d
        return data


class MarksEntrySheet(BaseModel):
    """
    Container for teacher manual marks entry totals (ADR-0016, S2 Task 1).
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    assessment_name: str
    subject: SubjectName
    max_marks: int
    cohort_label: str | None = None
    rows: list[MarksEntryRow]
    org_id: str = "DEFAULT_INSTITUTION"
    schema_version: int = 1

    @model_validator(mode="before")
    @classmethod
    def stamp_and_validate_rows(cls, data: Any) -> Any:
        if isinstance(data, dict):
            parent_org = data.get("org_id", "DEFAULT_INSTITUTION")
            parent_ver = data.get("schema_version", 1)
            parent_max = data.get("max_marks")
            parent_subject = data.get("subject")
            parent_assessment = data.get("assessment_name")

            raw_rows = data.get("rows", [])
            if isinstance(raw_rows, list):
                new_rows = []
                for r in raw_rows:
                    if isinstance(r, dict):
                        rd = dict(r)
                        if "org_id" not in rd:
                            rd["org_id"] = parent_org
                        if "schema_version" not in rd:
                            rd["schema_version"] = parent_ver
                        if "max_marks" not in rd and parent_max is not None:
                            rd["max_marks"] = parent_max
                        if "subject" not in rd and parent_subject is not None:
                            rd["subject"] = parent_subject
                        if "assessment_name" not in rd and parent_assessment is not None:
                            rd["assessment_name"] = parent_assessment
                        new_rows.append(rd)
                    else:
                        new_rows.append(r)
                data["rows"] = new_rows
        return data
