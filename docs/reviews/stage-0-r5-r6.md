# Stage S0-R5/R6 Independent Review Report

**Review Date:** 2026-10-21  
**Reviewer:** Independent Reviewer Agent  
**Governing Rules:** `AGENTS.md`, `PROJECT_SPEC.md`, `docs/prompt_pack/W2_review.md`  
**Target Scope:** `git diff stage-0-r4..stage-0-r6` and current repository state  
**Commits Inspected:**  
- Base Tag (`stage-0-r4`): `5e8377d43f206609c71ac4d2ed67bcd1f13f3ec9`  
- Target Tag (`stage-0-r6`): `8f59ebda2fcf46e52bb76da2c2abdb02c89b4600` (amended from `0b90ac594fb34646cf9e61c126b5a27c5a103279`)  
- Branch: `agent-run`  

---

## Executive Summary

| Check # | Check Topic | Status | Summary of Evidence |
| :---: | :--- | :---: | :--- |
| **1** | Scope Compliance | **PASS** | Exactly 38 files changed between `stage-0-r4` and `stage-0-r6`. All are docs, templates, and prompt-pack files. `docs/prompt_pack/S5.md` is unchanged. Zero application code (`src/`), zero fixtures (`fixtures/`), zero tests (`tests/`). |
| **2** | Frozen Values Integrity | **PASS** | `PROJECT_SPEC.md` (D-01 to D-14) diff is completely empty (0 lines changed). The 20-student OMR golden table in `docs/prompt_pack/S1.md` (lines 6–39) is bit-for-bit unchanged. |
| **3** | Marks-Entry Fixture Recomputation | **PASS** | Independently recomputed all 6 students, bands, ranks, averages, and percentages in `docs/prompt_pack/S1.md` using exact fractions and decimal rounding against D-01. ME_01 and ME_03 (60.0%) correctly classify as YELLOW per D-01 (30.0%–60.0% inclusive). |
| **4** | ADR Status & Section Completeness | **PASS** | Only ADR-0003, ADR-0007, ADR-0010 are `ACCEPTED` (per operator sign-off). ADR-0014 is `PROPOSED`. ADR-0016 to ADR-0020 are `PROPOSED`. All 20 ADRs contain all 5 required structural sections with $\ge 2$ options considered. |
| **5** | Contradiction Analysis | **PASS** | Side-by-side comparison of ADR-0016–0020 and amended stage prompts against D-01–D-14 and operator decisions 1–8 and mandates 1–5. Zero unapproved contradictions found. All non-OMR and multi-tenant extensions are either operator mandates or tracked under `OWNER-CONFIRM` in `docs/DECISIONS_OPEN.md`. |
| **6** | Message Rules Compliance | **PASS** | All messages in `docs/message_catalog.md` and `docs/templates/*.md` place greeting first, followed immediately by child name and class; use Latin digits; contain no banned D-06 terms; use gender-neutral phrasing; omit scores for absent students; and explicitly exempt OTP templates. |
| **7** | External & Meta Claims Sourcing | **PASS** | All Meta behaviour statements cite verified research rows (R-01 to R-15) or `docs/research/provider_contract.json` error codes (131048, 131056). All unverified items (onboarding, partner billing, webhook path) are explicitly marked `UNVERIFIED`. |
| **8** | Multi-Tenancy & Credential Rules | **PASS** | Global invariants 15 to 17 are defined in `docs/prompt_pack/00_global_invariants.md`. Every stage prompt requires explicit `org_id` on repository calls, CLI commands, and services; global credentials and shared phone numbers are strictly prohibited. |
| **9** | Tooling & Verification | **PASS** | `ruff check .` exited with code 0. `python scripts/guardrails.py` exited with code 0. |

**Overall Verdict: PASS**  
Zero BLOCKER findings. Zero MAJOR findings. Four MINOR findings (whitespace hygiene, root AGENTS.md mirror update, STATE.md commit hash string, unstaged operator edits in working tree).

---

## Detailed Findings by Check

### 1. Scope Compliance

**Status:** **PASS**

**Requirement:** Only docs, templates, and prompt-pack files changed; `docs/prompt_pack/S5.md` unchanged; no application code, fixtures, or tests.

**Evidence:**
- Command executed:
  ```bash
  git diff --name-status stage-0-r4..stage-0-r6
  ```
