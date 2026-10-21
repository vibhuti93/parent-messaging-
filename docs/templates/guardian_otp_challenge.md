# Template: `guardian_otp_challenge`

## Status & Meta Classification
- **Engine Status:** **`PROPOSED`** (Awaiting Operator Approval).
- **Meta Category:** `Authentication` (**`UNVERIFIED`** — Pre-submission draft).
- **Approval Outcome:** **`UNVERIFIED`**.
- **Purpose Gating:** Generated only during parent confirmation OTP challenge workflows (D-11, Stage S11).
- **Child Name Policy:** **EXEMPT** from the invariant requiring child and class/section tokens. Meta Authentication template rules strictly mandate predefined security text and passcodes, prohibiting recipient PII variables.

---

## Template Specification & Constraints
- **Template Name:** `guardian_otp_challenge_v1`
- **Language:** Hindi (`hi`)
- **Category:** `AUTHENTICATION`
- **Sub-type:** `ONE_TIME_PASSCODE`
- **Header:** None
- **Body:** Standard Meta OTP security copy
- **Button:** `COPY_CODE`

---

## Proposed Template Body with Placeholders
```text
{{1}} आपका सत्यापन कोड है। आपकी सुरक्षा के लिए, इस कोड को किसी के साथ साझा न करें।
```

### Parameter Mapping Table
| Variable Index | Domain Attribute | Sample Value | Description |
| :---: | :--- | :--- | :--- |
| `{{1}}` | `otp_code` | `482910` | Cryptographically random 6-digit numeric OTP |

### Buttons
- **Type:** `OTP` (`COPY_CODE`)
- **Text:** `कोड कॉपी करें` / `Copy Code`
