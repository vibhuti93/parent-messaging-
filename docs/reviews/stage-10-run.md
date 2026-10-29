# Stage S10 Run Review Report: Multi-Tenant Scheduler & Send Window Engine

**Date:** 2026-10-29
**Stage:** S10 (Multi-Tenant Scheduler & Send Window Engine)
**Target Package:** `omr_dispatch_engine` (`src/omr_dispatch/scheduler.py`, `src/omr_dispatch/`)
**Status:** COMPLETE (Gate 10 Passed; Ready for Operator Review)

---

## 1. Executive Summary

Stage S10 delivers the multi-tenant scheduler and send window engine (`src/omr_dispatch/scheduler.py`), responsible for deterministic send window planning, multi-tenant fair queue orchestration via Deficit Weighted Round-Robin (DWRR), per-sender daily message cap pacing, send window integrity validation, and single-instance dispatch concurrency locking.

All requirements from `docs/prompt_pack/S10.md`, `PROJECT_SPEC.md` (clause D-10), `ADR-0002`, `ADR-0005`, `ADR-0017`, `ADR-0019`, and `ADR-0020` have been fully met:
- **Pure Schedule Planning (`plan_schedule`):** Deterministic planning function anchored in `ZoneInfo("Asia/Kolkata")` with explicit `now: datetime` injection. Primary send window defaults to Sunday 20:30 IST (`20:30:00+05:30`).
- **Sunday OMR Window Validation:** Strictly validates that events claiming the primary Sunday OMR window occur on Sunday (`dt.weekday() == 6`). Non-Sunday events fail closed with explicit `InvalidScheduleWindowError`.
- **Target Fixture Match (D-10):** For event `2026-10-18 14:15+05:30` (Sunday):
  - Primary dispatch scheduled at: `2026-10-18 20:30:00+05:30`.
  - Reminder dispatch scheduled at: `2026-10-19 10:00:00+05:30` (Monday morning) strictly when `reminder_enabled=True`. Exactly zero reminders generated when disabled.
  - Distinct SHA-256 idempotency identities computed for primary vs. reminder dispatches.
- **DST-Free Sanity in Asia/Kolkata:** Verified invariant UTC+05:30 offset across year boundaries and seasons with zero DST shifts.
- **DWRR Multi-Tenant Fair Scheduling:** `DWRRQueue` maintains integer quantum credits and deficit tracking per tenant, mathematically preventing large tenants (e.g. Org A with 1,000 jobs) from starving small tenants (Org B with 10 jobs completes in Round 1).
- **Daily Cap Spreading:** Batches exceeding a tenant's daily message quota spread across consecutive eligible days within allowed send windows, automatically skipping academic/institutional holidays.
- **Edge Conditions Handled:** Late import, missed window, holiday override, provider outage, unapproved template hold.
- **Freeform Bypass Guardrail (Invariants 13 & 14):** Freeform messages are strictly prohibited from bypassing send window rules, failing closed with `WindowRuleBypassForbiddenError`.
- **Durable Persistence & Single-Instance Lock:** Persisted schedules and queue orders survive store reloads from disk (`SchedulerStore`), and `DispatchLock` prevents duplicate dispatches across concurrent workers.

---

## 2. Task 1: Pure Schedule Planning (`plan_schedule`)

