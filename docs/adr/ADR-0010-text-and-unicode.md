# ADR-0010: Text Processing, Unicode Normalization, and Script Digit Policy

## Status
`ACCEPTED` (Accepted by operator, 2026-10-20. Digit-style decision recorded in `docs/DECISIONS_OPEN.md`, item 8.)

## Context
The parent communication engine operates primarily in conversational Bolchal Hindi (D-06). Devanagari script text contains complex grapheme clusters: combining vowel signs (matras, e.g. `ि`, `ी`), nuktas (`़`), and viramas (`्`).
Naive string operations (such as Python `text[:50]`) break grapheme clusters mid-character, rendering corrupt text on parents' mobile phones. Furthermore, student names from legacy school spreadsheets arrive in inconsistent Unicode encodings (decomposed NFD vs precomposed NFC).
Finally, there is an open design question regarding whether numbers in parent-facing Hindi messages should display in Latin digits (`0-9`) or Devanagari digits (`०-९`).

## Options Considered

### Option 1: Raw String Slicing and Arbitrary Unicode Normalization
- *Description*: Use standard Python `[:N]` string slicing and pass through raw spreadsheet strings.
- *Pros*: No preprocessing.
- *Cons*: Broken matras and invalid Devanagari rendering on WhatsApp; character count mismatches against WhatsApp template limits (1024 body limit).

### Option 2: Unicode NFC Normalization, Grapheme-Safe Truncation, and Explicit Digit Policy
- *Description*:
  - **NFC Normalization:** Ingested student/parent names and generated Hindi text are immediately normalized to Unicode Normalization Form C (`unicodedata.normalize('NFC', text)`).
  - **Grapheme-Safe Truncation:** Truncation operations respect extended grapheme cluster boundaries (using regex `\X` or equivalent boundary parser), ensuring a base consonant is never separated from its matra.
  - **Name Fallback:** If a parent/student name is missing or contains only invalid characters, fallback to respectful generic salutation ("अभिभावक जी" / "विद्यार्थी").
  - **Digit Policy (`OWNER-CONFIRM`):**
    - *Proposal*: Use **Latin digits (`0, 1, 2, ... 9`)** for all parent-facing text, scorecards, percentages, and voice notes.
    - *Rationale*: In modern Indian Hindi education contexts, Latin numerals are universally recognized and taught across state and central boards. Devanagari numerals (`०, १, २, ... ९`) cause confusion for parents unfamiliar with older script notations, especially in percentage and time notations ("18.3%", "20:30 IST").
  - **Sorting:** Deterministic, locale-independent sorting by Unicode code point for internal lists and audit trails.
- *Pros*: Flawless mobile rendering; zero broken Hindi characters; high readability for diverse parent demographics.
- *Cons*: Slight overhead for grapheme-aware string length calculations.

## Proposed Decision
We propose **Option 2 (Unicode NFC Normalization, Grapheme-Safe Truncation, and Latin Digits)**.

### Digit Policy Proposal (`OWNER-CONFIRM`)
- All numbers in parent text, scorecards, and PTM slips use Latin digits: `"कुल नंबर: 300 में से 55 नंबर"`, `"18.3%"`, `"20:30 IST"`.
- Recorded as an open confirmation item in `docs/DECISIONS_OPEN.md`.

## Consequences
- **Positive**: Eliminates rendering bugs in Devanagari text; guarantees compliance with WhatsApp character limit constraints; universal parent comprehension.
- **Negative**: String truncation utilities must be tested against edge cases (viramas, conjuncts).
- **Neutral**: Enforced in Stage S4.

## Revisit When
Revisit if an institutional partner specifically mandates Devanagari numerals in formal printed A4 PTM slips.
