# Phase 02 (datagen): gate record
Commit: <sha> · Date: 2026-10-20 · Branch: phase/02-datagen · Tag: phase-02 · PR: <url>

## Commands run (verbatim) and results
| Command | pass / fail / skip |
|---|---|
| `BASE_URL=http://127.0.0.1:3000 bash scripts/gate.sh 02` | 13 of 13 automated steps PASS (265 unit tests, Phase 0 and 1 specs as regression, Phase 2 specs x2) |
| B1 over generated dense data | exactly the 50 CSV CRITICAL minutes; B0 = 0; builds Aug 1-30 in ~2.3 s; identical output across PYTHONHASHSEED |
| Shortcut-rule probe (warn log, rising 20 min, u@onset-15, nearby deploy) | precision 0.56 to 0.66 against a 0.56 chance level |

## Evidence flows
<!-- evidence:start -->
| Flow | Screenshots | What it proves |
|---|---|---|
| anchors-preserved | 1: 01-anchors-preserved.png | All 500 PS-02 rows are pinned in u-space; dense series between them stays below the CRITICAL band; the 08-01 AuthService to PaymentGateway cascade is visible |
| episode-gallery | 1: 01-episode-gallery.png | One generated episode per RC code and per negative (N1, N3, N4, N5, N6); N1 ramps like an incident (construction-bias guard) |
| csv-bench | 1: 01-csv-bench.png | The raw CSV bench: static threshold 0 of 28; the 95% rule 28 of 28 at 0.56 precision (test split 12 TP, 9 FP) |
| pytest-report | 1: 01-report.png | The Phase 2 pytest HTML report renders |
<!-- evidence:end -->

## Exit criteria
- [x] generator anchors all 500 rows in u-space (sanity gate 1 holds)
- [x] ps02 episode map covers the 50 CRITICAL rows; 28 incidents (6 abrupt), 22 negatives; RC-CERT never anchor-mapped (D7)
- [x] corpus excludes the test split by default and never returns the future or the incident itself
- [x] replayer: one message per service per tick, EventClock advanced before publish, agent-paced (D4)

## Interface changes since last freeze
`datagen.types`: METRIC_COLUMNS gained `anchor_ts`; `GroundTruthEpisode` gained `cause_event_id`. Additive; no `schemas.py` change.

## Skipped / deferred (with reason)

## Review findings and resolutions
Reviewer (opus) found no blockers and 7 majors; all fixed by two fix agents:
- Label leakage via pre-onset WARN/ERROR logs, precursor length and benign-deploy exclusion: fixed with background noise, widened negative leads and background deploys near negatives; shortcut rules now score near chance.
- Segment metric noise (6.8% of rows with u>=1): volume floor and rates adjusted (<0.5% now).
- `test_episode_map`/`test_corpus` lacked the `unit` marker (23 tests skipped by the gate): fixed.
- `docs_before` TypeError on aware timestamps, corpus stamped at onset not end, D3 test that could not fail, N3 label ignoring `benign_for`: all fixed.
- Deferred: shared `PS02_METRICS` constant (csv_bench keeps its own copy).
- Note: the demo MVP is preserved on branch `mvp-demo`; the phase branches stay on plan.
