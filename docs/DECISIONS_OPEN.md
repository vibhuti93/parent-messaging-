# Open Architectural & Business Decisions (DECISIONS_OPEN.md)

This document tracks items tagged `OWNER-CONFIRM`, requirement ambiguities, and deferred pre-deployment checklists per Part C Rule 3. No unapproved business-rule changes are permitted.

---

# Part 1: Owner Decisions (items 1–4 and 6–8 DECIDED on 2026-10-20; item 5 remains OPEN)

## 1. D-04: Bottom-Quarter PTM Rule for All-Green Batches (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  D-04 states: `PTM slip required iff ABSENT, or RED, or rank > floor(0.75 * present_count). OWNER-CONFIRM: bottom-quarter rule applies even when a whole batch is GREEN.`  
  In a high-performing batch where every student achieves > 60% net score (GREEN status), does the bottom quartile still receive a mandatory PTM summons?
* **Minimum Safe Resolution (Current Proposal):**  
  Apply the mathematical rule `rank > floor(0.75 * present_count)` strictly to all present students, ensuring deterministic behavior identical to the golden contract. PTM slips are generated for the bottom quartile regardless of status band unless explicitly disabled in batch policy.
* **Status:** DECIDED

**DECISION (operator):** Accept the current proposal. The bottom-quarter rule applies even if the whole batch is GREEN.
**Reason:** Simplest deterministic rule; no effect on the golden fixtures, where every bottom-quarter student is already RED.
**Date:** 2026-10-20
**Status:** DECIDED

---

## 2. D-11: Parent Confirmation (QR) Token TTL (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  D-11 proposes a default TTL of 72 hours for the single-use QR acknowledgment token. Parents receiving reports Sunday night at 20:30 IST would see the token expire Wednesday evening at 20:30 IST.
* **Minimum Safe Resolution (Current Proposal):**  
  Implement token TTL as an environment configuration parameter `QR_TOKEN_TTL_HOURS`, defaulting to 72 hours, with hard minimum of 12 hours and hard maximum of 168 hours (7 days).
* **Status:** DECIDED

**DECISION (operator):** Accept the current proposal: `QR_TOKEN_TTL_HOURS` defaults to 72, minimum 12, maximum 168. QR confirmation stays disabled by default (D-11).
**Reason:** Covers a weekend PTM cycle and stays configurable.
**Date:** 2026-10-20
**Status:** DECIDED

---

## 3. D-11: Guardian OTP Delivery Channel (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  D-11 requires OTP challenge to the already verified guardian number, with channel tagged `OWNER-CONFIRM (WhatsApp authentication template vs SMS; deferred to pre-deployment checklist)`.
* **Minimum Safe Resolution (Current Proposal):**  
  Primary OTP delivery channel: WhatsApp Authentication Template (`category: "authentication"`, `otp_type: "copy_code"`). Carrier SMS adapter is treated as an optional secondary plugin that remains dormant unless explicit `TRAI_DLT_PE_ID` and `TRAI_DLT_TEMPLATE_ID` credentials are provided. Carrier registration verification is deferred to pre-deployment.
* **Status:** DECIDED

**DECISION (operator):** Accept the current proposal. WhatsApp authentication template is the primary OTP channel; the SMS adapter stays dormant.
**Reason:** Avoids SMS regulatory setup during development.
**Date:** 2026-10-20
**Status:** DECIDED

---

## 4. D-12: Disclosure of Topper Score to Parents (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  D-12 states: `Own child's report + class average + topper score + rank "X out of N present". No other student's response-level data. OWNER-CONFIRM: topper score may be shown.`  
  Some educational institutions prefer displaying only class average to avoid excessive peer comparison.
* **Minimum Safe Resolution (Current Proposal):**  
  Include topper score as documented in golden fixtures (`expected_reports.json`), configurable via batch report template flag `show_topper_score` (defaulting to true for golden consistency).
* **Status:** DECIDED

**DECISION (operator):** Accept the current proposal. Show the class topper score on the parent report, controlled by the `show_topper_score` flag (default true).
**Reason:** Matches D-12 and the golden fixtures; the flag allows turning it off per batch.
**Date:** 2026-10-20
**Status:** DECIDED

---

