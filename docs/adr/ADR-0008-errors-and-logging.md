# ADR-0008: Typed Exception Hierarchy and Redacted Structured Logging

## Status
`ACCEPTED`

## Context
When processing examination scores and sending messages over carrier and WhatsApp networks, failures occur across diverse boundaries: malformed CSV rows, student-parent number collisions, OMR coordinate misalignments, WhatsApp rate limits, and audio duration overflows.
Ad-hoc exceptions (`raise Exception("failed")`) or raw unstructured console prints (`print(f"Sending to {phone}")`) violate Indian privacy requirements, leak personal data into log aggregators, and make automated retry decisions impossible.

## Options Considered

### Option 1: Standard Python Exceptions and Standard Logging
- *Description*: Native `ValueError`, `RuntimeError`, and standard format string logs.
- *Pros*: Familiar, zero boilerplate.
- *Cons*: Impossible to catch specific operational error classes cleanly; high risk of leaking PII (names, raw numbers) in exception traces.

### Option 2: Typed Domain Exception Hierarchy and Structured Masking Logger
- *Description*:
  - **Exception Hierarchy:** Rooted in `OMRDispatchError`, with stable error codes (e.g. `ERR_HYGIENE_SAME_NUMBER`, `ERR_PROVIDER_RATE_LIMIT`). Every exception carries structured attributes (row, field, code, operator_action_required).
  - **Structured JSON Logging & Invariant 17 (Primary Rule):** Invariant 17 is the primary logging rule: nothing sensitive is ever passed to a logger. Child names (`child_display_name`), class/section labels (`class_section`), phone numbers, tokens, scores, QR tokens, or audio payloads must never be passed to logger calls. Log records contain only timestamps, levels, correlation IDs, event names, and opaque context identifiers (`org_id`, `assessment_id`, `student_id`).
  - **Logger-Level Redaction (Backup Filter):** Automatic redacting filter installed on all logger handlers strictly as a defense-in-depth backup. The redaction filter is a safety net to catch accidental leaks; it is never a substitute for source-level hygiene.
  - **Masking Value Types:** Value types `PhoneNumber`, `Token`, `StudentName` whose `__str__` and `__repr__` automatically mask sensitive content (e.g., `+91 98*** **321`).
  - **Correlation ID:** Every batch run generates a unique `run_correlation_id` passed down to all logs and traces.
- *Pros*: Comprehensive privacy guarantee; strictly compliant with Invariant 17 and Rule 10 in `AGENTS.md`; predictable error handling.
- *Cons*: Developers must use domain exception classes instead of generic exceptions.

## Proposed Decision
We propose **Option 2 (Typed Exception Hierarchy, Invariant 17 Primary Logging Rule, and Redaction Filter as Backup)**.

### Logging Architecture & Privacy Invariants
1. **Primary Rule (Invariant 17 & Invariant 10):** Nothing sensitive is ever passed to a logger call. Specifically, child names (`child_display_name`), class/section labels (`class_section`), full phone numbers, student scores, QR tokens, and audio payloads must never appear in log arguments, format strings, or log record context dictionaries. Call sites log strictly opaque surrogate IDs (`student_id`, `assessment_id`, `org_id`, `job_id`, `correlation_id`), event names, and high-level progress counts.
2. **Backup Redaction Filter (Defense in Depth):** An automatic redacting filter is installed on all logger handlers strictly as a secondary backup/fallback to catch accidental leaks. Developers must never rely on the redaction filter to sanitize knowingly passed sensitive data.
3. **Masking Value Types:** Value types `PhoneNumber`, `Token`, `StudentName` automatically mask sensitive representations in strings/reprs as an additional layer of defense.
4. **Correlation ID:** Every batch run generates a unique `run_correlation_id` passed down to all logs and traces for end-to-end debugging without PII.

### Exception Hierarchy Design
```
OMRDispatchError (Base)
├── IngestionError
│   ├── SchemaValidationError
│   ├── DuplicateRecordError
│   └── NotSupportedError
├── ContactHygieneError
│   ├── InvalidPhoneNumberError
│   ├── InterceptionRiskError (student == parent)
│   └── UnverifiedSiblingCollisionError
├── DiagnosticError
│   ├── ZeroPresentStudentsError
│   └── CalculationMismatchError
├── TemplateError
│   ├── BannedVocabularyError
│   └── ConstraintViolationError
├── AudioError
│   ├── DurationOverflowError
│   └── TranscodingError
├── ProviderError
│   ├── RetrySafeProviderError
│   ├── OutcomeUnknownProviderError
│   ├── OperatorActionRequiredError
│   └── PermanentProviderError
└── PolicyError
    ├── ConsentRevokedError
    └── ServiceWindowExpiredError
```

## Consequences
- **Positive**: Strict compliance with Invariant 17 and Part C Rule 10; zero raw PII passed to or emitted by loggers; clear machine-readable error codes for audit logs.
- **Negative**: All custom errors must inherit from the hierarchy.
- **Neutral**: Enforced via pre-commit guardrail banning `print()` in `src/`.

## Revisit When
Revisit if third-party OpenTelemetry instrumentation replaces the local structured logging pipeline.
