# Parent-Facing Message Catalog (`docs/message_catalog.md`)

This document enumerates every parent-facing WhatsApp notification message supported by `omr_dispatch_engine`.

## Mandatory Message Identity Invariants (Operator Decision 5)
1. **Fixed Leading Greeting:** Every message begins with a fixed leading greeting: `"प्रिय अभिभावक, "`.
2. **Child Name Position:** The child's display name (`child_display_name`) and class/section (`class_section`) appear immediately after the fixed leading greeting. The child's name is **never the first token** of the template body (complying with Meta template guidelines requiring fixed text before variables, per research row **R-09**).
3. **Roll Number Policy:** The student roll number is **not included in message text by default** (`include_roll_in_text=false`). It appears visually on the scorecard PNG image and printable A4 PTM slip PDF. If a school explicitly enables `include_roll_in_text=true`, the roll number is inserted alongside class/section.
4. **Gender-Neutral Wording:** Copy uses natural, respectful, gender-neutral Bolchal Hindi (e.g. `"{child_name} के ... नंबर आए हैं"`, `"अनुपस्थित रहे"`).
5. **Latin Digits:** All numbers, scores, ranks, and percentages strictly use Latin digits (`0-9`) per approved Operator Decision on ADR-0010.
6. **Vocabulary Compliance (D-06):** Banned terms are strictly prohibited (`ऋणात्मक अंकन`, `प्रतिशतता`, `प्राप्तांक`, `पूर्णांक`, `औसत मान`).
7. **Observable Facts Only:** Copy describes observable indicators only; no inferences of intent, laziness, or psychology. Absent messages carry zero score, rank, or performance framing.
8. **Exemptions from Child/Class Naming:** The invariant to name the child and class/section applies to all student academic and attendance notifications (`MARKS_ENTRY_PRESENT`, `OMR_PRESENT`, `OMR_ABSENT`, `MARKS_ENTRY_ABSENT`, `PTM_SLIP_TEXT`). It explicitly **does not apply** to:
   - **`GUARDIAN_OTP_CHALLENGE`** (Authentication category): Security passcodes for parent confirmation / consent verification. Meta's authentication template guidelines strictly restrict template bodies to one-time passcodes and security copy, forbidding arbitrary recipient PII variables.
   - **Follow-up Audio Notes** (Media payload): Voice notes use gender-neutral phrasing (`"आपके बच्चे"`) without spoken child names or classes (ADR-0010, S7); they are never sent standalone without the accompanying named text message.

---

## Master Message Types

| Message Type ID | Assessment Kind | Attendance | Status | Description |
| :--- | :--- | :--- | :---: | :--- |
| `MARKS_ENTRY_PRESENT` | `MARKS_ENTRY_TOTALS` | `PRESENT` | **`APPROVED`** | Single-subject teacher marks entry score report (Operator Decision 4). |
| `OMR_PRESENT` | `OMR_MCQ` | `PRESENT` | **`PROPOSED`** | Comprehensive OMR score report with frozen score-line string. |
| `OMR_ABSENT` | `OMR_MCQ` | `ABSENT` | **`PROPOSED`** | Factual absence notice for OMR exam with test context. |
| `MARKS_ENTRY_ABSENT` | `MARKS_ENTRY_TOTALS` | `ABSENT` | **`PROPOSED`** | Factual absence notice for marks entry exam with subject context. |
| `PTM_SLIP_TEXT` | Both (PTM-linked) | Any | **`PROPOSED`** | Invitation to parent-teacher consultation meeting. |
| `GUARDIAN_OTP_CHALLENGE` | N/A (Authentication) | N/A | **`PROPOSED`** | 6-digit OTP challenge for PTM confirmation (exempt from naming child/class). |

---

## 1. `MARKS_ENTRY_PRESENT` (Single-Subject Marks Entry)
* **Status:** **`APPROVED`** (Golden message mandated by Operator Decision 4, 2026-10-21).
* **Category:** Utility (subject to Meta approval; marked `UNVERIFIED`).
* **Approved Golden String (Character-for-Character):**
  > "प्रिय अभिभावक, आरव (कक्षा 8-B) के यूनिट टेस्ट 1 (अंग्रेज़ी) में 50 में से 30 नंबर आए हैं (60.0%)। 18 उपस्थित बच्चों में आरव का रैंक 7 है। क्लास का औसत स्कोर 32.4 है। क्लास में सबसे ज़्यादा नंबर 47 हैं।"

