"""
Splits the OMR Dispatch prompt pack into 16 atomic files in docs/prompt_pack/
with 100% verbatim text fidelity.
"""
from pathlib import Path

OUTPUT_DIR = Path("docs/prompt_pack")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PACK_FILES = {
    "00_global_invariants.md": """# Part C — Global Invariants (paste into `AGENTS.md` / `CLAUDE.md`)

You are building `omr_dispatch_engine` (Python 3.11+, Pydantic v2, `src/omr_dispatch/`). These rules apply to every stage.

**Process**
1. Read `AGENTS.md`, `PROJECT_SPEC.md`, `docs/STATE.md` before acting. Work on exactly one stage per session. Stop at the end of the stage and report; never start the next one.
2. Inspect the repo before editing. Never overwrite user work. Stay inside the stage's **Allowed files**.
3. If two requirements conflict, or a decision is missing, write it to `docs/DECISIONS_OPEN.md` with the conflicting clauses and the minimum safe resolution, then stop and ask. Never make an unapproved business-rule change.
4. Report only evidence: files changed, commands actually run, exit codes, actual test counts, skips with reasons. Do not write "passed", "verified", "compliant", "delivered", or "production-ready" without matching evidence.
5. Update `docs/STATE.md` at the end of each stage (status, evidence, open questions, fixture manifest hash).

**Testing**
6. Expected values are literals from the approved fixtures; tests never compute expectations with the code under test. Never weaken, skip, or delete a test, or edit frozen fixtures/hashes, to make a build pass.
7. Mock only external boundaries (network, clock). Render, audio, HTTP-integration and diagnostics tests use real local components. No test contacts a real messaging endpoint or a real parent.

**Safety and privacy**
8. Live messaging is disabled by default. Credentials only via environment; `.env.example` holds placeholders. Never commit secrets or real personal data.
9. Never infer consent, guardian identity, or sibling status from a spreadsheet value or surname. A non-empty phone number is not consent.
10. Never log full phone numbers, tokens, names, scores, QR tokens, or audio payloads; mask them.
11. Synthetic scans, signatures, audio, or tones are test-only and must never appear in production output or be presented as evidence. A signature or QR alone is not identity proof.
12. Do not assert any external API, pricing, template, or legal fact that is not recorded in `docs/research/official_source_verification.md`. Unverified → mark `UNVERIFIED` and keep the dependent feature disabled.
13. Fail closed: uncertain input → `REVIEW_REQUIRED` / block / defer, never a guess. An uncertain send outcome is `UNKNOWN_NEEDS_REVIEW`, never a blind retry.
14. Parent-facing text describes observable indicators only; no claims about intent, lying, or psychology.
""",

    "PROJECT_SPEC.seed.md": """# Part B — Seed `PROJECT_SPEC.md` (the agent copies this into the repo in S0)

Items tagged `OWNER-CONFIRM` are proposals you must approve or change before S1 freezes anything. The agent must not alter any decision itself; contradictions go to `docs/DECISIONS_OPEN.md`.

**D-01 Status bands.** For PRESENT students, using full-precision net percentage: `< 30.0%` RED; `30.0%–60.0%` inclusive YELLOW; `> 60.0%` GREEN. Net score may be negative, so percentage may be negative; negative nets are RED. ABSENT students have a separate band `ABSENT` (neutral grey `#5F6368`, white text); they have no score, rank, or percentage (all null).

**D-02 Easy questions.** `accuracy = correct among PRESENT / PRESENT count`; easy iff `accuracy >= 0.75` at full precision (exactly 0.75 qualifies). Absent students are excluded from numerator and denominator. If there are zero present students, no question is easy and batch average/topper are null.

**D-03 Subject labels.** Compute `attempt_ratio = attempted/subject_questions`, `accuracy_ratio = correct/attempted`. Evaluate in this order:
1. `attempted == 0` → `NO_ATTEMPT`
2. `attempt_ratio >= 0.60 and accuracy_ratio < 0.65` → `ACCURACY_BLEED`
3. `attempt_ratio < 0.50 and accuracy_ratio >= 0.75` → `CONCEPTUAL_SPEED_GAP`
4. `attempt_ratio < 0.50 and accuracy_ratio < 0.65` → `FOUNDATIONAL_CRISIS`
5. `attempt_ratio >= 0.60 and accuracy_ratio >= 0.75` → `MASTERY_ZONE`
6. otherwise → `MODERATE_ZONE`

Labels are internal; parent-facing copy describes observable facts only (see D-06).

**D-04 Rank and PTM.** Standard competition rank: `1 + count(present students with strictly higher net)`. PTM slip required iff ABSENT, or RED, or `rank > floor(0.75 * present_count)`. Rank applies to PRESENT only. `OWNER-CONFIRM`: bottom-quarter rule applies even when a whole batch is GREEN.

**D-05 Arithmetic.** `gross = Σ positive marks of correct`; `bleed = Σ magnitude of negative marks of wrong`; `net = gross − bleed`; `percentage = net / max_positive_marks × 100`. Internal values are full precision; display is one decimal. `positive_marks_not_earned` = Σ positive marks of easy questions that were wrong or blank (never described as "marks gained if fixed").

**D-06 Hindi wording.** Conversational Bolchal Hindi for non-specialist parents. Banned user-facing terms: `ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, `औसत मान`. Preferred: "कुल नंबर", "गलत जवाबों से कटे नंबर", "क्लास का औसत स्कोर", "कम-से-कम 75% बच्चों ने सही किया". Never claim lying, deliberate guessing, laziness, or psychological cause. Never say "more than 75%" for a threshold of ≥ 75%. Never print `None`. Always give denominators ("300 में से", "N उपस्थित बच्चों में से").

**D-07 Banner colours.** RED `#D93025`, YELLOW `#F9AB00` (dark text), GREEN `#1E8E3E`, ABSENT `#5F6368`. Contrast must be checked.

**D-08 Audio.** Primary mode `RECORDED_TOKEN_STITCH` (human-supplied recorded Hindi tokens). Optional `NETWORK_TTS` adapter, off by default. Typical note 15–25 s; hard maximum 45 s. On overflow: use the approved concise script variant (score + max + absence/rank facts only); if still over, return `AUDIO_UNAVAILABLE` and keep text. Never truncate material score facts. Negative net uses a recorded "minus" token.

**D-09 Messaging.** Live dispatch disabled by default (config flag + separately configured provider). Text/image template first; audio only where S0 verification proves the message type supports it; otherwise defer audio or use a secure authenticated link if permitted.

**D-10 Schedule.** `Asia/Kolkata`. Primary: Sunday 20:30 IST after the result is finalised. Monday 10:00 IST only when the event has `reminder_enabled = true`, as a distinct reminder identity. Example: event `2026-10-18 14:15+05:30` → primary `2026-10-18 20:30+05:30`; reminder (if enabled) `2026-10-19 10:00+05:30`.

**D-11 Parent confirmation (QR).** Default **disabled**. If enabled: opaque random token, scoped to student/test/PTM event, stored hashed, TTL default 72 h (`OWNER-CONFIRM`), single use, ≤ 5 attempts per token, revocable, HTTPS only, OTP challenge to the already verified guardian number. OTP delivery channel is `OWNER-CONFIRM` (WhatsApp authentication template vs SMS; S0 must verify prerequisites, including any Indian SMS registration requirements).

**D-12 Disclosure to parents.** Own child's report + class average + topper score + rank "X out of N present". No other student's response-level data. `OWNER-CONFIRM`: topper score may be shown.

**D-13 Retention (proposal only, needs legal review).** Scans and reports: current academic year. Message/audit logs: 90 days, masked. Deletion on verified request unless a documented legal hold applies.

**D-14 Scale.** Up to 200 students per batch; test maximum configurable; golden exam is 300.
""",

    "S0.md": """## S0 — Discovery, Contracts, Source Verification

**Goal:** Prepare the workspace and contracts. No business logic.

**Allowed files:** `docs/**`, `PROJECT_SPEC.md`, `README.md`, `pyproject.toml`, lockfile, `.env.example`, empty module/test scaffold, `docs/STATE.md`.

**Tasks**
1. Inspect the working directory, git status, sources, tests, lockfiles, config, assets. Record pre-existing changes and files that must not be touched in `docs/architecture_inventory.md` (what exists, what is missing, what is reused). If an implementation exists, map it against this pack and make the smallest necessary change.
2. Create `PROJECT_SPEC.md` by copying Part B verbatim. Do not edit decisions.
3. Product boundary (record in the spec): the system imports/validates roster, answer key, decoded OMR responses and source scans; computes diagnostics; produces Hindi text, PNG scorecards, A4 PTM PDF, audio; quarantines unsafe contacts; dispatches only what verified WhatsApp rules and recorded consent permit; tracks status; offers optional QR confirmation. It does **not** perform bubble detection or scan alignment; decoded answers come from an external OMR service whose contract is defined in S2.
4. Create `docs/research/official_source_verification.md`. Use current official sources (Meta developer docs, Government of India texts). For each item record: retrieval date, exact URL, section, conclusion, unresolved uncertainty. If sources cannot be reached, mark `UNVERIFIED` and keep dispatch disabled. Verify:
   - supported API version for this build (pin in config with rationale; do not float versions);
   - customer-service window rules and when business-initiated templates are required;
   - template approval, opt-in, business verification, phone-number setup, billing/pricing prerequisites;
   - media supported in templates (image headers; whether audio is supported in which message types);
   - exact audio payload and media requirements (do not assume a `voice` field);
   - **template parameter constraints** (max lengths, newline/variable rules, variable count) → recorded as a machine-readable `TemplateConstraints` file used by S4;
   - webhook subscription/signature verification, status meanings, retry guidance, error codes, rate limits, idempotency guarantees;
   - OTP delivery options for guardian verification (authentication templates vs SMS) and any Indian SMS registration prerequisites;
   - India's DPDP framework: current legal texts, commencement/rules status, children's-data and guardian-consent requirements. Treat as release-blocking, needing documented legal review. Do not claim compliance.
5. Architecture docs: `docs/architecture_decisions.md`, `docs/privacy_and_security.md` (minimisation, masking, retention per D-13, deletion, access control, export, incident response), `docs/testing_strategy.md`. Plan modules: models, contacts/hygiene, ingestion, diagnostics, hindi_templates, omr_proof, renderer, audio_engine, messaging policy, provider, scheduler, durable store, webhooks, confirmation, orchestrator, cli, audit. Durable state: SQLite acceptable as reference with explicit limits; an in-memory scheduler is not durable or multi-replica safe.
6. `pyproject.toml` (dependency ranges, ruff/mypy/pytest config), lockfile if feasible, `README.md` (setup, offline vs network features, live dispatch off by default), `.env.example`.

**Gate 0:** baseline recorded; unresolved claims are `UNVERIFIED`; no credentials or real data added; commands documented; no contradictions between spec and this pack (list any in `DECISIONS_OPEN.md`).
""",

    "S1.md": """## S1 — Golden Dataset and Independent Contract

🧑 **Human gate:** before the agent runs, you review the literals in "Golden expected values" below. The agent may not change them.

**Allowed files:** `fixtures/golden/**`, fixture generator, `tests/test_stage1_golden_contract.py`, `tests/oracle.py`, fixture docs.

**Golden exam** (`test_paper_300.json`): 75 questions, IDs 1–75. Q1–25 PHYSICS, Q26–50 CHEMISTRY, Q51–75 MATHS. +4 correct, −1 wrong, 0 blank. `correct_option = ["A","B","C","D"][(q−1) % 4]`. Synthetic 800×600 geometry (fixture-only): `col=(q−1)//15`, `row=(q−1)%15`, `col_x=30+col*150`, `center_y=255+row*17`, option centre x = `col_x+35+opt_index*24`.

**Roster and responses** (`admissions_300.json`, `submissions_300.json`): `STU_01`–`STU_20`, one submission each; 16 PRESENT (01–16), 4 ABSENT (17–20, empty responses). Materialise every response in JSON. Wrong answer = next option in A→B→C→D→A order after the key.
- STU_01: Q1–10 ✓; Q11–20 ✗; Q21–25 blank; Q26–30 ✓; Q31–45 ✗; Q46–50 blank; Q51–55 ✓; Q56–75 blank.
- STU_02: Q1–70 ✓; Q71–72 ✗; Q73–75 blank.
- STU_03: Q1–23 ✓; Q26–27 ✗; rest blank.
- STU_04: Q1–45 ✓; rest blank.
- STU_05–13: Q1–20 ✓; rest blank.
- STU_14–16: all blank.

**Contacts and consent** (synthetic only). Default numbers: student `98200100nn`, parent `98300100nn` (nn = two-digit student number), consent `OPT_IN`, guardian `VERIFIED`. Exceptions:
- STU_01: student `+91 98111-22201`, parent `+91 98111-22202`.
- STU_02: student `09811122203`, parent `9811122203` → same normalised number → `INTERCEPTION_RISK_SAME_NUMBER`, blocked.
- STU_03, STU_04: shared parent `9811122299`, `verified_sibling=false` → `DUPLICATE_PARENT_UNVERIFIED` on both.
- STU_05, STU_06: shared parent `9811122288`, `verified_sibling=true` → not flagged.
- STU_07: parent `5511122207` → invalid.
- STU_08: consent `UNKNOWN`. STU_09: consent `REVOKED`. STU_10: guardian verification `UNVERIFIED`.
- STU_17: unique valid parent number, `VERIFIED`, `OPT_IN` (absent-path test case). STU_19: `REVOKED`.

**Golden expected values** (literals the agent commits to `expected_reports.json`):

| Student | Att | ✓ | ✗ | Gross | Bleed | Net | % | Rank | Band | PTM | Easy missed (ids / marks not earned) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | 45 | 20 | 25 | 80 | 25 | 55 | 18.33 | 13 | RED | yes | 11–20 / 40 |
| 02 | 72 | 70 | 2 | 280 | 2 | 278 | 92.67 | 1 | GREEN | no | none |
| 03 | 25 | 23 | 2 | 92 | 2 | 90 | 30.00 | 3 | YELLOW | no | none |
| 04 | 45 | 45 | 0 | 180 | 0 | 180 | 60.00 | 2 | YELLOW | no | none |
| 05–13 | 20 | 20 | 0 | 80 | 0 | 80 | 26.67 | 4 (tie) | RED | yes | none |
| 14–16 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 14 (tie) | RED | yes | 1–20 / 80 |
| 17–20 | ABSENT: score, rank, % null; band ABSENT; PTM yes |

Batch: enrolled 20, present 16, absent 4; class average `1323/16 = 82.6875`; topper 278; easy set is exactly Q1–20 (Q1–10 at 13/16, Q11–20 at 12/16 = 0.75; every Q21–75 below 12/16); PTM-eligible total 17.

Subject labels (D-03): STU_01 Physics `ACCURACY_BLEED`, Chemistry `ACCURACY_BLEED`, Maths `CONCEPTUAL_SPEED_GAP`. STU_02 all `MASTERY_ZONE`. STU_03 Physics `MASTERY_ZONE`, Chemistry `FOUNDATIONAL_CRISIS`, Maths `NO_ATTEMPT`. STU_04 Physics/Chemistry `MASTERY_ZONE`, Maths `NO_ATTEMPT`. STU_05–13 Physics `MASTERY_ZONE`, others `NO_ATTEMPT`. STU_14–16 all `NO_ATTEMPT`. ABSENT: no subject labels.

**Edge-case fixture** (`edge_cases.json`, separate from the 20-student golden set): an all-wrong student (net −75 → −25.00 %, RED), a tie-for-first pair, a zero-present batch, and a one-student batch. Percentage boundary values (29.99, 30.0, 60.0, 60.01) are tested at classifier level on raw percentages, since integer marks over 300 can't hit every boundary.

**Manifest:** `manifest.json` with fixture version and SHA-256 hashes. A generator may only reproduce approved bytes. `tests/oracle.py` may contain a minimal, test-local scorer used only for cross-checking arithmetic invariants; it shares no code with `src/`.

**Tests** (`tests/test_stage1_golden_contract.py`): 75 unique questions/300 max; 20 unique IDs, 16/4 split, one-to-one mapping; per-question accuracy properties; STU_01 arithmetic and missed set; STU_02/03/04 scores; valid option values; contact/consent cases match the contract; hashes match the manifest; every literal above matches `expected_reports.json`.

**Gate 1:** `pytest -q tests/test_stage1_golden_contract.py`; report command, exit code, actual test count. 🧑 Human signs off the frozen manifest hash in `docs/STATE.md`.
""",

    "S2.md": """## S2 — Input Contracts and Import (new)

**Goal:** Define how data enters the system. No scoring.

**Allowed files:** `src/omr_dispatch/models.py`, `ingestion.py`, `docs/input_contracts.md`, `tests/test_stage2_ingestion.py`, `fixtures/ingestion/**`.

**Tasks**
1. Strict Pydantic v2 models (`extra="forbid"`): `SubjectName`, `QuestionMeta` (id, subject, correct option, marks, optional bubble coords), `StudentAdmissionRow` (id, roll, Hindi display name/salutation, raw student/guardian contact, sibling-verification, guardian verification, consent status/scope/time/source/reference, revocation), `StudentOMRSubmission` (id, PRESENT/ABSENT, responses, scan reference, provenance), `CoordinateMap` (version, image width/height, per-question per-option centre, alignment confidence, source/transform history), `ScanProvenance`.
2. Importers for roster/answer-key/responses (CSV and JSON). Reject unknown columns, duplicate IDs, out-of-range question IDs, invalid options, and missing records. Never treat a missing record as zero. Preserve each decoded response's link to its source scan.
3. `docs/input_contracts.md` defines what an external OMR decoder must supply (response map, scan file, coordinate map, confidence). State explicitly that bubble detection is out of scope.
4. Importers return structured errors (row, field, reason); no partial silent import.

**Gate 2:** tests for every rejection path and for loading all golden fixtures. Run `pytest -q tests/test_stage2_ingestion.py`; report actuals.
""",

    "S3.md": """## S3 — Deterministic Diagnostics and Contact Hygiene

**Allowed files:** `src/omr_dispatch/diagnostics.py`, `contacts.py`, `models.py` (extend only), `tests/test_stage3_diagnostics_and_hygiene.py`. Do not touch fixtures.

**Tasks**
1. `normalize_indian_mobile(raw) -> str | None`: strip spaces, hyphens, parentheses, `+`; reject alphabetic/malformed input with a recorded reason. 12 digits starting `91` → drop prefix; 11 digits starting `0` → drop trunk prefix. Valid iff `^[6-9]\d{9}$` (a format check only; it does not prove an active parent number or WhatsApp capability).
2. `validate_admission_batch(rows)`: flags for invalid student/guardian numbers, same normalised student/parent number, repeated parent number without verified siblings. Flags are deduplicated and sorted. Dispatch eligibility requires valid + verified guardian contact, non-revoked `OPT_IN` for the purpose, and no unresolved quarantine flags. Provide a manual-resolution status; never bypass quarantine to reach an expected send count.
3. `evaluate_batch(questions, admissions, submissions) -> EvaluationBundle` implementing D-01 to D-05 exactly. `StudentDiagnosticReport` must carry everything S4 needs: present count, enrolled count, class average, topper score, rank, band, subject diagnostics, easy-missed ids, marks not earned, `requires_ptm_slip`, and the contact eligibility result kept separate from academic fields.
4. ABSENT: rank/percentage null, band `ABSENT`, no subject diagnostics. ID mismatches/duplicates raise; zero-present batch handled explicitly (no division by zero).

**Gate 3:** `tests/test_stage3_diagnostics_and_hygiene.py` using hard-coded values from the S1 table: all 20 students; boundary classifier cases (29.99/30.0/60.0/60.01), exactly 0.75 item accuracy, ties, no attempts, all-absent, negative net, invalid IDs, missing/duplicate responses, bad numbers, unknown/revoked/unverified, duplicate contact, sibling exception; invariants (attempted = correct + wrong, net = gross − bleed, subject totals reconcile). Run `pytest -q tests/test_stage3_diagnostics_and_hygiene.py`; also re-run S1/S2 suites.
""",

    "S4.md": """## S4 — Conversational Hindi Templates

**Allowed files:** `src/omr_dispatch/hindi_templates.py`, `template_constraints.py`, `tests/test_stage4_hindi_templates.py`. No rendering, audio, or API calls.

**Tasks:** `render_bolchal_templates(report, constraints) -> RenderedBolchalContent` with `banner_title_hi`, `banner_color_hex`, `score_line_hi`, `batch_context_line_hi`, `mark_bleed_line_hi`, `low_hanging_line_hi`, `voice_note_script_hi`, `ptm_slip_text_hi`, `message_caption_hi`, and `template_variables` honouring the `TemplateConstraints` recorded in S0 (max lengths, no newlines in variables, variable count). If constraints are `UNVERIFIED`, use the conservative defaults from the spec and mark the output `constraints_unverified=true`.

Rules (D-06, D-07, D-12):
- PRESENT: net/max and one-decimal percentage; "rank X out of N present students" (omit the sentence if rank missing); class average and topper score; with wrong answers show correct count/gross, wrong count, marks deducted, net; without wrong answers say so without implying everything was attempted. Easy-missed copy says **at least** 75% of present students got them right, gives the count and positive marks not earned; if none were missed say "no questions meeting the threshold were missed". Negative nets display with a minus sign.
- ABSENT: neutral grey banner "टेस्ट में अनुपस्थित"; state only that the student is recorded absent, the test maximum, and how many attended. No score, subject diagnosis, absence reason, proof, or signature.
- Subject lines use observable facts ("इस विषय में कोई सवाल हल नहीं किया गया" for `NO_ATTEMPT`); no internal label names are shown.

**Golden assertions:** STU_01 score line conveys "कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)"; voice copy says 25 wrong answers deducted 25 marks and the final score is 55; easy sentence: ten missed questions, 40 marks not earned, at least 75% peer accuracy. STU_17 copy: 300-mark test held, 16 students attended, no framing as a zero score.

**Gate 4:** test all 20 golden outputs plus all bands, absent, negative net, no-wrong-answers, exactly-75% item, no easy questions, missing rank, odd names/salutations, Unicode normalisation (NFC), long text, template-variable constraints, banned vocabulary. `pytest -q tests/test_stage4_hindi_templates.py`. 🧑 A Hindi-fluent reviewer signs off the golden copy (workflow W7).
""",

    "S5.md": """## S5 — OMR Proof Strip and Scan Provenance

**Allowed files:** `src/omr_dispatch/omr_proof.py`, `tests/test_stage5_omr_proof.py`, test-only fixture helpers.

**Tasks**
1. Input: original scan (path/object), submission, answer-key metadata, `CoordinateMap` from S2. Record source SHA-256, source reference, dimensions, processing version, coordinate-map version, timestamp, every transform applied (crop offsets applied exactly once; no silent rescaling).
2. Fail closed with `REVIEW_REQUIRED` if the map is missing, any coordinate is out of image bounds, or alignment confidence is below the configured threshold.
3. Draw on a copy; never alter the source. Correct = green ring/check (`#1E8E3E`); wrong = red cross on the selected bubble plus optional green outline on the key bubble (if validated); blank easy question = amber outline (`#F9AB00`) on the key bubble (if validated). Add a legend.
4. ABSENT or missing scan → explicit absent-proof result; no replacement sheet; no signature pixels. Real signatures: preserve original pixels only.
5. Synthetic fixture only: 800×600 → crop `(0,230,800,600)` → 800×370; Q1 centre `(65,255)` → `(65,25)`.

**Gate 5:** real Pillow tests: 800×370 output; Q1 green at `(65,25)`; STU_01 Q11 selected bubble (option D at `(137,425)` in source, i.e. `(137,195)` in crop) red; wrong/blank/correct states; corrupt image, missing scan, out-of-bounds, wrong dimensions, low confidence; source bytes/hash unchanged; no signature generated in production paths. `pytest -q tests/test_stage5_omr_proof.py`.
""",

    "S6.md": """## S6 — Devanagari Rendering, Scorecard PNG, PTM PDF

**Allowed files:** `src/omr_dispatch/renderer.py`, `templates/scorecard.html.j2`, `templates/ptm_slips.html.j2`, `assets/fonts/**`, `tests/test_stage6_renderer.py`.

**Tasks**
- Bundle licensed Noto Sans Devanagari in `assets/fonts/` with source/licence record; `@font-face`; wait for font readiness; no network at render time. Include shaping fixtures (`स्त`, `प्र`, `र्फ`, pre-base `ि`, real template strings). Record browser/font versions.
- Context-managed `PlaywrightRenderer` that reuses the browser and closes pages/processes properly.
- Scorecard PNG 800×1150 at scale 1 (document deviations): name/roll, banner (colour per D-07), score/max/%, batch context, mark-bleed breakdown, easy-question context, subject table, embedded proof strip (from real PNG bytes). ABSENT card has the grey banner and no proof/score. Escape all untrusted text. Size target < 500 KB; if missed, report a failed budget, don't silently degrade.
- PTM PDF: A4 portrait, `@page { size: A4 portrait; margin: 6mm; }`, 2×4 slips per page, `ceil(n/8)` pages, none for n = 0 (explicit empty result). Each slip: institution header, name/roll, approved performance text, confirmation method. A physical signature line is allowed but unverified. QR only if S11 supplies an opaque token; define an interface now (`QrTokenProvider`) and test with a stub token. Never encode personal data.

**Gate 6:** real Chromium. Open PNGs with Pillow: dimensions, banner colour, glyph pixels, proof present, size. Check font actually loaded and known strings; keep an image diagnostic fixture for hard conjuncts. PDFs for 0/1/8/9/11/16/17 slips with expected page counts (0, 1, 1, 2, 2, 2, 3); page size within tolerance; rasterise and inspect clipping/blank pages/overlap; HTML-like names render as text. `pytest -q tests/test_stage6_renderer.py`. Missing Chromium/fonts/rasteriser → report, don't claim success.
""",

    "S7.md": """## S7 — Hindi Audio (two sub-stages)

### S7A 🧑 Asset intake (human-led, agent assists)

The agent cannot produce genuine licensed speech. **Stop and ask the operator** to supply recordings (or a licensed corpus). The agent then:
1. Writes the token **recording sheet** (`docs/audio_recording_sheet.md`): numbers 0–99 recorded individually (Hindi 1–99 are irregular, so don't try to synthesise them by rule), "सौ", "माइनस", greeting, "कुल नंबर", "300 में से"-style phrase parts, wrong-answer / mark-deduction phrases, batch/rank phrases, absence phrases, plus pause tokens. Hundreds (100–300) and rank/roster counts up to 200 compose from "सौ" + 0–99.
2. Builds `assets/audio_tokens/manifest.json` (token ID, spoken text, voice, licence/source, sample rate, channels, SHA-256, version) and a preflight validator: manifest hashes, headers, formats, duration, silence boundaries; missing tokens fail loudly.
3. 🧑 A Hindi speaker confirms recordings match the sheet (W7).

### S7B Engine

**Allowed files:** `src/omr_dispatch/audio_engine.py`, `tests/test_stage7_audio_engine.py`.

- `RECORDED_TOKEN_STITCH` primary, `NETWORK_TTS` optional behind a provider interface (opt-in, timeouts, cached results, may change behaviour; never required for offline use). Tones/noise are never returned as speech.
- `synthesize_token_voice_note(report, catalog, out_path)`, `synthesize_network_tts(...)`, `transcode_to_whatsapp_ogg(in, out)` using real FFmpeg (`check=True`, timeout, mono, configured sample rate/bitrate per S0-verified requirements). Never rename WAV/MP3 to `.ogg`. FFmpeg failure → controlled failure, no success record.
- Define token order and pauses; no clipping or ambiguous number joins. Target 15–25 s, hard max 45 s, overflow per D-08.
- Cache key: mode/provider, voice/catalog version, language, rate/pitch, normalised text or token sequence, encoder settings version; manifest of result hashes. Cache paths and logs contain no names or message text.

**Gate 7:** real tokens + real FFmpeg: OGG header, Opus identification header, `ffprobe` codec/mono/rate/duration; token sequence matches expected score/absence facts for golden students (including negative net via edge fixture); cache hit/invalidations without a second synthesis call; missing token, corrupt input, missing FFmpeg, timeout/non-zero exit, TTS timeout/invalid response, offline run, duration violation, text-only fallback. Report whether network-TTS tests were skipped. Provide the human listening checklist (pronunciation, concatenation, number clarity, clipping, volume); automated tests alone don't certify intelligibility.
""",

    "S8.md": """## S8 — Messaging Policy Engine and Durable State (split from v2 Stage 7)

**Allowed files:** `src/omr_dispatch/messaging/policy.py`, `store.py`, `audit.py`, `tests/test_stage8_policy_and_state.py`. No provider HTTP yet.

**Tasks**
1. Policy decision before every send, recorded in the audit log: guardian verified, consent `OPT_IN` and non-revoked for purpose, no quarantine flags, service window state, free-form vs template, template approved and supports the content, account/phone-number/billing prerequisites configured, API contract status. Any failed or unknown check → block/defer with an exact reason code.
2. Durable store (SQLite reference): dispatch intent, attempt, provider message, webhook event, schedule, audit record, confirmation. States: `PENDING`, `BLOCKED_CONSENT`, `BLOCKED_HYGIENE`, `BLOCKED_POLICY`, `SCHEDULED`, `UPLOADING_MEDIA`, `SUBMITTED`, `DELIVERED`, `READ`, `FAILED`, `RETRY_PENDING`, `UNKNOWN_NEEDS_REVIEW`, `CANCELLED`.
3. Idempotency key from student/test/event/recipient/channel/purpose, with no raw phone numbers. One logical delivery per key unless a distinct reminder event is configured. Persist intent before any provider call.
4. A global kill switch and per-batch pause stop all dispatch and cancel pending jobs.

**Gate 8:** STU_02 → zero sends, exact block reason; STU_03/04, 07, 08, 09, 10 blocked; STU_01 and STU_05/06 allowed to proceed to policy-permitted mode; STU_17 eligible only with verified consent; STU_19 blocked; duplicate job invocation yields one logical delivery; state-transition table tests (illegal transitions rejected); restart recovery reloads state. `pytest -q tests/test_stage8_policy_and_state.py`.
""",

    "S9.md": """## S9 — Provider Adapter, Webhooks, Retries

**Allowed files:** `messaging/provider.py`, `whatsapp_cloud.py`, `webhooks.py`, `retry.py`, `tests/test_stage9_provider_and_webhooks.py`, `tests/fixtures/provider_contract/**`.

**Tasks**
- `MessagingProvider` interface and isolated `WhatsAppCloudProvider`; version/base URL from config (pinned in S0). Implement only capabilities verified in S0: media upload with durable media-ID storage, approved template sends, in-window free-form where permitted, audio payload only if verified. Persist provider message IDs and sanitised error classes.
- Retries: only classified transient failures; bounded exponential backoff with jitter; honour `Retry-After` and verified rate limits; permanent validation/template/consent failures are never retried. A timeout after the request may have been accepted → `UNKNOWN_NEEDS_REVIEW`, reconcile via webhook evidence, no blind resend.
- Webhooks: verify authenticity per the official method before processing; persist and deduplicate; map provider statuses while keeping the raw status/timestamp; tolerate duplicates and out-of-order events without regressing state. Submission success is never reported as delivered/read.
- Dry-run mode and cost controls from verified pricing sources; never hard-code unverified prices.

**Gate 9:** real local `HTTPServer` on an ephemeral loopback port capturing paths, headers, multipart, JSON, timing. Payload assertions come from the recorded contract fixture, not assumptions. Cases: 429, 5xx, permanent 4xx, malformed response, timeout after receipt, partial failure, duplicate/out-of-order/unknown webhook, invalid signature, handler retry, unapproved template, closed window, unsupported audio template media, `UNVERIFIED` contract → safe block. Report that green tests prove local request/state-machine behaviour only, not Meta acceptance or delivery.
""",

    "S10.md": """## S10 — Scheduler

**Allowed files:** `src/omr_dispatch/scheduler.py`, `tests/test_stage10_scheduler.py`.

- Pure `plan_schedule(event, now, policy)` using `ZoneInfo("Asia/Kolkata")` and injected time; persisted schedules survive restart. Validate that the event date is actually a Sunday for the primary window; never label another weekday's 20:30 as the Sunday window.
- Primary `2026-10-18 20:30+05:30` and (only when `reminder_enabled`) reminder `2026-10-19 10:00+05:30` for the event `2026-10-18 14:15+05:30`; distinct idempotency identities.
- Define late import, missed window, holiday override, provider outage, unapproved template, and events created outside the window; never bypass window rules with free-form content. Single-process lock or shared queue to stop two instances dispatching one job.

**Gate 10:** tests for each case above plus DST-free sanity, restart/recovery, lock contention. `pytest -q tests/test_stage10_scheduler.py`.
""",

    "S11.md": """## S11 — Parent Confirmation (QR + OTP), optional

Skip entirely if D-11 stays disabled (record "disabled" in `STATE.md`).

**Allowed files:** `src/omr_dispatch/confirmation.py`, `tests/test_stage11_confirmation.py`.

- Cryptographically random opaque token scoped to student/test/PTM event; store only its hash; QR contains only a secure URL with the opaque token.
- Expiry, revocation, single use, replay protection, rate limits (≤ 5 attempts), HTTPS, CSRF where relevant, audit trail.
- Confirmation requires an OTP challenge to the already verified guardian contact through the S0-verified channel. Record the verification method and time and claim no stronger assurance than the mechanism gives. Paper signature stays optional and unverified.

**Gate 11:** expiry, reuse, revocation, wrong-token, OTP failure/lockout, unauthorised access, token randomness/length, success path, no personal data in the QR payload. `pytest -q tests/test_stage11_confirmation.py`.
""",

    "S12.md": """## S12 — Orchestrator, CLI, Audit, Retention (new)

**Allowed files:** `src/omr_dispatch/orchestrator.py`, `cli.py`, `retention.py`, `tests/test_stage12_orchestrator.py`.

- CLI commands: `validate`, `evaluate`, `render`, `audio`, `plan-dispatch`, `dry-run`, `send` (refuses unless live flag + verified-contract + not-killed), `report`, `purge`, `review-queue`.
- Orchestrator wires S2→S10 for a batch; produces golden-batch outputs (diagnostic JSON, Hindi text, PNGs, PDF, audio, dispatch plan) into a run directory with a manifest of paths/sizes/hashes.
- Review queues: quarantined contacts, `REVIEW_REQUIRED` scans, `UNKNOWN_NEEDS_REVIEW` dispatches, audio fallbacks.
- Retention/deletion job per D-13; consent-revocation propagation cancels scheduled jobs.
- Audit records are masked and exportable; privacy tests scan logs and outputs for phone numbers, tokens, names.

**Gate 12:** end-to-end dry run of the golden batch against the local test provider only; counts match S1 (e.g., 17 PTM slips; STU_02/03/04/07/08/09/10/19 not dispatched); rerun produces no duplicate deliveries; purge removes what D-13 says. `pytest -q tests/test_stage12_orchestrator.py`.
""",

    "S13.md": """## S13 — Cross-Stage Release Gate

No new features; narrowly scoped blocker fixes only. Run in a **fresh session** (see W2).

1. Clean checkout; install from the lockfile; run lint, type checks, full `pytest -v`. Confirm Chromium, fonts, FFmpeg, tokens, and PDF rasteriser are present; no silent skips. Test traffic can't reach real messaging endpoints.
2. Inspect generated artifacts: diagnostic JSON, Hindi text, scorecards for RED/YELLOW/GREEN/ABSENT, PTM PDFs for 0/1/8/9/11/16/17 slips (rasterised), proof strips, OGG/Opus with `ffprobe`, state transitions, webhook handling, QR flow (if enabled), privacy masking.
3. **Release blockers:** changed fixture hashes without reviewed update; skipped/weakened/over-mocked mandatory test; threshold/boundary/arithmetic/rank mismatch; synthetic proof or signature in production; send without eligibility+consent or outside template policy; silent duplicate delivery or blind retry of an uncertain send; unverified API field used in the production adapter; unchecked webhook authenticity or falsely reported delivery; QR leaking personal data or treated as identity proof; secrets/unnecessary personal data in repo/logs/fixtures; audio without genuine token composition; absent students shown in a performance colour.
4. Write `docs/release_verification_report.md`: revision/working-tree identity, exact commands + exit codes, test counts and skip reasons, artifact paths/sizes/metadata, visual findings, source list/review date, limitations, open decisions, and whether live dispatch stays disabled or is eligible for a separate launch review (W8).
"""
}

def main():
    for filename, content in PACK_FILES.items():
        dest_file = OUTPUT_DIR / filename
        dest_file.write_text(content.strip() + "\n", encoding="utf-8")
        print(f"Created: {dest_file}")

    print(f"\nSuccessfully wrote {len(PACK_FILES)} atomic prompt pack files.")

if __name__ == "__main__":
    main()