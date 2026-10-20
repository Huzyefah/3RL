# Data strategy and scenario engineering

Preserve the organizer CSV as a separate benchmark lane. Add explicitly synthetic, temporally coherent payment-operations scenarios for warning and intervention experiments. No public payment dataset has been downloaded or used; public engineering documentation informs mechanism choices, not calibrated simulator parameters.

## Data sources and lineage

| Approach | Decision | Reason and limits |
|---|---|---|
| Original 500 records | Keep byte-identical in `data/raw` | Required sample-data demonstration; synthetic point labels, no episode onset |
| Map service/metric names to fintech | Conceptual mapping only | PaymentGateway can remain itself; DataPipeline can suggest a processing queue. Do not relabel unrelated records as measured banking telemetry |
| Augment original rows with business metrics | Reject as measured augmentation | Values and relationships do not establish transaction counts, capacity, units or money |
| Causal synthetic sequences | Execute separately | Allows precise fault, onset, action and negative-case evaluation; assumes the mechanism it is designed to test |
| Public logs or incident reports | P1 external-validity check | Operational postmortems can challenge narratives; no public fraud dataset solves payment reliability labels |

Raw → timestamp parse and ratio derivation → sorted organizer CSV. No imputation, resampling, outlier removal or unit conversion. Ratio assumes value and threshold are comparable, which is plausible but not documented. Timestamp timezone remains unknown. Do not interpolate each sparse service/metric into a dense fabricated time series.

Config/seed → exogenous demand, capacity and latency noise → fault ramp → retry feedback and queue recursion → observed telemetry → separate retrospective onset labels. The action branch reuses identical exogenous noise and changes the retry fraction cap only. `run_key`, `step`, timestamps and manifest metadata are excluded from the detector's feature allowlist.

## Executed generator

Source: [scenarios.py](../src/scenarios.py). Configurations and truth: [manifest](../data/scenarios/manifest.json), [experiment settings](../data/scenarios/experiment_config.json). All 96 sequences are synthetic, 180 one-minute windows each: 24 train, 24 validation, 48 final test. Seeds are disjoint; final test uses a sigmoid fault ramp while training uses linear and validation quadratic ramps. All share the same simulator family. No trained ML model uses the train partition; it is reserved for baseline behavior, scenario development and the proposed historical casebook.

Demand is approximately 55–65 unique arrival requests/s with a small sinusoid and Gaussian noise; nominal capacity is 80–90 attempts/s. Source units here are explicitly defined by us. Initial provider latency is 140–220 ms; a positive fault adds 350–650 ms gradually. The fault reduces nominal capacity by up to 18% for longer worker occupancy. These bounds are engineering assumptions, not empirical processor distributions.

At each step: retry fraction = clip(0.01 + 0.00065 × max(latency−250,0) + 0.0015 × max(queue_wait−15,0), 0.005, 0.65); retry-storm cases impose a fault-dependent retry floor. Attempt rate = arrival rate × (1 + previous retry fraction). Queue = max(0, previous queue + 60 × (attempt rate − capacity)). Queue wait = queue / capacity. Error fraction = clip(0.001 + 0.0008 × max(wait−60,0) + 0.00003 × max(latency−850,0), 0, 0.95). The simulator assumes a fluid FIFO queue, homogeneous attempt costs and stable noise. It omits individual transaction identities, timeouts competing with completions, real provider contracts, idempotency reconciliation, bank cutoffs and multi-region routing.

Incident onset is the **first** window in a three-window sustained period of queue wait >120 s or error fraction >5%. Labels are created retrospectively and never passed to the detector. The coarse incident end is the last breached window; a run contains at most one evaluated incident envelope, so recovery gaps are not separate episodes. This simplification must be replaced if using real multi-episode traces.

## Scenario catalog

Severity below is proposed operational severity; labels depend on actual generated breaches. A fault injection is not automatically an incident-positive sequence. Exact onset/end and seed are in the manifest.

