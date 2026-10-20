# ADR-0008: Typed Exception Hierarchy and Redacted Structured Logging

## Status
`PROPOSED`

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
  - **Structured JSON Logging:** Emit structured log records (`timestamp`, `level`, `correlation_id`, `event_name`, `context`).
  - **Logger-Level Redaction:** Automatic redacting filter installed on all logger handlers. Even if a developer accidentally logs a phone number or token, the handler masks it before output.
  - **Masking Value Types:** Value types `PhoneNumber`, `Token`, `StudentName` whose `__str__` and `__repr__` automatically mask sensitive content (e.g., `+91 98*** **321`).
  - **Correlation ID:** Every batch run generates a unique `run_correlation_id` passed down to all logs and traces.
- *Pros*: Comprehensive privacy guarantee; compliant with Rule 10 in `AGENTS.md`; predictable error handling.
- *Cons*: Developers must use domain exception classes instead of generic exceptions.

## Proposed Decision
We propose **Option 2 (Typed Exception Hierarchy and Redacted Structured Logging)**.

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
- **Positive**: Strict compliance with Part C Rule 10; zero raw PII in logs; clear machine-readable error codes for audit logs.
- **Negative**: All custom errors must inherit from the hierarchy.
- **Neutral**: Enforced via pre-commit guardrail banning `print()` in `src/`.

## Revisit When
Revisit if third-party OpenTelemetry instrumentation replaces the local structured logging pipeline.
