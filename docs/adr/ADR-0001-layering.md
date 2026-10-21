# ADR-0001: Pure Core vs. I/O Adapters Layering Architecture

## Status
`ACCEPTED`

## Context
The `omr_dispatch_engine` performs critical computational tasks: scoring student exams, evaluating diagnostic bands, assembling parent-facing Hindi messages, enforcing communication policies, rendering image/PDF assets, transcoding audio, and dispatching to WhatsApp.
If business rules, scoring logic, and template generation become intermingled with file system access, network calls (Meta Cloud API), subprocess calls (FFmpeg), or database operations (SQLite), the system suffers from non-deterministic test flakiness, difficult offline auditing, and complex failure modes.

## Options Considered

### Option 1: Monolithic Service / Transaction Scripts
- *Description*: All modules perform database queries, file reads, and HTTP calls directly within domain procedures (e.g., `calculate_and_send()`).
- *Pros*: Quick to scaffold initial prototypes.
- *Cons*: Violates testability; impossible to run fast unit tests without mocking database engines or HTTP sockets; breaks deterministic fixture replay.

### Option 2: Hexagonal / Ports & Adapters Architecture (Pure Core + I/O Adapters)
- *Description*: Enforce a strict boundary separating a pure, deterministic core from outer I/O adapters. The Core package contains no network calls, no database connections, no subprocess executions, no random number generators, and no system clock reads.
- *Pros*:
  - Deterministic testing: 100% of core diagnostics, template formatting, and policy decisions can be tested in-memory in milliseconds.
  - Replayability: Golden fixtures can be replayed through the core with zero external infrastructure.
  - Modularity: Adapters (e.g. swapping SQLite for Postgres or WhatsApp for SMS) can be replaced without touching domain rules.
- *Cons*: Requires formal protocol interfaces and parameter passing across layer boundaries.

## Proposed Decision
We propose **Option 2 (Pure Core + I/O Adapters Architecture)**.

### Module Mapping to Architecture Layers
1. **Pure Core Layer (`src/omr_dispatch/core/`):**
   - `models`: Domain Pydantic v2 data models (immutable, strictly validated).
   - `diagnostics`: Deterministic scoring arithmetic (gross, bleed, net, percentage, rank, bands, easy questions).
   - `hindi_templates`: Conversational Bolchal Hindi copy assembly, vocabulary validation, parameter formatting.
   - `messaging_policy`: Pure gatekeeper rules (consent verification, service window rules, quarantine checks).
   - *Invariant*: Zero external I/O dependencies. No `socket`, `urllib`, `requests`, `httpx`, `sqlite3`, `subprocess`, `os.environ`, or `datetime.now()`.
2. **Adapters Layer (`src/omr_dispatch/adapters/`):**
   - `provider`: WhatsApp Cloud API HTTP client (requests/httpx).
   - `durable_store`: SQLite WAL repository implementing durable event persistence.
   - `renderer`: Playwright Chromium wrapper for scorecards and ReportLab/WeasyPrint for PTM PDFs.
   - `audio_engine`: Token audio stitcher and FFmpeg Opus transcoder subprocess wrapper.
   - `omr_proof`: Image cropping and visual bubble overlay adapter.
   - `webhooks`: HTTP server handler and `X-Hub-Signature-256` HMAC verifier.
   - `confirmation`: Cryptographic random token generator and SHA-256 hasher.
   - `clock`: System clock adapter providing `tz-aware` UTC timestamps.
3. **Application Orchestration Layer (`src/omr_dispatch/orchestrator/` & `cli/`):**
   - `orchestrator`: End-to-end pipeline coordinator wiring Core rules with Adapters.
   - `cli`: Command-line entry points.

### Allowed Dependency Directions
- **Core** depends on: **NOTHING** outside `src/omr_dispatch/core/` (plus standard library data structures and Pydantic).
- **Adapters** depend on: **Core** protocols and models. Adapters never import other peer adapters directly.
- **Orchestrator** depends on: **Core** and **Adapters** via dependency injection.
*(Note: Import-linter rules enforcing these layer boundaries will be configured in Stage S2 when module packages exist).*

## Consequences
- **Positive**: Complete determinism for scoring and diagnostics; unit test execution times remain under 1 second; external failures (e.g. network disconnect) cannot corrupt domain state.
- **Negative**: Requires explicit dependency injection and adapter contracts.
- **Neutral**: Slightly more directory structure in `src/omr_dispatch/`.

## Revisit When
Revisit if the system introduces streaming real-time event processing that requires core stateful event-loop integration.
