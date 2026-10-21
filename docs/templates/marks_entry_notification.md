# Template: `marks_entry_notification`

## Status & Meta Classification
- **Engine Status:** **`APPROVED`** (Golden copy approved by Operator Decision 4, 2026-10-21).
- **Meta Category:** `Utility` (**`UNVERIFIED`** — Meta automated review outcome and category classification are subject to platform review algorithms per research rows **R-06** and **R-09**; do not claim approval).
- **Approval Outcome:** **`UNVERIFIED`** (Pre-submission draft).
- **Variable Density Risk:** **`UNVERIFIED`** (11 variable slots in body; Meta template review algorithms reject templates with excessive variable-to-text density).

---

## Template Specification & Constraints
- **Template Name:** `marks_entry_notification_v1`
- **Language:** Hindi (`hi`)
- **Header Type:** `None` (Text only, or optional `IMAGE` for scorecard PNG)
- **Constraint Compliance:**
  - Leading fixed text: `"प्रिय अभिभावक, "` (Variable is never first token).
  - Trailing fixed text: `" हैं।"` (Variable is never last token).
  - Body length limit: $\le 1024$ characters.
  - Variable length limit: $\le 40$ characters per variable.
  - No newlines in variable parameters.

---

## Approved Golden Body Text (Character-for-Character)
> "प्रिय अभिभावक, आरव (कक्षा 8-B) के यूनिट टेस्ट 1 (अंग्रेज़ी) में 50 में से 30 नंबर आए हैं (60.0%)। 18 उपस्थित बच्चों में आरव का रैंक 7 है। क्लास का औसत स्कोर 32.4 है। क्लास में सबसे ज़्यादा नंबर 47 हैं।"

---

## Raw Template Body with Placeholders
```text
प्रिय अभिभावक, {{1}} ({{2}}) के {{3}} ({{4}}) में {{5}} में से {{6}} नंबर आए हैं ({{7}})। {{8}} उपस्थित बच्चों में {{1}} का रैंक {{9}} है। क्लास का औसत स्कोर {{10}} है। क्लास में सबसे ज़्यादा नंबर {{11}} हैं।
```

### Parameter Mapping Table
| Variable Index | Domain Attribute | Golden Sample Value | Description |
| :---: | :--- | :--- | :--- |
| `{{1}}` | `child_name` | `आरव` | Student's display name |
| `{{2}}` | `class_section` | `कक्षा 8-B` | Cohort / class and section label |
| `{{3}}` | `test_name` | `यूनिट टेस्ट 1` | Name of the assessment |
| `{{4}}` | `subject` | `अंग्रेज़ी` | Academic subject assessed |
| `{{5}}` | `max_marks` | `50` | Maximum possible marks in subject |
| `{{6}}` | `marks` | `30` | Marks obtained by the child (Latin digits) |
| `{{7}}` | `percentage` | `60.0%` | Net percentage with 1 decimal |
| `{{8}}` | `present_count` | `18` | Total students present in cohort |
| `{{9}}` | `rank` | `7` | Standard competition rank |
| `{{10}}` | `class_average` | `32.4` | Arithmetic mean score of present cohort |
| `{{11}}` | `topper_marks` | `47` | Maximum score in present cohort |

---

## Fallback Shorter Variant (Reduced Variable Density)
If Meta automated review rejects the 11-variable template for high density:
```text
प्रिय अभिभावक, {{1}} ({{2}}) के {{3}} ({{4}}) में {{5}} में से {{6}} नंबर आए हैं ({{7}})। {{8}} उपस्थित बच्चों में {{1}} का रैंक {{9}} है।
```

---

## Absent Variant
See dedicated template: [`marks_entry_absent_notification.md`](marks_entry_absent_notification.md).
