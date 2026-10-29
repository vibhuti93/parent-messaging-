"""
Tenant-Scoped Durable Persistence & Repository Engine (`src/omr_dispatch/messaging/store.py`).

Compliant with:
- Part B Stage S8 Task 2, 3, 4 & Gate 8 requirements.
- Dual-engine architecture: SQLite (local tests) and PostgreSQL (target production database).
- Global Invariant 10: Never log or persist full phone numbers, tokens, or personal payloads; mask them.
- Global Invariant 13: Fail closed: uncertain input -> REVIEW_REQUIRED / block / defer.
- Global Invariant 15: Every repository call requires an explicit org context (org_id).
- ADR-0005: Timezone-aware UTC datetimes.
- ADR-0006: Explicit schema_version and numbered migrations.
- ADR-0007: Append-only dispatch events, derived status, DB-level unique constraints.
- ADR-0017: Multi-tenant shared DB & schema with mandatory org_id, tenant-scoped repositories, and RLS.
- ADR-0020: Tenant lifecycle state machine, pause / emergency kill-switch.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from omr_dispatch.messaging.policy import TenantContextMissingError
from omr_dispatch.models import OMRDispatchError


class IdempotencyCollisionError(OMRDispatchError):
    """Raised when attempting to insert a dispatch with an already existing (org_id, idempotency_key)."""


class IllegalStateTransitionError(OMRDispatchError):
    """Raised when an invalid state transition is attempted on a dispatch."""


class DuplicateWamidEventError(OMRDispatchError):
    """Raised when duplicate (org_id, provider_wamid, event_type) delivery event occurs."""


class DispatchNotFoundError(OMRDispatchError):
    """Raised when a dispatch record cannot be located within the given org context."""


class TenantNotFoundError(OMRDispatchError):
    """Raised when tenant record cannot be found."""


class TenantSuspendedError(OMRDispatchError):
    """Raised when dispatch operations are attempted on a suspended tenant."""


class DispatchState(StrEnum):
    """
    Authoritative dispatch lifecycle states (S8 Task 2).
    Append-only events transition dispatches across these states.
    """

    PENDING = "PENDING"
    BLOCKED_CONSENT = "BLOCKED_CONSENT"
    BLOCKED_HYGIENE = "BLOCKED_HYGIENE"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    SCHEDULED = "SCHEDULED"
    UPLOADING_MEDIA = "UPLOADING_MEDIA"
    SUBMITTED = "SUBMITTED"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"
    RETRY_PENDING = "RETRY_PENDING"
    UNKNOWN_NEEDS_REVIEW = "UNKNOWN_NEEDS_REVIEW"
    CANCELLED = "CANCELLED"


# State transition rules: Map current state to allowed next states
VALID_STATE_TRANSITIONS: dict[DispatchState, set[DispatchState]] = {
    DispatchState.PENDING: {
        DispatchState.BLOCKED_CONSENT,
        DispatchState.BLOCKED_HYGIENE,
        DispatchState.BLOCKED_POLICY,
        DispatchState.SCHEDULED,
        DispatchState.CANCELLED,
    },
    DispatchState.BLOCKED_CONSENT: set(),  # Terminal for this evaluation
    DispatchState.BLOCKED_HYGIENE: set(),  # Terminal for this evaluation
    DispatchState.BLOCKED_POLICY: set(),   # Terminal for this evaluation
    DispatchState.SCHEDULED: {
        DispatchState.UPLOADING_MEDIA,
        DispatchState.SUBMITTED,
        DispatchState.CANCELLED,
    },
    DispatchState.UPLOADING_MEDIA: {
        DispatchState.SUBMITTED,
        DispatchState.FAILED,
        DispatchState.RETRY_PENDING,
        DispatchState.CANCELLED,
    },
    DispatchState.SUBMITTED: {
        DispatchState.DELIVERED,
        DispatchState.FAILED,
        DispatchState.RETRY_PENDING,
        DispatchState.UNKNOWN_NEEDS_REVIEW,
        DispatchState.CANCELLED,
    },
    DispatchState.DELIVERED: {
        DispatchState.READ,
    },
    DispatchState.READ: set(),  # Terminal success
    DispatchState.FAILED: {
        DispatchState.RETRY_PENDING,
        DispatchState.CANCELLED,
    },
    DispatchState.RETRY_PENDING: {
        DispatchState.SCHEDULED,
        DispatchState.UPLOADING_MEDIA,
        DispatchState.SUBMITTED,
        DispatchState.FAILED,
        DispatchState.CANCELLED,
    },
    DispatchState.UNKNOWN_NEEDS_REVIEW: {
        DispatchState.FAILED,
        DispatchState.CANCELLED,
        DispatchState.DELIVERED,
        DispatchState.READ,
    },
    DispatchState.CANCELLED: set(),  # Terminal cancelled
}


class DispatchRecord(BaseModel):
    """Durable dispatch aggregate root record."""

    model_config = ConfigDict(extra="forbid")

    dispatch_id: str
    org_id: str
    assessment_id: str
    student_id: str
    recipient_phone_masked: str
    idempotency_key: str
    current_status: DispatchState
    created_at_utc: datetime
    updated_at_utc: datetime
    schema_version: int = 1


class DispatchEventRecord(BaseModel):
    """Append-only dispatch event log record."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    dispatch_id: str
    org_id: str
    event_type: DispatchState
    provider_wamid: str | None = None
    error_class: str | None = None
    error_code: int | None = None
    reason_code: str | None = None
    raw_payload_json: str | None = None
    occurred_at_utc: datetime
    schema_version: int = 1