Implemented in [`src/omr_dispatch/scheduler.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/scheduler.py):

1. **Deterministic Function Signature:**
   ```python
   def plan_schedule(
       event: AssessmentScheduleEvent | Any,
       now: datetime,
       policy: SchedulePolicy | None = None,
   ) -> ScheduledPlan:
   ```
   - Time Hygiene (ADR-0005): Strictly requires timezone-aware `now` and `event_timestamp`. Timezone-naive datetimes fail closed with `ValueError`.
   - Explicit tenant context (`org_id`) is strictly enforced; missing context raises `TenantContextMissingError` (Invariant 15).

2. **Sunday OMR Window Validation:**
   - Standard OMR assessments claim the `SUNDAY_OMR` window type.
   - Enforces `event_dt_ist.weekday() == 6`.
   - Events on Wednesday, Tuesday, Monday, or Saturday attempting to claim the Sunday window fail closed immediately with `InvalidScheduleWindowError`.

3. **Target Fixture Verification:**
   - Event `2026-10-18 14:15+05:30` (Sunday):
     - `primary_dispatch.scheduled_at_ist` = `2026-10-18 20:30:00+05:30` (window 20:30–21:30 IST).
     - When `reminder_enabled=True`: `reminder_dispatch.scheduled_at_ist` = `2026-10-19 10:00:00+05:30` (window 10:00–12:00 IST).
     - When `reminder_enabled=False`: `reminder_dispatch` is `None` (0 reminder jobs).
     - `primary_dispatch.idempotency_key` != `reminder_dispatch.idempotency_key`.

4. **DST-Free Sanity:**
   - Verified that `ZoneInfo("Asia/Kolkata")` provides invariant `+05:30` offset (19,800 seconds) and zero DST shifts across January, June, October, December, and year boundaries.

---

## 3. Task 2: Multi-Tenant Fair Scheduling & Daily Cap Pacing

Implemented in [`src/omr_dispatch/scheduler.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/scheduler.py):

1. **Deficit Weighted Round-Robin Engine (`DWRRQueue`):**
   - Implements deficit round-robin per M. Shreedhar and G. Varghese.
   - Each tenant receives integer quantum credits (`quantum * weight`) per round.
   - Core Numerics (ADR-0002): **Zero `float()` calls.** Quantums, deficits, weights, and costs are exact integers (`int`).
   - Anti-starvation proof:
     - Simulation with Org A (1,000 jobs), Org B (10 jobs), Org C (50 jobs) under quantum 20.
     - In Round 1, Org B dispatches all 10 jobs (last job index 29). Org B is 100% completed within the first 50 total jobs dispatched.
     - Org C dispatches 20, 20, and 10 jobs across rounds 1–3, completing within ~110 total dispatches.
     - Org A does not starve smaller tenants.

2. **Per-Sender Daily Message Limits & Multi-Day Spreading (`pace_batch_over_days`):**
   - Respects per-sender daily message limits (e.g. 250 recipients/24h per ADR-0019 R-10).
   - When a batch exceeds remaining capacity (e.g. 600 items with cap 250):
     - Day 1 (Sunday): 250 items (`SCHEDULED`).
     - Day 2 (Monday): 250 items (`PACED_DAILY_CAP`).
     - Day 3 (Tuesday): 100 items (`PACED_DAILY_CAP`).
   - Slices respect `current_sent_today` (e.g. if 150 already sent, Day 1 receives 100).
   - Skips declared academic/institutional holidays, automatically rolling remaining allocations to the next eligible business day.

---

## 4. Task 3: Edge & Window Condition Handling

