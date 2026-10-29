# Stage S12 Run Review Report: Orchestrator, CLI, Audit, and Retention

**Date:** 2026-10-29
**Stage:** S12 (Orchestrator, CLI, Audit, and Retention)
**Target Package:** `omr_dispatch_engine` (`src/omr_dispatch/orchestrator.py`, `src/omr_dispatch/cli.py`, `src/omr_dispatch/retention.py`)
**Status:** COMPLETE (Gate 12 Passed; Ready for Operator Review)

---

## 1. Executive Summary

Stage S12 is the capstone integration stage of `omr_dispatch_engine`. It delivers the Application Service Layer (`src/omr_dispatch/orchestrator.py`), a thin CLI wrapper (`src/omr_dispatch/cli.py`), and the Data Retention and Consent Revocation Engine (`src/omr_dispatch/retention.py`).

The orchestrator wires together all previous stages (Ingestion S2, Diagnostics S3, Hindi Templates S4, OMR Proofs S5, Rendering S6, Audio S7, Messaging Policy & Store S8, Provider & Webhooks S9, Scheduler S10, Confirmation S11) into a cohesive, production-grade application service boundary, fulfilling the walking skeleton architecture defined in [ADR-0013](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/docs/adr/ADR-0013-delivery-strategy.md) and [ADR-0018](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/docs/adr/ADR-0018-application-service-layer-and-security.md).

All specifications from `docs/prompt_pack/S12.md`, [ADR-0002](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/docs/adr/ADR-0002-numeric-semantics.md), [ADR-0005](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/docs/adr/ADR-0005-time-and-clocks.md), [ADR-0008](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/docs/adr/ADR-0008-errors-and-logging.md), [ADR-0009](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/docs/adr/ADR-0009-configuration.md), [ADR-0018](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/docs/adr/ADR-0018-application-service-layer-and-security.md), [ADR-0019](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/docs/adr/ADR-0019-per-school-sender-identity-and-routing.md), [ADR-0020](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/docs/adr/ADR-0020-tenant-lifecycle-and-controls.md), and Global Invariants 8, 10, 15, 17, and 18 have been strictly implemented:
- **Application Service Layer (`orchestrator.py`):** Authoritative boundary methods (`validate_batch`, `evaluate_batch`, `build_send_plan`, `approve_batch`, `cancel_batch`, `get_job_status`, `list_review_queue`, `resolve_review_item`, `get_artifact`, `execute_dry_run`, `execute_live_send`, `tenant_onboard`, `tenant_suspend`).
- **Security Context & Multi-Tenant Scoping (`Principal`):** Every service call mandates a typed `Principal` security context (`actor_type`, `actor_id`, `org_id`, `roles`). Enforces tenant isolation: callers can only access resources matching their `org_id` unless granted `PLATFORM_ADMIN`. Cross-tenant requests fail closed with `UnauthorizedError`.
- **Strict Dual-Switch Safety Mandate (Invariant 8 & D-09):** `execute_live_send` strictly enforces that BOTH `LIVE_DISPATCH_ENABLED=true` AND `DEPLOYMENT_COMPLIANCE_ACKNOWLEDGED=true` before invoking any outbound messaging provider call. If either switch is false, dispatch is refused with `SafetySwitchError`.
- **Emergency Kill-Switch (ADR-0020):** `tenant_suspend` immediately sets the tenant kill-switch and transitions all active dispatches (`PENDING`, `SCHEDULED`, `RETRY_PENDING`) to `CANCELLED`. Subsequent live sends against that tenant fail closed with `TenantSuspendedError`.
- **Thin CLI Interface (`cli.py`):** CLI adapter requiring mandatory institutional tenant identifier (`--org-id`) on all commands. Omitting or providing a blank `--org-id` fails closed.
- **Privacy Hygiene (Invariants 10 & 17):** Zero student personal names, roll numbers, marks, or raw phone numbers logged or output to stdout/stderr. All phone numbers are strictly masked (`mask_phone`).
- **Data Retention & Consent Cascade (`retention.py`):** Automated purge of transient media older than 30 days (`transient_media_days`) and dispatches older than 90 days (`audit_log_days`). Generates cryptographic SHA-256 tombstones (`PurgeTombstone`). Guardian consent revocation (`OPT_OUT`) immediately cancels pending dispatches, revokes confirmation tokens, and logs immutable audit records.

