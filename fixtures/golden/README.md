# Golden Fixtures (`fixtures/golden/`)

This directory contains the frozen golden fixtures for `omr_dispatch_engine` Stage S1.
All files are deterministically produced by `generate_fixtures.py` and locked by `manifest.json`.

## Fixture Inventory

1. `test_paper_300.json`: 75-question diagnostic examination (PHYSICS 1–25, CHEMISTRY 26–50, MATHS 51–75; +4/−1/0; max 300; synthetic bubble geometry).
2. `admissions_300.json`: 20-student roster (STU_01–STU_20) containing input attributes only (personalized names, sections, phone numbers, consent status, guardian verification status, and verified sibling flag).
3. `expected_contacts.json`: Expected contact quarantine and dispatch eligibility evaluations (reason codes: `INTERCEPTION_RISK_SAME_NUMBER`, `DUPLICATE_PARENT_UNVERIFIED`, `INVALID_PHONE_NUMBER`, consent/guardian exclusion reasons).
4. `submissions_300.json`: Materialized decoded responses for all 20 students (16 PRESENT, 4 ABSENT).
5. `expected_reports.json`: Frozen expected values for the 20-student OMR batch, containing exact arithmetic scores, ranks, bands, easy missed questions, and rendered parent messages.
6. `marks_entry_50.json`: 6-student manual marks entry assessment (English, Class 8-B, Max Marks 50) including half-marks and absence.
7. `expected_marks_reports.json`: Frozen expected metrics for the 6-student marks entry cohort.
8. `isolation_two_orgs.json`: Multi-tenant isolation fixture with overlapping roll numbers and identical parent phones across distinct schools.
9. `edge_cases.json`: Boundary conditions including all-wrong student (-25.0%), ties for first place, zero-present batches, single-student batches, percentage boundaries, and rounding-tie batch (49/4 = 12.25 -> 12.3).
10. `manifest.json`: Cryptographic SHA-256 integrity manifest for all fixture files.

## Invariants & Rules

- **Zero Float:** All scores and arithmetic are evaluated using integers, exact fractions, and decimal half-up quantization.
- **Numeric Representation Rule:**
  - Counts (enrolled, present, absent, attempted, correct, wrong, blank), integer marks (gross, bleed, net), and competition ranks remain JSON integers.
  - Every decimal value (percentages, averages, sums, half-marks, boundary percentages) is a JSON string with fixed decimal places:
    - `expected_reports.json`: batch metrics holds both exact rational class average `"82.6875"` and one-decimal display string `"82.7"`; student report holds table `"percentage": "18.33"` while the Hindi caption displays `"18.3%"`.
    - `expected_marks_reports.json`: holds sum `"109.5"`, average `"21.9"`, and topper `"47.0"`.
    - `edge_cases.json`: boundary percentages (`"29.99"`, `"30.0"`, `"60.0"`, `"60.01"`, `"-25.0"`, `"0.0"`) and rounding-tie average (`"12.25"` exact, `"12.3"` display) are strings.
- **Line Endings:** All files are strictly written with POSIX newline (`\n`). No CRLF (`\r\n`) line endings are permitted.
- **Input/Expected Separation:** `admissions_300.json` contains raw student inputs only. Expected quarantine flags, reason codes, and dispatch eligibility are segregated in `expected_contacts.json`.
- **Unicode NFC:** All text files are strictly encoded in Unicode Normalization Form C.
- **Latin Digits:** All numeric figures in messages use standard Latin numerals (0–9).
- **No Banned Vocabulary:** No user-facing text contains forbidden D-06 terms.
