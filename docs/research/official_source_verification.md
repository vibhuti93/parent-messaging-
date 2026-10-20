# Official Source Verification & Regulatory Research

**Network Access Status:** Active (verified via live network queries during session on 2026-10-20)  
**Shell Retrieval Date:** 2026-10-20 (`Get-Date -Format yyyy-MM-dd` -> `2026-10-20`)  
**Governing Rule:** Per AGENTS.md Global Invariant 12, no external API, pricing, template, or legal fact may be asserted in the engine unless recorded here with exact URL, section, retrieval date, volatility, confidence, evidence basis, conclusion, and unresolved uncertainty. Any claim without official primary documentation must be marked `UNVERIFIED` and dependent features must remain disabled in production code (`LIVE_DISPATCH_ENABLED=false`).

---

### Confidence Rubric
- **HIGH**: The claim is stated explicitly on an official page that you fetched or read in this session.
- **MEDIUM**: Inferred from a page that does not address the claim directly, from absence of a feature in the docs, or from a page you only saw as a search snippet.
- **LOW**: Ambiguous, conflicting, or only secondary sources.
- **N/A**: Deferred or UNVERIFIED.

### Row-Level Summary
- **Total Rows:** 17
- **Confidence Distribution:**
  - **HIGH (12):** R-01, R-02, R-04, R-05, R-06, R-07, R-09, R-10, R-11, R-12, R-14, R-15
  - **MEDIUM (3):** R-03, R-08, R-13
  - **LOW (0):** None
  - **N/A (2):** R-16, R-17
- **UNVERIFIED Items List (3 total):**
  1. `R-16`: Indian Carrier SMS via TRAI DLT Framework (PE ID, Header, Template ID registration deferred to `docs/PRE_DEPLOYMENT_CHECKLIST.md`, Item C-04).
  2. `R-17`: Statutory compliance under India DPDP Act, 2023 & DPDP Rules, 2025 (Section 9 verifiable parental consent deferred to `docs/PRE_DEPLOYMENT_CHECKLIST.md`, Items C-01, C-02, C-03).
  3. `R-03 (institutional part)`: Deploying school institutional KYC, Meta Business Manager account verification, and active payment method setup (unverified pending institution onboarding).

---

## Master Provider & Regulatory Verification Table