### Template Definition with Placeholders
```text
प्रिय अभिभावक, {child_name} ({class_section}) के {test_name} ({subject}) में {max_marks} में से {marks} नंबर आए हैं ({percentage})। {present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। क्लास का औसत स्कोर {class_average} है। क्लास में सबसे ज़्यादा नंबर {topper_marks} हैं।
```

### Template Variables
- `{{1}}`: `child_name` (e.g. `"आरव"`)
- `{{2}}`: `class_section` (e.g. `"कक्षा 8-B"`)
- `{{3}}`: `test_name` (e.g. `"यूनिट टेस्ट 1"`)
- `{{4}}`: `subject` (e.g. `"अंग्रेज़ी"`)
- `{{5}}`: `max_marks` (e.g. `"50"`)
- `{{6}}`: `marks` (e.g. `"30"` or `"28.5"`)
- `{{7}}`: `percentage` (e.g. `"60.0%"`)
- `{{8}}`: `present_count` (e.g. `"18"`)
- `{{9}}`: `rank` (e.g. `"7"`)
- `{{10}}`: `class_average` (e.g. `"32.4"`)
- `{{11}}`: `topper_marks` (e.g. `"47"`)

### Fallback Shorter Variant (for Length or Rate Throttling)
```text
प्रिय अभिभावक, {child_name} ({class_section}) के {test_name} ({subject}) में {max_marks} में से {marks} नंबर आए हैं ({percentage})। {present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है।
```

### With Optional Roll Number (`include_roll_in_text=true`)
```text
प्रिय अभिभावक, {child_name} (रोल नं. {roll_no}, {class_section}) के {test_name} ({subject}) में {max_marks} में से {marks} नंबर आए हैं ({percentage})। {present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। क्लास का औसत स्कोर {class_average} है। क्लास में सबसे ज़्यादा नंबर {topper_marks} हैं।
```

### Interactive Action Button (Decision s)
- **Quick-Reply Action Button:** `"ऑडियो सुनें"` (`Listen to Audio`)
- **Payload:** `ACTION_LISTEN_AUDIO`
- **Purpose:** Outbound template action button. When tapped by guardian, sends an inbound interaction opening the 24-hour customer service window required for subsequent audio voice note delivery.

---

## 2. `OMR_PRESENT` (OMR Diagnostic Scorecard Caption)
* **Status:** **`PROPOSED`** (Awaiting Operator Approval).
* **Category:** Utility (image header with scorecard PNG).
* **Alignment:** Preserves already-frozen OMR golden score-line string (`"कुल नंबर: 300 में से 55 नंबर आए हैं (18.3%)"`) and embeds the mandatory greeting, child name, and class/section.

### Proposed Template Definition
```text
प्रिय अभिभावक, {child_name} ({class_section}) के {test_name} में कुल नंबर: {max_marks} में से {net_marks} नंबर आए हैं ({net_percentage})। {present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। क्लास का औसत स्कोर {class_average} है। क्लास में सबसे ज़्यादा नंबर {topper_marks} हैं। सही जवाबों से मिले {gross_marks} नंबर, गलत जवाबों से {bleed_marks} नंबर कट गए।
```

### Golden Sample Values (STU_01):
- `child_name`: `"आरव"`
- `class_section`: `"कक्षा 10-A"`
- `test_name`: `"टर्म 1 डायग्नोस्टिक टेस्ट"`
- `max_marks`: `"300"`
- `net_marks`: `"55"`
- `net_percentage`: `"18.3%"`
- `present_count`: `"16"`
- `rank`: `"13"`
- `class_average`: `"82.7"`
- `topper_marks`: `"278"`
- `gross_marks`: `"80"`
- `bleed_marks`: `"25"`

### Fallback Shorter Variant (Concise OMR Caption)
```text
प्रिय अभिभावक, {child_name} ({class_section}) के {test_name} में कुल नंबर: {max_marks} में से {net_marks} नंबर आए हैं ({net_percentage})। {present_count} उपस्थित बच्चों में {child_name} का रैंक {rank} है। क्लास का औसत स्कोर {class_average} है।
```

### Interactive Action Button (Decision s)
- **Quick-Reply Action Button:** `"ऑडियो सुनें"` (`Listen to Audio`)
- **Payload:** `ACTION_LISTEN_AUDIO`
- **Purpose:** Outbound template action button. When tapped by guardian, sends an inbound interaction opening the 24-hour customer service window required for subsequent audio voice note delivery.

---

## 3. `OMR_ABSENT` (OMR Test Absence Notification)
* **Status:** **`PROPOSED`** (Awaiting Operator Approval).
* **Category:** Utility (no performance color, neutral grey `#5F6368` card).
* **Rule:** Strictly factual; carries no score, rank, or negative framing.

