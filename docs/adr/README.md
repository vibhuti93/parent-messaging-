# Architecture Decision Records (ADRs)

This directory documents architectural decisions for `omr_dispatch_engine`.

## Status Legend
- **`PROPOSED`**: The decision has been drafted and submitted for operator review.
- **`ACCEPTED`**: The operator has formally approved the decision.
- **`ACCEPTED (modified)`**: The decision was approved by the operator and subsequently amended by an operator mandate (e.g. ADR-0003 tenancy scope updated by ADR-0017).
- **`SUPERSEDED`**: The decision has been replaced by a later approved ADR.

---

## ADR Index

| ADR ID | Title | Status | Notes / OWNER-CONFIRM Items |
| :---: | :--- | :---: | :--- |
| [ADR-0001](ADR-0001-layering.md) | Pure Core vs. I/O Adapters Architecture | `ACCEPTED` | Accepted 2026-10-21 |
| [ADR-0002](ADR-0002-numeric-semantics.md) | Numeric Semantics, Exact Fractions, and Integer Arithmetic | `ACCEPTED` | Accepted 2026-10-21; display rounding `ROUND_HALF_UP` (S1-BLOCK-05) |
| [ADR-0003](ADR-0003-identifiers-and-keys.md) | Opaque Identifiers, Idempotency Keys, and Institutional Tenancy | `ACCEPTED` | Accepted 2026-10-20; multi-tenant amendment approved 2026-10-21 (see ADR-0017) |
| [ADR-0004](ADR-0004-marking-scheme-as-data.md) | Marking Scheme and Question Metadata as Data | `ACCEPTED` | Accepted 2026-10-21 |
| [ADR-0005](ADR-0005-time-and-clocks.md) | Time Representation, Timezones, and Injected Clocks | `ACCEPTED` | Accepted 2026-10-21 |
| [ADR-0006](ADR-0006-schema-and-contract-versioning.md) | Artifact Schema and SQL Migration Versioning | `ACCEPTED` | Accepted 2026-10-21 |
| [ADR-0007](ADR-0007-persistence-and-storage.md) | Persistence Strategy, SQLite WAL, and Append-Only Events | `ACCEPTED` | Accepted 2026-10-20; amended in S0-R5 (Postgres target, dual-engine contract tests) |
| [ADR-0008](ADR-0008-errors-and-logging.md) | Typed Exception Hierarchy and Redacted Structured Logging | `ACCEPTED` | Accepted 2026-10-21; Invariant 17 primary logging rule, redaction filter as backup |
| [ADR-0009](ADR-0009-configuration.md) | Typed Settings Object, Environment Validation, and SecretStr | `PROPOSED` | None |
| [ADR-0010](ADR-0010-text-and-unicode.md) | Text Handling, Unicode NFC, and Script Digit Policy | `ACCEPTED` | Accepted 2026-10-20 (Latin digits 0-9) |
| [ADR-0011](ADR-0011-canonical-environment-and-determinism.md) | Canonical Linux Environment and Test Determinism | `ACCEPTED` | Accepted 2026-10-21 |
| [ADR-0012](ADR-0012-test-architecture.md) | Test Architecture, Markers, and Coverage Floors | `PROPOSED` | None |
| [ADR-0013](ADR-0013-delivery-strategy.md) | Delivery Strategy via Walking Skeleton | `PROPOSED` | None |
| [ADR-0014](ADR-0014-dependencies-and-supply-chain.md) | Dependency Justification and Supply Chain Hardening | `PROPOSED` | None |
| [ADR-0015](ADR-0015-data-classification-and-lifecycle.md) | Data Classification, Masking, and Retention Lifecycle | `ACCEPTED` | Accepted 2026-10-21 |
| [ADR-0016](ADR-0016-assessment-model.md) | Assessment Entity, Multi-Kind Foundation, and Reporting Policy | `ACCEPTED` | Accepted 2026-10-21; PTM eligibility under D-04 applies to every assessment type (S1-BLOCK-01 Option 1) |
| [ADR-0017](ADR-0017-tenancy-model.md) | Multi-Tenant Database Architecture and Isolation Model | `ACCEPTED` | Accepted 2026-10-21 (Shared DB + Postgres RLS as defence in depth) |
| [ADR-0018](ADR-0018-application-service-layer-and-security.md) | Application Service Layer, Security Context, and Job Orchestration | `ACCEPTED` | Accepted 2026-10-21; Invariant 17 primary logging rule, redaction filter as backup |
| [ADR-0019](ADR-0019-per-school-sender-identity-and-routing.md) | Per-School Sender Identity, Credential Isolation, and Inbound Webhook Routing | `ACCEPTED` | Accepted 2026-10-21 (Dedicated sender identity per org) |
| [ADR-0020](ADR-0020-tenant-lifecycle-and-controls.md) | Tenant Lifecycle, Administrative Controls, Fair Scheduling, and Metering | `ACCEPTED` | Accepted 2026-10-21 |
