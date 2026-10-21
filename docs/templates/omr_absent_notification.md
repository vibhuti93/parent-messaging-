# Template: `omr_absent_notification`

## Status & Meta Classification
- **Engine Status:** **`PROPOSED`** (Awaiting Operator Approval).
- **Meta Category:** `Utility` (**`UNVERIFIED`** — Pre-submission draft).
- **Approval Outcome:** **`UNVERIFIED`**.
- **Performance Neutrality (D-01, D-06):** Completely neutral; carries zero score, rank, or diagnostic evaluation.

---

## Template Specification & Constraints
- **Template Name:** `omr_absent_notification_v1`
- **Language:** Hindi (`hi`)
- **Header Type:** `IMAGE` (Neutral grey `#5F6368` scorecard card with "टेस्ट में अनुपस्थित" banner) or `None`
- **Constraint Compliance:**
  - Leading fixed text: `"प्रिय अभिभावक, "`
  - Trailing fixed text: `" रहे।"`
  - Body length limit: $\le 1024$ characters.

---

## Proposed Template Body with Placeholders
```text
प्रिय अभिभावक, {{1}} ({{2}}) {{3}} के टेस्ट में अनुपस्थित रहे। कुल {{4}} नंबर का टेस्ट आयोजित किया गया था जिसमें {{5}} बच्चे उपस्थित रहे।
```

### Parameter Mapping Table
| Variable Index | Domain Attribute | Golden Sample Value (STU_17) | Description |
| :---: | :--- | :--- | :--- |
| `{{1}}` | `child_name` | `रिया` | Student's display name |
| `{{2}}` | `class_section` | `कक्षा 10-A` | Cohort / section label |
| `{{3}}` | `test_name` | `टर्म 1 डायग्नोस्टिक टेस्ट` | Name of the assessment |
| `{{4}}` | `max_marks` | `300` | Total test maximum marks |
| `{{5}}` | `present_count` | `16` | Total students who attended |

---

## Fallback Shorter Variant
```text
प्रिय अभिभावक, {{1}} ({{2}}) {{3}} के टेस्ट में अनुपस्थित रहे।
```