## 5. D-09 / Architecture: Pinned Meta Graph API Version Upgrade (STALE v21.0) (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  The engine currently pins Meta Graph API `v21.0` via configuration (`WHATSAPP_CLOUD_API_VERSION=v21.0`). Official source verification on 2026-10-20 shows:
  - Graph API `v21.0` was released on 2024-10-02.
  - The 2-year base guarantee expired on 2026-10-02 (18 days ago).
  - On the official Meta Graph API changelog, `v21.0` availability is stated as ending on **January 21, 2027** (~93 days from 2026-10-20).
  - Calling an expired version causes Meta to automatically default requests to the next oldest available version, creating breaking change risks.
  - The official WhatsApp Cloud API documentation now references `v26.0` in its primary examples.
  - S9 contract fixtures must record the exact version used.
* **Candidate Versions from Official Documentation:**
  1. **`v21.0` (Current Pin):** Status: `STALE`. Retains current development baseline. Sunsets 2027-01-21 (~3 months remaining). Low immediate change, but requires forced migration shortly after deployment.
  2. **`v24.0`:** Released 2025-10-08; available until 2028-02-18 (~16 months remaining). Intermediate stable baseline.
  3. **`v25.0`:** Released 2026-02-18; available until 2028-07-29 (~21 months remaining). Stable and widely deployed.
  4. **`v26.0` (Recommended):** Released 2026-07-29; latest version referenced across current WhatsApp Cloud API documentation. Active for full 2+ year support lifecycle (until mid-2028).
* **Effect of Unpinning vs. Pinning:**
  - **Pinning (Recommended):** Keeps contracts predictable, ensures reproducible unit and contract test mocks, and shields the engine from unexpected breaking changes when Meta updates platform defaults. The version is configuration-driven (`WHATSAPP_CLOUD_API_VERSION`).
  - **Unpinning:** Floating versions or omitting the version in request URLs causes Meta to fall back to the oldest active version permitted for the app, creating silent failures when legacy versions sunset.
* **Current Research Status:** `v21.0` is past its two-year base guarantee (which expired October 2, 2026). Per the official Meta Graph API changelog table, `v21.0` remains usable until its stated end date of **`January 21, 2027`** (~93 days remaining). Any deployment after January 21, 2027 would break because retired versions fall back to the next oldest available version, risking breaking schema changes. The latest version on the changelog is `v26.0` (released July 29, 2026).
* **Status:** Pending Owner Confirmation before Stage S9 provider implementation. **Decision Timing:** The choice of API version must be confirmed by the owner before Stage S9 execution begins, and S9 contract test fixtures (`tests/fixtures/provider_contract/**`) must record the exact API version used.

**DECISION (operator):** NOT YET DECIDED. Deliberately left open until before S9. Before deciding, re-check the changelog for any version newer than v26.0.
**Status:** OPEN

---

## 6. ADR-0003: Institutional Tenancy Scope (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  The engine is initially commissioned for a single school batch. Should data models, schemas, and idempotency keys include an `org_id` / institutional tenant identifier from Day 1, or remain strictly single-tenant?
* **Minimum Safe Resolution (Current Proposal):**  
  Include `org_id: str` (defaulting to `"DEFAULT_INSTITUTION"` or school code) across all database models, dispatch tables, and composite idempotency keys from inception. Adding an institutional tenant identifier later requires migrating every table, foreign key, and unique constraint across the database.
* **Status:** DECIDED

**DECISION (operator):** Single school for now, but include `org_id` from the start with one fixed default value (`"DEFAULT_INSTITUTION"`) in all models, dispatch tables and idempotency keys. No multi-tenant logic is built now.
**Reason:** Costs almost nothing now; avoids touching every table and key later.
**Date:** 2026-10-20
**Status:** DECIDED

> **AMENDMENT NOTE (2026-10-21, Stage S0-R5):** The single-school limitation in this decision is superseded by Operator Decision 1 below. The engine serves multiple schools from the start as a hosted multi-tenant service (ADR-0017). ADR-0003 status updated to `ACCEPTED (modified)`.

---