### Proposed Template Definition
```text
प्रिय अभिभावक, {child_name} ({class_section}) {test_name} के टेस्ट में अनुपस्थित रहे। कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।
```

### Golden Sample Values (STU_17):
- `child_name`: `"रिया"`
- `class_section`: `"कक्षा 10-A"`
- `test_name`: `"टर्म 1 डायग्नोस्टिक टेस्ट"`
- `max_marks`: `"300"`
- `present_count`: `"16"`

### Fallback Shorter Variant
```text
प्रिय अभिभावक, {child_name} ({class_section}) {test_name} के टेस्ट में अनुपस्थित रहे।
```

---

## 4. `MARKS_ENTRY_ABSENT` (Marks Entry Absence Notification)
* **Status:** **`PROPOSED`** (Awaiting Operator Approval).
* **Category:** Utility.
* **Rule:** Strictly factual; carries no score, rank, or negative framing.

### Proposed Template Definition
```text
प्रिय अभिभावक, {child_name} ({class_section}) {test_name} ({subject}) के टेस्ट में अनुपस्थित रहे। कुल {max_marks} नंबर का टेस्ट आयोजित किया गया था जिसमें {present_count} बच्चे उपस्थित रहे।
```

### Sample Values:
- `child_name`: `"आरव"`
- `class_section`: `"कक्षा 8-B"`
- `test_name`: `"यूनिट टेस्ट 1"`
- `subject`: `"अंग्रेज़ी"`
- `max_marks`: `"50"`
- `present_count`: `"18"`

### Fallback Shorter Variant
```text
प्रिय अभिभावक, {child_name} ({class_section}) {test_name} ({subject}) के टेस्ट में अनुपस्थित रहे।
```

---

## 5. `PTM_SLIP_TEXT` (PTM Consultation Invitation)
* **Status:** **`PROPOSED`** (Awaiting Operator Approval).
* **Category:** Utility.
* **Rule:** Generated only for assessments carrying the `PTM_LINKED` purpose flag.

### Proposed Template Definition
```text
प्रिय अभिभावक, {child_name} ({class_section}) के शैक्षणिक प्रदर्शन पर चर्चा हेतु आपको आगामी अभिभावक-शिक्षक बैठक (PTM) में सादर आमंत्रित किया जाता है। तारीख: {ptm_date}, समय: {ptm_time}।
```

### Sample Values:
- `child_name`: `"आरव"`
- `class_section`: `"कक्षा 8-B"`
- `ptm_date`: `"24-10-2026"`
- `ptm_time`: `"प्रातः 10:00 बजे"`

### Fallback Shorter Variant
```text
प्रिय अभिभावक, {child_name} ({class_section}) के लिए आगामी अभिभावक-शिक्षक बैठक (PTM) में सादर आमंत्रित किया जाता है। तारीख: {ptm_date}।
```

---

## 6. `GUARDIAN_OTP_CHALLENGE` (Parent Confirmation OTP)
* **Status:** **`PROPOSED`** (Awaiting Operator Approval).
* **Category:** Authentication (Meta WhatsApp Authentication Template).
* **Name Exemption:** **EXEMPT** from child and class/section naming invariants. Meta's strict authentication template specification restricts body content to one-time passcodes and standard security guidance, completely prohibiting recipient PII variables.

### Proposed Template Definition
```text
{{1}} आपका सत्यापन कोड है। आपकी सुरक्षा के लिए, इस कोड को किसी के साथ साझा न करें।
```

### Template Variables
- `{{1}}`: `otp_code` (e.g. `"482910"`)

### Button
- Copy Code button: `Copy Code` / `कोड कॉपी करें`

---

## Message Types in Catalog Lacking Child Name & Class
Per release verification and privacy invariants, only the following message artifacts in the system lack explicit child name and class/section tokens:
1. **`GUARDIAN_OTP_CHALLENGE`**: Standard authentication template message delivering 6-digit verification passcodes. Lacks student name and class due to Meta WhatsApp Authentication category restrictions.
2. **Recorded Token Audio Note (`voice_note_script_hi`)**: Companion voice note payload delivering spoken diagnostics. Uses gender-neutral phrasing (`"आपके बच्चे"`) without spoken child name or class (ADR-0010, S7). It is strictly delivered inside the 24-hour service window as an optional extra or quoted reply to the primary named text message, and never dispatched standalone.
3. **Interactive Audio Action Button (`AUDIO_QUICK_REPLY_BUTTON_HI`)**: Standard quick-reply action button labeled `"ऑडियो सुनें"` attached to outbound scorecard templates for Decision (s) service window initiation. Does not contain student PII.
