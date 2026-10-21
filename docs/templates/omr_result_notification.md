# Template: `omr_result_notification`

## Status & Meta Classification
- **Engine Status:** **`PROPOSED`** (Awaiting Operator Approval).
- **Meta Category:** `Utility` (**`UNVERIFIED`** — Category and approval status unverified; per **R-06** Meta may classify image-caption templates as Marketing if not strictly instructional).
- **Approval Outcome:** **`UNVERIFIED`** (Pre-submission draft).
- **Variable Density Risk:** **`UNVERIFIED`**.

---

## Template Specification & Constraints
- **Template Name:** `omr_result_notification_v1`
- **Language:** Hindi (`hi`)
- **Header Type:** `IMAGE` (Scorecard PNG image, max 5MB per **R-15**)
- **Constraint Compliance:**
  - Leading fixed text: `"प्रिय अभिभावक, "` (Variable is never first token).
  - Trailing fixed text: `" गए।"` (Variable is never last token).
  - Body length limit: $\le 1024$ characters.
  - Variable length limit: $\le 40$ characters per variable.
  - Preserves frozen OMR score-line string: `"कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)"`.

---

## Proposed Template Body with Placeholders
```text
प्रिय अभिभावक, {{1}} ({{2}}) के {{3}} में कुल नंबर: {{4}} में से {{5}} नंबर आए हैं ({{6}})। {{7}} उपस्थित बच्चों में {{1}} का रैंक {{8}} है। क्लास का औसत स्कोर {{9}} है। क्लास में सबसे ज़्यादा नंबर {{10}} हैं। सही जवाबों से मिले {{11}} नंबर, गलत जवाबों से {{12}} नंबर कट गए।
```

### Parameter Mapping Table
| Variable Index | Domain Attribute | Golden Sample Value (STU_01) | Description |
| :---: | :--- | :--- | :--- |
| `{{1}}` | `child_name` | `आरव` | Student's display name |
| `{{2}}` | `class_section` | `कक्षा 10-A` | Cohort / section label |
| `{{3}}` | `test_name` | `टर्म 1 डायग्नोस्टिक टेस्ट` | Name of the OMR exam |
| `{{4}}` | `max_marks` | `300` | Total maximum attainable marks |
| `{{5}}` | `net_marks` | `55` | Net marks earned (gross - bleed) |
| `{{6}}` | `net_percentage`| `18.3%` | Net percentage to 1 decimal |
| `{{7}}` | `present_count` | `16` | Present students in batch |
| `{{8}}` | `competition_rank`| `13` | Competition rank |
| `{{9}}` | `class_average` | `82.7` | Batch average net marks |
| `{{10}}` | `topper_marks` | `278` | Highest net score in batch |
| `{{11}}` | `gross_marks` | `80` | Marks from correct answers |
| `{{12}}` | `bleed_marks` | `25` | Marks deducted from wrong answers |

---

## Fallback Shorter Variant (Reduced Variable Density)
```text
प्रिय अभिभावक, {{1}} ({{2}}) के {{3}} में कुल नंबर: {{4}} में से {{5}} नंबर आए हैं ({{6}})। {{7}} उपस्थित बच्चों में {{1}} का रैंक {{8}} है। क्लास का औसत स्कोर {{9}} है।
```

---

## Absent Variant
See dedicated template: [`omr_absent_notification.md`](omr_absent_notification.md).
