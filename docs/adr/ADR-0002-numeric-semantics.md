# ADR-0002: Numeric Semantics, Exact Fractions, and Integer Arithmetic

## Status
`ACCEPTED`

## Context
Scoring academic examinations and categorizing student performance into high-stakes bands (RED, YELLOW, GREEN) requires absolute mathematical precision.
In IEEE 754 floating-point arithmetic (`float`), binary representation errors accumulate (e.g., `0.1 + 0.2 != 0.3`). A boundary case such as 29.999999999999996% vs. 30.00% can cause an erroneous status band classification (e.g. placing a student in RED instead of YELLOW), triggering unnecessary mandatory PTM slips and parental distress.

## Options Considered

### Option 1: Standard Python `float`
- *Description*: Use native `float` for marks, ratios, and percentages.
- *Pros*: Standard syntax, native operators.
- *Cons*: Precision loss; non-deterministic equality checks on boundary values (e.g. 0.75 accuracy threshold); unacceptable for examination scoring.

### Option 2: `decimal.Decimal` Everywhere
- *Description*: Use `Decimal` objects for all marks, sums, and percentages.
- *Pros*: Decimal representation matches human arithmetic.
- *Cons*: Division (e.g. `Decimal(1) / Decimal(3)`) requires configuring arbitrary precision contexts and rounding modes, which can still produce subtle rounding inaccuracies prior to final comparison.

### Option 3: Integer Marks, `fractions.Fraction` for Ratios, Cross-Multiplication for Comparisons, `Decimal` ROUND_HALF_UP for Display
- *Description*:
  - Positive, negative, gross, bleed, and net marks are stored as exact integers (`int`).
  - Ratios (attempt ratio, accuracy ratio, percentage ratio) are computed and preserved as `fractions.Fraction`.
  - Boundary threshold comparisons are executed via **integer cross-multiplication** (zero division, zero floating-point error).
  - Human-facing percentage strings are generated at presentation time using `decimal.Decimal` with explicit `ROUND_HALF_UP` to exactly one decimal place.
  - **Strict rule: No `float` permitted in the core package.**
- *Pros*: Mathematically exact; 100% immune to precision loss; exact boundary classification.
- *Cons*: Requires converting numbers to `Fraction` when evaluating ratio thresholds.

## Proposed Decision
We propose **Option 3 (Integer Marks, Exact Fractions, Cross-Multiplication, Decimal Display)**.

### Mathematical Invariants
1. Marks: `gross: int`, `bleed: int`, `net: int = gross - bleed`.
2. Percentage Ratio: `percentage_ratio = Fraction(net, max_positive_marks)`.
3. Threshold Comparisons via Integer Cross-Multiplication:
   - Status Band RED: `net / max_marks < 30 / 100` $\iff$ `net * 100 < max_marks * 30`.
   - Status Band YELLOW: `30 / 100 <= net / max_marks <= 60 / 100` $\iff$ `net * 100 >= max_marks * 30 and net * 100 <= max_marks * 60`.
   - Status Band GREEN: `net / max_marks > 60 / 100` $\iff$ `net * 100 > max_marks * 60`.
   - Easy Question Accuracy: `correct / present >= 75 / 100` $\iff$ `correct * 100 >= present * 75` (or `correct * 4 >= present * 3`).
4. Display Formatting:
   - `Decimal(str(Fraction(net * 100, max_positive_marks))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)` or `(net * 100 / max_positive_marks)` converted to string via exact decimal arithmetic.

### Worked Examples
1. **STU_01 (55 out of 300 marks):**
   - `net = 55`, `max = 300`.
   - Exact ratio: `Fraction(55, 300) = Fraction(11, 60)`.
   - Percentage: `55 * 100 / 300 = 5500 / 300 = 18.333333...%`.
   - Threshold check: `55 * 100 = 5500`; `300 * 30 = 9000`. `5500 < 9000` $
ightarrow$ **RED**.
   - Display quantization: `Decimal('5500') / Decimal('300') = 18.333...` $
ightarrow$ **`"18.3%"`**.
2. **Boundary Example (80 out of 300 marks):**
   - `net = 80`, `max = 300`.
   - Exact percentage: `8000 / 300 = 26.666666...%`.
   - Threshold check: `8000 < 9000` $
ightarrow$ **RED**.
   - Display quantization: `26.666...` with `ROUND_HALF_UP` $
ightarrow$ **`"26.7%"`**.
3. **High Scorer (278 out of 300 marks):**
   - `net = 278`, `max = 300`.
   - Exact percentage: `27800 / 300 = 92.666666...%`.
   - Threshold check: `278 * 100 = 27800`; `300 * 60 = 18000`. `27800 > 18000` $
ightarrow$ **GREEN**.
   - Display quantization: `92.666...` with `ROUND_HALF_UP` $