## 7. ADR-0007: Database Encryption at Rest (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  Sensitive student scores, PTM consultation requests, and masked contact records are stored in local SQLite WAL databases. Does development require application-level cryptographic database encryption (e.g. SQLCipher), or is host-level volume encryption sufficient?
* **Minimum Safe Resolution (Current Proposal):**  
  Rely on host operating system disk encryption (BitLocker on Windows, LUKS on Linux) for local development and offline test suites. Application-level database encryption (SQLCipher) is formally deferred to the pre-deployment compliance checklist (`docs/PRE_DEPLOYMENT_CHECKLIST.md`, Item P-04).
* **Status:** DECIDED

**DECISION (operator):** Accept the current proposal. Disk-level encryption for development (synthetic data only); application-level or field-level encryption is deferred to the pre-deployment checklist.
**Reason:** No real data exists yet, and the repository interface (ADR-0007) lets encryption be added later without rewriting callers.
**Date:** 2026-10-20
**Status:** DECIDED

---

## 8. ADR-0010: Script Digit Policy in Hindi Parent Communications (`OWNER-CONFIRM`)
* **Conflicting / Ambiguous Consideration:**  
  Parent-facing messages, scorecards, and consultation slips are rendered in conversational Bolchal Hindi. Should numeric representations (scores, percentages, dates, ranks) display in standard Latin digits (`0, 1, 2, ... 9`) or Devanagari numerals (`०, १, २, ... ९`)?
* **Minimum Safe Resolution (Current Proposal):**  
  Use **Latin digits (`0-9`)** across all parent-facing Hindi text, scorecards, and PTM consultation slips (e.g. `"कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)"`). In modern Indian education, Latin numerals are universally recognized across all state and central boards, whereas Devanagari numerals cause misinterpretation among parents of varying literacy levels.
* **Status:** DECIDED

**DECISION (operator):** Latin digits (0-9) in all parent-facing Hindi text, scorecards and PTM slips.
**Reason:** Matches the golden strings already in the pack and common WhatsApp usage.
**Date:** 2026-10-20
**Status:** DECIDED

---

# Part 1B: Operator Decisions (Given on 2026-10-21, Stage S0-R5)

### Decision 1: Multi-School Hosted Service from Inception
* **Mandate:** The engine serves multiple schools from the start as a hosted multi-tenant service.
* **Effect on ADR-0003:** Supersedes the single-school limitation of ADR-0003. ADR-0003 retains its text and is marked `ACCEPTED (modified)` with a pointer to ADR-0017.
* **Date:** 2026-10-21
* **Status:** DECIDED (Operator Mandate)

### Decision 2: Dedicated WhatsApp Business Number per School
* **Mandate:** Each school uses its own dedicated WhatsApp Business Phone Number. There is no shared number across schools.
* **Effect:** Formalized in ADR-0019 (`SenderIdentity`). Each org has its own phone-number ID, WABA ID, verified display name, quality rating, and secret references.
* **Date:** 2026-10-21
* **Status:** DECIDED (Operator Mandate)

### Decision 3: v1 Assessment Source Kinds
* **Mandate:** Version 1 supports two source assessment kinds: `OMR_MCQ` and `MARKS_ENTRY_TOTALS` (one total score per student, per assessment, per subject).
* **Effect:** Formalized in ADR-0016 (`Assessment` model and capability flags).
* **Date:** 2026-10-21
* **Status:** DECIDED (Operator Mandate)

### Decision 4: Approved Golden Message for `MARKS_ENTRY_TOTALS`
* **Mandate:** Approved golden parent message for marks entry totals (placeholders: `child_name`, `class_section`, `test_name`, `subject`, `max_marks`, `marks`, `percentage`, `present_count`, `rank`, `class_average`, `topper_marks`):
  > "प्रिय अभिभावक, आरव (कक्षा 8-B) के यूनिट टेस्ट 1 (अंग्रेज़ी) में 50 में से 30 नंबर आए हैं (60.0%)। 18 उपस्थित बच्चों में आरव का रैंक 7 है। क्लास का औसत स्कोर 32.4 है। क्लास में सबसे ज़्यादा नंबर 47 हैं।"
* **Invariants:** Gender-neutral Bolchal Hindi wording; Latin digits (`0-9`); observable facts only.
* **Date:** 2026-10-21
* **Status:** DECIDED (Operator Mandate, APPROVED)

