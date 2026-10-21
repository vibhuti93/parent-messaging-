# ADR-0015: Data Classification, Masking, and Retention Lifecycle

## Status
`ACCEPTED`

## Context
The engine processes sensitive academic performance data and contact coordinates of minor students in India.
Under emerging Indian data privacy principles (including the Digital Personal Data Protection Act, 2023), handling minor data requires strict purpose limitation, data minimization, privacy notices, parental consent verification, and automatic retention purging.
We need an architectural policy defining how data fields are categorized, logged, retained, and purged.

## Options Considered

### Option 1: Ad-hoc Field Handling
- *Description*: Store and log fields as needed without explicit classification or lifecycle rules.
- *Pros*: Zero design overhead.
- *Cons*: Violates privacy invariants; risks leaking student scores or phone numbers in logs; non-compliant.

### Option 2: Formal Data Classification Tiers and Lifecycle Management
- *Description*:
  - **Classification Tiers:** Classify all data into three explicit tiers:
    1. *Operational / System Data*: Timestamps, batch IDs, question metadata, error classes.
    2. *Confidential Educational Data*: Raw marks, answers, diagnostic classifications, ranks, scorecard images.
    3. *Sensitive Personal Information (PII)*: Student names, parent/guardian phone numbers, consent records, OTP tokens, QR confirmation secrets.
  - **Comprehensive Data Map:** Establish `docs/data_map.md` enumerating every stored or logged field, its PII category, purpose, retention rule, and logging policy.
  - **Retention Rules (D-13 Development Defaults):**
    - Scans, scorecard PNGs, PDF slips, audio notes: Retained for the **current academic year**.
    - Message logs, delivery events, audit logs: Retained for **90 days**, strictly masked.
  - **Deletion & Purging:** Automated CLI `purge` command enforcing retention limits; immediate cascade deletion on verified parental consent revocation.
  - **Log Masking Policy:** PII fields are **never** logged in the clear; phone numbers masked as `+91 98*** **321`; tokens masked as `tok_***`; scores masked in production logs.
- *Pros*: Strict privacy-by-design; audit-ready; clear engineering boundaries.
- *Cons*: Requires maintaining `docs/data_map.md` and implementing purge jobs.

## Proposed Decision
We propose **Option 2 (Formal Data Classification Tiers, Data Map, and Retention Lifecycle)**.

### Summary Data Map Reference
All stored and logged fields are formally registered in [docs/data_map.md](../data_map.md).

## Consequences
- **Positive**: Complete compliance with `AGENTS.md` Rule 8–10; robust safeguards against accidental data leakage; automated lifecycle management.
- **Negative**: Engineering effort required in Stage S12 to implement automated purge routines.
- **Neutral**: Legal compliance review remains formally tracked in `docs/PRE_DEPLOYMENT_CHECKLIST.md`.

## Revisit When
Revisit when the deploying institution's legal counsel completes formal review of `docs/PRE_DEPLOYMENT_CHECKLIST.md`.
