# Detection and agent workflow

## Separate signals from explanations

The detector calculates evidence. A language model chooses allowed read-only investigation tools, compares explanations and writes a structured assessment. A separate deterministic policy controls actions. The term “hybrid” in the executed synthetic results means **statistical multivariate rules**, not an evaluated LLM system. No API model was invoked in these experiments.

| Method | Supplied CSV fitness | Recommendation and reason |
|---|---|---|
| Static threshold | Valid point-rule comparison; zero threshold exceedances | Execute supplied threshold and ratio diagnostics; retain production SLO threshold comparator |
| Robust median/MAD | Metric names available but mixed units and sparse service streams | Use only within a metric/unit series after enough clean history; synthetic latency baseline uses first 30 windows |
| Rolling robust baseline | Sparse original sequences unsuitable | Production extension uses past-only 30–60 windows and freezes updates during anomalies |
| EWMA/CUSUM | Original series too sparse | P1 ablation after stable sampling; tune smoothing/drift and reset rules on validation |
| Isolation Forest | Can score static rarity, no proof rarity means incident | Optional offline comparator only after meaningful features; no need in MVP |
| Supervised incident predictor | 28 point labels with uncertain timing and likely generation artifact | Reject deployment; more labeled episodes and prediction-time feature audit required |
| Forecasting / LSTM / Transformer | 3–15 points per service/metric over a month | Reject for original data; insufficient density and seasonality coverage |
| Multivariate / dependency rules | New coherent sequences required | Default: sustained latency/retry/backlog evidence with explicit dependency graph |
| Change-point detection | Original temporal support weak | Optional detector ablation, not a core dependency |
| LLM interpretation | No actual causes or histories in source | Use evidence tools and curated synthetic casebook; evaluate separately |

## Executed statistical experiment

`src/scenarios.py` uses one-minute windows. The first 30 windows provide a presumed healthy warmup; this is an explicit experiment assumption. Latency z = (latency − warmup median) / max(1.4826 × MAD, 15 ms). Validation selects z from {3,4,5,6}; ties favor a stricter value, resulting in 6.

The actionable signal persists for three windows and requires either (latency z > 6 AND retry fraction > 0.08 AND queue wait > 20 s) OR (three-minute queue growth > 2 attempts/s AND queue wait > 20 s). These constants encode the simulated system, not universal payment limits. Static baseline: latency > 800 ms OR queue wait > 120 s OR error fraction > 0.05 for two windows. Both use the identical no-action stream. A multi-window SLO/burn-rate and a tuned static comparator are still required before claiming superiority over conventional monitoring generally.

Cold-start windows remain `warming_up`; do not infer safety from missing baseline. In production use previously verified history, not a guarantee that the first 30 minutes are normal. Low-MAD floors are per metric/unit. Missing two expected windows sets `data_gap`; telemetry older than two window lengths cannot authorize remediation. Out-of-order events within a two-window watermark may update evidence but never retroactively authorize an action. Later events are stored for analysis. Reorder handling is proposed, not exercised by the current offline detector.

## Proposed incident pipeline

1. Validate schema, nonfinite numbers, unit compatibility, timestamp and service scope. Derive idempotency from producer event ID and namespace; quarantine malformed records.
2. Aggregate by service, metric and unit on event time. Normalize only known equivalents. Organizer records remain in a separate unit-unknown lane and do not calibrate payment detectors.
3. Calculate baseline deviation, retry fraction, queue growth and measured error fraction. Track evidence windows and data completeness.
4. Correlate signals over the provider → adapter → queue → checkout graph. Open one incident episode keyed by service group and symptom family; merge related warnings.
5. Bounded investigator chooses tools for the most discriminating missing evidence. Compare provider degradation, worker capacity loss, deploy/config changes and normal demand surge.
6. Deterministic severity uses observed SLO/queue breach; evidence grades use freshness, completeness and independent signal families. “High evidence” is a policy grade, **not a calibrated probability**. No LLM confidence is used as incident probability.
7. Produce schema-valid assessment with facts, contradictory evidence, hypotheses, impact, retrieved history and recommended runbook. Each quantitative claim references an evidence ID.
8. Policy decides observe, alert/ticket, require approval or simulate a bounded action. The model cannot elevate its own permissions.
9. Verify fresh post-action windows, record success/failure/inconclusive and escalate if required. Collect human correction without claiming online retraining.

## Bounded investigator tools and decisions