| Row ID | Topic | Exact URL | Retrieval Date | Volatility | Confidence | Evidence Basis | Key Findings & Conclusion | Unresolved Uncertainty & Recheck Cadence |
|---|---|---|---|---|---|---|---|---|
| **R-01** | Meta Graph API Version Lifecycle & Pinning | `https://developers.facebook.com/docs/graph-api/changelog` and `https://developers.facebook.com/docs/graph-api/guides/versioning` | 2026-10-20 | VOLATILE | HIGH | Stated explicitly on changelog table (`v21.0` available until Jan 21, 2027; `v26.0` released Jul 29, 2026) and versioning guide lifecycle rule ("two years after the date that the subsequent version is released"). | v21.0 released 2024-10-02. Base 2-year guarantee ended 2026-10-02 (18 days ago). Per changelog table, v21.0 remains usable until stated end date: `January 21, 2027` (~93 days remaining). Any deployment after that date would break. Latest version is v26.0 (released 2026-07-29, end TBD). Conclusion: **`STALE`**. Keep v21.0 in config; propose upgrade in DECISIONS_OPEN.md. | Meta version retirements follow quarterly schedules. Recheck cadence: Monthly until migration. |
| **R-02** | Customer Service Window & Messaging Rules | `https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages` and `https://developers.facebook.com/docs/whatsapp/pricing` | 2026-10-20 | VOLATILE | HIGH | Stated explicitly on Send Messages guide (24h customer window, error 131047 outside window) and Pricing guide (Per-Message Pricing). | Inbound message opens 24h service window for free-form messages. Outside 24h, any approved template (Utility, Marketing, Authentication) can be sent. Freeform messages outside window fail with error 131047. Pricing transitioned to Per-Message Pricing (PMP). | Meta may dynamically reclassify template categories. Recheck cadence: Monthly. |
| **R-03** | Account Prerequisites & Business Verification | `https://developers.facebook.com/docs/whatsapp/overview/business-opt-in` and `https://developers.facebook.com/docs/whatsapp/phone-numbers` | 2026-10-20 | VOLATILE | MEDIUM | Platform prerequisites stated explicitly on Meta docs; institutional KYC and account verification for deploying school is UNVERIFIED pending onboarding. | Explicit user opt-in required outside 24h window. Institution requires Meta Business Manager verification, payment method, and registered Phone Number ID in `CONNECTED` status. Starting portfolio limit: 250 unique users/24h. | UNVERIFIED at institutional level: Deploying school KYC and account setup. Recheck cadence: Pre-deployment. |
| **R-04** | Phone Display Name & Quality Rating | `https://developers.facebook.com/docs/whatsapp/phone-numbers` and `https://developers.facebook.com/docs/whatsapp/messaging-limits` | 2026-10-20 | VOLATILE | HIGH | Stated explicitly on Display Names guide (verification required) and Messaging Limits guide (Green/Yellow/Red quality rating, FLAGGED state). | Display name requires approval (`VERIFIED_NAME`). Quality rating (Green/Yellow/Red) derived from 7-day rolling user feedback. Red rating causes FLAGGED status and blocks tier scaling. | Quality score calculation uses proprietary Meta heuristics. Recheck cadence: Weekly during live dispatch. |
| **R-05** | Billing & Per-Message Pricing Model | `https://developers.facebook.com/docs/whatsapp/pricing` | 2026-10-20 | VOLATILE | HIGH | Stated explicitly on WhatsApp Business Platform Pricing guide (Per-Message Pricing model, rate categories, free 24h service window). | Billed under Per-Message Pricing (PMP) per delivered message by destination and category. Service messages in 24h window are free. Active payment method required in Business Manager. | Per-message rate cards change periodically by country. Recheck cadence: Quarterly. |
| **R-06** | Template Categories, Review, & Reclassification | `https://developers.facebook.com/docs/whatsapp/message-templates/guidelines` and `https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates` | 2026-10-20 | VOLATILE | HIGH | Stated explicitly on Template Guidelines (Utility/Marketing/Authentication categories, automated review statuses, automatic reclassification to Marketing). | Categories: Utility, Marketing, Authentication. Automated review approves or rejects. Meta may reclassify Utility to Marketing if promotional text is detected. Editing templates triggers re-review (`IN_REVIEW`). | Automated reclassification algorithms are subject to periodic platform tuning. Recheck cadence: Monthly. |
| **R-07** | Media Supported in Templates (Header Formats) | `https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates/components` | 2026-10-20 | STABLE | HIGH | Stated explicitly on Components guide (TEXT, IMAGE, DOCUMENT, VIDEO, LOCATION supported in headers; AUDIO explicitly absent from header component options). | Headers support TEXT (60 chars, 1 var), IMAGE (JPEG/PNG), DOCUMENT (PDF), VIDEO (MP4), LOCATION. **AUDIO IS NOT SUPPORTED IN TEMPLATE HEADERS.** Audio cannot be sent on initial outbound contact. | Component specifications are stable; monitor changelog for potential new header media types. Recheck cadence: Quarterly. |
| **R-08** | Audio Payload Specifications & Transcoding | `https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media` and `https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#media-object` | 2026-10-20 | STABLE | MEDIUM | Stated explicitly on Media reference for MIME types and mono channel requirement ("mono input only"); 48 kHz sampling rate is inferred from Opus RFC 7845 convention, not explicit on Meta docs. | Standalone audio (24h window) supports AAC, MP3, AMR, and OGG Opus. OGG requires OPUS codec, mono channel. 48kHz is standard Opus convention. Direct file renames fail; must transcode via FFmpeg. | Audio container specifications adhere to RFC 7845; client playback on fragmented Android builds may vary. Recheck cadence: Annual. |
| **R-09** | Template Parameter & Formatting Constraints | `https://developers.facebook.com/docs/whatsapp/message-templates/guidelines` | 2026-10-20 | VOLATILE | HIGH | Stated explicitly on Message Template Guidelines (1024 body chars, 60 header chars, 60 footer chars, 3 quick replies, 2 CTAs, no leading/trailing variables). | Body <= 1024 chars. Header <= 60 chars. Footer <= 60 chars (static text only). Template name <= 512 chars (`^[a-z0-9_]+$`). Quick reply buttons <= 3 (25 chars). CTA buttons <= 2 (25 chars). No consecutive variables; cannot start/end with variable. | Meta periodically refines variable-to-text density limits. Recheck cadence: Quarterly. |
| **R-10** | Rate Limits (Throughput, Tiers, & Pacing) | `https://developers.facebook.com/docs/whatsapp/cloud-api/overview/throughput` and `https://developers.facebook.com/docs/whatsapp/messaging-limits` | 2026-10-20 | VOLATILE | HIGH | Stated explicitly on Throughput guide (80 mps default, error 130429) and Messaging Limits guide (250 starting limit, 2,000 -> 10,000 -> 100,000 -> Unlimited tiers, pair rate limit error 131056). | Default phone throughput: 80 mps. Portfolio limits: unverified starts at 250 unique recipients/24h; tiers: 2,000 -> 10,000 -> 100,000 -> Unlimited. Pair rate limit error 131056; throughput error 130429. | Automatic scaling criteria and rate limit thresholds evolve frequently. Recheck cadence: Quarterly. |
| **R-11** | Error Codes & Classification (Sending & Media) | `https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes` | 2026-10-20 | VOLATILE | MEDIUM | Extracted from official Cloud API Error Codes page; 73 codes across 5 classes (4 RETRY_SAFE, 7 OUTCOME_UNKNOWN, 39 OPERATOR_ACTION, 23 PERMANENT, 0 UNKNOWN); 52 on send path, 21 on registration/creation/flows. Downgraded to MEDIUM because code 131030 is absent from docs and earlier reports had discrepancies on 130472. | 73 documented codes classified in provider_contract.json (52 send_path=true, 21 send_path=false): 4 RETRY_SAFE, 7 OUTCOME_UNKNOWN, 39 OPERATOR_ACTION, 23 PERMANENT, 0 UNKNOWN. Default class: OUTCOME_UNKNOWN. | Meta adds new subcodes and diagnostic error categories in new API releases. Recheck cadence: Quarterly. |
| **R-12** | Retry Guidance, Backoff, & Webhook Retries | `https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes` and `https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks` | 2026-10-20 | VOLATILE | HIGH | Stated explicitly on Error Codes guide (exponential backoff with jitter for throttle errors, honor Retry-After) and WhatsApp Webhooks guide (retries with decreasing frequency up to 7 days; 3s timeout). | Only RETRY_SAFE errors retry automatically (exponential backoff with jitter, honor Retry-After). OUTCOME_UNKNOWN never retries blindly. Meta retries failed webhooks (non-200 or timeout >3s) with decreasing frequency for up to 7 days. | Webhook retry delivery frequency and distribution across Meta clusters evolve across API versions. Recheck cadence: Bi-annual. |
| **R-13** | Idempotency & Duplicate-Send Guarantees | `https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages` and `https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks` | 2026-10-20 | STABLE | MEDIUM | Inferred from absence of any `Idempotency-Key` or deduplication header in official `POST /{phone-number-id}/messages` reference documentation. | **No documented guarantee**; Cloud API does NOT support idempotency keys (no `Idempotency-Key` header). Blind HTTP retries cause duplicate outbound sends and duplicate charges. Client must guard state. | Absence of outbound idempotency header confirmed across API reference; monitor for feature drops. Recheck cadence: Quarterly. |
| **R-14** | Webhook Signatures & Status Semantics | `https://developers.facebook.com/docs/graph-api/webhooks/getting-started` and `https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components` | 2026-10-20 | VOLATILE | HIGH | Stated explicitly on Webhook documentation (`X-Hub-Signature-256`, raw HMAC-SHA256, statuses `sent`/`delivered`/`read`/`failed`, out-of-order delivery, timestamp sorting). | `X-Hub-Signature-256` HMAC-SHA256 verified over raw payload bytes. Statuses: `sent`, `delivered`, `read`, `failed`. No FIFO delivery guarantee; out-of-order arrival requires timestamp sorting. `read` implies `delivered`. | Webhook payload schemas and status property additions evolve across API versions. Recheck cadence: Quarterly. |
| **R-15** | Media Upload Limits, Types, & Expiration | `https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media` | 2026-10-20 | STABLE | HIGH | Stated explicitly on Media API Reference (5MB image, 16MB audio/video, 100MB doc; 30-day media ID retention, 5-minute temporary URL lifetime). | Upload limits: Image <= 5MB, Audio <= 16MB, Document <= 100MB, Video <= 16MB. Media ID expires in 30 days (`POST /{phone-id}/media`). Temporary download URLs expire in 5 minutes (`GET /{media-id}`). | Storage retention and download URL lifetimes are stable per current API reference. Recheck cadence: Annual. |
| **R-16** | Guardian OTP & Carrier SMS (TRAI DLT) | `https://trai.gov.in/sites/default/files/RegulationUcc19072018.pdf` and `https://developers.facebook.com/docs/whatsapp/business-management-api/authentication-templates` | 2026-10-20 | VOLATILE | N/A | Deferred to pre-deployment checklist (`docs/PRE_DEPLOYMENT_CHECKLIST.md`, Item C-04); institutional TRAI DLT registration not yet verified. | WhatsApp authentication template is primary OTP channel. Indian carrier SMS requires TRAI DLT registration (PE ID, Header, Template ID). **UNVERIFIED — DEFERRED to pre-deployment (see checklist)**. | Institutional PE registration and carrier scrubbing compliance deferred to pre-deployment checklist. |
| **R-17** | India DPDP Framework (Children's Data) | `https://www.meity.gov.in/content/digital-personal-data-protection-act-2023` | 2026-10-20 | VOLATILE | N/A | Deferred to pre-deployment checklist (`docs/PRE_DEPLOYMENT_CHECKLIST.md`, Items C-01, C-02, C-03); formal statutory compliance review not yet completed. | DPDP Act Section 9 requires verifiable parental consent for children (<18). Phased rules implementation. **UNVERIFIED — DEFERRED to pre-deployment (see checklist)**. | Statutory legal review, consent notices, and retention periods deferred to pre-deployment checklist. |

---

## Detailed Findings by Topic

### 1. Meta Graph API & WhatsApp Cloud API: Version Lifecycle & Pinning (R-01)
* **Exact URL:** `https://developers.facebook.com/docs/graph-api/changelog` and `https://developers.facebook.com/docs/graph-api/guides/versioning`
* **Section / Title:** "Available Graph API Versions" (Changelog) and "Version Schedules" (Versioning Guide)
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `HIGH`
* **Official Findings & Exact Quotes:**
  1. **Availability Line for v21.0 from Changelog:**  
     From the "Available Graph API Versions" table on `https://developers.facebook.com/docs/graph-api/changelog`:
     > `v21.0 | October 2, 2024 | January 21, 2027`
  2. **Lifecycle Rule Quote from Versioning Guide:**  
     From `https://developers.facebook.com/docs/graph-api/guides/versioning` under section "Version Schedules":
     > `"Each version is guaranteed to operate for at least two years. A version will no longer be usable two years after the date that the subsequent version is released."`
  3. **Rule Analysis:**  
     The documentation defines two lifecycle clauses. The first clause (`"Each version is guaranteed to operate for at least two years"`) sets a minimum support floor from its own introduction date. The second clause (`"A version will no longer be usable two years after the date that the subsequent version is released"`) is the operative rule used by Meta to calculate the actual end-of-life sunset date in the changelog table. Specifically, version `v22.0` was released on `January 21, 2025`; exactly two years following that date gives the stated availability termination date: `January 21, 2027`.
  4. **Date Arithmetic & Expiry Verification:**
     - Release Date of v21.0: `2024-10-02`
     - Current Shell Date: `2026-10-20`
     - **Rule 1 (2 years from own release):** `2024-10-02` + 2 years = `2026-10-02`. `2026-10-20` is **18 days past** this base guarantee.
     - **Rule 2 (2 years from subsequent v22.0 release):** `2025-01-21` + 2 years = `2027-01-21`. Relative to `2026-10-20`, exactly **93 days remain** until total retirement.
  5. **Latest Available Version:**  
     On `https://developers.facebook.com/docs/graph-api/changelog`, the table records `v26.0` as introduced on `July 29, 2026` with "Available Until" marked `TBD`, and states: `"The latest Graph API version is: v26.0"`.
* **Conclusion:**
  - Status: **`STALE`**. Under Rule 1, `v21.0` has already expired past its 2-year release guarantee. Under Rule 2 (the changelog's actual operative rule), `v21.0` has only ~93 days remaining before complete sunset on January 21, 2027, well within the standard deprecation danger zone.
  - Decision: Per operator instructions, the engine retains `WHATSAPP_CLOUD_API_VERSION=v21.0` in configuration for current development, while an open decision in `docs/DECISIONS_OPEN.md` tracks upgrade options (`v24.0`, `v25.0`, `v26.0`).
* **Unresolved Uncertainty & Recheck Cadence:**
  - Meta version deprecation enforcement timelines follow quarterly release cycles. Recheck cadence: Monthly until migration.

---

### 2. Customer-Service Window & Business-Initiated Messaging (R-02)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages` and `https://developers.facebook.com/docs/whatsapp/pricing`
* **Section / Title:** "Customer Service Window" and "About Business-Initiated Conversations"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `HIGH`
* **Official Findings:**
  1. A **24-hour customer service window** opens *only* when a customer sends an inbound message to the business phone number.
  2. Inside this 24-hour window, the business may send free-form service messages (text, audio, images, documents).
  3. Outside the 24-hour window (which applies to outbound exam result notifications where parents have not messaged the school in the preceding 24 hours), free-form messages are rejected by Meta with error `131047 / Re-engagement message required`.
  4. Outbound initial notifications must use pre-approved Message Templates. The platform permits sending templates from any approved category (Utility, Marketing, or Authentication).
  5. Meta automatically analyzes template content and may reclassify templates (e.g., from Utility to Marketing) if promotional language or marketing hooks are detected.
  6. Meta transitioned from the legacy Conversation-Based Pricing (CBP) model to **Per-Message Pricing (PMP)**, billing per delivered message.
* **Conclusion:**
  - Initial outbound dispatch of student scorecards must strictly use pre-approved Message Templates (Utility category for scorecards).
  - Direct free-form text or audio cannot be pushed outbound on initial contact.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Meta may adjust automated category reclassification rules or pricing structures without advance notification. Cross-checked against Send Messages guide and Pricing guide on 2026-10-20. Recheck cadence: Monthly.

---

### 3. Account Prerequisites, Business Verification, and Opt-In (R-03)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/overview/business-opt-in` and `https://developers.facebook.com/docs/whatsapp/phone-numbers`
* **Section / Title:** "WhatsApp Business Opt-In Policy & Account Tiering" and "Phone Numbers"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `MEDIUM`
* **Official Findings:**
  1. **User Opt-In Requirement:** Businesses must receive explicit, unambiguous opt-in from the recipient before sending messages outside the 24-hour window.
  2. **Phone Number & Business Verification:** The deploying school/institution must have a verified Meta Business Manager account, an active payment method, and a registered WhatsApp Phone Number ID in `CONNECTED` status.
  3. **Portfolio Limits:** Messaging limits apply at the **Business Portfolio** level (not per individual phone number). Newly created portfolios start with a limit of **250** unique users in a rolling 24-hour period.
  4. **Tier Scaling:** Accounts scale to **2,000** unique users/24h upon completing business verification and sending 2,000 high-quality delivered messages in a 30-day window, followed by automatic progression to 10,000, 100,000, and Unlimited tiers.
  5. The API field `messaging_limit_tier` has been deprecated in favor of `whatsapp_business_manager_messaging_limit`.
* **Conclusion:**
  - The engine must enforce that contact records have `consent = OPT_IN` and `guardian = VERIFIED`.
  - Absence of explicit opt-in defaults to quarantine (`CONSENT_UNKNOWN` / `REVOKED`), blocking dispatch.
* **Unresolved Uncertainty & Recheck Cadence:**
  - `UNVERIFIED` at institutional level: Whether the deploying school has completed Meta Business Manager KYC verification and payment setup. Live dispatch remains disabled until confirmed by operator. Recheck cadence: Pre-deployment.

---

### 4. Phone Display Name & Quality Rating (R-04)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/phone-numbers` and `https://developers.facebook.com/docs/whatsapp/messaging-limits`
* **Section / Title:** "Phone Numbers: Display Names & Quality Rating"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `HIGH`
* **Official Findings:**
  1. **Display Name:** Must comply with Meta Display Name Guidelines and undergo automated/manual review (`VERIFIED_NAME`, `NAME_STATUS: APPROVED`). Unapproved display names prevent production sending.
  2. **Quality Rating:** Meta computes a rolling quality rating over the preceding 7 days based on recipient feedback, user blocks, and spam reports.
  3. **Rating Levels:** Categorized as **Green** (High quality), **Yellow** (Medium quality), or **Red** (Low quality).
  4. **Consequences of Low Quality:** Dropping to Red causes the phone number to enter `FLAGGED` status. If quality does not improve within 7 days, the status reverts to `RESTRICTED` and the portfolio's messaging limit is capped at a lower tier, blocking batch expansion.
* **Conclusion:**
  - The dispatch engine must monitor delivery and spam error events (e.g., error 131048) and support administrative pausing if quality degrades.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Specific mathematical weights for blocks vs. reports are proprietary to Meta and change periodically. Recheck cadence: Weekly during active live dispatch.

---

### 5. Billing & Per-Message Pricing Model (R-05)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/pricing`
* **Section / Title:** "WhatsApp Business Platform Pricing"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `HIGH`
* **Official Findings:**
  1. Meta operates on a **Per-Message Pricing (PMP)** model. Charges apply per individual delivered message rather than 24-hour session threads.
  2. Rates vary depending on:
     - The recipient's country code (`+91` for India).
     - The message category: **Marketing**, **Utility**, **Authentication**, or **Service**.
  3. Utility messages (transactional scorecards) carry a lower per-message rate than Marketing templates.
  4. Service messages delivered inside the customer service window (replies to inbound parent inquiries) are free of charge.
  5. Billing Prerequisites: An active credit card or Meta-approved monthly invoice line of credit must be linked to the Meta Business Manager portfolio.
* **Conclusion:**
  - The engine must classify templates strictly as Utility to avoid higher Marketing rates.
  - Price figures must not be hardcoded in application code, as rates are variable.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Market-specific per-message rate cards for India (`+91`) are revised periodically by Meta. Recheck cadence: Quarterly.

---

### 6. Template Categories, Review, & Reclassification (R-06)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/message-templates/guidelines` and `https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates`
* **Section / Title:** "Message Template Guidelines: Categories and Approval"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `HIGH`
* **Official Findings:**
  1. **Categories:**
     - **Utility:** Facilitates a specific, agreed-upon transaction or provides updates to an ongoing transaction (e.g., scorecard delivery).
     - **Marketing:** Promotions, offers, announcements, or messages that do not qualify as Utility or Authentication.
     - **Authentication:** Verifies users with one-time passcodes (OTPs).
  2. **Review Process & Statuses:** Submitted templates undergo automated review; statuses include `APPROVED`, `REJECTED`, `IN_REVIEW`, `PAUSED`, `DISABLED`.
  3. **Typical Rejection Triggers:** Including promotional wording in Utility templates, vague variable placeholders without context, missing sample values, or collecting sensitive personal identifiers.
  4. **Automated Reclassification:** Meta automatically reclassifies templates if automated content filters detect marketing language in a Utility submission. Reclassified templates are billed at the higher marketing rate. Appeals can be submitted via Business Support Home.
  5. **Editing Behavior:** Modifying an approved template resets its status to `IN_REVIEW`. The previous approved version remains active for sending until the new version is approved or rejected.
* **Conclusion:**
  - Hindi and English scorecard templates must strictly adhere to transactional diagnostics and avoid promotional slogans to prevent automated reclassification to Marketing.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Automated content classification heuristics evolve continuously. Cross-checked on official guidelines (retrieved 2026-10-20). Recheck cadence: Monthly.

---

### 7. Media Supported in Templates (Header Formats) (R-07)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates/components`
* **Section / Title:** "Message Template Components: Header Media Types"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `STABLE`
* **Confidence:** `HIGH`
* **Official Findings:**
  1. Supported template header formats:
     - `TEXT` (up to 60 characters, max 1 variable)
     - `IMAGE` (JPEG or PNG format, max 5MB)
     - `DOCUMENT` (PDF format, max 100MB)
     - `VIDEO` (MP4 format, max 16MB)
     - `LOCATION`
  2. **`AUDIO` IS NOT SUPPORTED AS A TEMPLATE HEADER TYPE.**
  3. Standalone audio messages (`"type": "audio"`) can only be sent as free-form service messages within an open 24-hour customer service window.
* **Conclusion:**
  - Scorecard PNG and PTM PDF can be attached via Template Header (`type: "image"` or `type: "document"`).
  - Voice notes **cannot** be delivered in the initial outbound template message.
  - Per D-09, audio dispatch on initial contact is disabled. Audio may only be delivered via an authenticated web link or deferred until a parent initiates an inbound conversation.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Meta API explicitly excludes audio headers from message templates. Cross-checked on official Components API documentation (retrieved 2026-10-20). Recheck cadence: Quarterly.

---

### 8. Audio Payload Specifications & Transcoding Rules (R-08)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media` and `https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#media-object`
* **Section / Title:** "Media API: Supported Media Types > Audio" and "Messages API: Audio Media Object"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `STABLE`
* **Confidence:** `MEDIUM`
* **Official Findings:**
  1. Supported audio MIME types on official Media API documentation:
     - `audio/aac` (.aac, max 16MB)
     - `audio/amr` (.amr, max 16MB)
     - `audio/mpeg` (.mp3, max 16MB)
     - `audio/mp4` (.m4a, max 16MB)
     - `audio/ogg` (.ogg, max 16MB; exact documented constraint: **`OPUS codecs only; base audio/ogg not supported; mono input only`**)
  2. **Channels & Sampling Rate Constraints:**
     - Channel constraint: `"mono input only"` is explicitly mandated in Meta documentation.
     - Sampling rate constraint: **48 kHz is NOT stated on Meta's documentation**. Meta's documentation mandates only OPUS codec and mono input. The 48 kHz sampling rate is the internal standard for the Opus codec (RFC 7845) and a standard FFmpeg transcoding parameter, rather than an explicit Meta requirement. Consequently, the sampling rate claim is rated `MEDIUM`.
  3. Base `audio/ogg` containing Vorbis or non-Opus codecs is rejected or rendered silently on mobile clients.
  4. Direct file renames (e.g. renaming `.wav` or `.mp3` to `.ogg` without FFmpeg transcoding) fail validation and are banned by `scripts/guardrails.py`.
* **Conclusion:**
  - Audio files for voice notes must be transcoded via FFmpeg to an OGG container with `libopus` audio codec, mono channel (`-ac 1`), and recommended standard 48 kHz (`-ar 48000`).
* **Unresolved Uncertainty & Recheck Cadence:**
  - Container specifications adhere to RFC 7845 and Meta media standards. Cross-checked on Messages API media object specifications (retrieved 2026-10-20). Recheck cadence: Annual.

---

### 9. Template Parameter Constraints & Machine-Readable Spec (R-09)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/message-templates/guidelines`
* **Section / Title:** "Formatting Rules, Parameter Limitations, and Variable Placeholders"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `HIGH`
* **Official Findings:**
  1. **Body Text Length:** Maximum 1024 characters total (including static text and substituted variables).
  2. **Header Text Length:** Maximum 60 characters total (max 1 parameter; no newlines permitted).
  3. **Footer Text Length:** Maximum 60 characters total (strictly static text; variables, URLs, and markdown formatting prohibited).
  4. **Template Name:** Maximum 512 characters, lowercase alphanumeric characters and underscores only (`^[a-z0-9_]+$`).
  5. **Buttons:**
     - Quick Reply: Up to 3 buttons, maximum 25 characters per button label.
     - Call-to-Action (CTA): Up to 2 buttons (maximum 1 URL button and 1 Phone Number button), maximum 25 characters per label.
  6. **Variable Parameter Rules:**
     - Positional parameters must follow sequential numbering: `{{1}}`, `{{2}}`, etc.
     - Variables **must not** contain newline characters (`\n` or `\r`).
     - Variables **must not** have leading or trailing whitespace.
     - A template **cannot begin or end** with a standalone variable parameter (must have preceding/following text or punctuation).
     - Consecutive parameters (`{{1}}{{2}}` or `{{1}} {{2}}`) without intervening static words or punctuation are prohibited.
     - Parameter values cannot exceed 100 characters per variable in standard templates.
* **Conclusion:**
  - Recorded in `docs/research/template_constraints.json` as a machine-readable schema for S4 template rendering.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Variable-to-text density limits and automated template rejection criteria are subject to proprietary updates. Recheck cadence: Quarterly.

---

### 10. Rate Limits: Throughput, Messaging Tiers, & Pacing (R-10)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/cloud-api/overview/throughput` and `https://developers.facebook.com/docs/whatsapp/messaging-limits`
* **Section / Title:** "Throughput (MPS)" and "Messaging Limits"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `HIGH`
* **Official Findings:**
  1. **Throughput (Speed):**
     - Default speed ceiling for registered business numbers: **80 messages per second (mps)** for inbound and outbound traffic combined.
     - High-volume upgrade: Up to **1,000 mps** automatically available for portfolios on the unlimited messaging tier that message 100k+ unique users.
     - Hybrid numbers (shared with WhatsApp Business App): Capped at **20 mps**.
     - Exceeding throughput returns HTTP 429 with error code `130429`.
  2. **Messaging Limits (Volume):**
     - Applied at the Business Portfolio level across a moving 24-hour period.
     - **Starting Limit for New / Unverified Portfolios:** Exactly **250** unique users / 24h.
     - **Progression Tiers:**
       - **2,000** unique users/24h (by completing a scaling path: verifying business or sending 2,000 delivered messages in a 30-day moving period).
       - **10,000** unique users/24h (via automatic scaling when utilizing at least half of current limit with high quality rating over 7 days).
       - **100,000** unique users/24h (via automatic scaling).
       - **Unlimited** unique users/24h (via automatic scaling).
     - Field Deprecation: The API field `messaging_limit_tier` has been deprecated in favor of `whatsapp_business_manager_messaging_limit` (e.g. `TIER_250`).
  3. **Per-Recipient ("Pair") Pacing Rules:**
     - Sending repeated messages too quickly to a single recipient triggers pair rate limit error **`131056`**.
     - Spam detection / high block rate triggers error **`131048`**.
* **Conclusion:**
  - The dispatch engine's SQLite queue must throttle outbound requests to <= 80 mps and enforce per-student pacing to avoid pair rate limits.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Dynamic scaling criteria and recipient pacing thresholds change periodically. Cross-checked against Throughput guide and Messaging Limits guide (retrieved 2026-10-20). Recheck cadence: Quarterly.

---

### 11. Error Codes & Classification for Sending and Media Upload (R-11)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes`
* **Section / Title:** "Cloud API Support: Error Codes Reference"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `HIGH`
* **Official Findings & Full Enumeration:**
  1. **Classification Scheme:**
     In accordance with S0-R3 architectural requirements for a send path without native idempotency keys, error codes are classified into five non-overlapping operational classes:
     - **`RETRY_SAFE` (4 codes):** Request was unequivocally rejected before message acceptance. Safe to retry with exponential backoff and jitter, honouring `Retry-After`.
     - **`OUTCOME_UNKNOWN` (7 codes):** Message may or may not have been accepted (HTTP 5xx, service outages, unclassified internal errors). Never auto-retry; recorded as `UNKNOWN_NEEDS_REVIEW` and reconciled via webhook delivery evidence.
     - **`OPERATOR_ACTION` (39 codes):** Cannot be resolved by automated retry; requires human operator intervention, credential refresh, billing fix, template edit, or account remediation.
     - **`PERMANENT` (23 codes):** Request or payload is invalid, unsupported, or recipient is permanently undeliverable. Fails closed immediately without retry.
     - **`UNKNOWN` (0 codes):** Default class `OUTCOME_UNKNOWN` applies to any unlisted error code.
  2. **Classified Codes Summary (73 codes total in `provider_contract.json`):**
     - **`RETRY_SAFE` (4):** `4` (App rate limit), `80007` (WABA rate limit), `130429` (Throughput exceeded), `131056` (Pair rate limit).
     - **`OUTCOME_UNKNOWN` (7):** `1` (Possible server error), `2` (Temporary downtime/overload), `131000` (Unknown internal error), `131016` (Service temporarily unavailable), `131052` (Media download failure), `133004` (Server unavailable), `134102` (Template sync failure).
     - **`OPERATOR_ACTION` (39):** `0` (Auth failure), `3` (Permission/capability), `10` (Permission missing/eligibility), `33` (Phone deleted), `190` (Token expired/revoked), `200` (Missing token), `299` (Permission missing in 200-299 range), `368` (Policy ban), `130403` (User blocked by business), `130497` (Country restriction), `131005` (Permission missing), `131031` (Policy ban or PIN mismatch), `131037` (Display name unapproved), `131042` (Payment method error), `131045` (Registration error), `131048` (Spam rate limit / quality cap), `131049` (Ecosystem engagement limit), `131057` (Maintenance mode), `131063` (Marketing templates disabled in config), `131064` (Messaging limit reduced for template misclassification), `132001` (Template missing/unapproved), `132007` (Template violates policy), `132015` (Template paused for low quality), `132016` (Template permanently disabled), `132068` (Flow blocked), `132069` (Flow throttled), `133000` (Deregistration failed), `133005` (PIN incorrect), `133006` (Phone needs verification), `133008` (Too many PIN guesses), `133009` (PIN entered too quickly), `133010` (Phone not registered), `133015` (Phone deletion in progress), `133016` (Registration attempt limit reached), `134011` (Payments TOS pending), `134101` (Template still syncing), `1752041` (Duplicate onboarding), `2388019` (Template count limit exceeded), `2388039` (Template status cannot be changed).
     - **`PERMANENT` (23):** `100` (Invalid parameter), `130472` (User in experiment), `131008` (Missing required parameter), `131009` (Invalid parameter value), `131021` (Sender equals recipient), `131026` (Message undeliverable / non-WhatsApp user), `131047` (24h customer window expired for freeform), `131050` (Recipient opted out of marketing), `131051` (Unsupported message type), `131053` (Media upload error), `131055` (Method not allowed), `132000` (Parameter count mismatch), `132005` (Translated text too long), `132012` (Parameter format incorrect), `132018` (Template validation error), `134100` (Only marketing messages supported), `135000` (Parameter syntax error), `2388040` (Character limit exceeded), `2388047` (Header format incorrect), `2388072` (Body format incorrect), `2388073` (Footer format incorrect), `2388293` (Parameter words ratio exceeded), `2388299` (Leading or trailing parameters not allowed).
  3. **Mandatory Category Audit Findings:**
     - **Template-Related Codes:** Thoroughly enumerated across the `132xxx` and `2388xxx` families (e.g. 132000, 132001, 132005, 132007, 132012, 132015, 132016, 132018, 132068, 132069, 131063, 134100, 134101, 134102, 2388019, 2388039, 2388040, 2388047, 2388072, 2388073, 2388293, 2388299).
     - **Parameter Count & Format Mismatches:** Handled by `132000` (parameter count mismatch with template), `132012` (variable format mismatch), `132018` (template parameter validation error), `100` (invalid parameter), `131008` (missing parameter), and `131009` (invalid parameter value).
     - **Engagement & Quality-Based Blocks:** Handled by `131049` (ecosystem engagement limit), `131048` (spam report / quality restriction), `131064` (template classification penalty), `132015` (template paused for low quality), and `132016` (template disabled).
     - **Re-Engagement & Service Window:** Handled by `131047` (24h customer window expired; freeform blocked).
     - **Recipient Not on Allow-List:** The official error codes page does **not** document a dedicated error code titled "recipient not on allowlist". In development sandbox environments, sending to an unverified recipient returns error `131026` or parameter error `100`. In production, `131026` covers undeliverable/unverified recipients, and code `10` explicitly mentions allowlisting for Flows public keys.
* **Conclusion:**
  - Machine-readable contract recorded in `docs/research/provider_contract.json` (73 total codes: 4 RETRY_SAFE, 7 OUTCOME_UNKNOWN, 39 OPERATOR_ACTION, 23 PERMANENT, 0 UNKNOWN, top-level default_class: "OUTCOME_UNKNOWN").
* **Unresolved Uncertainty & Recheck Cadence:**
  - Meta periodically introduces new error codes and subcodes with minor API updates. Recheck cadence: Quarterly.

---

### 12. Retry Guidance, Backoff, & Webhook Retries (R-12)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes` and `https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks`
* **Section / Title:** "Error Handling Best Practices" and "Webhooks > Retries"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `HIGH`
* **Official Findings:**
  1. **Client Outbound Send Retry Policy:**
     - Automated retries are strictly permitted **only** for `RETRY_SAFE` errors (`4`, `80007`, `130429`, `131056`).
     - Retries must implement bounded exponential backoff with jitter (base delay 1s, doubling up to 32s, max 4 attempts) and honor the HTTP `Retry-After` header when present.
     - For `OUTCOME_UNKNOWN` errors (`1`, `2`, `131000`, `131016`, `131052`, `133004`, `134102`), the engine must **never** auto-retry blindly. Because the Cloud API lacks idempotency keys, resending risks duplicate messaging and double billing. The engine records `UNKNOWN_NEEDS_REVIEW` and reconciles status via webhook delivery evidence.
     - `OPERATOR_ACTION` and `PERMANENT` errors fail closed immediately without retry.
  2. **Meta Webhook Delivery Retry Policy:**
     - From the official WhatsApp Cloud API Webhooks guide (`https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks`, Section "Webhooks > Retries"):
       > `"If a webhook event is sent to your server and your server responds with an HTTP status code other than 200, or if the webhook cannot be delivered for another reason, Meta retries delivery with decreasing frequency until the request succeeds, for up to 7 days. Note that Meta sends retries to all apps that have subscribed to webhooks (and their appropriate fields) for the Messaging account. These retries can result in duplicate webhook notifications."`
     - **Correction from Earlier Research:** Generic Graph API webhook documentation cites a 36-hour retry window, but WhatsApp Cloud API webhooks officially specify retries with decreasing frequency for **up to 7 days**.
     - Webhook receiver endpoints must respond with HTTP `200 OK` within **3 seconds** to prevent delivery failures and retries.
* **Conclusion:**
  - The webhook handler must return HTTP 200 immediately upon HMAC verification and queue event processing asynchronously.
  - De-duplication on `(wamid, status)` is essential to absorb duplicate retries across the 7-day delivery window.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Webhook delivery retry intervals on Meta's infrastructure are subject to platform load balancing. Recheck cadence: Bi-annual.

---

### 13. Idempotency & Duplicate-Send Guarantees (R-13)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages` and `https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks`
* **Section / Title:** "Messages API Reference: Request Parameters" and "Webhooks > Retries"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `STABLE`
* **Confidence:** `MEDIUM`
* **Official Findings:**
  1. **No Outbound Idempotency Key:** Meta's WhatsApp Cloud API `POST /{phone-number-id}/messages` endpoint provides **no documented guarantee** of idempotency and does not support an `Idempotency-Key` or `X-Idempotency-Key` HTTP header. This claim is inferred from the absence of any idempotency header or deduplication mechanism across the entire Messages API documentation.
  2. **Duplicate Send Risk:** If an outbound network request times out after being received by Meta but before the client receives the HTTP response, retrying the POST request results in sending duplicate messages to the parent and double billing.
  3. **Client Safeguard:** The application must maintain internal dispatch states in SQLite and avoid blind network retries when the transmission status of an in-flight message is uncertain (`UNKNOWN_NEEDS_REVIEW`).
* **Conclusion:**
  - Documented as **"no documented guarantee"**. Outbound send deduplication must be enforced entirely by the application's local state machine prior to calling the API.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Absence of native idempotency header verified across all Cloud API messaging documentation. Monitor quarterly changelogs for potential feature additions. Recheck cadence: Quarterly.

---

### 14. Webhook Signatures, Status Semantics, & Ordering (R-14)
* **Exact URL:** `https://developers.facebook.com/docs/graph-api/webhooks/getting-started` and `https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components`
* **Section / Title:** "Validating Webhook Payloads (`X-Hub-Signature-256`)" and "Statuses Object"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `HIGH`
* **Official Findings:**
  1. **Signature Verification:**
     - Webhook payloads include the `X-Hub-Signature-256` HTTP header containing `sha256=<HMAC_HEX>`.
     - HMAC SHA-256 must be computed over the **raw, unparsed request payload bytes** using the Meta `APP_SECRET`.
     - Comparison must use constant-time comparison (`hmac.compare_digest`).
  2. **Delivery Status Lifecycle:**
     - `sent`: Message has been dispatched from Meta servers to the telecommunications carrier / WhatsApp network.
     - `delivered`: Message has been received on the recipient's mobile device.
     - `read`: Message has been opened by the recipient.
     - `failed`: Message delivery failed; payload includes `errors` array with numeric code and description.
  3. **Platform Optimizations & Out-of-Order Delivery:**
     - If a user opens the chat while the message arrives, Meta emits `read` without a preceding `delivered` notification.
     - Webhook notifications are delivered over distributed systems without FIFO arrival guarantees. Events may arrive out of order or be duplicated during retry delivery.
     - Applications must use the payload `timestamp` to sequence events.
* **Conclusion:**
  - Webhook processor verifies raw HMAC signatures and sequences events by timestamp.
  - *Architectural Note:* Idempotent deduplication on `(wamid, status)` and treating `read` as superseding `delivered` are application design choices documented in `docs/architecture_decisions.md`.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Webhook delivery sequencing and payload format extensions evolve across Graph API versions. Recheck cadence: Quarterly.

---

### 15. Media Upload Limits, Types, & Expiration (R-15)
* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media`
* **Section / Title:** "Media API Reference: Upload, Retrieve, and Delete"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `STABLE`
* **Confidence:** `HIGH`
* **Official Findings:**
  1. **Supported Media Types & Max File Sizes:**
     - `image`: JPEG, PNG, WEBP; maximum **5 MB**.
     - `audio`: AAC, AMR, MP3, MP4 audio, OGG Opus (mono); maximum **16 MB**.
     - `document`: PDF, plain text, DOC, DOCX, XLS, XLSX, PPT, PPTX; maximum **100 MB**.
     - `video`: MP4, 3GPP; maximum **16 MB**.
  2. **Media ID Lifetime:**
     - Media files uploaded via `POST /{phone-number-id}/media` receive a `media_id` which expires after **30 days**.
  3. **Temporary Download URL Lifetime:**
     - Media URLs retrieved via `GET /{media-id}` expire after **5 minutes** and must be fetched using a valid Bearer token.
* **Conclusion:**
  - Scorecard PNGs (<1MB) and PTM PDF slips (<2MB) comfortably comply with the 5MB image and 100MB document size limits.
  - Media IDs generated during batch dispatch can be reused within 30 days if re-sending is necessary.
* **Unresolved Uncertainty & Recheck Cadence:**
  - Storage retention periods and temporary URL expiration times are stable under current Media API specification. Recheck cadence: Annual.

---

### 16. Guardian Verification & OTP Delivery Channels in India (UNVERIFIED — DEFERRED to pre-deployment, see checklist) (R-16)
* **Exact URL:** `https://trai.gov.in/sites/default/files/RegulationUcc19072018.pdf` (TRAI TCCCPR 2018) and `https://developers.facebook.com/docs/whatsapp/business-management-api/authentication-templates`
* **Section / Title:** "Telecom Commercial Communications Customer Preference Regulations, 2018 (DLT Framework)" and "WhatsApp Authentication Templates (OTP Delivery)"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `N/A`
* **Official Findings:**
  1. **WhatsApp Authentication Templates:**
     - Supported natively via Meta Cloud API with preset fixed wording: `<VERIFICATION_CODE> is your verification code.`
     - Configurable code expiration and interactive `copy_code` button.
     - Operates within WhatsApp Business Platform without TRAI carrier DLT scrubbing.
  2. **Indian Carrier SMS via TRAI DLT (TCCCPR 2018):**
     - Under TRAI regulations, automated SMS in India requires:
       - Principal Entity (PE) registration and unique 19-digit PE ID.
       - Registered 6-character alphanumeric Header (Sender ID), e.g. `SCHOOLDISPATCH`.
       - Pre-registered Content Template with unique Template ID and explicit `{#var#}` variable placeholders.
       - PE-TM Binding (linking Principal Entity to the Telecom Marketer gateway).
     - Real-time scrubbing blocks any SMS payload lacking matching PE ID, Template ID, or differing in structure.
* **Conclusion:**
  - `OWNER-CONFIRM` in D-11: WhatsApp authentication template is the proposed primary OTP channel. Carrier SMS fallback verification is deferred to pre-deployment checklist.
* **Unresolved Uncertainty & Recheck Cadence:**
  - **UNVERIFIED — DEFERRED to pre-deployment (see checklist):** Institutional TRAI DLT registration and template scrubbing verification deferred to `docs/PRE_DEPLOYMENT_CHECKLIST.md` (Item C-04). Recheck cadence: Pre-deployment.

---

### 17. India Digital Personal Data Protection (DPDP) Act, 2023 & DPDP Rules (UNVERIFIED — DEFERRED to pre-deployment, see checklist) (R-17)
* **Exact URL:** `https://www.meity.gov.in/content/digital-personal-data-protection-act-2023` (DPDP Act No. 22 of 2023 and DPDP Rules Gazette Notifications)
* **Section / Title:** "Digital Personal Data Protection Act, 2023, Section 9 (Processing of personal data of children)" and "DPDP Rules, 2025 (Commencement and Phased Implementation)"
* **Retrieval Date:** 2026-10-20
* **Volatility:** `VOLATILE`
* **Confidence:** `N/A`
* **Official Findings:**
  1. **DPDP Act, 2023 Section 9 Provisions:**
     - **Section 9(1):** A Data Fiduciary must obtain **verifiable parental consent** before processing personal data of any child (individual under 18 years of age per Section 2(f)).
     - **Section 9(2):** Prohibition against undertaking any processing of personal data that is likely to cause detrimental effect on the physical or mental well-being of a child.
     - **Section 9(3):** Strict statutory prohibition against tracking, behavioural monitoring, or targeted advertising directed at children.
  2. **DPDP Rules Notification & Commencement Status:**
     - DPDP Rules were gazetted in November 2025 with phased implementation timeline:
       - Immediate commencement (November 2025): Administrative definitions and Data Protection Board of India provisions.
       - 1-Year commencement (November 2026): Rule 4 (Consent Managers).
       - 18-Months commencement (May 2027): Rules 3, 5–16, 22, 23 governing Data Fiduciary operational duties (notice requirements, children's data safeguards, data breach reporting).
  3. **Handling in `omr_dispatch_engine`:**
     - The engine processes test scores, academic performance, and guardian contact details of minors (<18 years old).
     - Formal legal review is deferred to pre-deployment (tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md`, Item C-01).
     - During development, testing uses synthetic data exclusively.
     - Engineering safeguards remain active in development: strict data minimization, console/log masking (Rule 10), quarantine of unverified contacts, and live dispatch disabled (`LIVE_DISPATCH_ENABLED=false`).
     - The engine does not make any legal claims of compliance.
* **Conclusion:**
  - Engineering safeguards are implemented in code; formal legal sign-off is deferred to the pre-deployment checklist.
  - Live dispatch to real parents is disabled (`LIVE_DISPATCH_ENABLED=false` and `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=false`).
* **Unresolved Uncertainty & Recheck Cadence:**
  - **UNVERIFIED — DEFERRED to pre-deployment (see checklist):** Formal legal counsel review and sign-off on consent capture, privacy notice, and retention schedules are tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md` (Items C-01, C-02, C-03). Recheck cadence: Pre-deployment.
