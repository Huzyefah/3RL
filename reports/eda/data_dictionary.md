# Organizer data dictionary

Row grain: one synthetic service/metric telemetry record with contemporaneous context and a point incident flag. It is not a wide snapshot of all service metrics, a transaction ledger or a known periodic sample. Timestamp is unique in this file; `(timestamp,service_name,metric_type)` can identify this artifact's rows but does not establish a stable producer ID. Use explicit IDs in a streaming application.

| Column | Parsed type | Meaning | Observed values and uncertainty | Role |
|---|---|---|---|---|
| timestamp | string → datetime | Observation time; ISO-like YYYY-MM-DDTHH:MM:SS | No timezone in any row; source clock unknown | Ordering only, not incident onset |
| service_name | string/category | Service reporting this record | 8 names; no dependency graph supplied | Predictor/group; not a unique identifier |
| metric_type | string/category | Metric name associated with value/threshold | 7 names; units absent | Group before comparing values |
| value | float64 | Observed metric reading | 10.38–97.76; mixed metrics cannot share a physical unit | Candidate predictor |
| threshold | float64 | Supplied comparison level | 11.29–134.29; exceeds value in every row | Availability/generation logic unknown |
| alert_level | string/category | NORMAL, WARNING or CRITICAL | Partitions match ratio bands at 0.75 and 0.95 | Exclude as predictive evidence; contemporaneous diagnostic |
| user_count_active | int64 | Named active-user count | 10–4998; measurement window unspecified | Candidate predictor if available at event time |
| error_count_last_hour | int64 | Named hourly error count | 0–50; rolling vs fixed hour and interval endpoint unspecified | Audit prediction-time availability |
| response_time_ms | int64 | Named response duration in milliseconds | 25–2998; percentile/request/window semantics unspecified | Candidate predictor; not interchangeable with latency_p99 value |
| is_incident | int64/binary | Supplied incident flag | 28 ones and 472 zeros; no episode IDs/onset/cause | Target only; never detector input |

Derived fields: `ratio = value / threshold` (dimensionless only if those fields are comparable); `parsed_timestamp` (naive, retained in memory); source-date/day aggregates for EDA. Do not set the source timezone to UTC without confirmation. Sorted processed data adds ratio but preserves source timestamp strings and labels. The synthetic dictionary is separate in `docs/data_strategy.md`.
