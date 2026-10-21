# Template: `marks_entry_absent_notification`

## Status & Meta Classification
- **Engine Status:** **`PROPOSED`** (Awaiting Operator Approval).
- **Meta Category:** `Utility` (**`UNVERIFIED`** — Pre-submission draft).
- **Approval Outcome:** **`UNVERIFIED`**.
- **Performance Neutrality (D-01, D-06):** Completely neutral; carries zero score, rank, or diagnostic evaluation.

---

## Template Specification & Constraints
- **Template Name:** `marks_entry_absent_notification_v1`
- **Language:** Hindi (`hi`)
- **Header Type:** `None`
- **Constraint Compliance:**
  - Leading fixed text: `"प्रिय अभिभावक, "`
  - Trailing fixed text: `" रहे।"`
  - Body length limit: $\le 1024$ characters.

---

## Proposed Template Body with Placeholders
```text
प्रिय अभिभावक, {{1}} ({{2}}) {{3}} ({{4}}) के टेस्ट में अनुपस्थित रहे। कुल {{5}} नंबर का टेस्ट आयोजित किया गया था जिसमें {{6}} बच्चे उपस्थित रहे।
```

### Parameter Mapping Table
| Variable Index | Domain Attribute | Sample Value | Description |
| :---: | :--- | :--- | :--- |
| `{{1}}` | `child_name` | `आरव` | Student's display name |
| `{{2}}` | `class_section` | `कक्षा 8-B` | Cohort / section label |
| `{{3}}` | `test_name` | `यूनिट टेस्ट 1` | Name of assessment |
| `{{4}}` | `subject` | `अंग्रेज़ी` | Academic subject assessed |
| `{{5}}` | `max_marks` | `50` | Maximum possible marks in subject |
| `{{6}}` | `present_count` | `18` | Total students who attended |

---

## Fallback Shorter Variant
```text
प्रिय अभिभावक, {{1}} ({{2}}) {{3}} ({{4}}) के टेस्ट में अनुपस्थित रहे।
```