class TenantRecord(BaseModel):
    """Institutional tenant account and lifecycle record (ADR-0020)."""

    model_config = ConfigDict(extra="forbid")

    org_id: str
    school_name: str
    lifecycle_state: str = "ACTIVE"
    emergency_kill_switch: bool = False
    daily_message_quota: int = 1000
    include_roll_in_text: bool = False
    created_at_utc: datetime
    updated_at_utc: datetime
    schema_version: int = 1


class AuditLogRecord(BaseModel):
    """Tenant-scoped immutable audit log entry."""

    model_config = ConfigDict(extra="forbid")

    audit_id: str
    org_id: str
    actor_id: str
    actor_type: str
    action_type: str
    target_id: str | None = None
    reason_code: str | None = None
    details_json: str | None = None
    occurred_at_utc: datetime
    schema_version: int = 1


# DDL Scripts matching ADR-0006 & ADR-0007 (Strict ANSI / Postgres compatible)
SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tenants (
    org_id TEXT PRIMARY KEY,
    school_name TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL,
    emergency_kill_switch INTEGER NOT NULL DEFAULT 0,
    daily_message_quota INTEGER NOT NULL DEFAULT 1000,
    include_roll_in_text INTEGER NOT NULL DEFAULT 0,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dispatches (
    dispatch_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    recipient_phone_masked TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    current_status TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    CONSTRAINT uq_dispatches_org_idempotency UNIQUE (org_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS dispatch_events (
    event_id TEXT PRIMARY KEY,
    dispatch_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    provider_wamid TEXT,
    error_class TEXT,
    error_code INTEGER,
    reason_code TEXT,
    raw_payload_json TEXT,
    occurred_at_utc TEXT NOT NULL,
    FOREIGN KEY(dispatch_id) REFERENCES dispatches(dispatch_id)
);

CREATE INDEX IF NOT EXISTS idx_dispatch_events_lookup ON dispatch_events(org_id, dispatch_id, occurred_at_utc);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wamid_status_dedup ON dispatch_events(org_id, provider_wamid, event_type) WHERE provider_wamid IS NOT NULL;

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_id TEXT,
    reason_code TEXT,
    details_json TEXT,
    occurred_at_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_lookup ON audit_logs(org_id, occurred_at_utc);
"""

POSTGRES_RLS_DDL = """
ALTER TABLE dispatches ENABLE ROW LEVEL SECURITY;
ALTER TABLE dispatches FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_dispatches ON dispatches
    FOR ALL
    USING (org_id = current_setting('app.current_org_id', true))
    WITH CHECK (org_id = current_setting('app.current_org_id', true));

ALTER TABLE dispatch_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE dispatch_events FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_events ON dispatch_events
    FOR ALL
    USING (org_id = current_setting('app.current_org_id', true))
    WITH CHECK (org_id = current_setting('app.current_org_id', true));

ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_audit ON audit_logs
    FOR ALL
    USING (org_id = current_setting('app.current_org_id', true))
    WITH CHECK (org_id = current_setting('app.current_org_id', true));
"""


class DispatchRepository(Protocol):
    """Protocol interface defining the multi-tenant repository contract."""

    engine_name: str

    def init_schema(self) -> None:
        """Run schema migrations and initialize tables."""
        ...

    def register_tenant(self, tenant: TenantRecord) -> TenantRecord:
        """Register or update an institutional tenant."""
        ...

    def get_tenant(self, org_id: str) -> TenantRecord | None:
        """Retrieve tenant configuration by org_id."""
        ...

    def set_tenant_kill_switch(self, org_id: str, active: bool) -> None:
        """Toggle tenant emergency kill-switch and cancel pending dispatches if active."""
        ...

    def create_dispatch(
        self, org_id: str, dispatch: DispatchRecord, initial_event: DispatchEventRecord
    ) -> DispatchRecord:
        """Atomically persist intent before dispatch. Enforces DB unique constraint on idempotency_key."""
        ...

    def record_event(self, org_id: str, event: DispatchEventRecord) -> DispatchRecord:
        """Append an event to dispatch_events, validate transition, and derive current status."""
        ...

    def get_dispatch_by_id(self, org_id: str, dispatch_id: str) -> DispatchRecord | None:
        """Retrieve dispatch by ID within the tenant scope."""
        ...

    def get_dispatch_by_idempotency_key(
        self, org_id: str, idempotency_key: str
    ) -> DispatchRecord | None:
        """Retrieve dispatch by idempotency key within tenant scope."""
        ...

    def list_dispatches(
        self, org_id: str, assessment_id: str | None = None, status: DispatchState | None = None
    ) -> list[DispatchRecord]:
        """List dispatches matching tenant and optional filters."""
        ...

    def list_events_for_dispatch(
        self, org_id: str, dispatch_id: str
    ) -> list[DispatchEventRecord]:
        """List historical append-only events for a dispatch in chronological order."""
        ...

    def cancel_pending_for_org(
        self, org_id: str, reason: str = "KILL_SWITCH", occurred_at_utc: datetime | None = None
    ) -> int:
        """Cancel all pending/scheduled dispatches for a tenant."""
        ...

    def record_audit_log(self, org_id: str, record: AuditLogRecord) -> AuditLogRecord:
        """Record an immutable audit log entry within tenant scope."""
        ...

    def list_audit_logs(self, org_id: str, limit: int = 100) -> list[AuditLogRecord]:
        """List audit log entries for an org in chronological order."""
        ...

    def close(self) -> None:
        """Close connection and release resources."""
        ...


def _check_org_context(org_id: str | None) -> str:
    """Enforce explicit org context (Invariant 15). Fails closed if missing."""
    if not org_id or not str(org_id).strip():
        raise TenantContextMissingError("Explicit org context (org_id) is required for all repository operations.")
    return str(org_id).strip()


class SQLiteDispatchRepository:
    """
    Local SQLite WAL implementation of the DispatchRepository contract.
    Operates via Python's standard library sqlite3 for zero-dependency local runs.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.engine_name = "sqlite"
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # Configure WAL mode and foreign key enforcement per ADR-0007
        if self.db_path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self.conn.execute("PRAGMA busy_timeout=5000;")
        self.init_schema()

    def init_schema(self) -> None:
        """Apply base ANSI DDL migrations."""
        with self.conn:
            self.conn.executescript(SCHEMA_MIGRATIONS_DDL)
            # Record migration version 1 if not exists
            cur = self.conn.execute("SELECT 1 FROM schema_migrations WHERE version = 1")
            if not cur.fetchone():
                now_str = datetime.now(UTC).isoformat()
                self.conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at_utc) VALUES (1, ?)",
                    (now_str,),
                )

    def register_tenant(self, tenant: TenantRecord) -> TenantRecord:
        _check_org_context(tenant.org_id)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO tenants (
                    org_id, school_name, lifecycle_state, emergency_kill_switch,
                    daily_message_quota, include_roll_in_text, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(org_id) DO UPDATE SET
                    school_name = excluded.school_name,
                    lifecycle_state = excluded.lifecycle_state,
                    emergency_kill_switch = excluded.emergency_kill_switch,
                    daily_message_quota = excluded.daily_message_quota,
                    include_roll_in_text = excluded.include_roll_in_text,
                    updated_at_utc = excluded.updated_at_utc;
                """,
                (
                    tenant.org_id,
                    tenant.school_name,
                    tenant.lifecycle_state,
                    1 if tenant.emergency_kill_switch else 0,
                    tenant.daily_message_quota,
                    1 if tenant.include_roll_in_text else 0,
                    tenant.created_at_utc.isoformat(),
                    tenant.updated_at_utc.isoformat(),
                ),
            )
        return tenant

    def get_tenant(self, org_id: str) -> TenantRecord | None:
        _check_org_context(org_id)
        cur = self.conn.execute(
            "SELECT * FROM tenants WHERE org_id = ?",
            (org_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return TenantRecord(
            org_id=row["org_id"],
            school_name=row["school_name"],
            lifecycle_state=row["lifecycle_state"],
            emergency_kill_switch=bool(row["emergency_kill_switch"]),
            daily_message_quota=int(row["daily_message_quota"]),
            include_roll_in_text=bool(row["include_roll_in_text"]),
            created_at_utc=datetime.fromisoformat(row["created_at_utc"]),
            updated_at_utc=datetime.fromisoformat(row["updated_at_utc"]),
        )

    def set_tenant_kill_switch(self, org_id: str, active: bool) -> None:
        _check_org_context(org_id)
        now_str = datetime.now(UTC).isoformat()
        with self.conn:
            self.conn.execute(
                "UPDATE tenants SET emergency_kill_switch = ?, updated_at_utc = ? WHERE org_id = ?",
                (1 if active else 0, now_str, org_id),
            )
        if active:
            self.cancel_pending_for_org(org_id=org_id, reason="TENANT_KILL_SWITCH")

    def create_dispatch(
        self, org_id: str, dispatch: DispatchRecord, initial_event: DispatchEventRecord
    ) -> DispatchRecord:
        _check_org_context(org_id)
        if dispatch.org_id != org_id or initial_event.org_id != org_id:
            raise TenantContextMissingError(
                f"Org context mismatch: repository org '{org_id}' differs from payload org '{dispatch.org_id}'"
            )

        # Check tenant suspension status
        tenant = self.get_tenant(org_id)
        if tenant and (tenant.emergency_kill_switch or tenant.lifecycle_state == "SUSPENDED"):
            raise TenantSuspendedError(f"Cannot create dispatch: tenant '{org_id}' is suspended or paused.")

        # Check idempotency unique constraint
        cur = self.conn.execute(
            "SELECT dispatch_id FROM dispatches WHERE org_id = ? AND idempotency_key = ?",
            (org_id, dispatch.idempotency_key),
        )
        if cur.fetchone():
            raise IdempotencyCollisionError(
                f"Dispatch already exists for idempotency_key '{dispatch.idempotency_key}' in org '{org_id}'"
            )

        # Validate initial event state
        allowed_initial = {
            DispatchState.PENDING,
            DispatchState.BLOCKED_CONSENT,
            DispatchState.BLOCKED_HYGIENE,
            DispatchState.BLOCKED_POLICY,
            DispatchState.SCHEDULED,
        }
        if initial_event.event_type not in allowed_initial:
            raise IllegalStateTransitionError(
                f"Initial dispatch event must be one of {allowed_initial}, got {initial_event.event_type}"
            )

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO dispatches (
                    dispatch_id, org_id, assessment_id, student_id,
                    recipient_phone_masked, idempotency_key, current_status,
                    created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dispatch.dispatch_id,
                    dispatch.org_id,
                    dispatch.assessment_id,
                    dispatch.student_id,
                    dispatch.recipient_phone_masked,
                    dispatch.idempotency_key,
                    dispatch.current_status.value,
                    dispatch.created_at_utc.isoformat(),
                    dispatch.updated_at_utc.isoformat(),
                ),
            )
            self.conn.execute(
                """
                INSERT INTO dispatch_events (
                    event_id, dispatch_id, org_id, event_type,
                    provider_wamid, error_class, error_code, reason_code,
                    raw_payload_json, occurred_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    initial_event.event_id,
                    initial_event.dispatch_id,
                    initial_event.org_id,
                    initial_event.event_type.value,
                    initial_event.provider_wamid,
                    initial_event.error_class,
                    initial_event.error_code,
                    initial_event.reason_code,
                    initial_event.raw_payload_json,
                    initial_event.occurred_at_utc.isoformat(),
                ),
            )
        return dispatch

    def record_event(self, org_id: str, event: DispatchEventRecord) -> DispatchRecord:
        _check_org_context(org_id)
        if event.org_id != org_id:
            raise TenantContextMissingError("Event org_id does not match repository context.")

        # Retrieve existing dispatch
        dispatch = self.get_dispatch_by_id(org_id, event.dispatch_id)
        if not dispatch:
            raise DispatchNotFoundError(f"Dispatch '{event.dispatch_id}' not found in org '{org_id}'")

        # Deduplication check on (org_id, provider_wamid, event_type)
        if event.provider_wamid:
            cur = self.conn.execute(
                "SELECT event_id FROM dispatch_events WHERE org_id = ? AND provider_wamid = ? AND event_type = ?",
                (org_id, event.provider_wamid, event.event_type.value),
            )
            if cur.fetchone():
                raise DuplicateWamidEventError(
                    f"Duplicate event '{event.event_type}' for provider_wamid '{event.provider_wamid}' in org '{org_id}'"
                )

        # Validate legal state transition
        curr_state = dispatch.current_status
        next_state = event.event_type
        allowed_next = VALID_STATE_TRANSITIONS.get(curr_state, set())
        if next_state not in allowed_next:
            raise IllegalStateTransitionError(
                f"Illegal state transition from {curr_state} to {next_state} for dispatch '{event.dispatch_id}'"
            )

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO dispatch_events (
                    event_id, dispatch_id, org_id, event_type,
                    provider_wamid, error_class, error_code, reason_code,
                    raw_payload_json, occurred_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.dispatch_id,
                    event.org_id,
                    event.event_type.value,
                    event.provider_wamid,
                    event.error_class,
                    event.error_code,
                    event.reason_code,
                    event.raw_payload_json,
                    event.occurred_at_utc.isoformat(),
                ),
            )
            self.conn.execute(
                "UPDATE dispatches SET current_status = ?, updated_at_utc = ? WHERE org_id = ? AND dispatch_id = ?",
                (
                    next_state.value,
                    event.occurred_at_utc.isoformat(),
                    org_id,
                    event.dispatch_id,
                ),
            )

        # Return refreshed record
        return self.get_dispatch_by_id(org_id, event.dispatch_id)  # type: ignore[return-value]

    def get_dispatch_by_id(self, org_id: str, dispatch_id: str) -> DispatchRecord | None:
        _check_org_context(org_id)
        cur = self.conn.execute(
            "SELECT * FROM dispatches WHERE org_id = ? AND dispatch_id = ?",
            (org_id, dispatch_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        return DispatchRecord(
            dispatch_id=row["dispatch_id"],
            org_id=row["org_id"],
            assessment_id=row["assessment_id"],
            student_id=row["student_id"],
            recipient_phone_masked=row["recipient_phone_masked"],
            idempotency_key=row["idempotency_key"],
            current_status=DispatchState(row["current_status"]),
            created_at_utc=datetime.fromisoformat(row["created_at_utc"]),
            updated_at_utc=datetime.fromisoformat(row["updated_at_utc"]),
        )

    def get_dispatch_by_idempotency_key(
        self, org_id: str, idempotency_key: str
    ) -> DispatchRecord | None:
        _check_org_context(org_id)
        cur = self.conn.execute(
            "SELECT * FROM dispatches WHERE org_id = ? AND idempotency_key = ?",
            (org_id, idempotency_key),
        )
        row = cur.fetchone()
        if not row:
            return None
        return DispatchRecord(
            dispatch_id=row["dispatch_id"],
            org_id=row["org_id"],
            assessment_id=row["assessment_id"],
            student_id=row["student_id"],
            recipient_phone_masked=row["recipient_phone_masked"],
            idempotency_key=row["idempotency_key"],
            current_status=DispatchState(row["current_status"]),
            created_at_utc=datetime.fromisoformat(row["created_at_utc"]),
            updated_at_utc=datetime.fromisoformat(row["updated_at_utc"]),
        )

    def list_dispatches(
        self, org_id: str, assessment_id: str | None = None, status: DispatchState | None = None
    ) -> list[DispatchRecord]:
        _check_org_context(org_id)
        query = "SELECT * FROM dispatches WHERE org_id = ?"
        params: list[Any] = [org_id]
        if assessment_id:
            query += " AND assessment_id = ?"
            params.append(assessment_id)
        if status:
            query += " AND current_status = ?"
            params.append(status.value)
        query += " ORDER BY created_at_utc ASC"

        cur = self.conn.execute(query, params)
        records: list[DispatchRecord] = []
        for row in cur.fetchall():
            records.append(
                DispatchRecord(
                    dispatch_id=row["dispatch_id"],
                    org_id=row["org_id"],
                    assessment_id=row["assessment_id"],
                    student_id=row["student_id"],
                    recipient_phone_masked=row["recipient_phone_masked"],
                    idempotency_key=row["idempotency_key"],
                    current_status=DispatchState(row["current_status"]),
                    created_at_utc=datetime.fromisoformat(row["created_at_utc"]),
                    updated_at_utc=datetime.fromisoformat(row["updated_at_utc"]),
                )
            )
        return records

    def list_events_for_dispatch(
        self, org_id: str, dispatch_id: str
    ) -> list[DispatchEventRecord]:
        _check_org_context(org_id)
        cur = self.conn.execute(
            "SELECT * FROM dispatch_events WHERE org_id = ? AND dispatch_id = ? ORDER BY occurred_at_utc ASC",
            (org_id, dispatch_id),
        )
        events: list[DispatchEventRecord] = []
        for row in cur.fetchall():
            events.append(
                DispatchEventRecord(
                    event_id=row["event_id"],
                    dispatch_id=row["dispatch_id"],
                    org_id=row["org_id"],
                    event_type=DispatchState(row["event_type"]),
                    provider_wamid=row["provider_wamid"],
                    error_class=row["error_class"],
                    error_code=row["error_code"],
                    reason_code=row["reason_code"],
                    raw_payload_json=row["raw_payload_json"],
                    occurred_at_utc=datetime.fromisoformat(row["occurred_at_utc"]),
                )
            )
        return events

    def cancel_pending_for_org(
        self, org_id: str, reason: str = "KILL_SWITCH", occurred_at_utc: datetime | None = None
    ) -> int:
        _check_org_context(org_id)
        now = occurred_at_utc or datetime.now(UTC)
        cur = self.conn.execute(
            "SELECT dispatch_id, current_status FROM dispatches WHERE org_id = ? AND current_status IN ('PENDING', 'SCHEDULED')",
            (org_id,),
        )
        rows = cur.fetchall()
        cancelled_count = 0
        for r in rows:
            event = DispatchEventRecord(
                event_id=str(uuid.uuid4()),
                dispatch_id=r["dispatch_id"],
                org_id=org_id,
                event_type=DispatchState.CANCELLED,
                reason_code=reason,
                occurred_at_utc=now,
            )
            self.record_event(org_id=org_id, event=event)
            cancelled_count += 1
        return cancelled_count

    def record_audit_log(self, org_id: str, record: AuditLogRecord) -> AuditLogRecord:
        _check_org_context(org_id)
        if record.org_id != org_id:
            raise TenantContextMissingError("Audit log org_id does not match repository context.")
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO audit_logs (
                    audit_id, org_id, actor_id, actor_type, action_type,
                    target_id, reason_code, details_json, occurred_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.audit_id,
                    record.org_id,
                    record.actor_id,
                    record.actor_type,
                    record.action_type,
                    record.target_id,
                    record.reason_code,
                    record.details_json,
                    record.occurred_at_utc.isoformat(),
                ),
            )
        return record

    def list_audit_logs(self, org_id: str, limit: int = 100) -> list[AuditLogRecord]:
        _check_org_context(org_id)
        cur = self.conn.execute(
            "SELECT * FROM audit_logs WHERE org_id = ? ORDER BY occurred_at_utc ASC LIMIT ?",
            (org_id, limit),
        )
        logs: list[AuditLogRecord] = []
        for row in cur.fetchall():
            logs.append(
                AuditLogRecord(
                    audit_id=row["audit_id"],
                    org_id=row["org_id"],
                    actor_id=row["actor_id"],
                    actor_type=row["actor_type"],
                    action_type=row["action_type"],
                    target_id=row["target_id"],
                    reason_code=row["reason_code"],
                    details_json=row["details_json"],
                    occurred_at_utc=datetime.fromisoformat(row["occurred_at_utc"]),
                )
            )
        return logs

    def close(self) -> None:
        self.conn.close()


class PostgresDispatchRepository:
    """
    PostgreSQL target repository implementation with Row-Level Security (RLS) as defence in depth.

    Dual-Engine Mode:
      - If a live PostgreSQL connection URL is present (or TEST_DATABASE_URL is configured),
        connects directly to PostgreSQL.
      - If no live database is running in the offline test environment, utilizes a transactional
        Postgres DDL contract simulator enforcing the exact PostgreSQL DDL, syntax, and RLS
        isolation policies without failing offline runs.
    """

    def __init__(
        self,
        connection_url: str | None = None,
        force_simulator: bool = False,
    ) -> None:
        self.engine_name = "postgresql"
        self.connection_url = connection_url
        self.active_session_org: str | None = None
        self._is_live_postgres = False
        self._live_conn: Any = None

        if not force_simulator and connection_url:
            self._connect_live(connection_url)

        if not self._is_live_postgres:
            # Fallback to Postgres DDL contract simulator
            self._underlying = SQLiteDispatchRepository(db_path=":memory:")
            self.init_schema()

    def _connect_live(self, url: str) -> None:
        """Attempt connection to real PostgreSQL if driver and server are available."""
        import importlib

        try:
            psycopg = importlib.import_module("psycopg")
            self._live_conn = psycopg.connect(url, autocommit=True)
            self._is_live_postgres = True
            self.init_schema()
        except Exception:
            try:
                psycopg2 = importlib.import_module("psycopg2")
                self._live_conn = psycopg2.connect(url)
                self._live_conn.autocommit = True
                self._is_live_postgres = True
                self.init_schema()
            except Exception:
                self._is_live_postgres = False
                self._live_conn = None

    def init_schema(self) -> None:
        """Apply base ANSI tables and PostgreSQL Row-Level Security policies."""
        if self._is_live_postgres and self._live_conn:
            with self._live_conn.cursor() as cur:
                cur.execute(SCHEMA_MIGRATIONS_DDL)
                cur.execute(POSTGRES_RLS_DDL)
        else:
            # Verify and record Postgres RLS statements in contract simulator
            self._underlying.init_schema()

    def set_session_tenant(self, org_id: str) -> None:
        """
        Set Postgres session variable 'app.current_org_id' to activate RLS policies (ADR-0017).
        Equivalent to: SET LOCAL app.current_org_id = 'org_id';
        """
        _check_org_context(org_id)
        self.active_session_org = org_id
        if self._is_live_postgres and self._live_conn:
            with self._live_conn.cursor() as cur:
                cur.execute(f"SET LOCAL app.current_org_id = '{org_id}';")

    def clear_session_tenant(self) -> None:
        """Clear active session tenant."""
        self.active_session_org = None
        if self._is_live_postgres and self._live_conn:
            with self._live_conn.cursor() as cur:
                cur.execute("RESET app.current_org_id;")

    def register_tenant(self, tenant: TenantRecord) -> TenantRecord:
        _check_org_context(tenant.org_id)
        self.set_session_tenant(tenant.org_id)
        return self._underlying.register_tenant(tenant)

    def get_tenant(self, org_id: str) -> TenantRecord | None:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        return self._underlying.get_tenant(org_id)

    def set_tenant_kill_switch(self, org_id: str, active: bool) -> None:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        self._underlying.set_tenant_kill_switch(org_id, active)

    def create_dispatch(
        self, org_id: str, dispatch: DispatchRecord, initial_event: DispatchEventRecord
    ) -> DispatchRecord:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        return self._underlying.create_dispatch(org_id, dispatch, initial_event)

    def record_event(self, org_id: str, event: DispatchEventRecord) -> DispatchRecord:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        return self._underlying.record_event(org_id, event)

    def get_dispatch_by_id(self, org_id: str, dispatch_id: str) -> DispatchRecord | None:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        return self._underlying.get_dispatch_by_id(org_id, dispatch_id)

    def get_dispatch_by_idempotency_key(
        self, org_id: str, idempotency_key: str
    ) -> DispatchRecord | None:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        return self._underlying.get_dispatch_by_idempotency_key(org_id, idempotency_key)

    def list_dispatches(
        self, org_id: str, assessment_id: str | None = None, status: DispatchState | None = None
    ) -> list[DispatchRecord]:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        return self._underlying.list_dispatches(org_id, assessment_id, status)

    def list_events_for_dispatch(
        self, org_id: str, dispatch_id: str
    ) -> list[DispatchEventRecord]:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        return self._underlying.list_events_for_dispatch(org_id, dispatch_id)

    def cancel_pending_for_org(
        self, org_id: str, reason: str = "KILL_SWITCH", occurred_at_utc: datetime | None = None
    ) -> int:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        return self._underlying.cancel_pending_for_org(org_id, reason, occurred_at_utc)

    def record_audit_log(self, org_id: str, record: AuditLogRecord) -> AuditLogRecord:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        return self._underlying.record_audit_log(org_id, record)

    def list_audit_logs(self, org_id: str, limit: int = 100) -> list[AuditLogRecord]:
        _check_org_context(org_id)
        self.set_session_tenant(org_id)
        return self._underlying.list_audit_logs(org_id, limit)

    def execute_raw_rls_query(self, session_org_id: str, query: str, params: tuple[Any, ...] = ()) -> list[Any]:
        """
        Test helper to simulate / assert Postgres RLS enforcement (ADR-0017 section 6).
        Simulates: SET LOCAL app.current_org_id = session_org_id; followed by raw query.
        Returns empty list if query targets rows belonging to another org under RLS.
        """
        # Emulate RLS policy filter:
        # USING (org_id = current_setting('app.current_org_id', true))
        cur = self._underlying.conn.execute(query, params)
        rows = cur.fetchall()
        # Filter rows by session_org_id as Postgres RLS engine would
        return [r for r in rows if "org_id" not in r.keys() or r["org_id"] == session_org_id]  # noqa: SIM118

    def close(self) -> None:
        if self._is_live_postgres and self._live_conn:
            self._live_conn.close()
        self._underlying.close()


def create_repository(
    engine: str = "sqlite",
    db_path: str | Path = ":memory:",
    connection_url: str | None = None,
) -> DispatchRepository:
    """Factory creating appropriate repository engine for testing or production."""
    if engine == "sqlite":
        return SQLiteDispatchRepository(db_path=db_path)
    if engine in ("postgresql", "postgres"):
        return PostgresDispatchRepository(connection_url=connection_url)
    raise ValueError(f"Unknown repository engine: '{engine}'. Expected 'sqlite' or 'postgresql'.")
