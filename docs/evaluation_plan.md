# Evaluation protocol

Separate three evidence tracks: organizer point labels; synthetic temporal detection/intervention; future LLM/agent/cloud evaluation. Actual computed results and limitations are in [evaluation report](../reports/evaluation/evaluation_report.md). This protocol defines how to extend them without turning planning targets into achieved metrics.

## Detection and early warnings

Original-data predictions match each contemporaneous `is_incident` row only. Compute TP/FP/FN/TN, precision, recall, F1 and **FPR = FP / (FP + TN)**. Chronological 300/100/100 descriptive slices are saved, but the entire dataset was inspected, so no untouched supervised test claim is justified. `alert_level` is a label-generation diagnostic, not a prediction feature. `threshold`/ratio may share generation logic and require an availability audit.

Synthetic final detector settings are selected from validation only. Rows in the same sequence never cross partitions. Training/validation/final test use different seeds and ramp shape; shared generator structure is a material limitation. Preserve the inspected exploratory pilot separately. All comparative detectors see the same no-action test streams; action-world labels must not replace counterfactual incident onset in warning evaluation.

Ground truth: first window of a sustained three-window queue-wait >120 s or modeled error fraction >5% breach. First alarm in [onset−20 min, onset) is an early match. An alarm from onset to coarse incident end is late and cannot count as successful prevention. One incident maximum per run in this experiment. Alarm episodes start on a false→true transition with a ten-minute refractory interval; continuous alarms are one episode. Multiple matched episodes count once toward event recall; extra matched episodes are duplicate alarms and should be reported separately in production evaluation. An alarm outside the incident envelope or warning horizon is unmatched. Missed incidents remain misses with null lead, never assigned lead zero or dropped from recall.

Report lead min, quartiles, median and max on early detections **alongside early-recall denominator**, late and missed counts. Event precision = detected incident episodes / (detected incident episodes + unmatched alarm episodes), with matched duplicates excluded and separately tracked. Negative-run false-alarm rate = nonincident runs with any alarm / all nonincident runs. Window FPR uses non-risk windows across both positive and negative runs, where risk includes the pre-onset horizon through incident end. These are different denominators and must not be interchanged.

For real multi-incident traces, use one-to-one matching by compatible service/dependency and onset horizon, assign an alarm only once, and split recovery/recurrent incidents explicitly. Use block/event bootstrap intervals; never independent-row bootstrap of correlated windows. Small synthetic event counts yield wide uncertainty and are conditional on the generator. Do not use point adjustment that retroactively marks an entire interval detected after one hit; [evaluation research](https://arxiv.org/abs/2109.05257) documents problems with that practice.

## Root-cause and retrieval quality

Create 12 fixed evidence packs: provider slowdown, retry amplification, capacity regression, normal surge, transient spike, missing metrics, stale telemetry, misleading historical match, no history, injection text, malformed tool output and model timeout. Ground truth is the controlled manifest and exact retrieved tool evidence, not an LLM grader. Withhold causal fault fields from model inputs. Two humans review independently if available; otherwise one reviewer and an explicit reviewer-count limitation. Blind provider labels during model bake-off.

Score each dimension 0/1/2: evidence grounding (invented/partial/fully supported), service identification, consistency with controlled fault, history relevance/no-match, separation of fact from hypothesis and actionable bounded runbook. Gate: mean >=1.5 per dimension and no unsupported quantitative fact or unsafe proposal reaching execution. Correct uncertainty is acceptable; “provider failure confirmed” without proof is not. Store reviewer ID, model/version, pack hash, score and rationale. An optional LLM critic can flag review candidates but is not definitive truth.

Retrieval is separate: at least 10 labeled queries with relevant case IDs and three no-match cases; report recall@3, MRR, verified-status correctness and no-match false acceptance. Ensure history predates current event time and test incident resolutions are absent from the index.

## Actions and system behavior

Appropriate-action rate = proposals matching the expert action rubric / scored proposals. Unsafe-action rate = forbidden or unauthorized executed actions / all executed actions; also count blocked unsafe proposals separately. Duplicate-action rate = duplicate logical effects / attempted logical actions. Verification success = actions with measured recovery and guardrails met / executed actions; inconclusive and failed must remain separate. Escalation rate uses completed investigations as denominator. Track detection→proposal, proposal→receipt and receipt→verification latency separately.

The executed paired simulation always caps retries one window after a hybrid alarm; it is **not an evaluated agent action-selection policy**. Measure modeled breach minutes, peak queue and expected failed attempts, with common exogenous noise and declared equations. Do not infer real money saved or unique transactions rescued. For live use, causal attribution needs a credible control or experimental design; before/after improvement alone is insufficient.

System benchmarks to run after app exists: 10 events/s sustained for ten minutes, 100 events/s one-minute burst, 100 duplicate deliveries, worker restart before/after commit, stale/missing/out-of-order events, store/model timeout and poisoned record. Save p50/p95 end-to-end latency, detection compute, tool/model latency, errors/timeouts, throughput, backlog, model calls/event, tokens and estimated cost. Local vectorized detector timing is not end-to-end streaming latency or throughput.

Acceptance gates: no duplicate logical actions or executed unsafe actions in fault tests; all source events either accepted or explicitly rejected; p95 processing under five seconds at the initial 10 events/s target excluding observation window; root-cause and retrieval gates above; original-data lane and synthetic cycle both demonstrated. These targets can be adjusted with team/time information, with changes logged before the final evaluation.

## Freeze and reporting

Version generator, features, thresholds, history, prompts, model, policy and fixtures. Select on validation, freeze, then evaluate final test once. If final-test feedback drives a change, report it as development and generate a new untouched test. Preserve negative cases and failures in the UI and report, not just one favorable live scenario. Raw counts and manifests accompany every reported percentage. No accuracy headline for this imbalanced task.
