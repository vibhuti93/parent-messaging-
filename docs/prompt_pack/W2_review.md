Role: independent reviewer. Do NOT fix anything and do not edit any file except docs/reviews/stage-0-r4.md.

Read AGENTS.md, PROJECT_SPEC.md, docs/STATE.md, docs/DECISIONS_OPEN.md, docs/adr/*.md, docs/domain_glossary.md, docs/data_map.md, docs/prompt_pack/*.md, docs/research/provider_contract.json.

Note: docs/prompt_pack/W2_review.md is this prompt file. Do not report it as a scope violation.

Review `git diff stage-0-r3..stage-0-r4` and the current state of the repo.

Check and report PASS/FAIL with file and line references for each:
1. Scope: any file changed outside the Stage S0-R4 SCOPE (docs/adr, docs/domain_glossary.md, docs/data_map.md, docs/architecture_decisions.md, docs/research, DECISIONS_OPEN.md, STATE.md, docs/prompt_pack amendments, pyproject.toml tool config, .pre-commit-config.yaml, scripts/guardrails.py). Any application code, fixture or test = FAIL.
2. Frozen spec: for EVERY ADR, list any statement that contradicts a decision in PROJECT_SPEC.md (D-01 to D-14). Quote both sides.
3. Stage prompts: list any ADR that contradicts, or any prompt amendment that goes beyond the few-line limit or changes an acceptance criterion.
4. ADR quality: each ADR has Context, Options (at least two), Proposed decision, Consequences, Revisit when; status values are valid (PROPOSED / ACCEPTED / SUPERSEDED); any ADR marked ACCEPTED was accepted by the operator and not the agent (check the git log and wording).
5. ADR-0002: recompute these with exact fractions and half-up rounding and compare with the ADR's worked examples: 55/300, 80/300, 278/300, 90/300, 180/300, and a net of -75. Report any mismatch.
6. ADR-0003/0007: do idempotency keys avoid PII, are dispatch events append-only with derived status, is there a DB-level uniqueness rule, do migrations start with the first table?
7. ADR-0004: do the S1 golden fixtures (+4/-1, 75 questions) still fit the marking-scheme data model without edits?
8. Part A: provider_contract.json parses as JSON; every code has class, source URL, date and send_path; default_class is OUTCOME_UNKNOWN; no RETRY_SAFE code is a 5xx or an auth error; 130472 and the other re-checked codes quote the page.
9. Tooling: run ruff, mypy, pre-commit and scripts/guardrails.py; report exit codes. Check the new guardrail rules skip cleanly when the target packages don't exist.
10. Honesty: any "verified", "compliant" or HIGH claim without a cited page and date.
11. The working tree contains uncommitted operator edits. Also review `git diff HEAD` (DECISIONS_OPEN.md, docs/adr/ADR-0003, ADR-0007, ADR-0010, docs/adr/README.md, docs/STATE.md). Confirm the three ADRs were changed only in their Status section, that README.md and STATE.md match, and that no ADR other than 0003, 0007 and 0010 was marked ACCEPTED.
12. DECISIONS_OPEN.md Part 3 says "No contradictions found." Do NOT trust it. Independently compare PROJECT_SPEC.md D-01 to D-14 against each ADR and each stage prompt, and report every contradiction with both quotes. If you find none, list what you compared.
13. Check that every reference in DECISIONS_OPEN.md resolves: the checklist item IDs it cites (C-01, C-03, P-04) must exist in docs/PRE_DEPLOYMENT_CHECKLIST.md, and every ADR it cites must exist.
14. Confirm each operator decision in DECISIONS_OPEN.md items 1-4 and 6-8 is consistent with the ADR or spec text it relates to (for example: the Latin-digit decision against the golden Hindi strings in S1 and S4, and the org_id decision against the idempotency-key design in ADR-0003).
15. Multi-tenancy and credential isolation: when reviewing S8, S9, S12 and S13, verify that every repository call requires an explicit org context (`org_id`), and that no global credentials or global phone-number IDs exist (every provider call resolves credentials from the calling org's sender identity).
Do not edit anything except docs/reviews/stage-0-r4.md.

## Mandatory Rigor Requirements for All Future Reviews
- **Raw Command Evidence:** Every check must include its exact command and its raw output (or tail), not just a bare PASS statement.
- **Clean Worktree Execution:** Guardrails and tooling must run on a clean `git worktree` checkout of the tag, and the report must explicitly state the SKIPPED count.
- **Attempts to Falsify (Min 3):** The report must include an "Attempts to falsify" section with at least 3 concrete attempts to find a defect, including the exact commands and results.
- **Zero-Defect Gating:** A report containing zero findings at MAJOR or BLOCKER severity is allowed only if the "Attempts to falsify" section is fully populated.