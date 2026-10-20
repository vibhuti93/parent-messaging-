# ADR-0006: Schema and Contract Versioning

## Status
`PROPOSED`

## Context
Educational institutions generate archival records that must be retained for at least the current academic year (per D-13), while dispatch events and audit logs must be retained for 90 days. Over time, schemas evolve: new fields are added to OMR reports, database tables require extra indexing, and external provider contracts shift.
If serialized JSON payloads and database schemas lack explicit version markers, deserialization code silently parses outdated models, corrupts archives, and breaks reproducible auditing.

## Options Considered

### Option 1: Implicit / Unversioned Schemas
- *Description*: Store JSON files and database tables without explicit version identifiers.
- *Pros*: Faster to prototype.
- *Cons*: Total breakdown upon schema modification; невозможно to distinguish v1 from v2 files during historical audit replays.

### Option 2: Explicit `schema_version` on All Artifacts and Numbered SQL Migrations
- *Description*:
  - **Serialized Artifacts:** Every JSON document, diagnostic report, input contract file, and run manifest must carry a top-level `"schema_version": int` (e.g. `1`).
  - **Database Migrations:** Numbered linear SQL migration scripts (e.g., `migrations/0001_initial_tables.sql`, `migrations/0002_add_delivery_attempts.sql`) applied from the very first table creation.
  - **Compatibility Rules:** Additive changes are non-breaking; field deletions or semantic shifts require incrementing `schema_version` and writing an explicit migration converter.
  - **Fixture Stability:** Strictly linked to the W4 fixture change protocol in `AGENTS.md`—frozen test fixtures are never edited in place to match new code.
- *Pros*: Clear schema provenance; backward compatibility; safe archival retrieval.
- *Cons*: Requires maintaining migration scripts and validator code.

## Proposed Decision
We propose **Option 2 (Explicit `schema_version` and Numbered SQL Migrations)**.

### Specification & Invariants
1. **JSON Schema Version:**
   ```json
   {
     "schema_version": 1,
     "created_at_utc": "2026-10-20T12:00:00Z",
     "payload": { ... }
   }
   ```
2. **SQL Migration Standard:**
   - Linear forward migrations tracked in a `schema_migrations` table:
     `CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at_utc TEXT NOT NULL);`
   - Migrations are idempotent and run automatically inside an explicit transaction on application startup.
3. **Fixture Change Process (W4):**
   - In accordance with `AGENTS.md` Rule 6, frozen fixtures are immutable. If a schema version bump requires new fixtures, new versioned fixture directories (e.g. `fixtures/v2/`) must be created, leaving golden v1 fixtures intact.

## Consequences
- **Positive**: Complete auditability; zero ambiguity when parsing historical diagnostic runs; automated database schema updates.
- **Negative**: Extra boilerplate for `schema_version` field on every domain model.
- **Neutral**: Enforces disciplined evolution.

## Revisit When
Revisit if multi-database distributed replication requires decentralized migration tooling (e.g. Alembic).
