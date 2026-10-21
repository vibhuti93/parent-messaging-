# ADR-0017: Multi-Tenant Database Architecture and Isolation Model

## Status
`PROPOSED`

## Context
Per Operator Decision 1 (Stage S0-R5), `omr_dispatch_engine` serves multiple educational institutions from inception as a hosted multi-tenant service.
Student records, examination marks, diagnostic evaluations, parent phone numbers, and WhatsApp delivery events belong to distinct, legally autonomous schools. Strict data isolation between institutions is paramount: no school may ever view, query, modify, or leak data belonging to another school.

We must select the database tenancy architecture that best balances isolation strength, operational overhead, per-tenant backup/restore and deletion capabilities, migration complexity, cost, and noisy neighbor mitigation.

## Options Considered

### Option 1: Shared Database & Shared Schema with `org_id` and Postgres Row-Level Security (RLS)
- *Description*:
  - All tenants share the same PostgreSQL database and database schema.
  - Every tenant-scoped table includes an indexed `org_id: str` column.
  - The application repository layer mandates a tenant context (`org_id`) on every query and transaction.
  - As defence in depth, PostgreSQL Row-Level Security (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`) is enforced at the database engine level, keying off `SET LOCAL app.current_org_id = '...'`. Even if application code omits a filter, the database rejects out-of-tenant row access.
- *Pros*:
  - **Cost & Resource Efficiency:** Minimal memory and connection overhead; single database connection pool; easily accommodates hundreds of schools.
  - **Schema Migrations:** Single migration run updates all tenants simultaneously; zero schema drift.
  - **Operational Simplicity:** Unified monitoring, indexing, and connection management.
  - **Isolation Strength:** Very high when combined with engine-level RLS and application repository enforcement.
- *Cons*:
  - Per-tenant restore requires selective table dumps or logical tenant filtering rather than raw database restores.
  - Misconfigured RLS policies could theoretically leak data if not guarded by strict contract tests.

### Option 2: Schema-per-Tenant (One Database, Separate Schemas)
- *Description*:
  - Each school is allocated its own PostgreSQL schema (e.g. `tenant_sch01`, `tenant_sch02`) inside a shared database instance.
  - Queries route by setting `search_path = tenant_sch01`.
- *Pros*:
  - Logical separation by namespace; simple per-tenant drop (`DROP SCHEMA ... CASCADE`) for offboarding.
- *Cons*:
  - **Migration Nightmare:** Applying migrations across hundreds of schemas requires iterating across every schema; failures midway cause severe schema drift.
  - **PostgreSQL Catalog Bloat:** PostgreSQL performance degrades when managing thousands of tables across hundreds of schemas (system catalog locks, shared buffer overhead).
  - Cross-tenant connection pooling (e.g. PgBouncer) is difficult to manage with dynamic `search_path`.

### Option 3: Database-per-Tenant (Physical Database Isolation)
- *Description*:
  - Each school is provisioned an independent PostgreSQL database (or separate managed database instance).
- *Pros*:
  - Maximum isolation; physical database-level blast radius containment; straightforward per-tenant backup, restore, and cryptographic key segregation.
- *Cons*:
  - **Extremely High Cost & Idle Overhead:** High base memory consumption per database; connection pool explosion; severely unviable for small budget rural schools.
  - **Migration Complexity:** Number of migrations scales linearly with tenants ($N \times migrations$).
  - Dynamic connection routing and resource management complexity.

## Comparison Matrix

| Evaluation Dimension | Option 1: Shared DB + Schema + RLS | Option 2: Schema-per-Tenant | Option 3: Database-per-Tenant |
| :--- | :--- | :--- | :--- |
| **Isolation Strength** | **High** (App Repository + Engine RLS) | **High** (Postgres search_path) | **Maximum** (Physical boundary) |
| **Migration Simplicity**| **Maximum** (1 migration for all tenants) | **Low** (Loop over N schemas; drift risk) | **Very Low** (Manage N discrete databases) |
| **Operational Cost** | **Lowest** (Shared pooling & memory) | **Medium** (Catalog bloat over time) | **Highest** (Dedicated storage/compute) |
| **Per-Tenant Deletion** | Clean (Logical `WHERE org_id = ...`) | Easy (`DROP SCHEMA CASCADE`) | Easiest (`DROP DATABASE`) |
| **Per-Tenant Restore** | Requires tenant-filtered logical restore | Dump/restore schema | Native database restore |
| **Noisy Neighbor Control**| Managed via rate limits & fair scheduling| Shared engine risks | Isolated compute |

## Proposed Decision
We propose **Option 1 (Shared Database & Schema with Mandatory `org_id`, Tenant-Scoped Repositories, and Postgres Row-Level Security as Defence in Depth)**.

### Architectural Invariants
1. **Mandatory Tenant Context in Repositories:**
   - Every repository method requires an explicit `org_id: str` parameter or a validated `Principal` context.
   - Any repository call initiated without a valid `org_id` context raises an immediate, non-catchable `TenantContextMissingError`.
2. **Postgres Row-Level Security (RLS) Policy:**
   ```sql
   -- Example RLS Policy Blueprint for Dispatches
   ALTER TABLE dispatches ENABLE ROW LEVEL SECURITY;
   ALTER TABLE dispatches FORCE ROW LEVEL SECURITY;

   CREATE POLICY tenant_isolation_policy ON dispatches
       FOR ALL
       USING (org_id = current_setting('app.current_org_id', true))
       WITH CHECK (org_id = current_setting('app.current_org_id', true));
   ```
3. **Dual-Engine Contract Strategy:**
   - **Target Database:** PostgreSQL is the production engine.
   - **Local Test Engine:** SQLite is used for zero-dependency local unit testing.
   - **Contract Test Suite:** From Stage S8, `test_stage8_repository_contract.py` runs identical queries against both SQLite and PostgreSQL. In SQLite, application-level repository scoping enforces tenant isolation; in PostgreSQL, tests additionally assert that RLS blocks cross-tenant access even if raw SQL queries attempt to bypass filters.
4. **Idempotency Keys:**
   - All idempotency keys are prefixed with `v1:{org_id}:...` ensuring mathematical uniqueness across tenants.

### Cross-Tenant Isolation Test Design
The contract test suite must implement the following specific isolation test cases:
1. **Overlapping Student Roll Numbers:**
   - Ingest student `STU_01` in `ORG_A` and student `STU_01` in `ORG_B` with different names and marks.
   - Querying `ORG_A` must return only `ORG_A`'s student; querying `ORG_B` must return only `ORG_B`'s student.
2. **Identical Parent Phone Number Across Orgs:**
   - Enroll the same parent phone number (`+91 98111 22201`) for a student in `ORG_A` and a student in `ORG_B`.
   - Dispatch to `ORG_A` must not mutate, resolve, or link any records in `ORG_B`.
3. **Idempotency Key Collisions:**
   - Generate dispatches with identical parameters in `ORG_A` and `ORG_B`.
   - Verify that composite keys `v1:ORG_A:TEST_1:STU_01:...` and `v1:ORG_B:TEST_1:STU_01:...` are stored independently without unique constraint collisions.
4. **Webhook Event Routing to Wrong Org:**
   - Transmit a mock webhook delivery receipt containing a `phone_number_id` belonging to `ORG_A`, but with an event payload referencing a message from `ORG_B`.
   - The webhook processor must reject the update with a tenant mismatch error and record an audit security alert.
5. **Missing Tenant Context Gate:**
   - Invoke repository query without setting tenant context. Must raise `TenantContextMissingError`.
6. **RLS Bypass Attempt:**
   - Set session `app.current_org_id = 'ORG_A'`; execute raw `SELECT * FROM dispatches WHERE org_id = 'ORG_B'`.
   - Must return 0 rows under Postgres RLS enforcement.

## Consequences
- **Positive**: Exceptional cost-efficiency; effortless schema migrations; multi-layered defence in depth (app layer + DB engine layer).
- **Negative**: Requires setting session variable `app.current_org_id` on PostgreSQL connections in the adapter.
- **Neutral**: Added to `docs/DECISIONS_OPEN.md` as `OWNER-CONFIRM` for operator confirmation.

## Revisit When
Revisit if an enterprise customer contract legally mandates physically isolated database infrastructure or customer-managed encryption keys (CMEK).
