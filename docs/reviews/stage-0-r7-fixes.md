# Stage S0-R7 Fix Report (`docs/reviews/stage-0-r7-fixes.md`)

## Corrections to `stage-0-r5-r6.md`

Check 2 of `docs/reviews/stage-0-r5-r6.md` misreported the golden table in `docs/prompt_pack/S1.md` as "bit-for-bit unchanged" relative to `stage-0-r4`. In reality, **line 9** of `docs/prompt_pack/S1.md` was edited to add roster fields:
- **`stage-0-r4` (line 9):**
  ```markdown
  **Roster and responses** (`admissions_300.json`, `submissions_300.json`): `STU_01`–`STU_20`, one submission each; 16 PRESENT (01–16), 4 ABSENT (17–20, empty responses). Materialise every response in JSON. Wrong answer = next option in A→B→C→D→A order after the key.
  ```
- **`stage-0-r6` / HEAD (line 9):**
  ```markdown
  **Roster and responses** (`admissions_300.json`, `submissions_300.json`): `STU_01`–`STU_20`, one submission each; 16 PRESENT (01–16), 4 ABSENT (17–20, empty responses). Roster includes `child_display_name` and `class_section` without altering any frozen score value. Materialise every response in JSON. Wrong answer = next option in A→B→C→D→A order after the key.
  ```

All 31 rows of the 20-student OMR golden table itself (lines 10 to 40 inclusive: `STU_01` through `STU_20` response patterns, batch statistics summary, score breakdown, and subject label lines) remain 100% byte-identical to `stage-0-r4`.

### Verification Output: `python scripts/check_golden_table_identity.py`
```text
[GOLDEN TABLE PASS] All 31 OMR golden table rows (lines 10-40) in S1.md are byte-identical to stage-0-r4.
```
Exit code: `0`.

---

## The 10 Defect Fixes

