# Sentinel for NovaPay

PS-02 hackathon entry (event 2026-10-20). Sentinel predicts payment-platform incidents from telemetry, runs a hybrid agent loop (LLM plans, code enforces invariants), and acts through a Policy Guard. Synthetic data only; the PS-02 CSV is the real anchor.

Authority: `docs/FINAL_PLAN.md` (FP) is the spec. `docs/superpowers/plans/2026-10-20-sentinel-implementation.md` (the plan) sets execution order, decisions D1-D14, the timer table and each phase's tests and evidence flows. Cite them instead of restating them.

## Commands

```
make setup                 # uv sync, npm install (frontend, e2e), playwright browsers, .env
make dev                   # api :8080, sim :8081, web :3000 (parts appear as phases land)
make test                  # pytest unit (no network) + integration, vitest
make lint                  # ruff + eslint
make e2e                   # playwright (set EVIDENCE_PHASE=phase-NN-<slug> to write screenshots)
make gate PHASE=NN         # scripts/gate.sh: static, regression, phase specs x2, evidence index
make evidence PHASE=NN     # rebuild the REPORT.md evidence table
make compose-up / compose-down
make help                  # stubs say "not implemented until Phase N"
```

Python runs through `uv run` only. Phase slugs and each phase's required evidence flows live in `scripts/phases.json`.

## Workflow

- Branch `phase/NN-<slug>`, one phase at a time. A phase is done when `make gate PHASE=NN` is green, the REPORT.md is filled, and the PR is open.
- **After every phase gate, stop and ask the user whether to continue to the next phase (D14).** Do not create the next branch or touch its files until they say yes. This includes 8b and conditional phases.
- Merging to `main` needs the user's go-ahead (D13).
- Build model: the lead dispatches one implementer sub-agent per independent task, test-first (red, green, commit). Debug red results with systematic-debugging; verify with verification-before-completion before claiming green.

## Hard rules

1. Never type a scorecard number by hand; only `run_eval.py` produces them.
2. Model IDs live only in env vars; never use `gemini-2.5-*`.
3. No PII in prompts (a test pins the `03\d{9}` pattern).
4. Test-split incidents never enter memory during evaluation; `recall_similar` never returns the future or the incident itself.
5. The scripted LLM is test-only and always shows its UI badge.
6. Write evidence only via `shot()`; earlier phases' evidence folders are read-only.
7. Never call system `python3`; always `uv run`.
8. Never rename or weaken an FP section 13 test or its acceptance numbers.
9. Never hard-code the time-of-day finding (FP section 5).
10. SDK guardrails trip; they do not regenerate. Regeneration lives in `runtime.py`.
11. LLM calls happen only on grouped candidates and log-novelty batches.
12. Changing `schemas.py` after Phase 1 requires a snapshot update and a note in REPORT.md.
13. Unit tests make no network calls.
14. Commit at least every 30 minutes.
15. Merging to `main` needs the user's go-ahead.

## Map

| Area | Guide | Owns |
|---|---|---|
| `backend/` | `backend/CLAUDE.md` | detection, agents, policy, API (sentinel-api) |
| `sim/` | `sim/CLAUDE.md` | finpay-sim traffic, chaos, admin |
| `frontend/` | `frontend/CLAUDE.md` | Next.js UI and the SSE proxy (sentinel-web) |
| `e2e/` | `e2e/CLAUDE.md` | Playwright specs and screenshot evidence |
| `infra/` | `infra/CLAUDE.md` | GCP scripts (Phase 8b onward) |
| `analysis/` | `analysis/CLAUDE.md` | standalone EDA |
| `test-evidence/` | `test-evidence/README.md` | gate records and screenshots |

Layout rule (D1): root `data/` holds only the given CSV; authored YAML, JSON and embeddings live in `backend/data/`. Docker build context is the repo root. Secrets only in `.env` (gitignored); `.env.example` documents every variable.