- Output (38 files changed):
  ```text
  M	docs/DECISIONS_OPEN.md
  M	docs/PRE_DEPLOYMENT_CHECKLIST.md
  M	docs/STATE.md
  M	docs/adr/ADR-0002-numeric-semantics.md
  M	docs/adr/ADR-0003-identifiers-and-keys.md
  M	docs/adr/ADR-0007-persistence-and-storage.md
  M	docs/adr/ADR-0010-text-and-unicode.md
  M	docs/adr/ADR-0014-dependencies-and-supply-chain.md
  A	docs/adr/ADR-0016-assessment-model.md
  A	docs/adr/ADR-0017-tenancy-model.md
  A	docs/adr/ADR-0018-application-service-layer-and-security.md
  A	docs/adr/ADR-0019-per-school-sender-identity-and-routing.md
  A	docs/adr/ADR-0020-tenant-lifecycle-and-controls.md
  M	docs/adr/README.md
  M	docs/architecture_decisions.md
  M	docs/data_map.md
  M	docs/domain_glossary.md
  A	docs/message_catalog.md
  M	docs/prompt_pack/00_global_invariants.md
  M	docs/prompt_pack/S1.md
  M	docs/prompt_pack/S10.md
  M	docs/prompt_pack/S11.md
  M	docs/prompt_pack/S12.md
  M	docs/prompt_pack/S13.md
  M	docs/prompt_pack/S2.md
  M	docs/prompt_pack/S3.md
  M	docs/prompt_pack/S4.md
  M	docs/prompt_pack/S6.md
  M	docs/prompt_pack/S7.md
  M	docs/prompt_pack/S8.md
  M	docs/prompt_pack/S9.md
  A	docs/prompt_pack/W2_review.md
  A	docs/templates/guardian_otp_challenge.md
  A	docs/templates/marks_entry_absent_notification.md
  A	docs/templates/marks_entry_notification.md
  A	docs/templates/omr_absent_notification.md
  A	docs/templates/omr_result_notification.md
  A	docs/templates/ptm_invitation.md
  ```
- Check for `S5.md`:
  ```bash
  git diff stage-0-r4..stage-0-r6 -- docs/prompt_pack/S5.md
  # Exited with code 0, 0 lines output (unchanged).
  ```
- Check for code, fixture, and test paths:
  ```bash
  git diff --name-only stage-0-r4..stage-0-r6 | grep -E '^(src/|tests/|fixtures/)'
  # Exited with code 0, 0 lines output.
  ```
- All 38 changed files are strictly inside `docs/`, `docs/adr/`, `docs/prompt_pack/`, or `docs/templates/`.
- **Note on working tree:** Unstaged modifications exist in the working directory for `docs/research/official_source_verification.md` (R-07 confidence updated from HIGH to MEDIUM), `pyproject.toml`, and `uv.lock` (adding dev dependencies `mypy` and `pre-commit`). Per the reviewer role instructions ("Do NOT fix anything and do not edit any file except docs/reviews/stage-0-r5-r6.md"), these files were left untouched.

---

### 2. Frozen Values Integrity

**Status:** **PASS**

**Requirement:** The 20-student OMR golden table and decisions D-01 to D-14 are unchanged versus `stage-0-r4`. Show diff command and output.

**Evidence:**
1. **D-01 to D-14 (`PROJECT_SPEC.md`):**
   ```bash
   git diff stage-0-r4..stage-0-r6 -- PROJECT_SPEC.md
   ```
   **Output:** (empty; exit code 0).
   The frozen specification in `PROJECT_SPEC.md` lines 12–46 (D-01 to D-14) is completely identical to `stage-0-r4`.