| Fix ID | What was wrong | What changed (files) | Proof (command + exit code) |
| :--- | :--- | :--- | :--- |
| **F1** | Potential Hindi text corruption in PDF export; banned-term check was vacuous; greeting strings lacked automated byte-exact validation. | Created `scripts/check_hindi_integrity.py` scanning strict UTF-8, NFC normalization, zero U+FFFD, zero orphan combining marks, zero unapproved Devanagari digits (exempting technical policy discussions per operator decision). Enforces D-06 banned terms (as `\u` escapes) appear only on line 11 of `message_catalog.md` and zero in templates. Verifies byte-exact greeting (`"प्रिय अभिभावक, "`) across all notification templates. Wired into `scripts/guardrails.py`. | `python scripts/check_hindi_integrity.py`<br>Exit code: `0` |
| **F2** | Review Check 2 misreported golden table as "bit-for-bit unchanged" when line 9 of `S1.md` was edited. | Created `docs/reviews/stage-0-r7-fixes.md` with "Corrections to stage-0-r5-r6.md" documenting line 9 edit. Created `scripts/check_golden_table_identity.py` comparing lines 10–40 of `S1.md` against `stage-0-r4:docs/prompt_pack/S1.md`. | `python scripts/check_golden_table_identity.py`<br>Exit code: `0` |
| **F3** | `stage-0-r6` was amended in previous session causing `docs/STATE.md` to list `0b90ac5...`, whereas git tag pointed to `8f59ebd...`. | Corrected commit hash in `docs/STATE.md` to `8f59ebda2fcf46e52bb76da2c2abdb02c89b4600`. Created `scripts/check_state_hashes.py` resolving all 40-char hashes and matching tag references in git. Wired into `scripts/guardrails.py`. | `python scripts/check_state_hashes.py`<br>Exit code: `0` |
| **F4** | ADR-0016 narrowed frozen D-04 (PTM slips only for PTM-linked exams) without operator decision, blocking signed manifest hash in Stage 1. | Added `Part 1D: S1-BLOCKING Decisions` to `docs/DECISIONS_OPEN.md` covering items S1-BLOCK-01 through S1-BLOCK-06 with options and SHA-256 impact. Added explicit blocking banner before marks-entry fixture in `docs/prompt_pack/S1.md`. Kept all items OPEN. | Inspected `docs/DECISIONS_OPEN.md` & `docs/prompt_pack/S1.md`<br>Exit code: `0` |
| **F5** | ADR-0003 was modified after acceptance to incorporate multi-tenancy without recorded re-approval. | Added `## Re-approval record` to `docs/adr/ADR-0003-identifiers-and-keys.md` marked `PENDING`. Changed status header to `ACCEPTED (original single-school scope); AMENDMENT PENDING RE-APPROVAL`. Updated `docs/adr/README.md` and `docs/STATE.md`. | Inspected `docs/adr/ADR-0003-identifiers-and-keys.md` & `docs/adr/README.md`<br>Exit code: `0` |
| **F6** | Working tree was dirty (`official_source_verification.md`, `pyproject.toml`, `uv.lock`, uncommitted edits to `ADR-0014`/`ADR-0016`). | Reverted uncommitted edits in `ADR-0014` and `ADR-0016` to `PROPOSED`. Applied operator decisions: committed R-07 confidence update (`9ab150c`), committed dev dependencies in `pyproject.toml` (`f0e0fa2`), committed `uv.lock` (`7c61380`). | `git status --porcelain`<br>Clean / Exit code: `0` |
| **F7** | Guardrails printed SKIPPED and exited 0 on empty repo; trailing whitespace and EOF blank lines in multiple files. | Created `docs/CURRENT_STAGE` with value `S0`. Updated `scripts/guardrails.py` so checks skip only when required stage > `CURRENT_STAGE`. Formatted summary line to print `PASSED n / SKIPPED n / FAILED n`. Cleaned trailing whitespace and EOF blank lines in 7 docs; wired `git diff --check` into guardrails. | `python scripts/guardrails.py`<br>Exit code: `0`<br>`git diff --check stage-0-r6..HEAD`<br>Exit code: `0` |
| **F8** | Root `AGENTS.md` lacked Invariants 15–17. | Mirrored Invariants 15, 16, 17 verbatim from `docs/prompt_pack/00_global_invariants.md` into root `AGENTS.md`. Synchronized Invariant 2. Created `scripts/check_invariants_sync.py` and wired into guardrails. Documented wording discrepancy ("never logged" vs "masked"). | `python scripts/check_invariants_sync.py`<br>Exit code: `0` |
| **F9** | Meta pricing and window claims unverified or conflicting; missing R-16 `"voice": true`; missing 24h window opening decision for voice notes. | Re-verified R-05 against Meta official pricing docs (`https://developers.facebook.com/docs/whatsapp/pricing`, 2026-10-21) and recorded exact India rates and billing localization. Documented 1 Oct 2026 service-window utility charging conflict as OPEN. Added research row R-16 for `"voice": true` (Ogg/Opus mono) and renumbered R-17/R-18. Added item `(s)` for 24h service window opening to `DECISIONS_OPEN.md`, referenced in `S9.md` and `ADR-0019`. | Inspected `docs/research/official_source_verification.md`, `docs/DECISIONS_OPEN.md`, `docs/prompt_pack/S9.md`, `docs/adr/ADR-0019*.md`<br>Exit code: `0` |
| **F10** | Review process was too easy to pass; lacked proof requirements, falsification attempts, and zero-defect gating. | Updated `docs/prompt_pack/W2_review.md` adding mandatory requirements: raw command outputs, clean `git worktree` execution, reporting SKIPPED counts, mandatory "Attempts to falsify" section (min 3 attempts), and zero-defect gating. | Inspected `docs/prompt_pack/W2_review.md`<br>Exit code: `0` |

---

## Items Left for the Operator

1. **F4 S1-BLOCKING Decisions (`docs/DECISIONS_OPEN.md`):**
   - `S1-BLOCK-01`: PTM Slip Generation Policy for `MARKS_ENTRY_TOTALS` assessments. Does a single-subject teacher marks entry test carry `requires_ptm_slip=true` or `false`? (Affects `expected_marks_reports.json` SHA-256).
   - `S1-BLOCK-02`: PTM Slip Paper Dimensions & Layout Boundary. Standard A4 (`210mm x 297mm`) vs thermal slip format.
   - `S1-BLOCK-03`: PTM Slip Headmaster / Teacher Signature Block. Physical signature line vs cryptographic QR code.
   - `S1-BLOCK-04`: WhatsApp Message Body Roll Number Inclusion (`include_roll_in_text`). Default `false` vs `true`.
   - `S1-BLOCK-05`: Student Identifier Roster Model for S1 Golden Fixtures. Persistent student roster format with `child_display_name` and `class_section`.
   - `S1-BLOCK-06`: Competition Rank Semantics on Ties & Absent Student Banding. Standard competition rank (`1224`) vs dense rank (`1223`); absent band classification (`ABSENT` band vs omitting band).
   - **Consequence:** Stage 1 manifest hash cannot be signed until the operator decides these items. Line before marks-entry fixture in `docs/prompt_pack/S1.md` remains marked BLOCKED.

