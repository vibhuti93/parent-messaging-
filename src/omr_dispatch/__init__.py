"""
OMR Dispatch Engine (`omr_dispatch_engine`)
A high-assurance, deterministic diagnostics and parent notification engine for schools.
"""

__version__ = "0.1.0"

from omr_dispatch.config import Settings, load_settings
from omr_dispatch.ingestion import (
    import_answer_key,
    import_marks_entry,
    import_marks_entry_sheet,
    import_roster,
    import_submissions,
    import_test_paper,
)
from omr_dispatch.models import (
    AttendanceStatus,
    CoordinateMap,
    ImportResult,
    IngestionError,
    IngestionErrorDetail,
    IngestionReasonCode,
    MarksEntryRow,
    MarksEntrySheet,
    MarksValidationError,
    NotSupportedError,
    OMRDispatchError,
    OMRSubmissionsBatch,
    OrgIdMismatchError,
    QuestionMeta,
    QuestionType,
    ScanProvenance,
    SchemaValidationError,
    StudentAdmissionRow,
    StudentOMRSubmission,
    StudentRoster,
    TestPaper,
    parse_marks_decimal,
)

__all__ = [
    "AttendanceStatus",
    "CoordinateMap",
    "ImportResult",
    "IngestionError",
    "IngestionErrorDetail",
    "IngestionReasonCode",
    "MarksEntryRow",
    "MarksEntrySheet",
    "MarksValidationError",
    "NotSupportedError",
    "OMRDispatchError",
    "OMRSubmissionsBatch",
    "OrgIdMismatchError",
    "QuestionMeta",
    "QuestionType",
    "ScanProvenance",
    "SchemaValidationError",
    "Settings",
    "StudentAdmissionRow",
    "StudentOMRSubmission",
    "StudentRoster",
    "TestPaper",
    "import_answer_key",
    "import_marks_entry",
    "import_marks_entry_sheet",
    "import_roster",
    "import_submissions",
    "import_test_paper",
    "load_settings",
    "parse_marks_decimal",
]
