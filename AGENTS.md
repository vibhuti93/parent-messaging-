# AGENTS.md - Global Invariants & Agent Instructions

You are building `omr_dispatch_engine` (Python 3.11+, Pydantic v2, `src/omr_dispatch/`). These rules apply to every stage.

## Process
1. Read `AGENTS.md`, `PROJECT_SPEC.md`, `docs/STATE.md` before acting. Work on exactly one stage per session. Stop at the end of the stage and report; never start the next one.
2. Inspect the repo before editing. Never overwrite user work. Stay inside the stage's Allowed files.
3. If two requirements conflict, or a decision is missing, write it to `docs/DECISIONS_OPEN.md` with the conflicting clauses and the minimum safe resolution, then stop and ask. Never make an unapproved business-rule change.
4. Report only evidence: files changed, commands actually run, exit codes, actual test counts, skips with reasons. Do not write "passed", "verified", "compliant", "delivered", or "production-ready" without matching evidence.
5. Update `docs/STATE.md` at the end of each stage (status, evidence, open questions, fixture manifest hash).

## Testing
6. Expected values are literals from the approved fixtures; tests never compute expectations with the code under test. Never weaken, skip, or delete a test, or edit frozen fixtures/hashes, to make a build pass.
7. Mock only external boundaries (network, clock). Render, audio, HTTP-integration and diagnostics tests use real local components. No test contacts a real messaging endpoint or a real parent.

## Safety and Privacy
8. Live messaging is disabled by default. Credentials only via environment; `.env.example` holds placeholders. Never commit secrets or real personal data.
9. Never infer consent, guardian identity, or sibling status from a spreadsheet value or surname. A non-empty phone number is not consent.
10. Never log full phone numbers, tokens, names, scores, QR tokens, or audio payloads; mask them.
11. Synthetic scans, signatures, audio, or tones are test-only and must never appear in production output or be presented as evidence. A signature or QR alone is not identity proof.
12. Do not assert any external API, pricing, template, or legal fact that is not recorded in `docs/research/official_source_verification.md`. Unverified → mark `UNVERIFIED` and keep the dependent feature disabled.
13. Fail closed: uncertain input → `REVIEW_REQUIRED` / block / defer, never a guess. An uncertain send outcome is `UNKNOWN_NEEDS_REVIEW`, never a blind retry.
14. Parent-facing text describes observable indicators only; no claims about intent, lying, or psychology.

## Stop-and-Ask Triggers
Stop and ask the operator when:
- A decision is tagged `OWNER-CONFIRM`.
- An official source is unreachable and a production claim depends on it.
- Audio assets are missing.
- A requirement conflicts with another.
- A test would require a fixture change.
- Any action could touch a real parent contact.