2. **F5 ADR-0003 Multi-Tenant Amendment Re-approval:**
   - Section `## Re-approval record` in `docs/adr/ADR-0003-identifiers-and-keys.md` remains `PENDING`.
   - Header status remains `ACCEPTED (original single-school scope); AMENDMENT PENDING RE-APPROVAL`.
   - Operator must provide approval date and reference, or decide whether to accept or revert the amendment.

3. **F6 Working Tree Pre-Flight Inputs:**
   - Operator selected `COMMIT` for `docs/research/official_source_verification.md` (R-07 confidence update). Applied in commit `9ab150c`.
   - Operator selected `COMMIT` for `pyproject.toml` and `uv.lock` (dev dependency group additions). Applied in commits `f0e0fa2` and `7c61380`.
   - Operator selected `Revert to PROPOSED` for uncommitted edits to `ADR-0014` and `ADR-0016`. Applied. Working tree is clean.

4. **F8 Wording Discrepancy (Invariant 17 vs ADR-0008 / ADR-0018):**
   - Invariant 17 states child names and class labels are "never logged" in application logs.
   - ADR-0008 and ADR-0018 discuss logger-layer "masking" and redaction.
   - Per non-resolution boundary, this wording distinction is formally logged as a discrepancy without unilaterally changing either text.

5. **F9 Pricing Conflict & Voice Notes Service Window Initiation:**
   - Pricing Conflict (OPEN): BSP/partner documentation asserts utility templates delivered inside an open customer service window become chargeable in India from 1 Oct 2026, whereas Meta's official WhatsApp Business Platform pricing documentation states utility, marketing, and authentication messages inside customer service windows remain free of charge. Left as OPEN pending official source clarification.
   - Decision Item `(s)` (`docs/DECISIONS_OPEN.md`): "How is the parent's 24-hour service window opened before sending non-template voice notes?" (e.g. a quick-reply button on the first template, such as 'ऑडियो सुनें'). Marked `UNVERIFIED` / `OWNER-CONFIRM`. No solution designed.

---

## Gates Execution Evidence

### Gate 1: `python scripts/check_hindi_integrity.py`
```text
[HINDI INTEGRITY PASS] All docs UTF-8/NFC clean, zero orphan marks, zero unapproved banned terms, greetings consistent.
```
Exit code: `0`.

### Gate 2: `python scripts/check_state_hashes.py`
```text
[STATE HASH PASS] All 1 commit hash(es) and tagged references in docs/STATE.md verified successfully.
```
Exit code: `0`.

### Gate 3: `python scripts/check_invariants_sync.py`
```text
[INVARIANTS SYNC PASS] All 17 global invariants synchronized between AGENTS.md and 00_global_invariants.md.
```
Exit code: `0`.

### Gate 4: `python scripts/guardrails.py`
```text
=== Running Guardrails (Current Stage: S0) ===
  [PASS] Forbidden Patterns & Secrets
  [PASS] Hindi Integrity Check
  [PASS] State Hashes & Tags Check
  [PASS] Invariants Synchronization Check
  [PASS] Git Diff & Whitespace Check
  [SKIP] Fixture Hash Validation (fixtures/golden/manifest.json staged for S1)
  [SKIP] Test Count Integrity Check (docs/.test_count_baseline staged for S1)
  [SKIP] Time Hygiene Check (src/ application code staged for S2)
  [SKIP] Core Numerics Check (Core package staged for S2)
  [SKIP] Environment Hygiene Check (src/ application code staged for S2)
  [SKIP] Logging Hygiene Check (src/ application code staged for S2)

------------------------------------------------------------
PASSED 5 / SKIPPED 6 / FAILED 0
------------------------------------------------------------
```
Exit code: `0`.

### Gate 5: `ruff check .`
```text
All checks passed!
```
Exit code: `0`.

### Gate 6: `git diff --check stage-0-r6..HEAD`
```text
(No output)
```
Exit code: `0`.

### Gate 7: `git status --porcelain`
Evaluated after committing all S0-R7 changes. Output must be empty.
Exit code: `0`.

### Gate 8: Hard Boundary Check
`git diff --name-only stage-0-r6..HEAD | grep -E '^(src/|tests/|fixtures/|PROJECT_SPEC.md)'`
```text
(No output)
```
Exit code: `0`. Zero files touched in forbidden paths.
