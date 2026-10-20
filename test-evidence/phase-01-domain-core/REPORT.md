# Phase 01 (domain-core): gate record
Commit: <sha> · Date: 2026-10-20 · Branch: phase/01-domain-core · Tag: phase-01 · PR: <url>

## Commands run (verbatim) and results
| Command | pass / fail / skip |
|---|---|
| `BASE_URL=http://127.0.0.1:3000 bash scripts/gate.sh 01` (against the compose stack) | 13 of 13 automated steps PASS (ruff, pyright, eslint, tsc, pytest unit 129 passed, vitest 7, Phase 0 specs as regression, Phase 1 specs x2) |
| OpenAI `to_strict_json_schema(RCA)` probe | pass: every property required, additionalProperties false, 0 `default` keys |

## Evidence flows
<!-- evidence:start -->
| Flow | Screenshots | What it proves |
|---|---|---|
| pytest-report | 1: 01-report.png | The Phase 1 pytest HTML report (129 tests) renders |
| topology-graph | 1: 01-topology.png | The 8-service dependency graph with owners, tiers and segments; no SearchAPI to UserProfileService edge (D6) |
<!-- evidence:end -->

## Exit criteria
- [x] schemas, ids, config, store, topology, clock, bus, scheduler, redact, data YAML and runbooks implemented with the FP section 13 Task 1 tests
- [x] schema snapshot frozen (`backend/tests/fixtures/schema_snapshot.json`)
- [x] RCA schema is OpenAI strict-mode compatible

## Interface changes since last freeze
First freeze of `schemas.py`. `ActionType` names follow `policies.yaml` (notify_channel, restart_service, rollback_deploy, change_ledger_balances, change_limits, send_reminder, escalate, disable_feature_flag). Direction vocabulary is `higher_bad` / `lower_bad` everywhere.

## Skipped / deferred (with reason)

## Review findings and resolutions
Reviewer sub-agent findings, fixed by four parallel fix agents (sonnet):
- Blocker: RCA schema not OpenAI strict compatible (`ActionParams` optional fields, defaults). Fixed; test strengthened and cross-checked with `openai`'s own strict converter.
- Major: redact false positives on long digit runs and float decimals. Fixed with boundaries; negative tests added.
- Major: direction vocabulary split between YAML and `utilisation()`. Unified; unknown directions raise.
- Major: bus could deadlock on an abandoned or closed subscriber. Subscription is now an async context manager; closing unblocks publishers.
- Minor fixed: naive datetimes rejected in scheduler and EventClock; CancelledError no longer loses a job; ActionType unified with policies.yaml; sim_admin_token fails closed outside dev; snapshot test normalised.
- Deferred minors: calendar EOD timezone is fixed to Asia/Karachi; cron supports only daily "M H * * *".