### Decision 5: Message Child Identity Invariants & Roll Number Policy
* **Mandate:** Every parent-facing text message, for both OMR and marks entry, names the child (`child_display_name`) and class/section (`class_section`) after a fixed leading greeting (`"प्रिय अभिभावक, "`), and never as the first token of the template body.
* **Roll Number Policy:** The student roll number is omitted from text copy by default (per-org setting `include_roll_in_text`, default `false`). It remains on the scorecard PNG image and printable A4 PTM slip PDF.
* **Date:** 2026-10-21
* **Status:** DECIDED (Operator Mandate)

---

# Part 1C: Stage S0-R5 Proposals Awaiting Operator Approval (`OWNER-CONFIRM`)

## (a) OMR Present Message Wording (`OWNER-CONFIRM`)
* **Proposal:** Retain already-frozen OMR golden score-line string (`"कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)"`) and wrap it with the mandatory fixed greeting, child display name, and class/section:
  `"प्रिय अभिभावक, {child_name} ({class_section}) के {test_name} में कुल नंबर: {max_marks} में से {net_marks} नंबर आए हैं ({net_percentage})। {present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। क्लास का औसत स्कोर {class_average} है। क्लास में सबसे ज़्यादा नंबर {topper_marks} हैं। सही जवाबों से मिले {gross_marks} नंबर, गलत जवाबों से {bleed_marks} नंबर कट गए।"`
  Fallback shorter variant:
  `"प्रिय अभिभावक, {child_name} ({class_section}) के {test_name} में कुल नंबर: {max_marks} में से {net_marks} नंबर आए हैं ({net_percentage})। {present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। क्लास का औसत स्कोर {class_average} है।"`
* **Status:** DECIDED (see S1-BLOCK-02, 2026-10-21, operator)

## (b) Absent Message Wordings & Absent Scorecard Card (`OWNER-CONFIRM`)
* **Proposal:** Three factual absence wordings carrying zero score, rank, or performance framing:
  1. `OMR_ABSENT`: `"प्रिय अभिभावक, {child_name} ({class_section}) {test_name} के टेस्ट में अनुपस्थित रहे। कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।"`
  2. `MARKS_ENTRY_ABSENT`: `"प्रिय अभिभावक, {child_name} ({class_section}) {test_name} ({subject}) के टेस्ट में अनुपस्थित रहे। कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।"`
  3. Absent Scorecard Card: Neutral grey `#5F6368` banner with white text `"टेस्ट में अनुपस्थित"`, omitting proof strip, scores, rank, and diagnostics.
* **Status:** DECIDED (see S1-BLOCK-03, 2026-10-21, operator)

## (c) Rank Scope (`OWNER-CONFIRM`)
* **Proposal:** For marks entry, compute standard competition rank per subject within the assessment among `PRESENT` students. An overall assessment rank is computed only when an assessment has multiple subjects and every present student has scores across all subjects.
* **Status:** DECIDED (see S1-BLOCK-04, 2026-10-21, operator)

## (d) Message Scope per Assessment (`OWNER-CONFIRM`)
* **Proposal:** Dispatch one message per subject for routine assessments, with a configurable option for a weekly digest consolidating multiple subject assessments into a single summary report.
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (e) Band Thresholds for Weekly Tests (`OWNER-CONFIRM`)
* **Proposal:** Apply standard D-01 percentage thresholds across all assessment kinds, including weekly tests (<30.0% RED, 30.0%–60.0% YELLOW, >60.0% GREEN).
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (f) PTM Slips Restricted to PTM-Linked Assessments (`OWNER-CONFIRM`)
* **Proposal:** Generate printable A4 PTM consultation slips only for assessments carrying the `PTM_LINKED` purpose flag. Routine weekly tests and unit tests do not generate PTM slips unless explicitly flagged.
* **Status:** DECIDED (see S1-BLOCK-01 Option 1, 2026-10-21, operator; PTM eligibility under D-04 applies to every assessment type with `is_ptm_linked` condition removed per ADR-0016 Section 4)

