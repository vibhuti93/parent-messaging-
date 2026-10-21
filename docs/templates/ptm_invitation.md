# Template: `ptm_invitation`

## Status & Meta Classification
- **Engine Status:** **`PROPOSED`** (Awaiting Operator Approval).
- **Meta Category:** `Utility` (**`UNVERIFIED`** — Pre-submission draft).
- **Approval Outcome:** **`UNVERIFIED`**.
- **Purpose Gating:** Generated only when an assessment carries the `PTM_LINKED` purpose flag.

---

## Template Specification & Constraints
- **Template Name:** `ptm_invitation_v1`
- **Language:** Hindi (`hi`)
- **Header Type:** `DOCUMENT` (Optional A4 PTM slip PDF attachment) or `None`
- **Constraint Compliance:**
  - Leading fixed text: `"प्रिय अभिभावक, "`
  - Trailing fixed text: `" जाता है।"` (or date/time fixed text)
  - Body length limit: $\le 1024$ characters.

---

## Proposed Template Body with Placeholders
```text
प्रिय अभिभावक, {{1}} ({{2}}) के शैक्षणिक प्रदर्शन पर चर्चा हेतु आपको आगामी अभिभावक-शिक्षक बैठक (PTM) में सादर आमंत्रित किया जाता है। तारीख: {{3}}, समय: {{4}}।
```

### Parameter Mapping Table
| Variable Index | Domain Attribute | Sample Value | Description |
| :---: | :--- | :--- | :--- |
| `{{1}}` | `child_name` | `आरव` | Student's display name |
| `{{2}}` | `class_section` | `कक्षा 8-B` | Cohort / section label |
| `{{3}}` | `ptm_date` | `24-10-2026` | Date of the PTM (Latin digits) |
| `{{4}}` | `ptm_time` | `प्रातः 10:00 बजे` | Scheduled time of consultation |

---

## Fallback Shorter Variant
```text
प्रिय अभिभावक, {{1}} ({{2}}) के लिए आगामी अभिभावक-शिक्षक बैठक (PTM) में सादर आमंत्रित किया जाता है। तारीख: {{3}}।
```
