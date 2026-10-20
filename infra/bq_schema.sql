-- BigQuery dataset `sentinel` (system of record). Applied idempotently by infra/bootstrap.sh.
CREATE TABLE IF NOT EXISTS `sentinel.events_raw` (
  data STRING, subscription_name STRING, message_id STRING, publish_time TIMESTAMP, attributes STRING
);
CREATE TABLE IF NOT EXISTS `sentinel.incidents` (
  incident_id STRING, opened_at TIMESTAMP, resolved_at TIMESTAMP, root_service STRING, segment_key STRING,
  severity STRING, verdict STRING, status STRING, rca JSON, source STRING
);
CREATE TABLE IF NOT EXISTS `sentinel.actions` (
  action_id STRING, incident_id STRING, type STRING, mode STRING, status STRING, params JSON,
  requested_at TIMESTAMP, decided_by STRING, evidence_ids ARRAY<STRING>, rollback_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS `sentinel.tickets` (
  ticket_id STRING, incident_id STRING, team STRING, cc ARRAY<STRING>, severity STRING, title STRING,
  body STRING, created_at TIMESTAMP, status STRING
);
CREATE TABLE IF NOT EXISTS `sentinel.agent_trace` (
  incident_id STRING, step INT64, ts TIMESTAMP, agent STRING, kind STRING, tool STRING, args JSON,
  evidence_id STRING, tokens INT64, latency_ms INT64
);
CREATE TABLE IF NOT EXISTS `sentinel.eval_results` (
  run_id STRING, ts TIMESTAMP, mode STRING, split STRING, config STRING, metrics JSON
);
CREATE TABLE IF NOT EXISTS `sentinel.feedback` (
  incident_id STRING, kind STRING, user STRING, ts TIMESTAMP
);
