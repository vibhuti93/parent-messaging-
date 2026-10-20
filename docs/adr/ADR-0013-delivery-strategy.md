# ADR-0013: Delivery Strategy via Walking Skeleton

## Status
`PROPOSED`

## Context
In large multi-stage projects, a common architectural failure is "big bang integration"—building isolated stages (models, diagnostics, templates, render, provider) and attempting to wire them together into an orchestrator only at the very end (Stage S12).
This risks discovering fundamental contract mismatches, data flow bottlenecks, and orchestration oversights too late in the implementation cycle.

## Options Considered

### Option 1: Waterfall Stage-by-Stage Isolation
- *Description*: Build each stage completely disconnected, deferring all pipeline execution to Stage S12.
- *Pros*: Follows prompt pack boundaries strictly.
- *Cons*: Extremely high risk at Stage S12; integration bugs surface only after all code is written.

### Option 2: Walking Skeleton Approach
- *Description*:
  - **Early Thin Thread:** Immediately following Stage S3 (Deterministic Diagnostics & Contact Hygiene), establish a thin, end-to-end command-line execution path:
    `omr-dispatch run-batch --input fixtures/golden/ --output run/`
  - This minimal skeleton executes: Ingest golden fixture -> Compute diagnostic report -> Generate preliminary text -> Emit structured JSON run manifest.
  - **Incremental Hardening:** Subsequent stages (S4 templates, S5-S6 render, S7 audio, S8 policy/store, S9 provider) incrementally plug their adapters into this existing execution thread.
  - **Stage S12 Role:** S12 *completes, hardens, and validates* the orchestrator and CLI suite rather than inventing them from scratch.
- *Pros*: Continuous end-to-end verification; early detection of contract mismatches; tangible progress visibility from early stages.
- *Cons*: Requires defining minimal CLI interface early in S3.

## Proposed Decision
We propose **Option 2 (Walking Skeleton Delivery Strategy)**.

### Phased Evolution of the Walking Skeleton
1. **End of S3:** CLI loads student submission JSON, executes `evaluate_batch()`, validates contact hygiene, and writes `run_manifest.json` containing diagnostic scores.
2. **End of S4:** CLI connects `render_bolchal_templates()` and attaches Hindi copy to the manifest.
3. **End of S6:** CLI attaches PNG scorecard and PDF slip paths to the manifest.
4. **End of S7:** CLI attaches stitched Ogg Opus audio voice note paths.
5. **End of S8:** CLI routes dispatches through SQLite WAL state store and messaging policy gate.
6. **End of S9:** CLI integrates WhatsApp Cloud API test provider adapter.
7. **Stage S12:** Full orchestrator hardening, review queues, purge jobs, and end-to-end golden batch validation.

## Consequences
- **Positive**: Drastically de-risks Stage S12; guarantees continuous alignment between domain stages and end-to-end pipeline.
- **Negative**: Slight update to Stage S3 prompt to record walking skeleton criteria.
- **Neutral**: Fully compliant with Stage boundaries.

## Revisit When
Revisit if the project transitions to a daemon microservice model instead of batch CLI execution.
