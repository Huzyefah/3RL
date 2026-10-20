# Demo and judging strategy

Target a four-to-five-minute presentation. Use the final test retry-storm fixture selected by run key in the computed report and a negative normal-surge fixture. Fixed seed and recorded versions make replay reliable. The statistical simulator is implemented; the deployed UI, model investigator and action tools remain backlog work and must pass the gates before they are presented as working.

| Time | Show | Evidence and intended takeaway |
|---|---|---|
| 0:00–0:30 | Payment retry-cascade problem and synthetic mode | A slow provider can amplify queued work; no claim of fraud or money saved |
| 0:30–1:00 | Healthy baseline; incoming metric/log/event feed | Statistical warmup/freshness, dependency graph and real deployed ingestion |
| 1:00–1:45 | Latency, retries and queue begin rising | Warning occurs before fixed no-action onset; show both event clock and processing timestamps |
| 1:45–2:30 | Agent investigation trace and history | Select metric/dependency/history tool, compare capacity alternative, cite verified training case or say no match |
| 2:30–3:10 | Summary and preventive workflow | Facts/hypotheses/uncertainty; ticket+alert receipt; runbook; policy-authorized simulator action |
| 3:10–3:45 | Verification and paired comparison | Same noise, retry-cap action only; queue/breach-minute change; receipt and audit; simulation label |
| 3:45–4:20 | Negative normal surge and a refusal | Traffic grows with capacity, no remediation; risky or stale-data proposal denied |
| 4:20–4:50 | Original CSV lane and honest results | 500 source rows; threshold/ratio baseline; no original lead-time claim; synthetic aggregate false alarms and limits |

Do not imply a four-minute presentation is a real four-minute incident: accelerated replay uses a distinct event clock. Do not hide a model failure behind prerecorded output marked live. Original sample demonstration and synthetic prevention demonstration are two explicit lanes; no metric is silently transferred between them.

## Rubric coverage

| Criterion | Where visible | Required artifact before submission |
|---|---|---|
| Detection lead time | Warning marker before counterfactual onset, distribution in evaluation | Frozen scenario metrics, onset definition and missed/late counts |
| False positives | Normal surge plus aggregate negative-run/window rates | FP/TN counts and false-positive investigations |
| Root-cause quality | Evidence-linked on-call summary and alternate hypothesis | Human-scored evidence packs, not just fluent prose |
| Agentic behavior | Tool selection, contradiction revision, policy action, verification | Durable state/tool/action trace; refusal case |
| Technical depth | GCP execution trace and typed contracts | Private authenticated worker, idempotency/restart tests |
| MVP completeness | Sample-data replay and full synthetic cycle | Running backend/frontend; all action statuses real or explicitly simulated |
| Scalability | Buffering, bounded work, load/failure panel | Measured cloud workload/latency with limits |
| Innovation | Payment-specific failure mechanism and paired verification | Causal assumptions visible; no broad novelty superiority claim |

## Short pitch

“PayGuard helps payment on-call teams catch retry cascades before checkout stalls. It combines persistent telemetry signals with a bounded investigation that checks dependencies and prior incidents. It opens a preventive ticket, recommends a grounded runbook, and demonstrates a retry-budget action in simulation with a verification trail. We show warning time and false alarms against the same baseline, including cases where the system should stay quiet.”

## Technical explanation

“The detector is deterministic and past-only. It combines robust latency deviation with retry and queue evidence; the language model does not decide whether a metric exceeded a boundary. One stateful investigator chooses scoped tools, tests competing hypotheses and produces a schema-validated assessment. A separate policy and idempotent action ledger control effects. GCP provides authenticated event delivery and durable state. Paired synthetic replays test one intervention under shared exogenous noise; production validation remains future work.”

## Contingencies

LLM unavailable: continue statistical replay and display a deterministic evidence summary with `model unavailable`; show a previously captured model trace labeled recorded and disclose that live reasoning failed. Cloud unavailable: use a locally served/readable report, fixture charts, saved metric files and a previously recorded deployed trace, clearly labeled offline. No cached artifact currently proves an application deployment; record it only after the actual application exists. Replay bug: use saved baseline/action CSV pair and show the exact seed/config. Do not claim a fallback recording satisfies a live-cloud gate without organizer agreement.

Before presenting: run the complete fixture twice; verify model/token budgets, credentials and replay clock; clear only disposable replay namespaces; keep original data, history and action ledger intact; open the negative case; keep an accessible saved report and 60-second recording. End with the benefit supported by actual measurements: earlier warning and fewer modeled breach minutes under stated assumptions, with the false-alarm tradeoff visible.
