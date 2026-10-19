# Official Source Verification & Regulatory Research

**Network Access Status:** Active (verified via web search queries during session on 2026-10-20)  
**Retrieval Date:** 2026-10-20  
**Governing Rule:** Per Part C Rule 12, no external API, pricing, template, or legal fact may be asserted in the engine unless recorded here with exact URL, section, retrieval date, conclusion, and unresolved uncertainty. Any claim without official primary documentation must be marked `UNVERIFIED` and dependent features must remain disabled in production code (`LIVE_DISPATCH_ENABLED=false`).

---

## 1. Meta Graph API & WhatsApp Cloud API: Version Lifecycle & Pinning

* **Exact URL:** `https://developers.facebook.com/docs/graph-api/changelog/version21.0` and `https://developers.facebook.com/docs/graph-api/guides/versioning`
* **Section / Title:** "Graph API v21.0 Changelog" and "Graph API Versioning & Lifecycle Policy"
* **Retrieval Date:** 2026-10-20
* **Official Findings:**
  1. Graph API `v21.0` was officially released on **October 2, 2024**.
  2. Meta enforces a strict **2-year support guarantee** for each major Graph API version from its release date before sunset/deprecation.
  3. `v21.0` is active and within its 2-year guaranteed support lifecycle.
  4. API endpoints explicitly include the version in the URL path: `https://graph.facebook.com/{version}/{phone-number-id}/messages`.
  5. Floating versions are unsafe: unpinned endpoints fall back to older baselines or change behavior on global out-of-cycle updates.
* **Conclusion:**
  - Build pins **`v21.0`** via configuration (`WHATSAPP_CLOUD_API_VERSION=v21.0` in `.env.example`).
  - Hardcoded version strings in application source code (`src/` and `templates/`) are strictly prohibited and enforced by `scripts/guardrails.py`.
* **Unresolved Uncertainty:**
  - Deprecation date for `v21.0` must be monitored quarterly via Meta developer changelogs.

---

## 2. Customer-Service Window & Business-Initiated Messaging

* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages` and `https://developers.facebook.com/docs/whatsapp/pricing`
* **Section / Title:** "Customer Service Window" and "About Business-Initiated Conversations"
* **Retrieval Date:** 2026-10-20
* **Official Findings:**
  1. A **24-hour customer service window** opens *only* when a customer sends an inbound message to the business phone number.
  2. Inside this 24-hour window, the business may send free-form service messages (text, audio, images, documents).
  3. Outside the 24-hour window (which applies to outbound exam result notifications where parents have not messaged the school in the preceding 24 hours), free-form messages are rejected by Meta with error `131047 / Re-engagement message required`.
  4. Outbound initial notifications **MUST** use pre-approved Message Templates (Utility category for school reports).
* **Conclusion:**
  - Initial outbound dispatch of student scorecards must strictly use pre-approved **Utility Message Templates**.
  - Direct free-form text or audio cannot be pushed outbound on initial contact.
* **Unresolved Uncertainty:** None.

---

## 3. Account Prerequisites, Business Verification, and Opt-In

* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/overview/business-opt-in`
* **Section / Title:** "WhatsApp Business Opt-In Policy & Account Tiering"
* **Retrieval Date:** 2026-10-20
* **Official Findings:**
  1. **User Opt-In Requirement:** Businesses must receive explicit, unambiguous opt-in from the recipient before sending messages outside the 24-hour window.
  2. **Phone Number & Business Verification:** The deploying school/institution must have a verified Meta Business Manager account, an active payment method, and a registered WhatsApp Phone Number ID.
  3. **Tier Limits:** Unverified businesses are capped at 250 business-initiated conversations in a rolling 24-hour window. Verified businesses start at Tier 1 (1,000 conversations/24h) and scale to Tier 2 (10,000), Tier 3 (100,000), and Tier 4 (unlimited).
* **Conclusion:**
  - The engine must enforce that contact records have `consent = OPT_IN` and `guardian = VERIFIED`.
  - Absence of explicit opt-in defaults to quarantine (`CONSENT_UNKNOWN` / `REVOKED`), blocking dispatch.
* **Unresolved Uncertainty:**
  - `UNVERIFIED` at institutional level: Whether the deploying school has completed Meta Business Manager KYC verification and tiered messaging quota setup. Live dispatch remains disabled until confirmed by operator.

---

## 4. Media Supported in Templates (Image Headers vs Audio)

* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates/components`
* **Section / Title:** "Message Template Components: Header Media Types"
* **Retrieval Date:** 2026-10-20
* **Official Findings:**
  1. Supported template header formats:
     - `TEXT` (up to 60 characters, max 1 variable)
     - `IMAGE` (JPEG or PNG format)
     - `DOCUMENT` (PDF format)
     - `VIDEO` (MP4 format)
     - `LOCATION`
  2. **`AUDIO` IS NOT SUPPORTED AS A TEMPLATE HEADER TYPE.**
  3. Standalone audio messages (`"type": "audio"`) can only be sent as free-form service messages within an open 24-hour customer service window.
* **Conclusion:**
  - Scorecard PNG and PTM PDF can be attached via Template Header (`type: "image"` or `type: "document"`).
  - Voice notes **cannot** be delivered in the initial outbound template message.
  - Per D-09, audio dispatch on initial contact is disabled. Audio may only be delivered via an authenticated web link or deferred until a parent initiates an inbound conversation.
* **Unresolved Uncertainty:** None. Meta API explicitly excludes audio headers from message templates.

---

## 5. Audio Payload Specifications & Transcoding Rules

* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages#media-object`
* **Section / Title:** "Messages API: Audio Media Object"
* **Retrieval Date:** 2026-10-20
* **Official Findings:**
  1. Supported audio MIME types:
     - `audio/aac` (.aac, max 16MB)
     - `audio/mp4` (.m4a, max 16MB)
     - `audio/mpeg` (.mp3, max 16MB)
     - `audio/amr` (.amr, max 16MB)
     - `audio/ogg; codecs=opus` (.ogg, max 16MB, **OPUS codec only, mono**)
  2. Base `audio/ogg` containing Vorbis or non-Opus codecs is rejected or silent on mobile devices.
  3. Direct file renames (e.g. renaming `.wav` or `.mp3` to `.ogg` without FFmpeg transcoding) fail validation and are banned by `scripts/guardrails.py`.
* **Conclusion:**
  - Audio files must be transcoded via FFmpeg specifically to Ogg container with `libopus` audio codec at 48kHz, mono channel.
* **Unresolved Uncertainty:** None.

---

## 6. Template Parameter Constraints & Machine-Readable Spec

* **Exact URL:** `https://developers.facebook.com/docs/whatsapp/message-templates/guidelines`
* **Section / Title:** "Formatting Rules, Parameter Limitations, and Variable Placeholders"
* **Retrieval Date:** 2026-10-20
* **Official Findings:**
  1. **Body Text Length:** Maximum 1024 characters total (including static text and resolved variable strings).
  2. **Header Text Length:** Maximum 60 characters total.
  3. **Header Parameter Count:** Maximum 1 variable parameter in header; no newlines permitted.
  4. **Footer Text Length:** Maximum 60 characters; variables are **not** permitted in footers.
  5. **Variable Parameter Rules:**
     - Positional parameters must follow sequential numbering: `{{1}}`, `{{2}}`, etc.
     - Variables **must not** contain newline characters (`\n` or `\r`).
     - Variables **must not** have leading or trailing whitespace.
     - A template **cannot begin or end** with a standalone variable parameter (must have preceding/following text or punctuation).
     - Consecutive parameters (`{{1}}{{2}}` or `{{1}} {{2}}`) without intervening static words or punctuation are prohibited.
     - Parameter values cannot exceed 100 characters per variable in standard templates.
