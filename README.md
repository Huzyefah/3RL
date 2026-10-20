# Sentinel for NovaPay (PS-02)

**Live:** https://sentinel-web-725314964496.us-central1.run.app (on Google Cloud Run, project `mda-atomcamp`)

Sentinel is agentic AIOps for a fictional Pakistani digital-payments platform, NovaPay. It does four things:
- **Predicts** payment-impacting incidents before they breach.
- **Argues false alarms down** with an adversarial Skeptic agent.
- **Writes grounded root-cause summaries** that link to past incidents.
- **Takes policy-gated preventive actions**, such as rerouting a degrading partner bank via Raast, with human approval.

> On the PS-02 data, a static threshold catches **0 of 28** incidents. The 95% rule catches all 28, but **44% of its pages are false**. Sentinel warns minutes earlier, argues away the noise, and arrives with the cause and the fix.

## Results

All numbers are computed by the scorer on the held-out split; none were typed by hand. The source is `backend/data/scorecard.json`.

**Splits:** τ was tuned on Aug 1–20 only. The report covers **Aug 21–30**, which has 12 incidents and 9 hard negatives.

| Config | Recall | Precision | False positives | Alerts | Median lead (p25–p75) | PKR protected (estimate) |
|---|---|---|---|---|---|---|
| B0: static threshold (u ≥ 1.0) | 0.00 | — | 0 | 0 | — | 0 |
| B1: today's 95% rule | 1.00 | 0.57 | 9 | 21 | 0 min | 0 |
| S1: Holt forecast only | 1.00 | 0.09 | 120 | 147 | 8 min | 129.0M |
| **S2: Sentinel detector + grouping** | **1.00** | **0.63** | **7** | **19** | **7 min (0.75–13)** | **92.5M** |

- **S2 vs B1:** S2 catches every incident with a median of 7 minutes of warning (B1 has 0), and every non-abrupt incident gets a lead greater than 0. It does this with fewer pages and fewer false positives than today's monitor.
- **Bootstrap 95% CIs:** S2 precision [0.50, 0.85], lead median [0.5, 13] min.
- **S3 (agents):** the Skeptic in S3 (Phase 4) then argues the remaining false positives (salary-day surges, batch jobs) down using cited calendar evidence.

**Sanity gates:**
- On the raw CSV, B0 TP = 0 and B1 = 28 TP / 22 FP (precision 0.56).
- On the dense replay, B1 recall is 1.0 with a lead of 0.

## How it works

```
PS-02 replay / finpay-sim ──► Detector (per series, every minute, no LLM)
                                u = share of error budget · Holt time-to-breach · EWMA z ·
                                binomial test per bank / OTP provider · corroboration → risk ≥ τ
                              ──► Grouping (cascade window 25 min, upstream service = root)
                              ──► Agents (gpt-6-luna)
                                  Commander: goal → plan v1 → … → plan v2 (re-plans on dispute / upstream signal)
                                  Investigator tools: metrics · segments · logs · forecast · topology
                                  Skeptic: calendar · deploys — tries to prove it's NOT an incident
                                  recall_similar (past postmortems) · PKR impact
                              ──► Policy Guard: AUTO (ticket, chat) · HITL (reroute bank, OTP failover, scale) · DENY
                              ──► UI over SSE: Live Ops · Incident trace · Scorecard
```

### Invariants enforced in code
| Invariant | Rule |
|---|---|
| I1 | No page without a Skeptic verdict |
| I2 | A BENIGN verdict needs a cited benign event **and** a recovering trend |
| I3 | Tier-0 incidents with high risk are never suppressed |
| I5 | Evidence ids are grounded (unknown ids → regenerate, then low-confidence) |
| I6 | Agents only *request* actions; the guard decides |
| I7 | Any LLM error → deterministic fallback; the system never goes silent |

### No ML classifier, on purpose
The EDA found that nothing in a single row separates real incidents from false ones (cross-validated AUC 0.41–0.48). A model trained on our own synthetic labels would only learn the generator back. Detection is therefore statistical. Only τ is grid-tuned; the hand weights were set once on the train split.

### Data honesty
- **Real:** all 500 PS-02 rows are pinned exactly in u-space.
- **Generated:** everything between them comes from a seeded, committed generator (`backend/data/ps02_episode_map.yaml`).
- **Hard negatives** ramp like incidents (surges, batch jobs, spikes, and unexplained N6 cases with no benign evidence), 20% of incidents are abrupt, and deploys and salary days coincide with real incidents.
- **Labelling:** the UI labels this "synthetic replay". PKR figures are estimates.

## Repository

| Path | Contents |
|---|---|
| `backend/` | FastAPI `sentinel-api`: `sentinel/{datagen,detect,eval,agents,actions,impact,api}` |
| `sim/` | `finpay-sim`: the NovaPay sandbox. Its BANK_C fault is fixed by a Raast reroute |
| `frontend/` | Next.js 16 `sentinel-web`: Live Ops, Incident, Scorecard |
| `infra/` | Preflight, idempotent GCP bootstrap, Cloud Build deploys (no local Docker needed) |
| `docs/test-evidence/phase-*/` | Per-phase test evidence: screenshots, charts, junit, READMEs |

Branches are kept separate per phase: `phase-m1-preflight` → `phase-00-bootstrap` → `phase-01-contracts` → `phase-02-generator-sim-ui` → `phase-03-detection-demo` → `phase-04-agents-api`.

### Run locally
```
cd backend && uv sync && uv run uvicorn sentinel.api.main:app --port 8080     # replays demo episodes automatically
cd frontend && npm ci && SENTINEL_API_URL=http://localhost:8080 npm run dev   # http://localhost:3000
cd backend && uv run pytest   # 64+ tests
uv run python -m sentinel.eval.ablation   # recomputes scorecard.json
```

## Status
| Scope | State |
|---|---|
| P0 phases −1 to 5 | Built and deployed |
| Scorecard S3/S3−Sk row, live-acceptance automation | Pending |
| P1 items (Security Sentinel, Log Analyst, Vertex judge, Scheduler) | Pending; see the phase plan |
