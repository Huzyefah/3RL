# Sentinel for NovaPay (PS-02)

Agentic AIOps for a fictional Pakistani payments platform. It predicts payment-impacting incidents before they breach (Holt ETA, binomial segment tests). An adversarial Skeptic argues false alarms down. It writes grounded RCAs linked to past incidents and takes policy-gated actions, one of which (reroute a bank via Raast) fixes a live fault on stage. Every number on the scorecard is computed on held-out data.

- **Spec:** `docs/FINAL_PLAN.md`. Where it conflicts with the "Global decisions" below, the decisions win (they come from an audit).
- **Execution plan:** phases −1…9 with a gate per phase. The status table is below.

## Layout and deployables
| Dir | Deploys to | Notes |
|---|---|---|
| `backend/` | Cloud Run `sentinel-api` (**private**, min=max=1, no CPU throttling) | FastAPI + detector + agents + policy guard. See `backend/CLAUDE.md` |
| `sim/` | Cloud Run `finpay-sim` (**private**, min=max=1) | NovaPay sandbox with chaos and admin. See `sim/CLAUDE.md` |
| `frontend/` | Cloud Run `sentinel-web` (public) | Next.js 16. Same-origin `/api/*` proxy to the api. See `frontend/CLAUDE.md` |
| `e2e/` | — | Playwright. Specs are tagged `@fake` (local stack) or `@live` (Cloud Run) |
| `infra/` | — | `preflight.sh`, `bootstrap.sh`, `deploy.sh`, `bq_schema.sql`, `cloudbuild/`. See `infra/CLAUDE.md` |
| `data/ps02_system_telemetry.csv` | — | Canonical PS-02 sample. **Never modify.** |
| `docs/test-evidence/` | — | Phase evidence (screenshots, junit, READMEs) |

## Commands
```
make test          # backend + sim pytest, frontend lint + build
make e2e           # all @fake Playwright specs (starts api :8080, sim :8081, web :3000 if not running)
make e2e-live      # @live specs; needs BASE_URL=https://sentinel-web-725314964496.us-central1.run.app
make dev           # run api + sim + web locally
make preflight     # read-only environment checks
make bootstrap     # idempotent GCP setup
make deploy-api | deploy-sim | deploy-web
```

## Non-negotiables
- Invariants I1–I8 (FINAL_PLAN §7.2) are enforced in code, and each has a test.
- **Model IDs only in env vars:**
  - `OPENAI_FAST_MODEL` and `OPENAI_SMART_MODEL` are both `gpt-6-luna`. The team chose the small tier for cost, so don't switch to sol or astra without asking.
  - `OPENAI_EMBED_MODEL` is `text-embedding-3-small`.
  - Never use a `gemini-2.5-*` ID.
- No PII ever reaches an LLM, SSE, a Chat card, BigQuery or the evidence. `assert_no_pii()` covers MSISDN `03\d{9}`, CNIC, and Luhn-valid PANs.
- Never type a number that the scorer didn't produce. Slides and the README cite `scorecard.json`.
- **Utilisation and bands:**
  - higher-is-bad: `u = value/threshold`
  - lower-is-bad: `u = (1−value)/(1−floor)`
  - Bands: NORMAL < 0.75 ≤ WARNING < 0.95 ≤ CRITICAL
- All YAML config lives in `backend/data/`. The root `data/` holds only the CSV.
- Secrets live only in `.env` (gitignored) and in Secret Manager. Never print or commit keys.
- Pre-existing Cloud Run services `gcp-openai-demo` and `mda-atomcamp` must never be touched.

## Global decisions (from the audited plan)
- **Build:** `gcloud builds submit` runs from the repo root (no local Docker), then `gcloud run deploy --image`. `/healthz` reports `csv_rows=500`.
- **Browser → web → api:** the browser talks only to `sentinel-web`. The web proxy adds a Google ID token, plus the operator token on mutating calls, which lives server-side only. The api is reachable only by `sa-web` and `sa-push` (Pub/Sub OIDC), and the sim only by `sa-api`.
- **Replay** runs in-process (InMemoryBus) and is mirrored to Pub/Sub. Only the sim emitter uses push, with a reorder buffer and `event_id` dedupe.
- **Time:** `sentinel/clock.py` provides a sim/wall Clock. Re-checks, expiry, TTL, verification and cooldowns all use it.
- **LLM mode:** runtime `llm_mode = fake|live|off` via `PUT /policy`, never by redeploying. Plan v2 is code-triggered when an upstream candidate attaches.
- **Grouping:** cross-service cascade window of 25 min. Edge TransactionSearchAPI → CustomerProfile. All 28 CSV incidents are mapped in P0.

## Phase gate protocol
1. TDD: tests first (red), then implement (green).
2. Cumulative `make test` and `make e2e` (@fake) at every gate. `@live` specs run at their owning phase's gate, and the full live suite at Phases 7 and 9.
3. **Evidence path:** `docs/test-evidence/phase-NN-<slug>/<flow-slug>/NN-<step>.png`, made with `flowEvidence()` in `e2e/utils/evidence.ts`, or as matplotlib PNGs. Backend flows also save `junit.xml` and raw `*.json`/`*.txt`. No tokens or webhook URLs in screenshots. Videos go to `gs://mda-atomcamp-sentinel-evidence/`, never git.
4. `docs/test-evidence/phase-NN-<slug>/README.md` records the commands, pass/fail per flow, metrics, deviations, and a ticked gate checklist.
5. `/simplify` every phase. `/code-review high` and `/security-review` run over the full diff at Phase 7 (P0-complete) and Phase 9.
6. Redeploy each changed service after its phase, with a live `/healthz` smoke check.
7. **Git:** branch `phase-NN-<slug>`, conventional commits, merge `--no-ff` to `main` when green. **Do not push to GitHub without asking.**
8. Never carry a red gate forward. If a phase runs over its timebox, apply that phase's pre-written cut and record it.

## Phase status
| Phase | Scope | Status |
|---|---|---|
| −1 | Preflight | ✅ |
| 0 | Bootstrap, tooling, CLAUDE.md, hello-world deploy | in progress |
| 1 | Contracts, clock, CSV bench (sanity gate 1) | — |
| 2 | Generator ∥ sim core ∥ UI shell | — |
| 3 | Detection, grouping, impact, scorer ∥ sim emitter + ingest | — |
| 4 | Tools, memory, agents, grounding, S3 eval | — |
| 5 | Policy guard, executors, API/SSE, closed loop, deploy api+sim | — |
| 6 | Frontend P0 screens, deploy web | — |
| 7 | P0 live acceptance (a)–(d), demo-local, docs, recording → `p0-complete` | — |
| 8a–f | P1: security sentinel, log analyst, Vertex, scale, seeded+memory, scheduler | — |
| 9 | Final eval, reviews, slides | — |
