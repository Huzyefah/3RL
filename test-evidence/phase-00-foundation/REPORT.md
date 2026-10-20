# Phase 00 (foundation): gate record
Commit: <sha> · Date: 2026-10-20 · Branch: phase/00-foundation · Tag: phase-00 · PR: <url>

## Commands run (verbatim) and results
| Command | pass / fail / skip |
|---|---|
| `BASE_URL=http://127.0.0.1:3000 bash scripts/gate.sh 00` (against the compose stack) | 12 of 12 automated steps PASS: ruff check/format, pyright, eslint, tsc (frontend, e2e), pytest unit (8 passed) and integration/e2e_http (none yet, exit 5 mapped to pass), vitest (7 passed), Playwright x2 (flake check; 2 passed, 1 skipped on the repeat run because the report spec runs once), evidence index |
| `docker compose build` | pass: sentinel-api, finpay-sim, sentinel-web |
| `docker compose up -d` + curl `/healthz` on :8080 and :8081, `/` and `/api/healthz` on :3000 | pass: both services report ok; web returns 200; the proxy reaches the API through the containers |
| OpenAI key check in the web container | 0 OPENAI variables present (key goes to sentinel-api only) |

## Evidence flows
<!-- evidence:start -->
| Flow | Screenshots | What it proves |
|---|---|---|
| harness-smoke | 1: 01-home.png | The real Next.js page renders "Sentinel" with an icon+text status badge, and axe finds no serious violations |
| pytest-report | 1: 01-report.png | The pytest HTML report renders and is captured by the evidence pipeline |
| eda-facts | 1: 01-rule-baselines.png | The standalone EDA reproduces the PS-02 baselines: B0 0/28, B1 28 TP / 22 FP at 0.56 precision |
<!-- evidence:end -->

## Exit criteria
- [x] `make gate PHASE=00` automated steps green
- [x] All three images build and start under compose (placeholder `/healthz` apps for api and sim)
- [ ] CI green on the PR (checked after push)

## Interface changes since last freeze

## Skipped / deferred (with reason)
- Pub/Sub and BigQuery emulators in compose: planned for Phase 8.
- `gcloud` not installed; manual task 0.11 pending (user). Not needed until Phase 8b.

## Review findings and resolutions
Reviewer sub-agent (code-review) findings, all verified before fixing:
- Blocker: regression Playwright runs wrote evidence (`EVIDENCE_PHASE=regression`). Fixed in `e2e/support/evidence.ts`.
- Blocker: CI/gate had no frontend server. Added a Playwright `webServer` (skipped when `BASE_URL` is set).
- Major: `backend/data` and `backend/prompts` missing, so the image build failed (also seen in a real build). Added with `.gitkeep`.
- Major: sim lacked uvicorn. Switched to `fastapi[standard]` and added placeholder apps.
- Major: `evidence_index.py` wiped hand-written text. Now preserved.
- Major: over-broad `.claude/settings.json` allowlist. Narrowed (no `gh pr merge`, no arbitrary `uv`/`npm`/`docker compose` subcommands).
- Minor: compose passed the key to every service and bound to 0.0.0.0. Key now goes to sentinel-api only; ports bind to 127.0.0.1.
- Minor, left as is: duplicate plan copies under `docs/`; Node version tie between `.nvmrc` and CI.
