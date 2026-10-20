# backend/ → sentinel-api

Python 3.12, uv, FastAPI. Run commands from `backend/`:
```
uv sync                       # install
uv run pytest                 # unit + integration (no network)
uv run ruff check . && uv run ruff format .
uv run uvicorn sentinel.api.main:app --port 8080
```

## Package map (`sentinel/`)
| Module | Role |
|---|---|
| `config.py` | `Settings` (env + `.env`). CSV path resolves to the repo `data/` dir or `/app/data` in the container |
| `schemas.py` | CES, Candidate, IncidentCandidate, RCA (FINAL_PLAN §7.5), Action, Ticket, TraceStep, PolicyState |
| `topology.py` · `bus.py` · `redact.py` · `clock.py` | Dependency graph + blast radius · InMemoryBus / PubSubBus · PII masking + `assert_no_pii` · sim/wall Clock + scheduler |
| `datagen/` | Generator in two modes: `ps02` (CSV anchors pinned in u-space) and `seeded` (P1) · corpus · replay |
| `detect/` | Holt ETA, EWMA z, binomial segment test, corroboration, risk, grouping, engine |
| `agents/` | runtime (invariants I1–I8, fallback), commander, specialists (`Agent.as_tool`), tools, grounding, llm |
| `memory/` · `impact/` · `actions/` | recall_similar store (cached embeddings + TF-IDF fallback) · PKR impact · policy_guard, executors, audit |
| `eval/` | splits, scorer, ablation, csv_bench, rca_eval, run_eval |
| `api/` | FastAPI app, SSE, routes |

## Conventions
- Config YAML lives in `backend/data/`. Prompts live in `backend/prompts/*.md`.
- Unit tests make no network calls. Use `FakeLLM` (scripted per episode from `tests/fixtures/llm_scripts/`), `FakeEmbedder` and `InMemoryBus`. Tests that touch GCP or OpenAI are marked `live` and skipped by default.
- Every tool returns `{"evidence_id": "<kind>:<hash8>", ...}` matching `^[a-z_]+:[0-9a-f]{8}$`. Tools return aggregates and redacted samples only.
- **Splits** (`eval/splits.py`):
  - `ps02`: tune on Aug 1–20, report on Aug 21–30.
  - `seeded`: tune on seeds 0–9, report on 100–129.
  - Test-split incidents never enter the memory corpus during eval.
- Anything time-based uses `Clock`, never `time.time()` or `datetime.now()` directly.
- Demo replay is in-process. `/ingest/pubsub` handles only the sim emitter. Cloud Run IAM authenticates push (`sa-push` OIDC).
- `llm_mode` (fake|live|off) is runtime state in PolicyState, toggled with `PUT /policy`.
- Mutating routes require `X-Operator-Token`, compared with `hmac.compare_digest`. `/docs` is disabled when `ENV=prod`.
- The OpenAI Agents SDK is pinned (`openai-agents==0.24.0`) and `OPENAI_AGENTS_DISABLE_TRACING=1` is set. Our own trace goes to BigQuery `agent_trace`.