2. **20-Student OMR Golden Table (`docs/prompt_pack/S1.md`):**
   ```bash
   git diff stage-0-r4..stage-0-r6 -- docs/prompt_pack/S1.md
   ```
   **Output:**
   ```diff
   diff --git a/docs/prompt_pack/S1.md b/docs/prompt_pack/S1.md
   index e8660f7..f531fe2 100644
   --- a/docs/prompt_pack/S1.md
   +++ b/docs/prompt_pack/S1.md
   @@ -6,7 +6,7 @@
    
    **Golden exam** (`test_paper_300.json`): 75 questions, IDs 1–75. Q1–25 PHYSICS, Q26–50 CHEMISTRY, Q51–75 MATHS. +4 correct, −1 wrong, 0 blank. `correct_option = ["A","B","C","D"][(q−1) % 4]`. Synthetic 800×600 geometry (fixture-only): `col=(q−1)//15`, `row=(q−1)%15`, `col_x=30+col*150`, `center_y=255+row*17`, option centre x = `col_x+35+opt_index*24`.
    
   -**Roster and responses** (`admissions_300.json`, `submissions_300.json`): `STU_01`–`STU_20`, one submission each; 16 PRESENT (01–16), 4 ABSENT (17–20, empty responses). Materialise every response in JSON. Wrong answer = next option in A→B→C→D→A order after the key.
   +**Roster and responses** (`admissions_300.json`, `submissions_300.json`): `STU_01`–`STU_20`, one submission each; 16 PRESENT (01–16), 4 ABSENT (17–20, empty responses). Roster includes `child_display_name` and `class_section` without altering any frozen score value. Materialise every response in JSON. Wrong answer = next option in A→B→C→D→A order after the key.
    - STU_01: Q1–10 ✓; Q11–20 ✗; Q21–25 blank; Q26–30 ✓; Q31–45 ✗; Q46–50 blank; Q51–55 ✓; Q56–75 blank.
    - STU_02: Q1–70 ✓; Q71–72 ✗; Q73–75 blank.
    - STU_03: Q1–23 ✓; Q26–27 ✗; rest blank.
   @@ -39,10 +39,28 @@ Batch: enrolled 20, present 16, absent 4; class average `1323/16 = 82.6875`; top
    
    Subject labels (D-03): STU_01 Physics `ACCURACY_BLEED`, Chemistry `ACCURACY_BLEED`, Maths `CONCEPTUAL_SPEED_GAP`. STU_02 all `MASTERY_ZONE`. STU_03 Physics `MASTERY_ZONE`, Chemistry `FOUNDATIONAL_CRISIS`, Maths `NO_ATTEMPT`. STU_04 Physics/Chemistry `MASTERY_ZONE`, Maths `NO_ATTEMPT`. STU_05–13 Physics `MASTERY_ZONE`, others `NO_ATTEMPT`. STU_14–16 all `NO_ATTEMPT`. ABSENT: no subject labels.
    
   +**Marks Entry Golden Fixture** (`marks_entry_50.json`, `expected_marks_reports.json`):
   +6 students, Class 8-B, English (Max Marks 50):
   +- ME_01: Aarav, PRESENT, marks 30.0 (60.0%), rank 2 (tie), band YELLOW (D-01 threshold: 30.0%–60.0% inclusive)
   +- ME_02: Priya, PRESENT, marks 47.0 (94.0%), rank 1 (topper), band GREEN (> 60.0%)
   +- ME_03: Rohan, PRESENT, marks 30.0 (60.0%), rank 2 (tie), band YELLOW (D-01 threshold: 30.0%–60.0% inclusive)
   +- ME_04: Ananya, PRESENT, marks 2.5 (5.0%), rank 4, band RED (< 30.0%)
   +- ME_05: Vikram, PRESENT, marks 0.0 (0.0%), rank 5, band RED (< 30.0%)
   +- ME_06: Meera, ABSENT, marks null, band ABSENT
   +Batch: enrolled 6, present 5, absent 1; sum 109.5, average 21.9, topper 47.0.
   +
   +**Two-Org Isolation Fixture** (`isolation_two_orgs.json`):
   +Org Alpha and Org Beta with overlapping roll numbers (`01`), identical parent phone numbers across orgs with different student identities, verifying strict tenant isolation.
   +
   +**Golden Caption & Rendering Expectations:**
   +- STU_01 (OMR): Caption includes greeting, child name, and class/section enclosing frozen score line `"कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)"`.
   +- STU_05 and STU_06 (verified siblings sharing parent number `9811122288`): Captions must differ by child name.
   +- Direct template-rendering test: Approved MARKS_ENTRY message rendered with Decision 4 sample values as a direct data object matches character-for-character.
   +
    **Edge-case fixture** (`edge_cases.json`, separate from the 20-student golden set): an all-wrong student (net −75 → −25.00 %, RED), a tie-for-first pair, a zero-present batch, and a one-student batch. Percentage boundary values (29.99, 30.0, 60.0, 60.01) are tested at classifier level on raw percentages, since integer marks over 300 can't hit every boundary.
    
    **Manifest:** `manifest.json` with fixture version and SHA-256 hashes. A generator may only reproduce approved bytes. `tests/oracle.py` may contain a minimal, test-local scorer used only for cross-checking arithmetic invariants; it shares no code with `src/`.
    
   -**Tests** (`tests/test_stage1_golden_contract.py`): 75 unique questions/300 max; 20 unique IDs, 16/4 split, one-to-one mapping; per-question accuracy properties; STU_01 arithmetic and missed set; STU_02/03/04 scores; valid option values; contact/consent cases match the contract; hashes match the manifest; every literal above matches `expected_reports.json`.
   +**Tests** (`tests/test_stage1_golden_contract.py`): 75 unique questions/300 max; 20 unique IDs, 16/4 split, one-to-one mapping; per-question accuracy properties; STU_01 arithmetic and missed set; STU_02/03/04 scores; valid option values; contact/consent cases match the contract; marks entry 6-student fixture properties; two-org isolation fixture properties; golden caption and direct template-rendering tests; hashes match the manifest; every literal above matches `expected_reports.json`.
    
    **Gate 1:** `pytest -q tests/test_stage1_golden_contract.py`; report command, exit code, actual test count. 🧑 Human signs off the frozen manifest hash in `docs/STATE.md`.
   ```
- Every question, response, score, gross marks, bleed deductions, net score, percentage, rank, PTM trigger, easy question missed, and subject diagnostic label for `STU_01` through `STU_20` is bit-for-bit unchanged.
- The single edit to line 9 merely clarifies that `child_display_name` and `class_section` are present in roster data without altering any score values.

---

### 3. Marks-Entry Fixture Recomputation

**Status:** **PASS**

**Requirement:** Independently recompute every band, rank, average, and percentage in the marks-entry fixture against D-01 (`30.0%` to `60.0%` inclusive is YELLOW).

**Specification Rules (D-01, D-04, D-05):**
- Total Maximum Marks: $50$
- Percentage formula: $\frac{\text{marks}}{\text{max\_marks}} \times 100$
- Status Band thresholds (D-01):
  - $< 30.0\% \implies \text{RED}$
  - $30.0\% \le \text{percentage} \le 60.0\% \implies \text{YELLOW}$
  - $> 60.0\% \implies \text{GREEN}$
  - Absent student $\implies \text{ABSENT}$ (marks, percentage, and rank are null)
- Standard Competition Rank (D-04): $1 + \text{count}(\text{present students with strictly higher marks})$.

**Independent Python Recomputation Script:**
```python
from decimal import Decimal
from fractions import Fraction

