# Frontend and interaction design

Build an incident workspace for payment on-call engineers. The central question is “What is approaching failure, what evidence supports that, and what happened after the action?” Use a restrained light interface with dark readable text, service colors only where they convey state, and a persistent **Synthetic replay / Organizer sample / Live** mode label. Live remains disabled until a real source is connected. No currency-saved counter without independently defined business data.

| View | Purpose and content | APIs | States and acceptance |
|---|---|---|---|
| Overview | Health with freshness; open early warnings; at-risk dependency; queue wait and failed-attempt fraction; service/severity counts; detector status | overview, incidents | No warnings explains observed window; stale data displays unknown health; load/error states preserve last timestamp; cards open investigation |
| Incident investigation | Shared clock timeline; metric versus baseline; provider→adapter→queue→checkout graph; facts vs hypotheses; supporting and contradicting evidence; similar past cases and source status | incident, evidence, timeline | Warming up, investigating, no history, model unavailable, contradictory evidence, resolved; each summary evidence link focuses the chart/window |
| Action center | Policy reason, proposed parameters, approval requirement, pending actions, receipts, verification and rollback/escalation | actions, propose/approve/reject | Proposed→allowed/denied/awaiting approval→executing→unknown/verified/failed/inconclusive; simulation button always says simulate; approver controls hidden from viewer |
| Evaluation and learning | Baseline versus proposed counts and FPR denominators; lead-time distribution with misses/late; root-cause rubric measured/unmeasured; corrections | evaluation, feedback | No data means not evaluated, not 0%; compare same dataset/version/partition; show false-positive runs alongside successful demo |
| Replay | Select fixture; pause/step/speed; event feed; detector state; tool timeline; baseline and intervention worlds | scenarios, replays, timeline | Explicit initializing/running/paused/completed/failed; complete means all expected events and final state recorded; pause must stop clock advancement |

## Investigation wireframe

```text
PayGuard      Synthetic replay      Replay clock 01:14      Data fresh
Incident PG-001   Early warning   Queue service at risk   Evidence high

Provider -> Adapter -> Processing queue -> Checkout
[latency and retry chart]          [queue wait and breach boundary]

Observed facts                    Current hypotheses
E12 provider duration rising      1 provider slowdown with retry load
E13 retries + queue growth        2 worker capacity loss (contradicted E18)

Similar verified case H03         Runbook RB-retry-budget v1
What matches / what differs       Preconditions, limits, verification

Ticket created T001   Alert recorded   [Simulate retry cap]
Verification: pending fresh windows   Execution receipt A001
```

MVP uses four navigation items by combining evaluation and replay controls in one workspace. Overview, incident and action views are the core. Include accessible keyboard focus, explicit state text alongside color, responsive single-column charts and clear time/unit labels. Use service names the judge understands; do not place infrastructure implementation jargon in the user journey. Raw tool arguments remain available in an audit details drawer for technical review.

Business impact: show measured queue and failed-attempt estimates, and a separate “potential exposure” formula only if arrival, duration and unit assumptions are explicit. Attempts are not customers or unique transactions. An optional hypothetical monetary exposure uses user-entered average transaction value and a deduplicated request count; omit it in this MVP because that data is absent.