---

## 2. Core Implementation Analysis

### Task 1: Application Service Layer (`src/omr_dispatch/orchestrator.py`)
Implemented in [`src/omr_dispatch/orchestrator.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/orchestrator.py):

1. **Security Context & Role Matrix (ADR-0018 Section 1 & 3):**
   - Data contracts: `Principal(actor_type: ActorType, actor_id: str, org_id: str, roles: list[UserRole])`.
   - `_assert_permission` evaluates role permissions and tenant scoping:
     - `TEACHER`: can validate, evaluate, plan, and view status for own org. Cannot approve batches, cancel batches, or suspend tenants.
     - `SCHOOL_ADMIN`: full operational authority within their own `org_id`.
     - `PLATFORM_ADMIN`: cross-tenant operational authority.
     - Cross-tenant access attempt raises `UnauthorizedError`.
2. **Batch Validation & Evaluation (`validate_batch`, `evaluate_batch`):**
   - Supports both `OMR_MCQ` and `MARKS_ENTRY_TOTALS` assessment kinds.
   - Computes diagnostic metrics, evaluates contact hygiene quarantine rules, and enqueues blocked/quarantined students into the human review queue.
3. **Pure Send Plan Generation & Scheduling (`build_send_plan`):**
   - Integrates with S10 schedule planner (`plan_schedule`) and DWRR multi-tenant scheduler store.
4. **Approval & Emergency Cancellation (`approve_batch`, `cancel_batch`):**
   - `approve_batch`: transitions dispatches from `PENDING` to `SCHEDULED`, requiring `SCHOOL_ADMIN` or `PLATFORM_ADMIN` role.
   - `cancel_batch`: transitions all pending/scheduled dispatches to `CANCELLED` and appends cancellation audit events.
5. **Human Review Queue Management (`list_review_queue`, `resolve_review_item`):**
   - Manages quarantined contacts, scan review items, and dispatch review anomalies.
   - Resolving an item records resolution status, notes, and timestamp with an audit trail entry.
6. **Secure Artifact Retrieval (`get_artifact`):**
   - Opaque key addressing with tenant scoping `(org_id, assessment_id, student_id, artifact_type)`. Cross-tenant retrieval raises `UnauthorizedError`.
7. **End-to-End Dry Run (`execute_dry_run`):**
   - Wires S2 ingestion -> S3 diagnostics -> S4 templates -> S5 proof -> S6 render -> S7 audio -> S10 scheduler -> S11 confirmation with zero network calls.
8. **Live Send with Dual-Switch Safety (`execute_live_send`):**
   - Evaluates `live_dispatch_enabled` AND `deployment_compliance_acknowledged`. Fails closed with `SafetySwitchError` if either is false.
   - Checks tenant emergency kill-switch (`TenantSuspendedError`).
   - Verifies sender identity status is `READY` (ADR-0019).

---

### Task 2: Thin Command-Line Interface (`src/omr_dispatch/cli.py`)
Implemented in [`src/omr_dispatch/cli.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/cli.py):

1. **Mandatory `--org-id` Parameter:**
   - Enforced across all CLI subcommands: `validate`, `evaluate`, `render`, `audio`, `plan-dispatch`, `dry-run`, `send`, `report`, `purge`, `review-queue`, `tenant-onboard`, `tenant-suspend`, `sender-configure`, `sender-status`, and legacy `run-batch`.
   - Omitting `--org-id` causes `argparse` to exit with code 2. Providing empty/blank `--org-id` exits with code 2.