max_marks = Fraction(50, 1)
students = [
    ("ME_01", "Aarav", True, Fraction(30, 1)),
    ("ME_02", "Priya", True, Fraction(47, 1)),
    ("ME_03", "Rohan", True, Fraction(30, 1)),
    ("ME_04", "Ananya", True, Fraction(5, 2)),  # 2.5
    ("ME_05", "Vikram", True, Fraction(0, 1)),
    ("ME_06", "Meera", False, None),
]

present = [s for s in students if s[2]]
total_sum = sum(s[3] for s in present)
avg = total_sum / len(present)
topper = max(s[3] for s in present)

print(
    f"Enrolled: {len(students)}, Present: {len(present)}, Absent:"
    f" {len(students)-len(present)}"
)
print(
    f"Sum: {float(total_sum)}, Average: {float(avg)}, Topper: {float(topper)}"
)

for sid, name, is_present, marks in students:
  if not is_present:
    print(
        f"{sid} ({name}): ABSENT, marks=None, pct=None, rank=None, band=ABSENT"
    )
    continue
  pct = (marks / max_marks) * 100
  band = "RED" if pct < 30 else ("YELLOW" if pct <= 60 else "GREEN")
  rank = 1 + sum(1 for other in present if other[3] > marks)
  print(
      f"{sid} ({name}): marks={float(marks):.1f}, pct={float(pct):.1f}%,"
      f" rank={rank}, band={band}"
  )
```

**Execution Output:**
```text
Enrolled: 6, Present: 5, Absent: 1
Sum: 109.5, Average: 21.9, Topper: 47.0
ME_01 (Aarav): marks=30.0, pct=60.0%, rank=2, band=YELLOW
ME_02 (Priya): marks=47.0, pct=94.0%, rank=1, band=GREEN
ME_03 (Rohan): marks=30.0, pct=60.0%, rank=2, band=YELLOW
ME_04 (Ananya): marks=2.5, pct=5.0%, rank=4, band=RED
ME_05 (Vikram): marks=0.0, pct=0.0%, rank=5, band=RED
ME_06 (Meera): ABSENT, marks=None, pct=None, rank=None, band=ABSENT
```

**Comparison with `docs/prompt_pack/S1.md` Lines 44–50:**
- `ME_01`: Aarav, PRESENT, marks 30.0 (60.0%), rank 2 (tie), band YELLOW $\implies$ **EXACT MATCH** (Confirmed: $60.0\% \le 60.0\%$ belongs in YELLOW, correcting S0-R5 finding F1).
- `ME_02`: Priya, PRESENT, marks 47.0 (94.0%), rank 1 (topper), band GREEN $\implies$ **EXACT MATCH** ($94.0\% > 60.0\%$).
- `ME_03`: Rohan, PRESENT, marks 30.0 (60.0%), rank 2 (tie), band YELLOW $\implies$ **EXACT MATCH** ($60.0\% \le 60.0\%$).
- `ME_04`: Ananya, PRESENT, marks 2.5 (5.0%), rank 4, band RED $\implies$ **EXACT MATCH** ($5.0\% < 30.0\%$).
- `ME_05`: Vikram, PRESENT, marks 0.0 (0.0%), rank 5, band RED $\implies$ **EXACT MATCH** ($0.0\% < 30.0\%$).
- `ME_06`: Meera, ABSENT, marks null, band ABSENT $\implies$ **EXACT MATCH**.
- Batch Summary: Enrolled 6, present 5, absent 1; sum 109.5, average 21.9, topper 47.0 $\implies$ **EXACT MATCH**.

---

### 4. ADR Status & Section Completeness

**Status:** **PASS**

**Requirement:**
- Only ADR-0003, ADR-0007, ADR-0010 (and ADR-0014 only if recorded as operator-accepted) are `ACCEPTED`.
- ADR-0016 to ADR-0020 are `PROPOSED`.
- Every ADR has Context, Options (at least two), Proposed decision, Consequences, and Revisit when.

**Evidence:**
1. **ADR Status Verification (all 20 ADR files in `docs/adr/`):**
   - `ADR-0001`: `PROPOSED`
   - `ADR-0002`: `PROPOSED`
   - `ADR-0003`: `ACCEPTED (modified)` (Operator accepted 2026-10-20; single-school scope updated by operator multi-tenant mandate)
   - `ADR-0004`: `PROPOSED`
   - `ADR-0005`: `PROPOSED`
   - `ADR-0006`: `PROPOSED`
   - `ADR-0007`: `ACCEPTED` (Operator accepted 2026-10-20)
   - `ADR-0008`: `PROPOSED`
   - `ADR-0009`: `PROPOSED`
   - `ADR-0010`: `ACCEPTED` (Operator accepted 2026-10-20; Latin digits)
   - `ADR-0011`: `PROPOSED`
   - `ADR-0012`: `PROPOSED`
   - `ADR-0013`: `PROPOSED`
   - `ADR-0014`: `PROPOSED` (Not marked accepted)
   - `ADR-0015`: `PROPOSED`
   - `ADR-0016`: `PROPOSED`
   - `ADR-0017`: `PROPOSED`
   - `ADR-0018`: `PROPOSED`
   - `ADR-0019`: `PROPOSED`
   - `ADR-0020`: `PROPOSED`

   *Conclusion on Status:* Exactly three ADRs are `ACCEPTED` (ADR-0003, ADR-0007, ADR-0010). ADR-0014 is `PROPOSED`. ADR-0016 through ADR-0020 are strictly `PROPOSED`. Matches `docs/adr/README.md` and `docs/STATE.md`.

2. **Structural Sections Check:**
   Every ADR from `ADR-0001` through `ADR-0020` was parsed programmatically for the five mandatory headers:
   - `## Context`: Present in all 20 ADRs.
   - `## Options Considered`: Present in all 20 ADRs.
   - Count of distinct options:
     - ADR-0001: 3 options
     - ADR-0002: 6 options / representations
     - ADR-0003: 3 options
     - ADR-0004: 3 options
     - ADR-0005: 3 options
     - ADR-0006: 3 options
     - ADR-0007: 3 options
     - ADR-0008: 3 options
     - ADR-0009: 3 options
     - ADR-0010: 3 options
     - ADR-0011: 3 options
     - ADR-0012: 3 options
     - ADR-0013: 3 options
     - ADR-0014: 3 options
     - ADR-0015: 3 options
     - ADR-0016: 3 options
     - ADR-0017: 7 options (physical, schema-per-tenant, shared DB + RLS, etc.)
     - ADR-0018: 3 options
     - ADR-0019: 3 options
     - ADR-0020: 3 options
     (All $\ge 2$ options).
   - `## Proposed Decision`: Present in all 20 ADRs.
   - `## Consequences`: Present in all 20 ADRs.
   - `## Revisit When`: Present in all 20 ADRs.

