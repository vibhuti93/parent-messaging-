# ADR-0004: Marking Scheme and Question Metadata as Data

## Status
`ACCEPTED`

## Context
Different examinations employ varying scoring rules (e.g. +4 for correct, -1 for incorrect, 0 for unattempted). Some advanced competitive exams feature multiple-correct choices, numerical values, or matrix matching.
Hardcoding subject names (Physics, Chemistry, Mathematics) or question types as Python code constants creates rigid code that breaks when schools introduce Biology, English, or non-negative marking.

## Options Considered

### Option 1: Hardcoded Constants for Subjects and Questions
- *Description*: Python `Enum` for `Subject(Enum)` and fixed scoring formulas in `diagnostics.py`.
- *Pros*: Quick to write for a single specific 3-subject test paper.
- *Cons*: Cannot handle different test structures, subjects, or alternate marking schemes without code edits.

### Option 2: Marking Scheme and Subject Sections Defined Strictly as Ingested Data
- *Description*:
  - The answer key and test definition define the marking scheme per question (`positive_marks: int`, `negative_marks: int`, `partial_marks: int = 0`).
  - Subject names and question types are dynamic data attributes.
  - **Version 1 Scope**: Strictly supports `SINGLE_CORRECT` multiple-choice questions. Any question record with an unsupported type (`MULTI_CORRECT`, `NUMERICAL`, `MATRIX_MATCH`) raises an explicit `NotSupportedError("Question type {type} is not supported in Version 1")`.
  - Golden fixtures are unaffected.
- *Pros*: Full flexibility for any subject names or integer marking schemes; robust fail-closed validation for unsupported types.
- *Cons*: Ingestion must validate that the sum of positive marks equals the expected total marks.

## Proposed Decision
We propose **Option 2 (Marking Scheme and Subject Sections as Data; Version 1 SINGLE_CORRECT Only)**.

### Model Specification
```python
class QuestionType(str, Enum):
    SINGLE_CORRECT = "SINGLE_CORRECT"
    # Future types (rejected with NotSupportedError in v1)
    MULTI_CORRECT = "MULTI_CORRECT"
    NUMERICAL = "NUMERICAL"
    MATRIX_MATCH = "MATRIX_MATCH"

class QuestionMeta(BaseModel):
    id: int
    subject: str                      # Ingested string (e.g. "Physics", "Science")
    question_type: QuestionType = QuestionType.SINGLE_CORRECT
    correct_option: str               # "A", "B", "C", "D"
    positive_marks: int               # e.g. 4
    negative_marks: int               # e.g. 1 (magnitude subtracted if wrong)
    bubble_coordinates: CoordinateMap | None = None
```

## Consequences
- **Positive**: Subjects and marking weights are dynamic data; golden test fixtures pass without modification; clear error path for advanced question types.
- **Negative**: Need explicit validation in `ingestion.py` verifying that all positive marks and negative marks are non-negative integers.
- **Neutral**: Enforces fail-closed safety.

## Revisit When
Revisit in Version 2 if multi-correct or numerical input questions are added to the external OMR engine scope.
