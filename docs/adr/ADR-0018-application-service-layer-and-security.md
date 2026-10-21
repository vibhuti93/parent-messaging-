# ADR-0018: Application Service Layer, Security Context, and Job Orchestration

## Status
`PROPOSED`

## Context
In a multi-tenant hosted system serving multiple schools, business operations (such as batch evaluation, send plan generation, emergency batch cancellation, review queue resolution, and scorecard retrieval) must be strictly isolated, authorized, auditable, and resilient to system interruptions.

If CLI commands or background workers directly manipulate low-level repositories, filesystems, and provider HTTP clients without a mediating application service boundary:
1. Tenant isolation checks are scattered and easily bypassed.
2. Long-running batch operations (such as rendering 200 scorecard images or dispatching messages over throttled WhatsApp connections) cannot resume after a process crash or restart.
3. Artifacts (scorecard PNGs, A4 PTM PDFs, audio clips) addressed by direct filesystem paths leak cross-tenant paths and break in distributed container environments.
4. Audit logs lack consistent caller attribution (`org_id`, `actor_type`, `actor_id`).

## Options Considered

### Option 1: Direct CLI & Script Execution over Repositories
- *Description*: CLI scripts directly instantiate repositories, load models, perform loops, and write files to disk paths.
- *Pros*: Simple procedural scripting.
- *Cons*: Zero central authorization; no resumable job abstraction; high risk of tenant bleed; untracked state mutations; unacceptable for multi-tenant hosted SaaS.

### Option 2: Unified Application Service Layer with Principal Context and Resumable Jobs
- *Description*:
  - Define an explicit **Application Service Boundary** exposing high-level use-case functions.
  - Every service function requires a typed `Principal` security context representing the authenticated caller (`actor_type`, `actor_id`, `org_id`, `roles`).
  - Authorization is evaluated at the service perimeter before any domain logic executes.
  - The CLI becomes a thin client adapter that constructs a CLI Principal and invokes the service layer.
  - Asynchronous and batch workflows run as persisted, resumable `Job` entities.
  - Artifacts are managed and retrieved via opaque `artifact_id` handles with mandatory org-scoping rather than raw filesystem paths.
- *Pros*: Clean architectural decoupling; complete audit trail with actor identity on every event; safe multi-tenancy; graceful recovery from service restarts; frontend-ready API contract.
- *Cons*: Requires defining formal service signatures and job state persistence.

## Proposed Decision
We propose **Option 2 (Unified Application Service Layer, Principal Context, and Resumable Jobs)**.

### 1. Principal Security Context
Every use-case function at the service boundary mandates a `Principal` argument:
```python
class ActorType(str, Enum):
    SYSTEM = "SYSTEM"          # Automated scheduled daemon or background worker
    CLI = "CLI"                # Command-line operator
    USER = "USER"              # Authenticated user via future API/UI adapter

class UserRole(str, Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"  # Platform operator (cross-tenant maintenance, onboarding)
    SCHOOL_ADMIN = "SCHOOL_ADMIN"      # School principal / administrator (full org authority)
    TEACHER = "TEACHER"                # Classroom teacher (marks entry, batch initiation)
    AUDITOR = "AUDITOR"                # Read-only audit and compliance reviewer

class Principal(BaseModel):
    schema_version: int = 1
    actor_type: ActorType
    actor_id: str                      # Opaque user ID or "cli_operator"
    org_id: str                        # Mandatory tenant scope (or "*" for PLATFORM_ADMIN)
    roles: list[UserRole]
```

*Frontend / Auth Extension Point:* In v1, authentication screens, user management, passwords, and web frontends are **strictly out of scope**. The CLI acts as an adapter providing a local CLI Principal (`actor_type=CLI`, `org_id=args.org`, `roles=[SCHOOL_ADMIN]`). When web frontends or identity providers (OAuth2/OIDC) are added post-v1, they simply authenticate the user and inject the corresponding `Principal` at the service boundary without touching core logic.

### 2. Service Boundary Use-Case Functions
The service interface exposes the following authoritative use-case functions:

```python
class DispatchEngineService(Protocol):
    def validate_batch(
        self, principal: Principal, assessment_id: str, input_files: dict[str, bytes]
    ) -> ValidationSummary:
        """Validates roster, answer key, and submissions for an assessment."""
        ...

    def evaluate_batch(
        self, principal: Principal, assessment_id: str
    ) -> JobStatus:
        """Triggers deterministic diagnostic evaluation and creates a resumable background job."""
        ...

    def build_send_plan(
        self, principal: Principal, assessment_id: str, schedule_time_utc: datetime | None = None
    ) -> SendPlanSummary:
        """Computes message payloads, templates, hygiene gates, and scheduled dispatch windows."""
        ...

    def approve_batch(
        self, principal: Principal, assessment_id: str
    ) -> ApprovalReceipt:
        """Formally approves a reviewed send plan, transitioning dispatches from PENDING to SCHEDULED."""
        ...

    def cancel_batch(
        self, principal: Principal, assessment_id: str, reason: str
    ) -> CancellationReceipt:
        """Emergency kill-switch: cancels all pending and scheduled dispatches for a batch."""
        ...

    def get_job_status(
        self, principal: Principal, job_id: str
    ) -> JobRecord:
        """Retrieves progress, state, and errors of an active or completed background job."""
        ...

    def list_review_queue(
        self, principal: Principal, queue_type: ReviewQueueType
    ) -> list[ReviewQueueItem]:
        """Lists items requiring human review (quarantined contacts, OCR anomalies, uncertain dispatches)."""
        ...

    def resolve_review_item(
        self, principal: Principal, review_item_id: str, resolution: ReviewResolution
    ) -> ReviewReceipt:
        """Applies a human review decision (e.g. confirming sibling status or overriding quarantine)."""
        ...

    def get_artifact(
        self, principal: Principal, artifact_id: str
    ) -> ArtifactPayload:
        """Retrieves an asset (scorecard PNG, PTM PDF, audio OGG) by opaque artifact ID with org isolation."""
        ...
```