---

### 5. Contradiction Analysis

**Status:** **PASS**

**Requirement:** Compare ADR-0016 to ADR-0020 and amended stage prompts against D-01 to D-14 and operator decisions; quote both sides for each conflict, or list what was compared.

**Items Compared Side-by-Side:**
1. **ADR-0016 (Assessment Model) vs. D-01 (Status Bands) & D-05 (Arithmetic):**
   - *D-01 Rule:* `< 30.0%` RED; `30.0%–60.0%` inclusive YELLOW; `> 60.0%` GREEN.
   - *ADR-0016 Section 4 Matrix:* "D-01 Status Band: RED (<30%), YELLOW (30–60%), GREEN (>60%), ABSENT."
   - *Comparison:* In full alignment. The boundary was specifically corrected in S0-R6 so that $60.0\%$ maps to YELLOW.
2. **ADR-0016 vs. D-02 (Easy Questions) & D-03 (Subject Diagnostics):**
   - *D-02 / D-03 Rules:* Require item-level bubble accuracy and response maps.
   - *ADR-0016 Section 4 Matrix:* Evaluates availability by `AssessmentKind`. For `OMR_MCQ`, both are `Available`. For `MARKS_ENTRY_TOTALS`, item-level diagnostics are explicitly marked `NOT_AVAILABLE` and omitted from student-facing output (no guessing or fabricated item data).
   - *Comparison:* Conforms to Fail Closed (Invariant 13) and observable indicators only (Invariant 14).
3. **ADR-0016 vs. D-04 (Rank & PTM):**
   - *D-04 Rule:* "PTM slip required iff ABSENT, or RED, or rank > floor(0.75 * present_count)."
   - *ADR-0016 Section 4:* "Available (if PTM-linked)| Generated only if assessment has is_ptm_linked=True. (OWNER-CONFIRM)".
   - *Open Decision Tracking:* Recorded in `docs/DECISIONS_OPEN.md` item (f) tagged `OWNER-CONFIRM`. ADR-0016 does not unilaterally alter D-04; it proposes scoping PTM slips to PTM-linked exams, pending operator confirmation.
4. **ADR-0017 (Tenancy Model) vs. Operator Decision 1 & ADR-0003:**
   - *Operator Decision 1 (2026-10-21):* "Multi-School Hosted Service from Inception. The platform is designed from inception as a multi-school hosted service."
   - *ADR-0017 Proposed Decision:* Shared PostgreSQL database and schema with mandatory `org_id` on every table, tenant-scoped repositories, and PostgreSQL Row-Level Security (RLS).
   - *ADR-0003 Status:* Updated to `ACCEPTED (modified)` referencing ADR-0017.
   - *Comparison:* Direct implementation of operator mandate.