Implemented in [`src/omr_dispatch/scheduler.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/scheduler.py):

1. **Late Import:**
   - Assessment imported after window start (e.g. 20:45 IST when window began at 20:30 IST).
   - Policy default (`allow_late_import=False`) flags status as `ScheduleStatus.DEFERRED_LATE_IMPORT` with reason `"LATE_IMPORT_AFTER_WINDOW_START"`.
   - When enabled, allows scheduling within remaining window bounds.

2. **Missed Window:**
   - Current time exceeds window end (e.g. 22:00 IST when window closed at 21:30 IST).
   - Flags status as `ScheduleStatus.MISSED_WINDOW` with reason `"MISSED_SEND_WINDOW_END"`.

3. **Holiday Override:**
   - Event date in `policy.holidays` (e.g. Sunday 2026-10-18 is a holiday).
   - Flags status as `ScheduleStatus.DEFERRED_HOLIDAY`.
   - Automatically advances primary send time to the next eligible non-holiday day at the designated window time.

4. **Upstream Provider Outage:**
   - `policy.provider_operational=False`.
   - Flags status as `ScheduleStatus.HOLD_PROVIDER_OUTAGE`.
   - Jobs remain safely queued without dropping records or violating window closures.

5. **Unapproved Template Hold:**
   - `policy.template_approved=False`.
   - Flags status as `ScheduleStatus.HOLD_UNAPPROVED_TEMPLATE`.
   - Dispatches held without dispatching free-form content as a bypass.

6. **Free-Form Bypass Prevention (Invariants 13 & 14):**
   - Attempting to bypass window closures using free-form text (`is_freeform=True` or `allow_freeform_bypass=True`) raises `WindowRuleBypassForbiddenError`.

---

## 5. Task 4: Single-Instance Dispatch Lock & Persistence

Implemented in [`src/omr_dispatch/scheduler.py`](file:///c:/Users/91933/OneDrive/Pictures/Documents/new_parent_messaging/src/omr_dispatch/scheduler.py):

1. **Single-Instance Dispatch Lock (`DispatchLock`):**
   - Concurrency guard using SQLite table `dispatch_locks` with reentrant process lock (`threading.RLock`).
   - Context manager `with DispatchLock(db_path, lock_key, owner_id, ttl_seconds):` acquires mutex.
   - Competing worker attempting to acquire held lock receives `False` or raises `LockAcquisitionError`.
   - Built-in TTL auto-expiration prevents permanently locked resources if a worker process terminates unexpectedly.
   - Multi-threaded contention test: 10 worker threads concurrently attempt to claim the same job; invariant `max_simultaneous_holders == 1` holds strictly, with zero duplicate dispatches.

2. **Durable Persistence & Restart Recovery (`SchedulerStore`):**
   - SQLite tables: `scheduled_jobs`, `dispatch_locks`.
   - Atomically persists planned schedules with window metadata, idempotency keys, and queue order.
   - Restart verification: Store saved to disk, closed, re-opened in fresh instance; asserted 100% equivalence of timestamps, idempotency keys, and queue order.

---

## 6. Deliberate Mutation Testing

Per Part C Rule 4 and Gate 10 requirements, 4 deliberate mutations were injected into `src/omr_dispatch/scheduler.py` to prove test suite sensitivity:

### Mutation 1: Allow Non-Sunday Event to Claim Sunday OMR Window
- **Mutation:** Disabled weekday check in `plan_schedule` (`if False and window_type == "SUNDAY_OMR"...`).
- **Command:** `uv run --frozen pytest tests/test_stage10_scheduler.py -k test_sunday_validation`
- **Result:** **FAILED (4 tests failed)**
  ```
  FAILED tests/test_stage10_scheduler.py::test_sunday_validation_fails_closed_for_non_sunday_events[non_sunday_dt0-Wednesday] - Failed: DID NOT RAISE <class 'omr_dispatch.scheduler.InvalidScheduleWindowError'>
  FAILED tests/test_stage10_scheduler.py::test_sunday_validation_fails_closed_for_non_sunday_events[non_sunday_dt1-Tuesday] - Failed: DID NOT RAISE <class 'omr_dispatch.scheduler.InvalidScheduleWindowError'>
  FAILED tests/test_stage10_scheduler.py::test_sunday_validation_fails_closed_for_non_sunday_events[non_sunday_dt2-Saturday] - Failed: DID NOT RAISE <class 'omr_dispatch.scheduler.InvalidScheduleWindowError'>
  FAILED tests/test_stage10_scheduler.py::test_sunday_validation_fails_closed_for_non_sunday_events[non_sunday_dt3-Monday] - Failed: DID NOT RAISE <class 'omr_dispatch.scheduler.InvalidScheduleWindowError'>
  ```
- **Outcome:** Mutation caught immediately; reverted cleanly.

### Mutation 2: Generate Identical Idempotency Keys for Primary and Reminder Dispatches
- **Mutation:** Modified reminder key calculation to pass `event_type="PRIMARY"` instead of `"REMINDER"`.
- **Command:** `uv run --frozen pytest tests/test_stage10_scheduler.py -k "test_canonical_schedule or test_persistence"`
- **Result:** **FAILED (2 tests failed)**
  ```
  FAILED tests/test_stage10_scheduler.py::test_canonical_schedule_primary_and_reminder_enabled - AssertionError: assert '094c788e...' != '094c788e...'
  FAILED tests/test_stage10_scheduler.py::test_persistence_and_restart_recovery - AssertionError
  ```
- **Outcome:** Mutation caught immediately; reverted cleanly.

### Mutation 3: Disable DWRR Deficit Tracking (Starving Small Tenants)
- **Mutation:** Removed deficit credit check in `DWRRQueue.drain_round()`, draining all jobs from the first tenant queue.
- **Command:** `uv run --frozen pytest tests/test_stage10_scheduler.py -k test_dwrr`
- **Result:** **FAILED (2 tests failed)**
  ```
  FAILED tests/test_stage10_scheduler.py::test_dwrr_fair_scheduling_starvation_prevention - AssertionError: assert 1000 == 20
  FAILED tests/test_stage10_scheduler.py::test_dwrr_weighted_fairness - AssertionError: assert 100 == 20
  ```
- **Outcome:** Mutation caught immediately; reverted cleanly.

### Mutation 4: Bypass Send Window Checks When Template is Unapproved
- **Mutation:** Bypassed `if not active_policy.template_approved:` check, allowing unapproved templates to proceed to `SCHEDULED`.
- **Command:** `uv run --frozen pytest tests/test_stage10_scheduler.py -k test_unapproved_template`
- **Result:** **FAILED (1 test failed)**
  ```
  FAILED tests/test_stage10_scheduler.py::test_unapproved_template_holds_jobs_without_freeform_bypass - AssertionError: assert <ScheduleStatus.SCHEDULED: 'SCHEDULED'> == <ScheduleStatus.HOLD_UNAPPROVED_TEMPLATE: 'HOLD_UNAPPROVED_TEMPLATE'>
  ```
- **Outcome:** Mutation caught immediately; reverted cleanly.

---

## 7. Verification Commands & Execution Evidence

### 1. Stage 10 Specific Tests
```powershell
uv run --frozen pytest tests/test_stage10_scheduler.py
```
**Raw Output:**
```
.......................                                                  [100%]
23 passed in 0.71s
```
**Exit Code:** 0

### 2. Full Test Suite (S1–S10)
```powershell
uv run --frozen pytest
```
**Raw Output:**
```
........................................................................ [ 25%]
........................................................................ [ 51%]
........................................................................ [ 77%]
.............................................................            [100%]
277 passed in 43.22s
```
**Exit Code:** 0 (277 passed, 0 skipped, 0 failed)

### 3. Linter Check
```powershell
uv run ruff check .
```
**Raw Output:**
```
All checks passed!
```
**Exit Code:** 0

### 4. Strict Type Check
```powershell
uv run mypy src
```
**Raw Output:**
```
pyproject.toml: note: unused section(s): module = ['reportlab.*', 'weasyprint.*']
Success: no issues found in 21 source files
```
**Exit Code:** 0

### 5. Guardrail Checker
```powershell
python scripts/guardrails.py
```
**Raw Output:**
```
=== Running Guardrails (Current Stage: S10) ===
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
```
**Exit Code:** 0

---

## 8. Git Diff & Working Tree Status

### `git --no-pager diff --name-only stage-9`
```
docs/.test_count_baseline
docs/CURRENT_STAGE
docs/STATE.md
src/omr_dispatch/__init__.py
```

### `git --no-pager status --porcelain`
```
 M docs/.test_count_baseline
 M docs/CURRENT_STAGE
 M docs/STATE.md
 M src/omr_dispatch/__init__.py
?? docs/reviews/stage-10-run.md
?? src/omr_dispatch/scheduler.py
?? tests/test_stage10_scheduler.py
```

All modified and created files are strictly within the Stage S10 boundary. Zero external packages, fixtures, or frozen configurations were modified.

---

## 9. Next Stage Handover

- **Current Stage:** S10 (Completed)
- **Next Stage:** S11 (Parent Confirmation - QR + OTP)
- **Stage Tagging:** Tagging `stage-10` is reserved for Operator Review sign-off.