## (g) Class Average Definition for Marks Entry (`OWNER-CONFIRM`)
* **Proposal:** Arithmetic mean of net marks among all `PRESENT` students in the assessment cohort: evaluated at full precision (`Fraction`), rendered to 1 decimal place with `ROUND_HALF_UP` on display (e.g. `32.4`). Null if zero present.
* **Status:** DECIDED (see S1-BLOCK-05, 2026-10-21, operator)

## (h) Multi-Tenant Database Architecture (`OWNER-CONFIRM`)
* **Proposal:** Adopt Option 1 of ADR-0017: Shared database and schema with indexed `org_id` on every table, mandatory `org_id` enforcement in repositories, and PostgreSQL Row-Level Security (RLS) as defence in depth.
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (i) Target Database Engine (`OWNER-CONFIRM`)
* **Proposal:** PostgreSQL is the production target database engine; SQLite WAL is used for zero-dependency local unit testing; a dual-engine contract test suite runs against both from S8 on (ADR-0007 amendment, ADR-0017).
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (j) Sender Identities per Organization (`OWNER-CONFIRM`)
* **Proposal:** Schema and database model support multiple senders per organization (`SenderIdentity`); Version 1 strictly enables one active sender per organization (ADR-0019).
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (k) Meta Billing Responsibility (`OWNER-CONFIRM`)
* **Proposal:** Each school attaches its own institutional credit card or payment method to its Meta Business Manager account for direct Meta per-message billing (R-05). Platform invoices only for hosted software services. Deferred to `docs/PRE_DEPLOYMENT_CHECKLIST.md` (Item P-08).
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (l) `include_roll_in_text` Default Setting (`OWNER-CONFIRM`)
* **Proposal:** Per-organization configuration parameter `include_roll_in_text` defaults to `false`. Roll numbers appear on scorecard PNG images and PTM slips, but are omitted from WhatsApp text bodies unless explicitly enabled by the school.
* **Status:** DECIDED (see S1-BLOCK-06, 2026-10-21, operator)

## (m) Proposed Wording to Widen Product Boundary in `PROJECT_SPEC.md` (`OWNER-CONFIRM`)
* **Proposal (Wording draft only; PROJECT_SPEC.md is NOT modified):**
  > "The system is a hosted multi-tenant notification and diagnostics service serving multiple educational institutions, each via its own dedicated WhatsApp Business number. It imports/validates student rosters, answer keys, decoded OMR responses, source scans, and manual teacher marks entry totals; computes deterministic diagnostics; produces personalized conversational Hindi text naming the child and class, PNG scorecards, A4 PTM PDFs, and audio voice notes; quarantines unsafe contacts; dispatches only what verified WhatsApp rules and recorded consent permit; tracks status; and offers optional QR confirmation. It does not perform bubble detection or scan alignment; decoded answers come from an external OMR service whose contract is defined in S2. User authentication, login screens, billing gateways, and web frontends are out of scope for v1."
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (n) Supported Languages Beyond Hindi (`OWNER-CONFIRM`)
* **Proposal:** Defer additional languages (e.g. English, Marathi, Gujarati) to post-v1; v1 operates strictly in conversational Bolchal Hindi per D-06 and ADR-0010.
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (o) Longitudinal & Week-over-Week Performance Trends (`OWNER-CONFIRM`)
* **Proposal:** Defer week-over-week performance tracking, multi-test trend lines, and longitudinal analytics to post-v1; each assessment in v1 is evaluated on its own cohort context.
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (p) Audio Voice Notes for Marks Entry Totals Reports (`OWNER-CONFIRM`)
* **Proposal:** Audio voice notes in v1 are generated exclusively for `OMR_MCQ` diagnostic assessments where detailed question-level and mark bleed breakdown exists. `MARKS_ENTRY_TOTALS` assessments do not generate audio notes in v1.
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (q) Cohort Scope Definition (`OWNER-CONFIRM`)
* **Proposal:** Rank, class average, and topper score are computed over the assessment's participant set (cohort), which the school designates as a single section (e.g. "8-B") or a full grade (e.g. "Grade 8"). The cohort label is presented to parents as "क्लास" (e.g. "कक्षा 8-B").
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (r) Audio Personalization & Name Pronunciation (`OWNER-CONFIRM`)
* **Proposal:** In v1, audio voice notes never speak the child's name or class (avoiding synthetic pronunciation errors); recorded audio uses gender-neutral "आपके बच्चे". Audio is an optional extra sent only inside the open 24h window (R-02, R-07, R-08), sent as a quoted reply to the named text message for sibling disambiguation. School-recorded name clips are deferred to post-v1.
* **Status:** PROPOSED (`OWNER-CONFIRM`)