2. **Subcommand Set:**
   - `validate`: ingests and verifies assessment files.
   - `evaluate`: evaluates contact hygiene and policy rules.
   - `render`: generates scorecards and PTM slips.
   - `audio`: prepares stitched Hindi audio voice notes.
   - `plan-dispatch`: generates send plan with primary and reminder windows.
   - `dry-run`: executes end-to-end dry run and prints masked summary report.
   - `send`: triggers live dispatch with dual safety switches (`--live-dispatch`, `--compliance-ack`).
   - `report`: outputs batch job status summary (pending, scheduled, delivered, blocked, failed, cancelled).
   - `purge`: executes D-13 data retention cleanup with dry-run/execute modes.
   - `review-queue`: inspects and resolves human review items.
   - `tenant-onboard`, `tenant-suspend`: tenant lifecycle administration.
   - `sender-configure`, `sender-status`: WhatsApp sender identity registration and status.
3. **Privacy Hygiene:**
   - Output uses `_write_stdout` and `_write_stderr` (no raw `print()` statements in `src/`).
   - All student personal names and marks are omitted from terminal outputs; phone numbers are strictly masked (`98*** **01`).

---

### Task 3: Data Retention & Consent Revocation Engine (`src/omr_dispatch/retention.py`)
Implemented in [`src/omr_dispatch/retention.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/retention.py):

1. **D-13 Retention Defaults & Purge Pipeline (`purge_retention_data`):**
   - Media retention cutoff: 30 days (`transient_media_days`). Unlinks transient scorecard PNGs, PTM PDFs, and audio notes.
   - Audit/dispatch retention cutoff: 90 days (`audit_log_days`). Purges terminal dispatches (`DELIVERED`, `READ`, `FAILED`, `CANCELLED`).
   - Confirmation tokens: purges expired tokens beyond 90 days.
   - Dry-run inspection mode: counts candidate records and bytes freed without destructive deletion.
   - Cryptographic tombstone: generates SHA-256 digest (`tombstone_hash`) over purged record IDs and timestamps.
2. **Real-Time Consent Revocation Propagation (`propagate_consent_revocation`):**
   - Triggered upon guardian opt-out (`OPT_OUT` / `CONSENT_REVOKED`).
   - Cancels all active dispatches (`PENDING`, `SCHEDULED`, `RETRY_PENDING`, `UPLOADING_MEDIA`) for the target student across all batches.
   - Cancels pending jobs in scheduler queue.
   - Revokes active parent confirmation tokens in `ConfirmationStore`.
   - Records append-only audit event (`CONSENT_REVOCATION_PROPAGATED`).

---

## 3. Gate 12 Verification & Exact Golden Fixture Counts

The end-to-end dry run was executed on the approved golden fixtures (`fixtures/golden/test_paper_300.json`, `admissions_300.json`, `submissions_300.json`).

| Metric | Expected Value | Actual Value | Status |
| :--- | :---: | :---: | :---: |
| **Total Enrolled Students** | `20` | `20` | PASS |
| **PTM Slips Generated** | `17` | `17` | PASS |
| **Eligible Outbound Dispatches** | `12` | `12` | PASS |
| **Blocked Student Exclusions** | `8` | `8` | PASS |
| **Visual Scorecards Rendered** | `16` | `16` | PASS |
| **Audio Voice Notes Prepared** | `20` | `20` | PASS |
| **Duplicate Runs / Resends on Rerun** | `0` | `0` | PASS |
| **Real Network Calls Contacted** | `0` | `0` | PASS |

### Exact Blocked Student Exclusions

| Student ID | Normalized Phone | Exclusion Reason Code | Status Band | Reason |
| :--- | :---: | :--- | :---: | :--- |
| `STU_02` | `98*** **03` | `INTERCEPTION_RISK_SAME_NUMBER` | `GREEN` | Student and guardian share phone number |
| `STU_03` | `98*** **04` | `DUPLICATE_PARENT_UNVERIFIED` | `RED` | Duplicate parent contact without sibling proof |
| `STU_04` | `98*** **04` | `DUPLICATE_PARENT_UNVERIFIED` | `ABSENT` | Duplicate parent contact without sibling proof |
| `STU_07` | `None` | `INVALID_PHONE_NUMBER` | `GREEN` | Invalid/malformed phone format |
| `STU_08` | `98*** **07` | `CONSENT_UNKNOWN` | `ABSENT` | Guardian consent status unknown |
| `STU_09` | `98*** **08` | `CONSENT_REVOKED` | `YELLOW` | Guardian opted out / consent revoked |
| `STU_10` | `98*** **09` | `GUARDIAN_UNVERIFIED` | `RED` | Guardian contact unverified |
| `STU_19` | `98*** **16` | `CONSENT_REVOKED` | `ABSENT` | Guardian opted out / consent revoked |

### Exact Eligible Students Dispatched (12 Students)
`STU_01`, `STU_05`, `STU_06`, `STU_11`, `STU_12`, `STU_13`, `STU_14`, `STU_15`, `STU_16`, `STU_17`, `STU_18`, `STU_20`.

---

## 4. Deliberate Mutations Analysis

To ensure complete test sensitivity and eliminate false positives, 4 deliberate mutations were injected into the codebase, verified to fail the exact corresponding test assertions, and immediately reverted.

### Mutation 1: Bypass Dual-Switch Safety Check in `execute_live_send`
- **Location:** `src/omr_dispatch/orchestrator.py` (`execute_live_send`)
- **Modification:** Bypassed the safety switch check: `if False and (not live_dispatch_enabled or not compliance_ack): raise SafetySwitchError`.
- **Expected Failure:** `test_send_refused_when_both_switches_false` and `test_send_refused_when_only_one_switch_true` must fail.
- **Observed Result:**
  ```
  FAILED tests/test_stage12_orchestrator.py::TestDualSwitchSafety::test_send_refused_when_both_switches_false
  Failed: DID NOT RAISE <class 'omr_dispatch.orchestrator.SafetySwitchError'>
  FAILED tests/test_stage12_orchestrator.py::TestDualSwitchSafety::test_send_refused_when_only_one_switch_true
  Failed: DID NOT RAISE <class 'omr_dispatch.orchestrator.SafetySwitchError'>
  ```
- **Reversion:** Mutation reverted; checks restored.

### Mutation 2: Allow CLI to Execute Without Requiring `--org-id`
- **Location:** `src/omr_dispatch/cli.py` (`build_parser`)
- **Modification:** Changed `dry_p.add_argument("--org-id", required=True)` to `required=False, default="DEFAULT_INSTITUTION"`.
- **Expected Failure:** `test_cli_omitted_org_id_fails` must fail.
- **Observed Result:**
  ```
  FAILED tests/test_stage12_orchestrator.py::TestCLITenantBoundariesAndRoles::test_cli_omitted_org_id_fails
  Failed: DID NOT RAISE <class 'SystemExit'>
  ```
- **Reversion:** Mutation reverted; `required=True` restored.

### Mutation 3: Disable Consent Revocation Dispatch Cancellation
- **Location:** `src/omr_dispatch/retention.py` (`propagate_consent_revocation`)
- **Modification:** Bypassed dispatch cancellation SQL: `if False and repository is not None:`.
- **Expected Failure:** `test_consent_revocation_cancels_dispatches_and_tokens` must fail.
- **Observed Result:**
  ```
  FAILED tests/test_stage12_orchestrator.py::TestRetentionAndConsentRevocation::test_consent_revocation_cancels_dispatches_and_tokens
  AssertionError: assert 0 == 1
   + where 0 = ConsentRevocationResult(...).dispatches_cancelled
  ```
- **Reversion:** Mutation reverted; cascade cancellation restored.

### Mutation 4: Permit `STU_02` (Interception Risk) to Bypass Blocking
- **Location:** `src/omr_dispatch/orchestrator.py` (`evaluate_batch`)
- **Modification:** Injected bypass allowing `STU_02` to be marked eligible: `if c.student_id == "STU_02": eligible_count += 1; blocked_count -= 1; continue`.
- **Expected Failure:** `test_golden_batch_dry_run_exact_counts` must fail.
- **Observed Result:**
  ```
  FAILED tests/test_stage12_orchestrator.py::TestGoldenBatchDryRun::test_golden_batch_dry_run_exact_counts
  AssertionError: assert 7 == 8
   + where 7 = DryRunResult(...).blocked_count
  ```
- **Reversion:** Mutation reverted; strict hygiene blocking restored.

---

## 5. Verification Commands & Execution Log

```
1. Linter Verification:
$ uv run ruff check .
All checks passed!
Exit code: 0

2. Type Checker Verification:
$ uv run mypy src
pyproject.toml: note: unused section(s): module = ['reportlab.*', 'weasyprint.*']
Success: no issues found in 24 source files
Exit code: 0

3. Stage S12 Unit and Integration Tests:
$ uv run --frozen pytest -v tests/test_stage12_orchestrator.py
============================= test session starts =============================
collected 19 items
tests/test_stage12_orchestrator.py ...................                   [100%]
============================= 19 passed in 7.38s ==============================
Exit code: 0

4. Full Project Test Suite (All Stages S1–S12):
$ uv run --frozen pytest
........................................................................ [ 22%]
........................................................................ [ 45%]
........................................................................ [ 68%]
........................................................................ [ 91%]
............................                                             [100%]
316 passed in 108.04s (0:01:48)
Exit code: 0

5. Guardrails Integrity Check:
$ uv run python scripts/guardrails.py
=== Running Guardrails (Current Stage: S12) ===
  [PASS] Forbidden Patterns & Secrets
  [PASS] Hindi Integrity Check
  [PASS] State Hashes & Tags Check
  [PASS] Invariants Synchronization Check
  [PASS] Git Diff & Whitespace Check
  [PASS] Fixture Hash Validation
  [PASS] Test Count Integrity Check
  [PASS] Time Hygiene Check
  [PASS] Core Numerics Check
  [PASS] Environment Hygiene Check
  [PASS] Logging Hygiene Check
------------------------------------------------------------
PASSED 11 / SKIPPED 0 / FAILED 0
------------------------------------------------------------
Exit code: 0
```

---

## 6. Allowed Files Boundary Audit

Per `docs/prompt_pack/S12.md`, changes for Stage S12 are strictly confined to the allowed file boundary:

| File | Status | Scope Description |
| :--- | :---: | :--- |
| `src/omr_dispatch/orchestrator.py` | New | Application Service Layer (ADR-0018), Principal context, S2→S11 orchestration |
| `src/omr_dispatch/cli.py` | Modified | Thin CLI wrapper, mandatory `--org-id`, dual safety switch on `send` |
| `src/omr_dispatch/retention.py` | New | D-13 data retention engine, purge tombstones, consent revocation propagation |
| `src/omr_dispatch/__init__.py` | Modified | Public symbol re-exports from orchestrator and retention modules |
| `tests/test_stage12_orchestrator.py` | New | Gate 12 end-to-end integration test suite (19 tests) |
| `docs/CURRENT_STAGE` | Modified | `S12` |
| `docs/.test_count_baseline` | Modified | Updated test baseline count (`316`) |
| `docs/STATE.md` | Modified | Stage S12 execution evidence and status update |
| `docs/reviews/stage-12-run.md` | New | Formal Stage S12 execution review report |

Zero modifications occurred outside of the permitted Stage S12 boundary.
Zero new dependencies were added to `pyproject.toml` or `uv.lock`.

---

## 7. Next Steps for Operator

Per `AGENTS.md` Rule 1:
- The agent stops immediately at the end of Stage S12 and reports evidence.
- The operator reviews this report and approves the stage.
- The operator authorizes committing the files and tagging `stage-12`.
