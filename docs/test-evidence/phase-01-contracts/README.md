# Phase 1: Contracts, clock, CSV bench

## Commands
| Command | Result |
|---|---|
| `cd backend && uv run pytest --junitxml=…/csv-bench/junit.xml` | **17 passed** (0 failed) |
| `uv run ruff check .` | clean |
| `uv run python -m sentinel.eval.csv_bench` | writes `analysis/outputs/rule_baselines.csv` and `csv_bench.json` |
| `uv run python -m tools.evidence_phase01 <dir>` | chart + JSON below |

## Flows
| Flow | Evidence | Result |
|---|---|---|
| `csv-bench`: sanity gate 1 on the raw 500 rows | [chart](csv-bench/01-csv-bench-b0-vs-b1.png) · [json](csv-bench/csv_bench.json) · [junit](csv-bench/junit.xml) | PASS: B0 TP=0 FP=0 · B1 TP=28 FP=22 FN=0, precision 0.56, recall 1.0 · 0 band mismatches (the CSV's `alert_level` is exactly u bands 0.75/0.95) |

## Tests added
`test_u_higher_bad`, `test_u_lower_bad`, `test_bands_match_ps02`, `test_ces_u_property_and_defaults`, `test_candidate_and_rca_roundtrip`, `test_blast_radius_ledgersync_includes_reporting`, `test_cascade_edges_from_csv_pairs_are_linked`, `test_owner_team_and_tier`, `test_bus_backpressure`, `test_bus_fifo`, `test_redact_msisdn_pan_cnic` (Luhn-checked), `test_assert_no_pii_helper`, `test_sim_clock_scheduler`, `test_sim_clock_cancel`, `test_csv_bench_matches_eda` (**hard-coded** expected values), `test_csv_bands_reproduce_alert_level`.

## Deviations
- `PubSubBus` is deferred to Phase 3 lane B, where the ingest/mirror path is built. Phase 1 ships the `Bus` protocol and `InMemoryBus`.
- Evidence charts live in `backend/tools/` (a dev-only dependency on matplotlib), using the dataviz skill's reference palette.
- Built in a git worktree while the Phase 0 deploys were uploading, to keep work-in-progress out of the images.
- The `/simplify` pass is folded into the Phase 2 gate, where the run covers the Phase 1 diff too. Self-review was done here.

## Gate checklist
- [x] TDD red → green
- [x] Sanity gate 1 passes against hard-coded EDA values
- [x] Cumulative suite green (backend 17, sim 1)
- [x] Evidence saved (chart, JSON, junit)
