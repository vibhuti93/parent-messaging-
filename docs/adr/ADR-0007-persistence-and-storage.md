# ADR-0007: Persistence Strategy, SQLite WAL, and Append-Only Events

## Status
`PROPOSED` (Contains `OWNER-CONFIRM` item on Encryption at Rest)

## Context
Dispatching notifications involves money (WhatsApp Per-Message Pricing), strict compliance (parental consent and service windows), and severe deduplication requirements.
If an application crashes mid-dispatch or restarts during network latency, an unpersisted state leads to blind resends (double-charging and spamming parents) or lost delivery statuses.
We need a robust, offline-capable persistence layer for batches of up to 200 students per batch (D-14).

## Options Considered

### Option 1: In-Memory State or Ephemeral JSON Files
- *Description*: Keep dispatch queue in memory and write final results to JSON.
- *Pros*: Zero database setup.
- *Cons*: Process crash loses all state; impossible to implement transactional idempotency; strictly banned by architectural decisions.

### Option 2: SQLite WAL with Repository Interfaces and Append-Only Event Log
- *Description*:
  - **Storage Engine:** SQLite running in Write-Ahead Logging (WAL) mode (`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA synchronous=NORMAL;`).
  - **SQL Subset:** Strict ANSI/Postgres-compatible SQL subset (standard types: `INTEGER`, `TEXT`, `BLOB`), ensuring that swapping SQLite for PostgreSQL requires zero DDL changes.
  - **Append-Only Events:** State transitions are not in-place overwrites; they are written to an append-only `dispatch_events` table (`id`, `dispatch_id`, `event_type`, `payload`, `timestamp_utc`). The current status is derived from the latest event.
  - **Persist Intent Before Send:** Dispatch intent (`SUBMITTED`) must be durably committed to the database *before* the HTTP request is transmitted over the wire.
  - **DB-Level Constraints:** Unique index on `idempotency_key` and composite unique index on `(wamid, status)` to prevent race conditions.
  - **Backup:** Atomic online backup via SQLite `.backup` API.
  - **Encryption at Rest (`OWNER-CONFIRM`):** For development, rely on host operating system disk encryption (BitLocker / LUKS). Application-level database encryption (e.g. SQLCipher) is deferred to the pre-deployment compliance checklist (`docs/PRE_DEPLOYMENT_CHECKLIST.md`).
- *Pros*: ACID transactions; single-file portability; immune to network partitioning; zero external database server dependency for offline use.
- *Cons*: SQLite is single-writer; write concurrency is serialized (acceptable for 200 students at 80 mps = 2.5 seconds total write time).

## Proposed Decision
We propose **Option 2 (SQLite WAL, Repository Pattern, Append-Only Events, Persist-Intent-Before-Send)**.

### Database Schema Blueprint
```sql
CREATE TABLE dispatches (
    dispatch_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    test_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    recipient_phone_masked TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    current_status TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE dispatch_events (
    event_id TEXT PRIMARY KEY,
    dispatch_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- PENDING, SUBMITTED, DELIVERED, READ, FAILED, etc.
    provider_wamid TEXT,
    error_class TEXT,
    error_code INTEGER,
    raw_payload_json TEXT,
    occurred_at_utc TEXT NOT NULL,
    FOREIGN KEY(dispatch_id) REFERENCES dispatches(dispatch_id)
);
CREATE INDEX idx_dispatch_events_lookup ON dispatch_events(dispatch_id, occurred_at_utc);
CREATE UNIQUE INDEX idx_wamid_status_dedup ON dispatch_events(provider_wamid, event_type) WHERE provider_wamid IS NOT NULL;
```

## Consequences
- **Positive**: Guaranteed idempotency even if the process is killed midway; full audit history of every transition; atomic recovery on restart.
- **Negative**: Requires writing migration scripts and maintaining clean repository abstractions.
- **Neutral**: Added `OWNER-CONFIRM` item on encryption to `docs/DECISIONS_OPEN.md`.

## Revisit When
Revisit if concurrent batch ingestion from multiple physical campuses exceeds 1,000 writes/sec, requiring PostgreSQL clustering.
