# ADR-0020: Tenant Lifecycle, Administrative Controls, Fair Scheduling, and Metering

## Status
`ACCEPTED`

## Context
As a hosted multi-tenant system serving multiple educational institutions, `omr_dispatch_engine` requires formal lifecycle management for tenant organizations.
Schools onboard at different dates, configure distinct operational policies, require emergency pause capabilities (e.g. during school closures or accidental batch trigger), need fair resource allocation so large schools do not starve smaller schools, and may eventually offboard, requesting full cryptographic deletion of student data under privacy laws.

Without explicit tenant lifecycle controls and fairness guarantees:
1. One large institution submitting 1,000 students could monopolize the background worker queue and provider rate limits, delaying time-sensitive reports for other schools.
2. Tenant offboarding or data deletion requests could leave orphaned rows or inadvertently delete records belonging to other tenants.
3. Administrative settings (such as parent report customization or send schedules) would remain globally hardcoded rather than institution-specific.

## Options Considered

### Option 1: Ad-hoc Manual Database Scripts for Tenant Lifecycle
- *Description*: Handle onboarding, suspension, and offboarding via manual SQL scripts executed directly against the database by developers.
- *Pros*: Zero upfront control plane code.
- *Cons*: Extremely dangerous; high human error risk (e.g. `DELETE` without proper `WHERE org_id`); no audit trail; cannot enforce tenant-fair scheduling in application memory.

### Option 2: Formal Tenant Control Plane with Fair Scheduling and Isolated Metering
- *Description*:
  - Model a first-class `Tenant` entity and lifecycle state machine (`ACTIVE`, `SUSPENDED`, `OFFBOARDING`, `DELETED`).
  - Provide typed per-tenant settings (including `include_roll_in_text`, daily quotas, emergency kill-switch).
  - Implement **Tenant-Fair Scheduling** (round-robin / deficit round-robin per tenant) across worker queues to prevent starvation.
  - Track per-tenant message dispatch meters for billing attribution and cost reporting.
  - Implement an atomic per-tenant export and cascade deletion pipeline.
- *Pros*: Safe, automated, auditable tenant operations; deterministic noisy neighbor mitigation; accurate billing allocation.
- *Cons*: Additional control plane logic.

## Proposed Decision
We propose **Option 2 (Formal Tenant Control Plane, Per-Tenant Controls, Fair Scheduling, and Isolated Metering)**.

### 1. Tenant Lifecycle State Machine
```python
class TenantLifecycleState(str, Enum):
    ONBOARDING = "ONBOARDING"      # Profile created; verification pending
    ACTIVE = "ACTIVE"              # Fully operational
    SUSPENDED = "SUSPENDED"        # Temporarily halted (kill-switch or non-payment)
    OFFBOARDING = "OFFBOARDING"    # Read-only; export/deletion in progress
    DELETED = "DELETED"            # Tombstone record; data purged

class TenantSettings(BaseModel):
    schema_version: int = 1
    org_id: str
    school_name: str
    contact_email: str
    emergency_kill_switch: bool = False
    daily_message_quota: int = 1000
    include_roll_in_text: bool = False   # Per-org setting; default False per Decision 5
    default_send_window: str = "SUNDAY_2030_IST"
    retention_academic_year_days: int = 365
    retention_audit_log_days: int = 90
    created_at_utc: datetime
    updated_at_utc: datetime
```

### 2. Tenant Lifecycle Operations
1. **Onboarding (`tenant_onboard`):**
   - Provisions tenant record, initializes default `TenantSettings`, registers `SenderIdentity`, and executes baseline database migrations under tenant isolation.
2. **Emergency Kill-Switch & Suspension (`tenant_suspend`):**
   - Setting `emergency_kill_switch = True` immediately halts all active workers and scheduled dispatches for that specific `org_id`.
   - Pending jobs transition to `CANCELLED`. In-flight network calls are aborted where supported.
   - Other tenants continue normal dispatch without interruption.
3. **Offboarding & Full Deletion (`tenant_purge`):**
   - Transition state to `OFFBOARDING` (blocks any new ingestion or dispatch).
   - Generates an encrypted archive of student and diagnostic records for school handover.
   - Executes atomic cascade deletion of all tenant data (`dispatches`, `dispatch_events`, `submissions`, `roster`, `assessments`, `rendered_assets`, `audio`) using strictly parameterized `WHERE org_id = :org_id` queries.
   - Retains a minimal cryptographic audit tombstone (`TenantDeletedEvent`: `org_id`, `deleted_at_utc`, `hash_of_records_deleted`) for 90 days before final expiry.

### 3. Tenant-Fair Scheduling (Starvation Prevention)
To prevent a large school's massive batch from delaying another school's urgent parent notifications:
1. **Fair Queue Architecture:**
   - Background workers do not draw from a single FIFO queue.
   - Worker dispatch pulls from tenant queues using **Deficit Weighted Round-Robin (DWRR)**.
   - Each tenant receives a fair dispatch allotment per cycle (e.g. up to 20 messages per cycle), alternating between active tenants.
2. **Provider Concurrency Pacing:**
   - Outbound dispatch honors each sender's individual rate limits (80 mps default) and daily limits without bottlenecking across different senders.

### 4. Per-Tenant Metering & Cost Attribution
1. **Message Metering:**
   - Every `DELIVERED` event increments an institutional usage counter broken down by category:
     - `utility_messages_count: int`
     - `marketing_messages_count: int`
     - `authentication_messages_count: int`
     - `free_tier_service_messages_count: int`
2. **Audit & Usage Export:**
   - Provides `export_tenant_usage(org_id, date_range)` to generate verified delivery counts and cost estimates based on official Meta rate cards (**R-05**).

### 5. Configurable Settings (`include_roll_in_text`)
Per Operator Decision 5:
- By default, `include_roll_in_text` is `False`. The roll number is omitted from parent text notifications and appears only on visual scorecards and PTM slips.
- If a school explicitly enables `include_roll_in_text = True`, the template renderer appends the roll number in the child identity segment (e.g. `"आरव (रोल नं. 14, कक्षा 8-B)"`).

## Consequences
- **Positive**: Complete administrative control; safe data deletion and export; guaranteed queue fairness across schools; exact per-school billing metrics.
- **Negative**: Worker scheduler logic requires multi-queue round-robin implementation.
- **Neutral**: Added to `docs/DECISIONS_OPEN.md`.

## Revisit When
Revisit if dynamic credit-based prepaid billing wallets are integrated directly into the engine.