### 3. Role-Based Permission Matrix

| Service Operation | `PLATFORM_ADMIN` | `SCHOOL_ADMIN` | `TEACHER` | `AUDITOR` |
| :--- | :---: | :---: | :---: | :---: |
| `validate_batch` | Yes (Any Org) | Yes (Own Org) | Yes (Own Org) | No |
| `evaluate_batch` | Yes (Any Org) | Yes (Own Org) | Yes (Own Org) | No |
| `build_send_plan` | Yes (Any Org) | Yes (Own Org) | Yes (Own Org) | No |
| `approve_batch` | Yes (Any Org) | Yes (Own Org) | No | No |
| `cancel_batch` | Yes (Any Org) | Yes (Own Org) | No | No |
| `get_job_status` | Yes (Any Org) | Yes (Own Org) | Yes (Own Org) | Yes (Own Org) |
| `list_review_queue`| Yes (Any Org) | Yes (Own Org) | Yes (Own Org) | Yes (Own Org) |
| `resolve_review_item`| Yes (Any Org) | Yes (Own Org) | No | No |
| `get_artifact` | Yes (Any Org) | Yes (Own Org) | Yes (Own Org) | Yes (Own Org) |
| `tenant_onboard` | Yes | No | No | No |
| `tenant_purge` | Yes | Yes (With Confirmation)| No | No |

*Strict Invariant:* An actor with `SCHOOL_ADMIN` or `TEACHER` role can only operate on resources where `principal.org_id == resource.org_id`. Any cross-tenant access attempt raises an immediate `UnauthorizedTenantAccessError` and writes a security audit event.

### 4. Persisted, Resumable Job Model
To survive service restarts and process interruptions during large batches, all background operations run through a persistent `Job` entity:
```python
class JobKind(str, Enum):
    BATCH_INGEST = "BATCH_INGEST"
    BATCH_EVALUATE = "BATCH_EVALUATE"
    RENDER_SCORECARDS = "RENDER_SCORECARDS"
    RENDER_PTM_PDF = "RENDER_PTM_PDF"
    STITCH_AUDIO = "STITCH_AUDIO"
    DISPATCH_BATCH = "DISPATCH_BATCH"
    TENANT_PURGE = "TENANT_PURGE"

class JobState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class JobRecord(BaseModel):
    schema_version: int = 1
    job_id: str                      # Opaque UUID
    org_id: str                      # Mandatory tenant identifier
    kind: JobKind
    state: JobState
    created_at_utc: datetime
    started_at_utc: datetime | None = None
    completed_at_utc: datetime | None = None
    progress_current: int = 0        # e.g. 45 scorecards rendered
    progress_total: int = 0          # e.g. 200 total scorecards
    last_processed_id: str | None = None  # Cursor for resumable recovery
    error_code: str | None = None
    error_message: str | None = None
    created_by_actor_id: str
```

**Resumption Semantics:**
- When a worker restarts, it queries for `state == RUNNING` jobs scoped to its node/partition.
- Using `last_processed_id`, the worker resumes execution from the exact next item rather than restarting the batch from scratch.
- State updates are committed in small batches (e.g. every 10 items) to minimize duplicate processing.

### 5. Mandatory Attribution on All Audit and Dispatch Events
Every audit event (`AuditRecord`) and dispatch event (`dispatch_events`) must record:
- `org_id: str`
- `actor_type: str`
- `actor_id: str`
This guarantees complete forensic traceability for every single outbound notification, plan approval, or configuration change.

### 6. Artifact Management by Opaque Identifier
Artifacts (scorecards, PDFs, audio notes) are stored in an abstract object store (local disk in development, Cloud Storage in production).
- Artifacts are keyed by: `artifact_id = v1:{org_id}:{assessment_id}:{student_id}:{artifact_type}`.
- Physical filesystem paths are never returned to callers or embedded in parent URLs.
- The `get_artifact(principal, artifact_id)` method verifies that `principal.org_id == artifact.org_id` before streaming bytes.

## Consequences
- **Positive**: Complete security boundary; bulletproof tenant isolation; atomic batch recovery on system crash; clean foundation for future web APIs.
- **Negative**: CLI commands must pass through the service interface rather than executing direct procedural scripts.
- **Neutral**: Enforced by architecture rules.

## Revisit When
Revisit when implementing OAuth2/OIDC user identity providers and web frontend gateways.
