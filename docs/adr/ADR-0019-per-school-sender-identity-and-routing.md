# ADR-0019: Per-School Sender Identity, Credential Isolation, and Inbound Webhook Routing

## Status
`PROPOSED`

## Context
Per Operator Decision 2 (Stage S0-R5), each educational institution uses its **own WhatsApp Business Phone Number**. There is **no shared number** across schools.
This institutional requirement aligns with educational reality: parents recognize and trust their local school's official contact number and verified WhatsApp display name.

Operating multiple distinct WhatsApp Business numbers within a single hosted service introduces critical technical challenges:
1. **Sender Identity & State:** Each school's number has its own WhatsApp Business Account (`WABA ID`), Phone Number ID, verified display name, automated Quality Rating (Green/Yellow/Red, per research row **R-04**), messaging tier limit (per **R-10**), and approved template catalog (per **R-06**).
2. **Credential Segregation:** Credentials (access tokens, system user tokens, webhook app secrets) must be isolated per school. Compromise, revocation, or token expiration of School A's credentials must never disrupt School B.
3. **Webhook Demultiplexing:** Meta dispatches delivery receipts (`sent`, `delivered`, `read`, `failed`) and inbound parent messages to a single registered webhook URL. The incoming payload identifies the destination phone number via `metadata.phone_number_id`. The engine must securely route each webhook event to the correct school tenant before applying any state changes.
4. **Rate Limits & Batch Spreading:** Each phone number possesses an independent throughput limit (default 80 mps) and daily portfolio tier (starting at 250 unique users/24h for unverified accounts, per **R-03** and **R-10**). Batches exceeding an institution's daily tier must be spread across days.

## Options Considered

### Option 1: Global Platform Sender (Shared Number)
- *Description*: All schools send messages from a single central SaaS WhatsApp Business number.
- *Pros*: Single token, single webhook, single template review.
- *Cons*: **Strictly rejected by Operator Decision 2.** Destroys institutional trust; one school's spam complaints degrade quality rating for all schools; parents cannot reply to their local school; violates data segregation principles.

### Option 2: Per-School Sender Identity with External Credential References and Dynamic Webhook Demultiplexing
- *Description*:
  - Model a first-class `SenderIdentity` entity scoped to each `org_id`.
  - Store credentials as **secret references** (pointers to environment variables or secret manager paths), never in the application database or audit logs.
  - Implement a unified webhook endpoint that inspects `phone_number_id`, resolves the matching `org_id` and secret reference, verifies the cryptographic signature, and dispatches the event into the tenant's isolated event stream.
  - Model multiple senders per org in the schema, but enable strictly one sender per org in v1.
- *Pros*: Perfect tenant isolation; local school branding; blast radius of token failures restricted to a single school; matches operator mandate.
- *Cons*: Requires managing multiple credentials, multiple template registrations, and dynamic webhook signature resolution.

## Proposed Decision
We propose **Option 2 (Per-School Sender Identity, Isolated Secret References, and Dynamic Webhook Demultiplexing)**.

### 1. Sender Identity Data Model
```python
class SenderStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"      # Created but credentials not yet attached
    CONNECTED = "CONNECTED"                # Credentials verified with Meta Graph API
    TEMPLATES_PENDING = "TEMPLATES_PENDING"# Waiting for template approval
    READY = "READY"                        # Fully operational for outbound dispatch
    SUSPENDED = "SUSPENDED"                # Manually paused by school or platform admin
    FLAGGED = "FLAGGED"                    # Meta flagged due to Red quality rating (R-04)

class QualityRating(str, Enum):
    GREEN = "GREEN"      # High quality
    YELLOW = "YELLOW"    # Medium quality
    RED = "RED"          # Low quality; risk of messaging limit downgrade
    UNKNOWN = "UNKNOWN"

class TemplateRegistrationStatus(str, Enum):
    APPROVED = "APPROVED"
    IN_REVIEW = "IN_REVIEW"
    PAUSED = "PAUSED"
    REJECTED = "REJECTED"

class SenderIdentity(BaseModel):
    schema_version: int = 1
    sender_id: str                          # Opaque UUID
    org_id: str                             # Mandatory tenant owner
    waba_id: str                            # Meta WhatsApp Business Account ID
    phone_number_id: str                    # Meta Phone Number ID (unique index)
    display_phone_number: str               # e.g. "+91 98765 43210"
    verified_display_name: str              # Approved name (e.g. "Delhi Public School Sec 4")
    status: SenderStatus = SenderStatus.NOT_CONFIGURED
    quality_rating: QualityRating = QualityRating.UNKNOWN
    daily_message_limit: int = 250          # Starting tier (R-10), updated from Meta API
    credential_secret_ref: str              # Pointer e.g. "ENV:WHATSAPP_TOKEN_SCH01"
    app_secret_ref: str                     # Pointer e.g. "ENV:WHATSAPP_APP_SECRET_SCH01"
    template_registry: dict[str, TemplateRegistrationStatus] = {}
    is_primary: bool = True                 # v1 supports one active sender per org
```

