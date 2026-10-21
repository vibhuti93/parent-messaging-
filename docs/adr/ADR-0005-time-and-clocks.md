# ADR-0005: Time Representation, Timezones, and Injected Clocks

## Status
`ACCEPTED`

## Context
Dispatch scheduling, customer service window tracking (24h window), webhook timestamps, audit logging, and QR token expirations (72h TTL) depend heavily on time calculations.
System-wide bugs frequently arise from naive datetimes (ambiguity during daylight savings or timezone conversion) and hardcoded calls to `datetime.now()` (making unit tests dependent on execution time and impossible to test at boundary conditions).

## Options Considered

### Option 1: System Local Time and Unmocked `datetime.now()`
- *Description*: Call `datetime.now()` across application code and rely on the host machine's timezone.
- *Pros*: Familiar syntax.
- *Cons*: Disaster on servers located in UTC vs IST; non-deterministic tests; potential failure of the 24h customer service window checks.

### Option 2: UTC Everywhere Internally, Asia/Kolkata at Edges, and Injected `Clock` Protocol
- *Description*:
  - **Storage & State:** All datetimes must be timezone-aware (`tz-aware`) and stored/persisted strictly in UTC (`datetime.timezone.utc`).
  - **Presentation Edges:** All human-facing displays (scorecards, PDF slips, Bolchal Hindi text) and dispatch schedules (Sunday 20:30 IST, Monday 10:00 IST) convert to `Asia/Kolkata` (`ZoneInfo("Asia/Kolkata")`).
  - **Injected Clock:** All components that read current time receive an injected `Clock` protocol instance. In production, `SystemClock` returns `datetime.now(timezone.utc)`. In tests, `FrozenClock(current_time)` allows deterministic boundary verification.
  - **Lint Rule**: Strict ban on `datetime.now()` without timezone, `datetime.utcnow()`, and naive datetimes.
- *Pros*: 100% deterministic testing; zero timezone drift; compliant with Indian regulatory and school operational time.
- *Cons*: Requires passing the clock dependency down to policy and scheduler modules.

## Proposed Decision
We propose **Option 2 (UTC Storage, Asia/Kolkata Presentation, and Injected Clock)**.

### Clock Protocol Specification
```python
class Clock(Protocol):
    def now_utc(self) -> datetime:
        ...

class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

class FrozenClock:
    def __init__(self, frozen_time: datetime):
        if frozen_time.tzinfo is None:
            raise ValueError("FrozenClock requires tz-aware datetime")
        self._time = frozen_time.astimezone(timezone.utc)

    def now_utc(self) -> datetime:
        return self._time

    def advance(self, delta: timedelta) -> None:
        self._time += delta
```

## Consequences
- **Positive**: Fully deterministic tests for 24h customer service window and 72h QR token expiration; no ambiguity between UTC and IST.
- **Negative**: All datetime instantiations must explicitly pass `tzinfo=timezone.utc`.
- **Neutral**: Enforced via pre-commit guardrail.

## Revisit When
Revisit if international schools in multiple timezones are onboarded.