| ID / narrative | Fault and initial conditions | Observable evidence and expected behavior | Incident/onset and warning | Hypothesis and preventive workflow | Success and failure |
|---|---|---|---|---|---|
| S1 provider_slow | Healthy warmup; provider response slows over 10–19 min, capacity contracts | Provider latency then retries then queue; require persistence and backlog | Onset per sustained breach, high severity if reached; desired 5–20 min warning | Provider slowdown with retry amplification; ticket, retry-budget runbook, simulated 2% cap | Earlier warning and fewer breach minutes; fail if no benefit, unsafe recommendation or normal slowdown over-alert |
| S2 retry_storm | Same warmup; slow provider plus increasing retry floor | Extra attempts consume capacity and amplify queue | Same onset rule; strongest demo candidate | Retry amplification plausibly contributes; simulate cap, verify common-noise comparison | Reduced queue/severity; fail on duplicated action or claim of unique payments saved |
| S3 capacity_loss | Worker capacity falls 30–42%, without a provider latency fault | Queue grows before errors; provider evidence stays normal | Same onset; warning supported by queue-growth channel | Worker capacity loss; recommend capacity diagnostic; retry cap may help secondary load but may not recover service | Revise provider hypothesis; escalate when cap fails or only partly helps |
| S4 normal_surge | Demand and capacity both rise 65% during campaign | More traffic without growing backlog/error burden | Negative unless breach unexpectedly occurs; no desired action | Healthy capacity-matched demand | Observe; fail on financial-loss claim or remediation |
| S5 transient_spike | Two one-minute provider-latency spikes | Short latency/retry disturbance; persistence gate should filter | Usually negative; no intended incident | Transient issue, insufficient sustained evidence | No action; fail on premature remediation |
| S6 healthy | Stable operation with ordinary noise | Normal fluctuation | Negative | No incident | No action; fail on alerts or invented history |

Runbook action is restricted to a simulator retry cap at 0.02 beginning one window after the first hybrid alarm. It does not improve provider latency, restore capacity or change monetary state. It can reduce secondary amplification even when the primary capacity fault remains. Some reductions follow directly from the assumed equations; this is mechanism validation, not independent efficacy evidence.

## Synthetic dictionary

| Field | Meaning / unit | Availability and handling |
|---|---|---|
| run_key | Opaque sequence grouping key | Evaluation only, excluded as predictor |
| timestamp | UTC minute boundary | Replay clock; repeated across runs is intentional, namespace by run |
| step | Minute index 0–179 | Replay/evaluation only |
| arrival_tps | New request arrivals per second | Assumed observable aggregate, not money |
| attempt_tps | Initial plus retried attempts/s | Can exceed unique requests; never sum as unique payments |
| provider_latency_ms | Modeled provider duration | Defined milliseconds, not the original `latency_p99` variable |
| queue_depth | Fluid queued attempts | Continuous modeled count, not individual transaction records |
| queue_wait_seconds | Queue/capacity | Model approximation; not directly measured queue age |
| retry_fraction | Modeled additional attempts per arriving request | Simplified bounded fraction, not geometric unlimited retries |
| error_fraction | Expected failed-attempt fraction | Synthetic outcome proxy, not financial loss |
| capacity_tps | Worker processing capacity in attempts/s | Known in simulator; production needs observable throughput/capacity estimate |

`context_events.jsonl` supplements metrics with untrusted log/event examples. These are generated from scenario configuration and are **not consumed in the measured statistical experiment**. The proposed application must also ingest actual typed logs/events/span references and test their tool use; the package does not claim that implementation exists. In a later benchmark, remove causal diagnosis from log text and separate deployment history from hidden fault labels.

## Validation and next evidence

Executed checks verify no missing or negative features, 180 ordered windows/run, unique run/step keys, disjoint seeds, no exact cross-partition sequences and no fault/target columns in feature files. Coherent queue recursion is in executable source; schema feature filtering enforces prediction-time scope. These checks do not prove distributions realistic. Add independent demand shapes, abrupt faults, sustained benign latency, delayed/missing telemetry, clock skew and unsupported faults before deployment. The exploratory pilot is preserved under `reports/evaluation/exploratory_pilot`; its test was inspected during development, so it is not the final held-out evaluation.

Public data is optional, not necessary to complete the hackathon. If added, document license, timestamp semantics, sampling, cause confirmation and domain mismatch. Obtain real anonymized operational traces and an expert-reviewed incident casebook for any claim beyond synthetic demonstration.