ightarrow$ **`"92.7%"`**.
4. **Exact 30.0% Boundary (90 out of 300 marks):**
   - `net = 90`, `max = 300`.
   - Threshold check: `90 * 100 = 9000`; `300 * 30 = 9000`. `9000 >= 9000` and `9000 <= 18000` $
ightarrow$ **YELLOW**.
   - Display quantization: **`"30.0%"`**.
5. **Exact 60.0% Boundary (180 out of 300 marks):**
   - `net = 180`, `max = 300`.
   - Threshold check: `180 * 100 = 18000`; `300 * 60 = 18000`. `18000 <= 18000` (inclusive boundary per D-01) $
ightarrow$ **YELLOW**.
   - Display quantization: **`"60.0%"`**.
6. **Negative Net Score (Gross 10, Bleed 25 -> Net -15 out of 300 marks):**
   - `net = -15`, `max = 300`.
   - Threshold check: `-15 * 100 = -1500 < 9000` $
ightarrow$ **RED**.
   - Display quantization: `Decimal('-1500') / Decimal('300') = -5.0` $
ightarrow$ **`"-5.0%"`**.
   - Voice note script uses explicit "minus" token per D-08.

### S0-R5 Amendment: Fractional Marks (Half Marks) in Manual Marks Entry
Per Stage S0-R5, teacher marks entry (`MARKS_ENTRY_TOTALS`) permits fractional half marks (multiples of `0.5`, e.g. `0.5`, `2.5`).

#### Representation Proposal
We evaluate two exact representations for half marks:
1. **Option A: Exact `fractions.Fraction`:** Store marks directly as `Fraction(numerator, 2)` (e.g. `Fraction(5, 2)` for 2.5, `Fraction(1, 2)` for 0.5). Integer marks are represented as `Fraction(n, 1)` or `int`.
2. **Option B: Integer Mark-Units (Scaled Integers):** Store marks as integer half-mark units (`mark_units = int(round(marks * 2))`). Every integer mark is 2 units; 0.5 marks = 1 unit; 2.5 marks = 5 units. Max marks is also scaled: `max_units = max_marks * 2`. Threshold comparisons remain pure integer arithmetic: `net_units * 100 < max_units * 30`.

**Recommendation:** `fractions.Fraction` is proposed as the primary domain type (`int | Fraction`), with scaled integer mark-units supported internally for high-performance comparisons. Floating-point `float` remains strictly forbidden in the core package.

#### Worked Examples with Fractional Marks
7. **Fractional Mark: 2.5 out of 10 marks:**
   - `net = Fraction(5, 2)`, `max = 10`.
   - Scaled units check: `net_units = 5`, `max_units = 20`.
   - Threshold comparison: `5 * 100 = 500`; `20 * 30 = 600`. `500 < 600` -> **RED**.
   - Exact percentage: `Fraction(5, 2) / 10 * 100 = Fraction(500, 20) = 25.0%`.
   - Display quantization: `Decimal('25.0')` -> **`"25.0%"`**.
8. **Fractional Mark: 0.5 out of 50 marks:**
   - `net = Fraction(1, 2)`, `max = 50`.
   - Scaled units check: `net_units = 1`, `max_units = 100`.
   - Threshold comparison: `1 * 100 = 100`; `100 * 30 = 3000`. `100 < 3000` -> **RED**.
   - Exact percentage: `Fraction(1, 2) / 50 * 100 = Fraction(100, 100) = 1.0%`.
   - Display quantization: `Decimal('1.0')` -> **`"1.0%"`**.
9. **All-Wrong Negative Net Score (-75 out of 300 marks, Edge Case Fixture):**
   - Exam: 75 questions, all answered incorrectly.
   - `gross = 0`, `bleed = 75 * 1 = 75`, `net = 0 - 75 = -75`, `max = 300`.
   - Exact ratio: `Fraction(-75, 300) = Fraction(-1, 4)`.
   - Threshold check: `-75 * 100 = -7500 < 300 * 30 = 9000` -> **RED**.
   - Display quantization: `Decimal('-7500') / Decimal('300') = -25.0` -> **`"-25.0%"`**.
   - Golden values: Matches edge case fixture `edge_cases.json` exactly.

*Golden OMR Invariant:* Frozen OMR golden values (`expected_reports.json`) are completely unaffected because all OMR questions and scores in the frozen dataset remain exact integers (+4/-1).

## Consequences
- **Positive**: Supports half-marks in manual marks entry without precision loss; preserves strict zero-float rule in core; supports negative scores down to -75.
- **Negative**: Core arithmetic functions must accept `int | Fraction` for marks.
- **Neutral**: Enforced via pre-commit guardrail `no_float_in_core`.

## Revisit When
Revisit if non-half-mark fractions (e.g. 0.33, 0.25) are introduced by a future examination board.
