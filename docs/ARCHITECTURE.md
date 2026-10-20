# Architecture

Sentinel runs the same pipeline against three sources: the PS-02 replayer, a densified synthetic replay, and the NovaPay simulator. LLM provider: **OpenAI only**, with a deterministic fallback.

## System flow

```mermaid
flowchart LR
  REP["PS-02 replayer / synthetic replay"] --> NORM
  SIM["NovaPay sim + chaos"] --> NORM
  NORM["CES normaliser + PII redactor"] --> DET["Detector<br/>Holt ETA, EWMA z, binomial segments"]
  DET --> GRP["Grouping + cascade link"]
  GRP --> CMD["Commander agent"]
  CMD <--> SKP["Skeptic agent"]
  CMD <--> TOOLS["Data tools: metrics, calendar, topology, past incidents"]
  CMD <--> OAI{{"OpenAI API<br/>or deterministic fallback"}}
  CMD --> POL{"Policy Guard"}
  POL -->|auto-allowed| EXE["Executors"]
  POL -->|needs approval| APPR["Approval queue"]
  APPR -->|approved| EXE
  POL -->|denied| DENY["Rejected + audited"]
  EXE -->|reroute| SIM
  EXE -->|outcome verified| CMD
  CMD --> UI["REST + SSE -> Web UI + scorecard"]
```

## GCP target mapping

```mermaid
flowchart LR
  SRC["Replayer / finpay-sim"] --> PS[("Pub/Sub telemetry")]
  PS -->|push| API["sentinel-api (Cloud Run)"]
  PS -->|subscription| BQ[("BigQuery: events, incidents, scorecard")]
  API --> BQ
  SM["Secret Manager<br/>OPENAI_API_KEY"] --> API
  CS["Cloud Scheduler /jobs/tick"] --> API
  API <--> OAI{{"OpenAI API"}}
  API <--> WEB["sentinel-web (Cloud Run)"]
  API -->|policy-gated actions| SIMR["finpay-sim (Cloud Run)"]
```

## Implemented vs planned

| Capability | Status |
|---|---|
| Detector: Holt ETA, EWMA, binomial segment tests | Implemented |
| Skeptic + Commander with OpenAI and deterministic fallback | Implemented |
| Policy-gated reroute with live recovery verification | Implemented |
| Scorecard computed from CSV | Implemented |
| Recall over 28 incidents + 22 false alarms | Implemented |
| Web UI (live ops, incident trace, approvals) | Implemented |
| GCP deployment | Planned / not yet |
| Pub/Sub and BigQuery adapters | Planned / not yet |
| Security Sentinel | Planned / not yet |
| Log Analyst | Planned / not yet |
| Seeded evaluation mode | Planned / not yet |

Locally everything runs in one process with an in-memory bus and store; the GCP mapping is the deployment target, not a claim of a deployed system.