## (s) 24-Hour Customer Service Window Initiation for Audio Notes (`OWNER-CONFIRM`)
* **Question:** How is the parent's 24-hour service window opened before sending non-template voice notes? (e.g. a quick-reply button on the first template, such as 'ऑडियो सुनें' / 'Listen to Audio').
* **Status:** PROPOSED (`OWNER-CONFIRM`, `UNVERIFIED`)
* **Design Note:** Per Stage S0-R7 instructions, no solution is designed at this stage. Formally recorded as an open question referenced in `docs/prompt_pack/S9.md` and `docs/adr/ADR-0019-per-school-sender-identity-and-routing.md`.

---

# Part 1D: S1-BLOCKING Decisions (`OWNER-CONFIRM`)

The following OWNER-CONFIRM items directly block the finalization and freeze of the signed Stage 1 fixture manifest hash (`fixtures/golden/manifest.json`). Tests never compute expectations dynamically (Part C Rule 6); every expected report attribute in `expected_reports.json` and `expected_marks_reports.json` is a literal derived from approved decisions.

### S1-BLOCK-01: D-04 / ADR-0016 Scope of `requires_ptm_slip` on Marks Entry Reports (`OWNER-CONFIRM`)
* **What it changes:** Whether `expected_marks_reports.json` records `requires_ptm_slip = true` for students triggering D-04 criteria (ABSENT student ME_06, RED students ME_04 and ME_05, and bottom-quartile students), or whether PTM slips are generated strictly when an assessment carries the `PTM_LINKED` purpose flag per ADR-0016 Section 4.
* **Options:**
  - *Option 1 (Literal D-04 Invariant):* Apply D-04 universally. Any student who is ABSENT, RED, or bottom-quarter receives `requires_ptm_slip = true` regardless of assessment kind or purpose.
  - *Option 2 (ADR-0016 Purpose-Gated):* Restrict PTM slip generation to assessments flagged `PTM_LINKED`. Routine single-subject marks entry assessments (e.g. `marks_entry_50.json`) set `requires_ptm_slip = false` for all students.
* **Consequence for S1 Hash:** Inverts `requires_ptm_slip` booleans in `expected_marks_reports.json` across 3 out of 6 students in the golden marks-entry fixture, altering the signed fixture manifest SHA-256 hash.
* **Status:** DECIDED (Option 1, 2026-10-21, operator)

### S1-BLOCK-02: OMR Present Parent Message Body String (Item (a) / `MSG-OMR-PRESENT`) (`OWNER-CONFIRM`)
* **What it changes:** The literal rendered message text in `expected_reports.json` for PRESENT OMR students (STU_01 through STU_16).
* **Options:**
  - *Option 1 (Full Diagnostics):* Wrap the frozen score-line string with greeting, child name, class/section, present count, rank, class average, topper marks, gross marks, and bleed marks.
  - *Option 2 (Concise Variant):* Wrap frozen score line with greeting, child name, class/section, rank, and class average (omitting mark-bleed breakdown).
* **Consequence for S1 Hash:** Alters expected message strings across 16 student report objects in `expected_reports.json`, modifying the fixture SHA-256 hash.
* **Status:** DECIDED (Option 1, 2026-10-21, operator)

### S1-BLOCK-03: Absent Message Template Copy (Item (b) / `MSG-ABSENT`) (`OWNER-CONFIRM`)
* **What it changes:** Rendered notification strings for absent students (STU_17–STU_20 in OMR and ME_06 in marks entry).
* **Options:**
  - *Option 1 (Full Context):* Factual notice including assessment name, cohort maximum marks, and total students attending.
  - *Option 2 (Minimal Notice):* Single-sentence factual notice naming the child, class/section, and assessment only.
* **Consequence for S1 Hash:** Directly alters `message_text` for absent student objects in `expected_reports.json` and `expected_marks_reports.json`.
* **Status:** DECIDED (Option 1, 2026-10-21, operator)