5. **ADR-0018 (Service Layer) vs. Invariants 15–17 & Operator Decision 5:**
   - *Invariants 15–17:* Mandatory `org_id` context; no global credentials; masked child display names in logs.
   - *ADR-0018 Proposed Decision:* Pure application service use-case functions taking `SecurityContext(org_id, actor_type, actor_id)`, verifying tenant authorization before executing domain logic.
   - *Comparison:* Exact alignment.
6. **ADR-0019 (Sender Identity) vs. Operator Decision 2 & D-09:**
   - *Operator Decision 2 (2026-10-21):* "Each school uses its own dedicated WhatsApp Business Phone Number. There is no shared number across schools."
   - *ADR-0019 Proposed Decision:* Models `SenderIdentity` entity holding `waba_id`, `phone_number_id`, and secret references per organization.
   - *Comparison:* Exact alignment.
7. **ADR-0020 (Tenant Lifecycle) vs. D-10 (Schedule) & D-13 (Retention):**
   - *D-10 / D-13 Rules:* Dispatch scheduling in `Asia/Kolkata`; 90-day retention for message logs.
   - *ADR-0020 Proposed Decision:* Deficit Weighted Round-Robin (DWRR) fair scheduling honoring per-sender rate limits within the D-10 delivery windows; tenant offboarding and deletion workflows enforcing D-13.
   - *Comparison:* Exact alignment.
8. **Amended Stage Prompts (S1–S13) vs. Operator Mandates 1–5:**
   - S1 adds marks entry and two-org isolation fixtures without touching the 20-student OMR golden table.
   - S2 adds fractional marks parsing (`Fraction`) and `MARKS_ENTRY_TOTALS` input contracts.
   - S3 wires assessment entity into `evaluate_batch`.
   - S4 references `docs/message_catalog.md` and enforces child name / class invariants.
   - S6 adds child name/class to PNG/PDF headers.
   - S7 documents token count and keeps recordings neutral.
   - S8 enforces tenant-scoped repository calls with `org_id`.
   - S9 enforces per-sender credential resolution and demultiplexing.
   - S10 enforces fair scheduling across tenants.
   - S11 scopes QR confirmation per org and sender.
   - S12 wraps service layer and requires `--org-id` on CLI.
   - S13 lists missing org context, cross-tenant data leaks, and missing child name as release blockers.
   - *Comparison:* All prompt amendments are strictly aligned with the operator mandates.

*Conclusion:* Zero contradictions found.

---

### 6. Message Rules Compliance

**Status:** **PASS**