| Tool | Typed parameters / limits | Result and permission |
|---|---|---|
| get_metric_window | incident service set; start/end <= current event time; <=60 min | Redacted aggregates, units, coverage, evidence IDs; read-only |
| get_dependencies | versioned service ID | Directed graph and source timestamp; read-only |
| get_context_events | service set; <=60 min; max 50 items | Deploy/log/span evidence with untrusted text; read-only |
| search_incidents | symptom features; resolved_before current time; top_k <=3 | Verified history or no-match; read-only |
| get_runbook | allowlisted runbook ID and version | Preconditions, risk, verification and rollback; read-only |
| propose_action | catalog enum, validated parameters, evidence IDs | Proposal only; no direct effect |

A single stateful investigator is enough. Start with an explicit Python state machine and persisted transition version; LangGraph becomes useful only if branching/checkpoint complexity warrants an extra dependency. No independent agents with overlapping permissions are required. Bound each investigation to four read calls, two model turns and a 30-second deadline; include token usage and tool latency in the trace. A second model turn may change the hypothesis after a tool result; do not expose hidden chain-of-thought. Persist tool choices, evidence, conclusions and short decision reasons.

Example self-correction: provider latency rises, so fetch provider spans. Spans show normal upstream duration but workers slowed after a deploy. Revise to capacity regression, fetch runbook and refuse provider retry remediation as the primary fix. If tools fail or evidence conflicts, alert with uncertainty and request diagnostic review.

## Historical incident correlation

Store incident ID, tenant, occurred/resolved times, affected services/dependencies, metric direction vector and normalized deviations, error codes, redacted summary, cause status (`verified`, `hypothesis`, `unknown`), verified cause, action receipts, verification outcome, source/provenance and runbook version. Seed 8–12 **synthetic** case records from training only, plus distinct normal surge and unknown examples. Never index validation/test fault manifests or future resolutions.

Filter by tenant, resolved time and related service/dependency. Score = 0.35 symptom-direction overlap + 0.25 service/dependency overlap + 0.25 error-code overlap + 0.15 normalized shape similarity; renormalize over available evidence and require at least two families. Initial no-match threshold 0.65 is a proposed tuning value. Return top three with score breakdown and verification status. Curated records can fit Firestore and an in-process scan initially. Semantic embeddings are optional when enough text makes lexical/structured retrieval inadequate; a vector database adds no demonstrated value here.

Evaluate recall@3, mean reciprocal rank and no-match false acceptance on separately annotated queries. The LLM compares retrieved history to current evidence and must preserve differences. Similarity is not a cause probability; no relevant match must remain an allowed outcome.

## Action policy

| Action | Evidence requirement | MVP authority | Verification |
|---|---|---|---|
| Read diagnostic | Valid scope and current incident | Automatic within tool budget | Tool receipt and timestamp |
| Internal ticket and alert | Persistent multivariate warning, fresh evidence | Automatic; one logical ticket/episode | Read ticket ID and alert delivery record back |
| Suggested runbook | Relevant versioned runbook and stated uncertainty | Automatic recommendation | Record cited preconditions; never imply execution |
| Retry cap in simulator | Backlog growth and retry load; simulation namespace | Automatic simulation or explicit UI simulate button | Compare no-action and action worlds under common noise |
| Real scaling or retry configuration | Service-owner allowlist, bounded parameters, current approval and rollback | Disabled in hackathon default; operator approval required if later enabled | Real fresh windows plus change receipt and rollback checks |
| Money, routing, account or settlement changes | Outside scope | Always denied | Denial audited |

Keys: incident scope + episode ID + action kind + policy version. Firestore transaction claims a state transition and writes an outbox job; never call external tools inside a retried database transaction. An action worker uses an idempotency key, writes the receipt, and reconciles unknown outcomes before retry. Ten-minute episode cooldown; at most one remediation attempt, one rollback and one escalation per episode. A resolved episode reopens only after recovery plus new persistent evidence. Expiring human approvals bind incident/version/action parameters, not a free-text suggestion.

Simulated verification: measure queue and breach windows after action versus paired no-action run, with identical exogenous noise; label model assumptions. Production verification: require five fresh windows with recovery in the targeted queue/error indicators and no guardrail regression; record `inconclusive` on missing data. Before/after recovery in live operations alone does not prove causality. Never mark success solely from an execution HTTP status.

## Typed assessment

See the full [incident JSON schema](../contracts/incident_assessment.schema.json) and separate [model-only assessment schema](../contracts/model_assessment.schema.json). Include incident ID, detection/event timestamps, service/dependency IDs, anomaly type, observed/baseline evidence windows, severity, evidence grade, uncertainty, facts, ranked hypotheses with supporting/contradicting IDs, historical references, measured/projected impact separately, recommended catalog action, deterministic policy result, approval requirement, execution receipts, verification and lifecycle status. Validate evidence IDs and numerical facts against tool outputs in application code in addition to schema validation. The application owns evidence grade, calibrated confidence, action permission and lifecycle fields; never accept authority fields directly from model output. Confidence probability stays null until an independently evaluated calibration version exists.