### 2. Credential Security & Isolation
1. **Zero Database Storage:** API access tokens and app secrets are **never** stored in database tables, serialized models, or log outputs. They are stored as opaque reference keys (e.g. `WHATSAPP_TOKEN_ORG_<ORG_ID>`) resolved at runtime via the typed `Settings` adapter (ADR-0009).
2. **Per-Org Token Failure Isolation:**
   - If an API call for `ORG_A` returns an authentication or permission error (`131037`, `190`, `OAuthException`), the engine flags `ORG_A`'s sender status as `OPERATOR_ACTION` and blocks only `ORG_A`'s dispatch queue.
   - Other schools continue uninterrupted.

### 3. Unified Inbound Webhook Demultiplexing
Meta sends all webhook payloads to a single shared HTTPS endpoint: `POST /api/v1/webhooks/whatsapp`.

**Processing Pipeline:**
1. **Extract Destination Phone Number ID:**
   - Inspect incoming JSON payload: `entry[0].changes[0].value.metadata.phone_number_id`.
   - If missing, reject immediately with HTTP 400.
2. **Resolve Tenant Scope:**
   - Query the `SenderIdentity` registry by `phone_number_id`.
   - If `phone_number_id` is unknown: reject with HTTP 404, log a security warning (omitting the payload to prevent PII exposure), and abort. Zero state mutation occurs.
3. **Cryptographic Signature Verification:**
   - Resolve `app_secret_ref` for the identified tenant.
   - Compute HMAC SHA-256 over raw request bytes using tenant's app secret.
   - Compare in constant time against `X-Hub-Signature-256`. If mismatched: reject with HTTP 401 and write an audit security alert.
4. **Tenant-Scoped Processing:**
   - Hand the validated payload to the tenant-scoped event handler with `org_id` context.
   - Update message status (`sent`, `delivered`, `read`, `failed`) inside an isolated transaction governed by Postgres RLS.

### 4. Per-Sender Daily Cap and Multi-Day Spreading
1. **Tier Enforcement:**
   - The engine tracks unique recipients messaged in a rolling 24-hour window per sender (`daily_recipients_count`).
   - If an institution with a 250-recipient limit attempts to dispatch a batch of 400 students, the scheduler spreads the batch across two consecutive days (e.g. 200 on Sunday evening, 200 on Monday evening).
   - This prevents triggering Meta throttle error `131048` or `131056` (research row **R-10**).
2. **Template Status Gating:**
   - Outbound sends check `sender.template_registry[template_name] == APPROVED`.
   - A paused or rejected template halts dispatch only for that specific school.

### 5. UNVERIFIED Platform Questions (Meta Multi-Business Onboarding)
In accordance with `AGENTS.md` Invariant 12, the engine makes **no claims** regarding Meta onboarding flows and multi-business governance. The following operational items are explicitly marked **`UNVERIFIED`**:
1. *Onboarding Architecture:* Does Meta require each school to be an independent Meta Business Manager account linked via Partner Onboarding / Tech Provider API, or can one Business Manager hold multiple client phone numbers?
2. *Webhook Subscription:* Can a single Meta App receive webhooks from multiple distinct WABA accounts across different business entities, or must each WABA register its own webhook subscription?
3. *Token Lifecycle:* Are permanent System User tokens issued per WABA, or are short-lived tokens refreshed via OAuth2?
4. *Billing Liability:* Does Meta bill each school's attached credit card directly, or does the SaaS platform invoice via consolidated partner billing?

*Engineering Stance:* All dependent multi-account onboarding automation remains disabled. Development uses statically configured sender identities via environment references.

## Consequences
- **Positive**: Strict tenant isolation; zero cross-school blast radius; institutional display name recognition; safe dynamic webhook routing.
- **Negative**: Adds operational overhead in provisioning and configuring separate phone numbers and credentials per school.
- **Neutral**: Enforced at the service and webhook boundaries.

## Revisit When
Revisit when Meta Partner Tech Provider Onboarding APIs are officially evaluated and verified.