**Requirement:** Every message in `docs/message_catalog.md` and `docs/templates/*.md` has:
1. Greeting first (`"प्रिय अभिभावक, "`).
2. Child name and class immediately after greeting.
3. Latin digits (`0-9`).
4. No banned D-06 terms (`ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, `औसत मान`).
5. No gendered verb forms.
6. No score for absent students.
7. Explicit OTP exemption.

**Evidence:**
1. **Greeting and Child Name Placement:**
   - `MARKS_ENTRY_PRESENT`: `"प्रिय अभिभावक, {child_name} ({class_section}) के..."` (Greeting first, child name and class/section follow immediately).
   - `OMR_PRESENT`: `"प्रिय अभिभावक, {child_name} ({class_section}) के {test_name} में कुल नंबर:..."` (Greeting first, child name and class/section follow immediately; preserves frozen score line `"कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)"`).
   - `OMR_ABSENT`: `"प्रिय अभिभावक, {child_name} ({class_section}) {test_name} के टेस्ट में अनुपस्थित रहे।..."` (Greeting first, child name and class/section follow immediately).
   - `MARKS_ENTRY_ABSENT`: `"प्रिय अभिभावक, {child_name} ({class_section}) {test_name} ({subject}) के टेस्ट में अनुपस्थित रहे।..."` (Greeting first, child name and class/section follow immediately).
   - `PTM_SLIP_TEXT`: `"प्रिय अभिभावक, {child_name} ({class_section}) के शैक्षणिक प्रदर्शन पर चर्चा हेतु..."` (Greeting first, child name and class/section follow immediately).
2. **Latin Digits Policy (D-10, ADR-0010):**
   - Zero Devanagari numerals (`[०-९]`) found in `docs/message_catalog.md` or any template under `docs/templates/`.
   - All numbers, percentages, dates, and times use standard ASCII Latin numerals (`0-9`), e.g., `50 में से 30 नंबर आए हैं (60.0%)`, `रैंक 7`, `32.4`, `10:00 बजे`.
3. **Banned Vocabulary (D-06):**
   - Verified that neither `ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, nor `औसत मान` appears in any message template body or sample text.
   - (Occurrences in `docs/message_catalog.md` line 11 are solely in the normative rule statement explicitly forbidding them).
4. **Gender-Neutral Verb Forms:**
   - Verbs used across all templates are gender-neutral plural honorifics or impersonal passives:
     - `नंबर आए हैं` (score arrived)
     - `कट गए` (were deducted)
     - `मिले` (were received)
     - `उपस्थित रहे` / `अनुपस्थित रहे` (honorific neutral plural)
     - `आमंत्रित किया जाता है` (impersonal passive invitation)
   - Zero gendered third-person forms (`रहा है` / `रही है`, `आया` / `आई`, `किया` / `की` referring to student).
5. **Absence Messages (Zero Score / Rank):**
   - `OMR_ABSENT` template: `"प्रिय अभिभावक, {child_name} ({class_section}) {test_name} के टेस्ट में अनुपस्थित रहे। कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।"`
   - `MARKS_ENTRY_ABSENT` template: `"प्रिय अभिभावक, {child_name} ({class_section}) {test_name} ({subject}) के टेस्ट में अनुपस्थित रहे। कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।"`
   - Contains zero student marks, zero student percentage, zero student rank, and zero performance judgment. The `{max_marks}` variable denotes the total paper maximum marks for the cohort, not a student score.
6. **OTP Exemption:**
   - Explicitly documented in `docs/message_catalog.md` lines 13–17, 28, 174, and 191; `docs/templates/guardian_otp_challenge.md` lines 8–9; `docs/prompt_pack/S4.md` line 14; and `docs/prompt_pack/S13.md` line 4.
   - Meta WhatsApp Authentication Template regulations strictly forbid recipient PII variables in OTP templates.

---

### 7. External & Meta Claims Sourcing

**Status:** **PASS**

**Requirement:** Any statement about Meta behaviour must have a corresponding row in `docs/research/official_source_verification.md` or `provider_contract.json`. Unverified items must be marked `UNVERIFIED`.

**Evidence:**
1. **Verified Claims Cited with Source Rows:**
   - Phone display name, Quality rating & FLAGGED state $\implies$ Cited research row **R-04**.
   - Per-message utility & authentication pricing $\implies$ Cited research row **R-05**.
   - Template category rules & automated review reclassifications $\implies$ Cited research rows **R-06** and **R-09**.
   - 250 daily message starting tier $\implies$ Cited research row **R-10**.
   - Rate limit throttle errors `131048` and `131056` $\implies$ Cited research row **R-10** and verified in `docs/research/provider_contract.json` lines for codes `131048` (spam limit hit) and `131056` (pair rate limit exceeded).
   - Webhook signature verification via app secret HMAC-SHA256 $\implies$ Cited research row **R-14**.
2. **Unverified Claims Explicitly Marked and Gated:**
   - Meta Partner Tech Provider multi-business onboarding architecture $\implies$ Marked **`UNVERIFIED`** in ADR-0019 Section 5, tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md` item `P-07`.
   - Meta direct billing vs. consolidated invoicing $\implies$ Marked **`UNVERIFIED`** in ADR-0019 Section 5 and `docs/DECISIONS_OPEN.md` item (k), tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md` item `P-08`.
   - Template category approval outcome for marks entry and OMR caption $\implies$ Marked **`UNVERIFIED`** in `docs/templates/*.md` and `docs/message_catalog.md`.
   - Webhook demultiplexing JSON path `entry[].changes[].value.metadata.phone_number_id` $\implies$ Marked **`UNVERIFIED`** in `docs/prompt_pack/S9.md` with explicit instruction to verify against recorded contract fixtures.

---

### 8. Multi-Tenancy & Credential Rules

**Status:** **PASS**

**Requirement:** Global invariants 15 to 17 exist; no stage prompt allows a global credential or a repository call without an org context.

**Evidence:**
1. **Global Invariants 15 to 17 Definition:**
   `docs/prompt_pack/00_global_invariants.md` lines 24–26 explicitly defines:
   ```markdown
   15. Every repository call requires an explicit org context (`org_id`); calls without an org context must fail closed.
   16. No global credentials or shared phone-number IDs; every provider call resolves credentials from the calling org's sender identity.
   17. Child names (`child_display_name`) and class/section labels are never logged in application logs.
   ```
2. **Stage Prompts Verification:**
   - **`S8.md` (Persistence):** "Tenant-scoped durable repositories: every repository call requires an explicit org context (`org_id`); calls without an org context must fail closed."
   - **`S8.md` (Idempotency):** `sha256(f"{org_id}:{student_id}:{assessment_id}:{purpose}:{channel}:{event_type}")`.
   - **`S9.md` (Provider Dispatch):** "Every provider call resolves credentials, `phone_number_id`, and sender configuration strictly from the calling org's `SenderIdentity` (ADR-0019); no global access token or shared phone-number ID exists."
   - **`S10.md` (Scheduling):** "Daily message cap pacing and multi-tenant fair scheduling (ADR-0019, ADR-0020): respect per-sender daily message limits and enforce fair scheduling across tenants."
   - **`S11.md` (Parent Confirmation):** "Scoped strictly per org (`org_id`) and per sender (`sender_id`)... sent to the verified guardian contact using the calling org sender's registered WhatsApp identity."
   - **`S12.md` (Service Layer & CLI):** "The CLI is a thin wrapper over the service layer; every CLI command requires an explicit `--org-id` parameter. CLI commands without an explicit `--org-id` fail closed with an exit code of 2 and an error message."
   - **`S13.md` (Release Verification Blockers):** "any repository call without an org context; any global credential or global phone-number ID; cross-tenant data visible in isolation tests..."
3. **Absence of Global Credentials in Prompts:**
   Every prompt uniformly rejects global provider credentials, requiring multi-tenant resolution from the organization's `SenderIdentity`.

---

### 9. Tooling & Verification

**Status:** **PASS**

**Requirement:** Run `ruff` and `scripts/guardrails.py`; report exit codes.

**Execution Commands & Outputs:**

1. **Ruff Check:**
   ```powershell
   ruff check .
   ```
   - **Exit Code:** `0`
   - **Output:**
     ```text
     All checks passed!
     ```

2. **Pre-Commit Guardrails:**
   ```powershell
   python scripts/guardrails.py
   ```
   - **Exit Code:** `0`
   - **Output:**
     ```text
     === Running W3 & Foundation Guardrails ===
     [FIXTURE GUARD] fixtures/golden/manifest.json not present yet (S1 pending) -> SKIPPED
     [TEST INTEGRITY] docs/.test_count_baseline not found -> SKIPPED (staged for S1)
     [TIME HYGIENE] No application source files in src/ yet -> SKIPPED
     [CORE NUMERICS] Core package not present yet -> SKIPPED (ADR-0002 staged)
     [ENV HYGIENE] No non-settings source files in src/ yet -> SKIPPED (ADR-0009 staged)
     [LOGGING HYGIENE] No application source files in src/ yet -> SKIPPED (ADR-0008 staged)
     [GUARDRAIL PASS] All pre-commit guardrails satisfied.
     ```

3. **Git Diff Hygiene Check (Supplemental Review Tool):**
   ```powershell
   git diff --check stage-0-r4..stage-0-r6
   ```
   - **Exit Code:** `1` (Identified minor markdown whitespace occurrences; detailed below in Minor Findings).

---

## Findings by Severity

### BLOCKER Findings
*None.*

### MAJOR Findings
*None.*

### MINOR Findings

1. **Markdown Formatting & Trailing Whitespace (Git Diff Check):**
   - **File & Line References:**
     - `docs/adr/ADR-0002-numeric-semantics.md` lines 77–109, 111, 112, 116 (trailing spaces on section text and worked examples).
     - `docs/adr/ADR-0017-tenancy-model.md` line 73.
     - `docs/architecture_decisions.md` lines 5, 6.
     - New blank lines at EOF in `docs/PRE_DEPLOYMENT_CHECKLIST.md` (line 72), `docs/data_map.md` (line 229), `docs/domain_glossary.md` (line 150), and `docs/message_catalog.md` (line 193).
   - **Impact:** Formatting only; does not affect parsing, schemas, or guardrails.

2. **Mirroring Global Invariants 15–17 into Repo-Root `AGENTS.md`:**
   - **File & Line References:** `AGENTS.md` lines 16–24 vs. `docs/prompt_pack/00_global_invariants.md` lines 24–26.
   - **Details:** `00_global_invariants.md` has added Invariants 15, 16, and 17 (per Stage S0-R5/R6 prompt pack updates) with the comment `# Part C — Global Invariants (paste into AGENTS.md / CLAUDE.md)`. The root `AGENTS.md` currently ends at Invariant 14.
   - **Impact:** The stage prompt pack is authoritative for prompt construction, but operator or next session should mirror items 15–17 into root `AGENTS.md`.

3. **Commit Hash String in `docs/STATE.md`:**
   - **File & Line References:** `docs/STATE.md` lines 9 and 54.
   - **Details:** `docs/STATE.md` lists stage tag `stage-0-r6` commit hash as `0b90ac594fb34646cf9e61c126b5a27c5a103279`. In the git history, this commit was amended to `8f59ebda2fcf46e52bb76da2c2abdb02c89b4600` (which is where the `stage-0-r6` tag currently points).
   - **Impact:** Informational only.

4. **Unstaged Working Tree Edits:**
   - **Files:** `docs/research/official_source_verification.md`, `pyproject.toml`, `uv.lock`.
   - **Details:** The working tree contains uncommitted changes adjusting row R-07 confidence (HIGH to MEDIUM) and adding `mypy` and `pre-commit` to `[dependency-groups]`. These are not part of the committed `stage-0-r6` tag.
   - **Impact:** Informational; left untouched per reviewer instructions.

---

## Review Verdict

**OVERALL VERDICT: PASS**

The changes between `stage-0-r4` and `stage-0-r6` strictly respect all stage boundary constraints, frozen golden arithmetic and tables, ADR status policies, message formatting invariants, Meta claim sourcing requirements, and multi-tenant credential isolation rules. The repository is ready to proceed to human sign-off for Stage 1.
