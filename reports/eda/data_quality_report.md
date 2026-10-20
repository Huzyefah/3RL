# Data quality and fitness

Structural validity is good; task fitness is limited. No source rows were modified or removed. The data is synthetic according to the organizer, and its point flags cannot establish future incidents or causes.

| check | count | meaning |
|---|---|---|
| missing_cells | 0 | expected 0 |
| unparseable_timestamps | 0 | expected 0 |
| duplicate_rows | 0 | expected 0 |
| duplicate_timestamps | 0 | global only |
| duplicates_without_timestamp | 0 | all other columns exact |
| coarsened_near_duplicates | 0 | exclude timestamp; value/threshold whole; users/response bins 100; errors bins 5 |
| nonpositive_threshold | 0 | invalid for ratio |
| negative_numeric_cells | 0 | semantic nonnegativity |
| invalid_incident_flags | 0 | binary |
| values_over_threshold | 0 | diagnostic, not error |
| critical_label_ratio_disagreements | 0 | hypothesis discovered in full sample |
| normal_label_ratio_disagreements | 0 | hypothesis discovered in full sample |
| timezone_designators | 0 | 0 implies unknown timezone |

No categorical whitespace/case normalization is needed in the observed names. Value and threshold units are unestablished; a threshold above 100 for CPU is not automatically invalid because percentage semantics were never provided. Likewise decimal queue values cannot be called invalid counts without a unit definition. Preserve uncertainties instead of “cleaning” assumed errors.

| Task | Evidence classification | Reason |
|---|---|---|
| Statistical anomaly detection | Partially sufficient | Static metric/threshold checks possible; adaptive/temporal evidence weak. |
| Supervised incident prediction | Insufficient | 28 contemporaneous labels, shared alert/ratio logic and unknown prediction-time availability. |
| Unsupervised anomaly detection | Partially sufficient | Can score numerical rarity; rarity has no independently verified operational meaning. |
| Time-series forecasting | Insufficient | Only 3–15 points per service/metric, irregular gaps and no reliable seasonality. |
| Early-warning lead time | Insufficient | No incident episode ID/onset or coherent preceding sequence. |
| Root-cause inference | Insufficient | No faults, deploy context, dependency graph or verified causes. |
| Historical incident retrieval | Insufficient | Flags are not resolved incident records; casebook must be supplemental. |
| Streaming simulation | Sufficient for replay mechanics only | CSV can be emitted as events; replay is not evidence of real-time production throughput. |
| Fintech demonstration | Partially sufficient | Relevant service/metric names; no transaction/processor/currency/settlement semantics. |

Main semantic risks: alert labels directly match ratio bands; thresholds correlate strongly with values; context fields show little cross-variable signal; hourly error observation boundaries and incident flag timing are unknown. The source might have been generated with independently randomized features, but this remains an inference rather than a recovered generator. No dense temporal seasonality or historical verified resolution exists. Missingness zero does not establish complete telemetry coverage.

No exact/coarsened duplicate records were found under the saved check definition. Splits must still keep related synthetic sequences and fault templates apart; row deduplication alone does not prevent generator leakage. The final synthetic experiment changes ramp family and seeds but remains within one simulator. See the separate synthetic validity report and limitations.