### S1-BLOCK-04: Marks Entry Competition Rank Scope (Item (c) / `RANK-SCOPE-ME`) (`OWNER-CONFIRM`)
* **What it changes:** The `rank` attribute in `expected_marks_reports.json`.
* **Options:**
  - *Option 1 (Subject Cohort Rank):* Rank evaluated within the single-subject participant cohort (Aarav and Rohan tied at rank 2; topper Priya at rank 1).
  - *Option 2 (Composite Assessment Rank):* Rank computed only across multi-subject totals, omitting rank from single-subject reports.
* **Consequence for S1 Hash:** Alters numeric `rank` field across student records in `expected_marks_reports.json`.
* **Status:** DECIDED (Option 1, 2026-10-21, operator)

### S1-BLOCK-05: Class Average Numeric Quantization for Marks Entry (Item (g) / `CLASS-AVG-ME`) (`OWNER-CONFIRM`)
* **What it changes:** String/numeric representation of `class_average` in `expected_marks_reports.json`.
* **Options:**
  - *Option 1:* 1 decimal place with `ROUND_HALF_UP` display quantization (`"21.9"` for batch sum 109.5 over 5 present).
  - *Option 2:* Exact rational / 2 decimal places (`"21.90"`).
* **Consequence for S1 Hash:** Changes JSON representation of batch metrics in `expected_marks_reports.json`.
* **Status:** DECIDED (Option 1, 2026-10-21, operator)

### S1-BLOCK-06: Student Roll Number Policy in Message Body (Item (l) / `ROLL-IN-TEXT`) (`OWNER-CONFIRM`)
* **What it changes:** Whether rendered parent text in `expected_reports.json` and `expected_marks_reports.json` includes `"(रोल नं. X)"`.
* **Options:**
  - *Option 1:* Default `include_roll_in_text=false` (omitted from WhatsApp text, present on scorecard PNG and PDF).
  - *Option 2:* `include_roll_in_text=true` (inserted into text next to class/section).
* **Consequence for S1 Hash:** Adds or removes roll tokens from message text in golden fixture expectations.
* **Status:** DECIDED (Option 1, 2026-10-21, operator)

---

# Part 2: Deferred to Pre-Deployment (see docs/PRE_DEPLOYMENT_CHECKLIST.md)

## 9. D-13: Retention Policy & Statutory Compliance (`DEFERRED`)
* **Background:**  
  D-13 establishes the development default: student scans and reports for the active academic year; message/audit logs for 90 days (masked). Deletion on verified request.
* **Status:**  
  **DEFERRED TO PRE-DEPLOYMENT.** Tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md` (Items C-01 and C-03). Development and testing continue using synthetic data only. Prior to production deployment or handling real parent/student data, qualified legal counsel must confirm retention schedules and statutory consent mechanisms under India's DPDP Act, 2023.

---

# Part 3: Contradiction Check Result (Gate 0 / S0-R4)

* **Status:** **No contradictions found.**
* **Methodology:** Systematic cross-comparison of `PROJECT_SPEC.md` clauses D-01 through D-14, `AGENTS.md` (Rules 1–14), `docs/prompt_pack/` (`S0.md`–`S13.md`), and Foundation ADRs (ADR-0001 through ADR-0015).
* **Verification Details:**
  - Status bands (D-01), easy question thresholds (D-02), subject diagnosis priority ordering (D-03), and rank arithmetic (D-04, D-05) align exactly with ADR-0002 (integer marks, Fraction ratios, cross-multiplication, Decimal ROUND_HALF_UP).
  - Hindi wording rules and banned terms (D-06) align with Rule 14, S4, ADR-0010, and `scripts/guardrails.py`.
  - Palette colors and contrast (D-07) align with S5/S6 renderers and ADR-0011.
  - Audio duration (<45s) and token-stitch hierarchy (D-08) align with S7 audio engine and ADR-0011.
  - Scheduling (D-10) and live messaging default off (D-09) align with Rule 8, S0, S8, S9, ADR-0005 (Asia/Kolkata presentation, UTC storage), and ADR-0009.
  - Scale limit (D-14: <=200 students/batch) aligns with SQLite WAL concurrency limits in ADR-0007.
