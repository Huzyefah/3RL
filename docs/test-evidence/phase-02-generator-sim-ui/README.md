# Phase 2: Generator ∥ sim core ∥ UI shell

Lanes B (sim) and C (UI) were built by parallel sub-agents in disjoint directories. Lane A (the generator) was built by the lead.

## Suites (cumulative)
| Suite | Result |
|---|---|
| backend `uv run pytest` | **64 passed**: Phases 1, 2 and 3-in-progress, all green; ruff clean |
| sim `uv run pytest` | **25 passed**; ruff clean |
| frontend `npm run lint && npm run build` | pass |
| e2e `MOCK=1 npx playwright test tests/phase-02` (@fake) | **pass**, 6 consecutive runs after one flake fix |

## Flows
| Flow | Evidence | Result |
|---|---|---|
| `generate-ps02`: ps02-mode dataset | [RC-BANK episode](generate-ps02/01-rc-bank-episode.png) · [N1 surge](generate-ps02/02-n1-surge-hard-negative.png) · [N5 spike](generate-ps02/03-n5-transient-spike.png) · [summary](generate-ps02/summary.json) · [junit](generate-ps02/junit.xml) | PASS: 43,260 minutes × 69 series; all 500 anchors preserved in u-space (to 1e-6, bands unchanged); **B1 = exactly 50 alert runs, B0 = 0** (reproduces the CSV); 28 incidents, of which 6 are abrupt (21%); 22 hard negatives (N1 ×6, N3 ×5, N5 ×6, N6 ×5); confounders (surge, deploy) and about 1 benign deploy a day |
| `replay-inmemory`: single-episode replay through InMemoryBus | [replay.json](replay-inmemory/replay.json) | PASS: 77–104 one-minute ticks per episode, 8 envelopes per tick, about 0.1 s at speed 0, PII check passes on every envelope |
| `sim-reroute`: finpay-sim closed loop (deterministic engine) | [chart](sim-reroute/01-bank-c-success-rate.png) · [series](sim-reroute/series.json) · [junit](sim-reroute/junit.xml) | PASS: BANK_C success 0.985, falling to 0.729 under `bank_c_slow` (first below 0.97 at +20 s), then 0.996 after reroute → Raast; recovered within the first 5 s window |
| `ui-shell-mock`: Live Ops + Incident on mock SSE through the same-origin proxy | [desktop](ui-shell-mock/01-live-ops-desktop.png) · [countdown](ui-shell-mock/02-live-ops-incident-countdown.png) · [trace v2](ui-shell-mock/03-incident-trace-plan-v2.png) · [evidence popover](ui-shell-mock/04-incident-evidence-popover.png) · [business summary](ui-shell-mock/05-incident-business-summary.png) · [mobile](ui-shell-mock/06-live-ops-mobile.png) · [incident mobile](ui-shell-mock/07-incident-mobile.png) · [dark](ui-shell-mock/08-live-ops-dark.png) | PASS: the countdown decreases; BANK_C turns Warning while the other banks stay Normal; the trace shows plan v1 → DISPUTED → plan v2; no horizontal scroll at 390 px |

## Decisions and deviations
- **Episode map** (`backend/data/ps02_episode_map.yaml`) is seeded and committed, and the regeneration test proves it is reproducible.
  - Codes come from an auditable metric/service table. Initial draft: 17 of 28 were RC-DBPOOL, so the table was rebalanced to 9 DBPOOL / 8 QUEUE / 6 MEMLEAK / 3 BANK / 2 OTP.
  - N6 ("unexplained") is kept off calendar-event days and away from surge confounders on the same service, so it truly has no benign evidence (`test_n6_has_no_benign_evidence`).
- **Bumps toward WARNING rows** are wide (σ = 10 min). The first draft's σ = 4 produced incident-like ramps; this was caught in Phase 3 on the **train** split.
- **PII detector fix:** float fractions such as `0.9715381759683208` could pass the Luhn check and were flagged as PANs. Digit runs after a `.` are now excluded, covered by a new test.
- **Campaign names in synthetic events** are fictional only; a real-brand reference was removed.
- **Sim (lane B):**
  - Standby-provider probes keep P2's health observable. `cred_stuffing` and `/admin/throttle` are deferred to P1 (8a).
  - A Pub/Sub sink for the emitter is Phase 3 lane B.
- **UI (lane C):** the SSE contract is documented in `frontend/lib/types.ts`. A `snapshot` is sent on every (re)connect, and `actions` are included so pending approvals survive a reconnect. Approve, reject and feedback are wired to the API in Phase 6.
- The `/simplify` pass for Phases 1–2 ran as a self-review. Lint auto-fixes were applied, and dead code (an `if False` branch and a whole-series clamp bug in `_sympathetic`) was removed.

## Gate checklist
- [x] All 28 anchors mapped; anchors preserved; B1 = 50 on ps02 mode
- [x] Sim closed loop proven deterministically
- [x] UI shell renders on mock SSE through the real proxy, desktop + mobile
- [x] Screenshots reviewed by eye
