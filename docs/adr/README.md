# Architecture Decision Records (ADRs)

This directory documents architectural decisions for `omr_dispatch_engine`.

## Status Legend
- **`PROPOSED`**: The decision has been drafted and submitted for operator review. (All ADRs in this directory are currently `PROPOSED`).
- **`ACCEPTED`**: The operator has formally approved the decision. *(Per S0-R4 rules, the agent only proposes; the operator accepts. No ADR is marked ACCEPTED by the agent)*.
- **`SUPERSEDED`**: The decision has been replaced by a later approved ADR.

---

## ADR Index

| ADR ID | Title | Status | OWNER-CONFIRM Items |
| :---: | :--- | :---: | :--- |
| [ADR-0001](ADR-0001-layering.md) | Pure Core vs. I/O Adapters Architecture | `PROPOSED` | None |
| [ADR-0002](ADR-0002-numeric-semantics.md) | Numeric Semantics, Exact Fractions, and Integer Arithmetic | `PROPOSED` | None |
| [ADR-0003](ADR-0003-identifiers-and-keys.md) | Opaque Identifiers, Idempotency Keys, and Institutional Tenancy | `PROPOSED` | **OWNER-CONFIRM**: Tenancy scope (proposing `org_id` from inception) |
| [ADR-0004](ADR-0004-marking-scheme-as-data.md) | Marking Scheme and Question Metadata as Data | `PROPOSED` | None |
| [ADR-0005](ADR-0005-time-and-clocks.md) | Time Representation, Timezones, and Injected Clocks | `PROPOSED` | None |
| [ADR-0006](ADR-0006-schema-and-contract-versioning.md) | Artifact Schema and SQL Migration Versioning | `PROPOSED` | None |
| [ADR-0007](ADR-0007-persistence-and-storage.md) | Persistence Strategy, SQLite WAL, and Append-Only Events | `PROPOSED` | **OWNER-CONFIRM**: Encryption at rest (proposing disk-level for dev) |
| [ADR-0008](ADR-0008-errors-and-logging.md) | Typed Exception Hierarchy and Redacted Structured Logging | `PROPOSED` | None |
| [ADR-0009](ADR-0009-configuration.md) | Typed Settings Object, Environment Validation, and SecretStr | `PROPOSED` | None |
| [ADR-0010](ADR-0010-text-and-unicode.md) | Text Handling, Unicode NFC, and Script Digit Policy | `PROPOSED` | **OWNER-CONFIRM**: Digit policy (proposing Latin digits `0-9`) |
| [ADR-0011](ADR-0011-canonical-environment-and-determinism.md) | Canonical Linux Environment and Test Determinism | `PROPOSED` | None |
| [ADR-0012](ADR-0012-test-architecture.md) | Test Architecture, Markers, and Coverage Floors | `PROPOSED` | None |
| [ADR-0013](ADR-0013-delivery-strategy.md) | Delivery Strategy via Walking Skeleton | `PROPOSED` | None |
| [ADR-0014](ADR-0014-dependencies-and-supply-chain.md) | Dependency Justification and Supply Chain Hardening | `PROPOSED` | None |
| [ADR-0015](ADR-0015-data-classification-and-lifecycle.md) | Data Classification, Masking, and Retention Lifecycle | `PROPOSED` | None |
