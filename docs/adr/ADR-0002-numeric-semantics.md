# ADR-0002: Numeric Semantics, Exact Fractions, and Integer Arithmetic

## Status
`PROPOSED`

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
   - Threshold check: `55 * 100 = 5500`; `300 * 30 = 9000`. `5500 < 9000` $ightarrow$ **RED**.
   - Display quantization: `Decimal('5500') / Decimal('300') = 18.333...` $ightarrow$ **`"18.3%"`**.
2. **Boundary Example (80 out of 300 marks):**
   - `net = 80`, `max = 300`.
   - Exact percentage: `8000 / 300 = 26.666666...%`.
   - Threshold check: `8000 < 9000` $ightarrow$ **RED**.
   - Display quantization: `26.666...` with `ROUND_HALF_UP` $ightarrow$ **`"26.7%"`**.
3. **High Scorer (278 out of 300 marks):**
   - `net = 278`, `max = 300`.
   - Exact percentage: `27800 / 300 = 92.666666...%`.
   - Threshold check: `278 * 100 = 27800`; `300 * 60 = 18000`. `27800 > 18000` $ightarrow$ **GREEN**.
   - Display quantization: `92.666...` with `ROUND_HALF_UP` $ightarrow$ **`"92.7%"`**.
4. **Exact 30.0% Boundary (90 out of 300 marks):**
   - `net = 90`, `max = 300`.
   - Threshold check: `90 * 100 = 9000`; `300 * 30 = 9000`. `9000 >= 9000` and `9000 <= 18000` $ightarrow$ **YELLOW**.
   - Display quantization: **`"30.0%"`**.
5. **Exact 60.0% Boundary (180 out of 300 marks):**
   - `net = 180`, `max = 300`.
   - Threshold check: `180 * 100 = 18000`; `300 * 60 = 18000`. `18000 <= 18000` (inclusive boundary per D-01) $ightarrow$ **YELLOW**.
   - Display quantization: **`"60.0%"`**.
6. **Negative Net Score (Gross 10, Bleed 25 -> Net -15 out of 300 marks):**
   - `net = -15`, `max = 300`.
   - Threshold check: `-15 * 100 = -1500 < 9000` $ightarrow$ **RED**.
   - Display quantization: `Decimal('-1500') / Decimal('300') = -5.0` $ightarrow$ **`"-5.0%"`**.
   - Voice note script uses explicit "minus" token per D-08.

## Consequences
- **Positive**: Zero risk of floating-point classification errors; perfect alignment with frozen spec rules D-01, D-02, D-05.
- **Negative**: Developers cannot casually use `/` division in core code; all arithmetic must use integer ops or `Fraction`.
- **Neutral**: Enforced via pre-commit guardrail `no_float_in_core`.

## Revisit When
Revisit only if fractional marking schemes (e.g. 0.33 marks per question) are approved by the operator in a future version.
