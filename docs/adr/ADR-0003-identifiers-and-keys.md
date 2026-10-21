# ADR-0003: Identifiers, Idempotency Keys, and Institutional Tenancy

## Status
`ACCEPTED` (Originally accepted by operator 2026-10-20; multi-tenant amendment re-approved by operator 2026-10-21 per Operator Decision 1 establishing multi-school hosted service from inception. See ADR-0017 for multi-school tenancy architecture. ADR-0003 core text, opaque UUIDs, and composite idempotency key design with `org_id` prefixing are retained.)

## Context
The system tracks students, exams, scanned sheets, diagnostic records, delivery attempts, and parent confirmations.
Using external identifiers (such as school roll numbers or parent phone numbers) as primary database keys leads to data collisions (roll numbers repeat every academic year and across sections) and privacy leaks (embedding phone numbers in idempotency keys exposes PII in logs and URLs).
Furthermore, while the engine initially runs for a single batch/institution, designing the schema without an institutional tenancy identifier (`org_id`) makes future multi-branch or SaaS deployment require massive schema redesign.

## Options Considered

### Option 1: Roll Numbers as Primary Keys, Single-Tenant Only
- *Description*: Tables keyed on `roll_number` and `test_id`. No `org_id`.
- *Pros*: Simple, mirrors school spreadsheet columns directly.
- *Cons*: Collisions when roll numbers change or duplicate; inability to support multiple branches; difficult data isolation.

### Option 2: Opaque Surrogate UUIDs, PII-Free Composite Keys, Multi-Tenancy from Inception
- *Description*:
  - Internal entities use opaque unique identifiers (UUIDv4 or ULID).
  - External roll numbers are stored as indexed attributes scoped to an institution.
  - Idempotency keys are composite, structured, versioned, and free of PII:
    `v1:{org_id}:{exam_id}:{student_id}:{channel}:{event_type}:{sequence}`
  - Schema includes `org_id: str` on all persistent records from Day 1.
- *Pros*: Guaranteed uniqueness; zero PII leakage into third-party headers; future-proof multi-tenancy.
- *Cons*: Requires joining on surrogate IDs when correlating with raw spreadsheet inputs.

## Proposed Decision
We propose **Option 2 (Opaque Surrogate UUIDs, PII-Free Composite Keys, and `org_id` Tenancy)**.

### Invariants & Specifications
1. **Internal IDs:** `student_id`, `submission_id`, `dispatch_id`, `event_id` are 128-bit opaque UUIDs (formatted as hex strings).
2. **Idempotency Key Composition:**
   - Format: `v1:{org_id}:{test_id}:{student_id}:{channel}:{purpose}:{sequence}`
   - Example: `v1:SCH01:EXAM_20261018:STU_001:WHATSAPP:PRIMARY:0`
   - *Strict Rule*: Phone numbers, guardian names, tokens, and marks are **never** included in the idempotency key.
3. **Tenancy Scope (`OWNER-CONFIRM`):**
   - **Proposal**: Include `org_id: str` (e.g. `"DEFAULT_INSTITUTION"` or school code) across all database tables and models from inception.
   - *Rationale*: Adding `org_id` now costs negligible overhead; adding it later requires migrating every table, foreign key, and unique constraint.

## Consequences
- **Positive**: Complete privacy preservation; bulletproof idempotency without leaking phone numbers to Meta API logging; seamless scaling across multiple batches or branches.
- **Negative**: Ingestion must generate and map surrogate IDs from raw CSV rows.
- **Neutral**: Added to `docs/DECISIONS_OPEN.md` for operator confirmation.

## Revisit When
Revisit if the operator confirms the deployment will permanently remain single-school standalone with no multi-institution requirement.

## Re-approval record
- **Status:** APPROVED
- **Approved by:** Operator (Human Sign-off)
- **Date:** 2026-10-21
- **Scope of Re-approval:** Confirms amendment of ADR-0003 from single-school scope to multi-tenant scope (`org_id` mandatory across all tenant-scoped entities, repositories, and composite idempotency keys `sha256(f"{org_id}:{student_id}:{assessment_id}:{purpose}:{channel}:{event_type}")`), in alignment with Operator Decision 1 (2026-10-21) and ADR-0017. Opaque internal UUIDs and natural key scoping rules remain unchanged.
