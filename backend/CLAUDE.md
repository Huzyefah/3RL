# backend (sentinel-api)

Python 3.12 uv workspace member. Phase 1 creates the package contract below; later phases fill it in. Do not assume a module exists before its phase (see the plan's per-phase Files lists).

## Commands

```
uv run pytest -m unit --disable-socket --allow-unix-socket   # hermetic, no network
uv run pytest -m integration                                  # in-process API, sim, ScriptedModel
uv run pytest -m e2e_http                                     # real uvicorn on free ports (Phase 5+)
uv run pytest -m live                                         # real OpenAI; reported skipped without a key
uv run ruff check . && uv run ruff format --check . && uv run pyright
uv run uvicorn sentinel.api.main:app --port 8080 --reload     # Phase 6+
```

Markers: `unit`, `integration`, `e2e_http`, `live`, `gcp`. `live` and `gcp` are deselected by default.

## Package map (target)

`sentinel/{config,schemas,ids,topology,bus,redact,clock,store,scheduler,pipeline}.py` plus `datagen/ detect/ agents/ memory/ actions/ impact/ eval/ connectors/ api/`. Full tree: the plan's "Target repository layout". Authored data in `backend/data/`, prompts in `backend/prompts/`.

## Contracts to hold

- Utilisation `u = value/threshold` (direction-aware); `band = 1[u >= 0.95]`. Defined once in `schemas.py`/`utilisation()`.
- Evidence IDs match `^[a-z_]+:[0-9a-f]{8}$`.
- B0/B1 evaluate only the 7 PS-02 metric series (D3). Segment metrics feed S1 and up.
- Timers use the clock named in the plan's timer table (event vs wall); `test_timer_clock_assignment` enforces it. Detector parameters are per-minute, converted by `per_tick`.
- Risk score and features: the plan's "Risk features". Grouping: D5/D6. Replay pacing: D4. Fake and scripted LLMs are SDK `Model` implementations: D11.
- Invariants I1-I8 (FP section 7.2) live in `agents/runtime.py` and `request_action`; one test per invariant.
- `actions/policy_guard.py` needs a test per rule; `test_every_policy_rule_has_a_test` checks every `policies.yaml` key is referenced.
- Incident IDs: D9. Segment/ps02 episode map rules: Phase 2 in the plan.
- Schema snapshot (`tests/fixtures/schema_snapshot.json`): update it deliberately and note it in REPORT.md.