* **Conclusion:**
  - Recorded in `docs/research/template_constraints.json` as a machine-readable schema for S4 template rendering.
* **Unresolved Uncertainty:** None.

---

## 7. Webhook Signatures, Delivery Receipts, & Idempotency

* **Exact URL:** `https://developers.facebook.com/docs/graph-api/webhooks/getting-started` and `https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components`
* **Section / Title:** "Validating Webhook Payloads (`X-Hub-Signature-256`)" and "Statuses Object"
* **Retrieval Date:** 2026-10-20
* **Official Findings:**
  1. **Signature Verification:** Every webhook notification contains the `X-Hub-Signature-256` HTTP header containing `sha256=<HMAC_HEX>`.
     - HMAC SHA-256 must be computed over the **raw, unparsed request payload bytes** using the Meta `APP_SECRET`.
     - Comparison must use constant-time comparison (`hmac.compare_digest`).
  2. **Status Sequence:**
     - Valid statuses: `sent` -> `delivered` -> `read`, or `failed`.
     - *Optimization alert:* If a user opens a message directly from notification, Meta may emit `read` without a preceding `delivered` notification. The engine must treat `read` as implicitly satisfying delivery.
  3. **Retry & Acknowledgment:**
     - The webhook endpoint must return HTTP `200 OK` promptly (< 3 seconds).
     - If the endpoint times out or returns non-2xx, Meta retries delivery with exponential backoff over up to 36 hours.
  4. **Idempotency:**
     - Each webhook event has a unique message ID `wamid.HB...` and timestamp.
     - The dispatch store must de-duplicate webhook events on `(message_id, status)` to ensure idempotent state updates.
* **Conclusion:**
  - Webhook engine requires raw byte HMAC verification and idempotent status tracking.
* **Unresolved Uncertainty:** None.

---

## 8. Guardian Verification & OTP Delivery Channels in India

* **Exact URL:** `https://trai.gov.in` (TRAI TCCCPR 2018) and `https://developers.facebook.com/docs/whatsapp/business-management-api/authentication-templates`
* **Section / Title:** "Telecom Commercial Communications Customer Preference Regulations, 2018 (DLT Framework)" and "WhatsApp Authentication Templates (OTP Delivery)"
* **Retrieval Date:** 2026-10-20
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
  - `OWNER-CONFIRM` in D-11: WhatsApp authentication template is the proposed primary OTP channel. SMS fallback requires explicit TRAI DLT registration.
* **Unresolved Uncertainty:**
  - `UNVERIFIED` institutional readiness: Whether the school holds registered TRAI DLT PE ID and templates for SMS fallback.

---

## 9. India Digital Personal Data Protection (DPDP) Act, 2023 & DPDP Rules

* **Exact URL:** `https://www.meity.gov.in` (DPDP Act No. 22 of 2023 and DPDP Rules Gazette Notifications)
* **Section / Title:** "Digital Personal Data Protection Act, 2023, Section 9 (Processing of personal data of children)" and "DPDP Rules, 2025 (Commencement and Phased Implementation)"
* **Retrieval Date:** 2026-10-20
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
  3. **Impact on `omr_dispatch_engine`:**
     - The engine processes test scores, academic performance, and guardian contact details of minors (<18 years old).
     - **TREAT AS RELEASE-BLOCKING.**
     - The engine must not infer parental consent or guardian identity from spreadsheet data alone (Part C Rule 9).
     - The engine must NEVER claim legal compliance without documented institutional legal review.
* **Conclusion:**
  - All minor data must be minimized, masked in logs, and protected by unverified guardian quarantine.
  - Live dispatch to parents is blocked (`LIVE_DISPATCH_ENABLED=false`) pending formal institutional legal counsel review.
* **Unresolved Uncertainty:**
  - `UNVERIFIED` legal clearance: Specific institutional legal sign-off on consent mechanism under DPDP framework remains open in `docs/DECISIONS_OPEN.md`.
