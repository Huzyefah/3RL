# PayGuard implementation blueprint

Build a narrowly scoped **payment retry-cascade prevention assistant** for PS-02. Retain a general queue-saturation AIOps fallback. The winning submission should connect early statistical evidence, tool-directed investigation, a pre-emptive ticket/runbook, a clearly simulated retry-budget action and verification. This package completes analysis/research/planning and local data experiments. It does not implement or deploy the application.

## 1 Executive decision

Use PayGuard's concrete payment-operation narrative if the team can explain retry semantics and build the simulator-to-app replay. If implementation time is tight, keep the same detector/agent and present a generic queue-investigation product. Prioritize one credible complete cycle over additional agents, fintech domains or cloud services. The recommendation follows the [weighted candidate comparison](product_strategy.md), not an assumption that fintech is inherently better.

## 2 Dataset evidence

The original has 500 rows, 10 columns, eight services, seven metric types, 28 incident points (5.6%) and no missing cells or duplicate rows. Observations span 1–30 August 2026 without a timezone. Each service/metric has only 3–15 points; median within-series median gap is about 50.7 hours. Every value is below its threshold. Ratio >=0.95 exactly reproduces CRITICAL and yields TP28/FP22/FN0/TN450. These are contemporaneous synthetic labels, not evidence of future prediction. See [computed EDA](../reports/eda/eda_report.md).

## 3 Data fitness

Use original data for descriptive EDA, point-rule evaluation and organizer replay. It cannot establish warning onset, true causes, dense forecasting, historical verified incidents, real payment throughput or prevention. Strong value/threshold association and deterministic alert bands suggest shared synthetic generation logic; exact generator and label timing are unknown. Exclude alert labels from predictive claims. See [quality assessment](../reports/eda/data_quality_report.md).

## 4 Candidate comparison

Payment reliability scores 4.6/5 versus general queue AIOps 4.3 under stated judgment weights. Generic AIOps wins under feasibility-heavy weights. Settlement/reconciliation and fraud directions require unavailable domain truth; auth anomalies cannot establish malicious intent. [Product strategy](product_strategy.md) records users, buyers, signals, outcomes and sensitivities.

## 5 Product and scope

PayGuard targets an on-call reliability engineer responsible for payment-provider adapters and processing queues. It warns when retries and backlog threaten checkout, explains evidence/uncertainty, finds verified similar incidents and records a safe preventive workflow. It does not decide fraud, move money, reroute live payments, edit settlement or block accounts.

## 6 Feature set

Essential: typed ingestion for metrics/logs/events and trace references; organizer replay lane; statistical candidate detection; one bounded investigator with metric/history/dependency/runbook tools; structured summary; durable internal alert/ticket; simulated retry cap; verification/audit; incident UI; baseline/evaluation view. Stretch: real Monitoring adapter, BigQuery analytics, richer retrieval and model bake-off UI. See [traceability](requirements_traceability.md) for demonstration criteria.

## 7 Data expansion

Keep raw organizer file unchanged. Execute separate synthetic causal queue/retry runs with fixed seeds, disjoint partitions, hidden fault manifests, normal surge/transient/healthy negatives and paired no-action/action worlds. The package includes 96 sequences and 17,280 windows plus a preserved exploratory pilot. Shared simulator family and assumed equations limit external validity. [Data strategy](data_strategy.md) details lineage, rules and scenarios.

## 8 Detection and evaluation

Baseline supplied thresholds and a synthetic static SLO-style rule. Proposed statistical pipeline uses robust latency deviation, retry fraction, queue growth and persistence with a backlog gate. Validation selects z=6. Final synthetic test: 18/18 early incident matches, median lead nine minutes, 2/30 negative runs alerted. Static baseline: 1/18 early, 17 late and 1/30 negative runs alerted. The proposed rule improves early warning on this mechanism but raises more false alarms. [Evaluation report](../reports/evaluation/evaluation_report.md) provides counts/denominators, uncertainty, intervention outcomes and failure cases.

## 9 Agentic investigation and action

One explicit state machine: observe→candidate→investigate→policy→action→verify→resolve/escalate. Agent chooses a discriminating read tool and can revise its hypothesis. Four reads/two turns/30 s maximum. Deterministic policy permits internal tickets/alerts/runbooks and simulation, not financial or unrestricted infrastructure changes. [Detection and workflow](detection_and_agent_workflow.md) specifies permissions, stop conditions and idempotency.

## 10 Historical correlation

Start with 8–12 curated synthetic training cases, verified cause/resolution fields, dependency/symptom/error/shape ranking and explicit no-match. Restrict retrieval to prior resolved cases; never index test truth. Structured scan suffices; add embeddings only if measured retrieval failures justify it. Evaluate retrieval separately from generated summary quality.

## 11 GCP and model architecture

Two Cloud Run services (API/UI and private worker), authenticated Pub/Sub, Firestore operational state/outbox, Storage artifacts, Secret Manager and Logging/Monitoring. Scheduled authenticated sweep ensures resumable durable work. BigQuery/live Monitoring are P1. OpenAI GPT-5.4 mini default with a tested snapshot; Gemini 3.8 Flash on GCP fallback, both subject to access and evidence-pack bake-off. No model advantage has been measured. See [architecture and editable diagrams](architecture.md).

## 12 Contracts and storage

Versioned [event schema](../contracts/telemetry_event.schema.json), [incident schema](../contracts/incident_assessment.schema.json) and [API contract](api_contract.md). Namespace event, window, incident, action, ticket, history and audit records. Optimistic versioning plus transactional state/outbox protects transitions; side effects occur outside retried transactions. Model recommendations never write authority/execution fields.

## 13 Product experience

Overview prioritizes early incidents and freshness. Investigation combines timeline, dependency graph, baseline deviations, facts/hypotheses and history. Action center distinguishes proposal/approval/receipt/verification. Evaluation/replay shows the same stream through baseline/proposed and no-action/action worlds. See [screens and states](frontend_experience.md). Use explicit synthetic mode, unknown/unmeasured states and units.

## 14 Security and reliability

Single demo tenant, identity-derived scope, viewer/operator/approver roles, least privilege, server-only keys, redaction, schema validation, prompt-injection boundaries, tool allowlists, durable idempotency, DLQ, freshness checks, bounded retries and model-outage fallback. Real changes disabled by default. [Risk register](security_and_risk.md) maps controls to verification.

## 15 Evaluation gates

Compare identical no-action windows; report point/window/event metrics separately, early/late/missed cases and false-alarm denominators. Score summary grounding/services/cause/history/uncertainty/actionability against manifests and human review. Add action policy, duplicate/crash/staleness/injection and GCP load tests. All LLM, retrieval, live action and cloud metrics remain unmeasured until implemented. [Protocol](evaluation_plan.md) defines targets and freeze rules.

## 16 Cost

Filter before model calls, merge incidents, cache stable context, limit turns/tokens/concurrency and retain only needed data. Illustrative 100-episode inference cost is $0.99 at 6,000 input +1,200 output tokens/episode for the documented default. Small-demo listed service assumptions total about $2.15 before free allowances, excluding several cost categories; retain a separate budget reserve. No observed bill is claimed. [Cost plan](cost_and_deployment.md) gives sources, calculations and exclusions.

## 17 Deployment

Confirm project/region/quotas, create scoped identities/state/topics/secrets, build pinned image, deploy private worker and authenticated API, configure push/DLQ/scheduled sweeps, load synthetic training casebook, run original and synthetic smoke tests, then capture cloud evidence and tag passing revision. Rollback preserves action ledger and stops new action claims. Exact deployment scripts are backlog work; [deployment sequence](cost_and_deployment.md) is concrete enough to implement after application creation.

## 18 Milestone roadmap

Hackathon duration, team size and skill mix are **unknown**. Estimates are person-hours for a capable team, not elapsed-hour promises, and include normal integration/QA but not access delays. Completed analysis below should be reused, not reimplemented.

| Milestone | Deliverable / dependency | Estimated remaining effort | Acceptance | Risk and fallback |
|---|---|---:|---|---|
| M0 Evidence | EDA, baseline, scenarios, blueprint | Done in package | Reproduce artifact checks | Clarify original semantics; preserve limitations |
| M1 Core replay | Event schemas, API, durable source clock, detector | 8–12 h; M0 | All 500 original rows and one synthetic run processed with visible modes | Ingestion overhead; start one event source, then add logs/events before final gate |
| M2 Investigation | History, dependencies, runbook tools, structured model | 8–12 h; M1, model access | Tool choice plus contradiction revision; no-match case | Model outage; deterministic fallback for rehearsal, live reasoning gate still required |
| M3 Action cycle | Policy, tickets/alerts, outbox, simulator, verification | 8–12 h; M1–2 | One action receipt, verified/inconclusive outcome, duplicate-safe | State races; simplify to internal tools and simulation |
| M4 Incident UI | Overview/investigation/action/replay | 8–12 h; contracts M1 | Judge can follow end-to-end cycle and inspect evidence | UI overreach; combine views and retain clear timeline |
| M5 GCP deployment | Cloud Run, IAM, Pub/Sub, Firestore, secrets | 5–8 h; M1–3, access | Authenticated deployed cycle and health evidence | Access blocked; prioritize access smoke test early; offline fallback disclosed |
| M6 Evaluation and faults | Model rubric, retrieval and load/failure tests | 6–10 h; M2–5 | Saved results with failures/denominators; no unsafe or duplicate effects | Limited reviewers; disclose one reviewer and freeze evidence packs |
| M7 Demo polish | Fixed fixture, pitch, recording, README | 3–5 h; all | Timed 4–5 min run plus negative case and offline backup | Live failure; labeled recording and stored audit |

Total roughly **46–71 person-hours remaining**. A small team may overlap UI and backend once contracts stabilize, but team allocation is not assumed. If substantially less capacity is available, use the generic queue fallback and internal tools; do not imply all production controls fit a few hours.

## 19 Prioritized backlog

| ID | Task | Priority | Effort | Depends | Workstream | Acceptance | Requirement / judging |
|---|---|---|---|---|---|---|---|
| B01 | Access smoke test GCP and both model candidates | P0 | 1–2 h | none | Platform | Private Run endpoint and one schema response in chosen route | C1/J2 |
| B02 | Typed metric/log/event/span ingest and organizer adapter | P0 | 3–4 h | contracts | Backend | Accepted/rejected counts reconcile to inputs | R1/J3 |
| B03 | Replay clock, namespaces and original-data mode | P0 | 2–3 h | B02 | Backend | Pause/resume, 500 original rows preserved | R1/J3 |
| B04 | Past-only detector and persisted windows | P0 | 3–5 h | B02 | Detection | Match local frozen detector output; gap/warmup states | R2/E1/E2 |
| B05 | Casebook, dependency and runbook tools | P0 | 3–4 h | B02 | AI/data | Training-only history, scored matches, no-match | R5/J5 |
| B06 | Bounded model investigator and assessment validator | P0 | 5–8 h | B04–05, B01 | AI | Tool choice, hypothesis revision, grounded schema | R2/R4/J1 |
| B07 | Policy, versioned state/outbox and internal ticket/alert | P0 | 4–6 h | B04, B06 | Backend/policy | Duplicate/restart yields one logical effect | R3/J1 |
| B08 | Retry simulator adapter and verification/escalation | P0 | 4–6 h | B07 | Detection/policy | Shared-noise pair and failed/inconclusive path | R3/E1/J3 |
| B09 | Incident UI and evidence timeline | P0 | 6–8 h | B02–08 contracts | Product | Facts, hypotheses, history and action states readable | R4/J3 |
| B10 | Replay/evaluation/negative-case interface | P0 | 2–4 h | B09 | Product | Same partitions and denominators, false alarms visible | E1/E2/J5 |
| B11 | Authenticated cloud deployment and observability | P0 | 4–6 h | B01–08 | Platform | Deployed ingestion→verification trace | C1/J2/J4 |
| B12 | Human summary review and retrieval evaluation | P0 | 2–4 h | B05–06 | QA/domain | 12 scored packs; recall@3 and no-match results | E3/R5 |
| B13 | Action/security/failure/load tests | P0 | 4–6 h | B07–11 | QA/platform | No unsafe/duplicate effects; latency and failure report | J2/J4 |
| B14 | Timed pitch, backup recording and judging coverage | P0 | 3–5 h | B10–13 | Product | Repeatable full cycle plus negative case | all |
| B15 | Live Monitoring adapter and BigQuery export | P1 | 4–8 h | B11 | Platform | Real source freshness; bounded analytical queries | R1/J4 |
| B16 | Tuned conventional SLO/EWMA comparator | P1 | 3–5 h | B04 | Detection/QA | Validation-selected comparator on frozen test | E1/E2 |
| B17 | Model bake-off and prompt ablation | P1 | 2–4 h | B12 | AI/QA | Blinded quality, tokens and latency comparison | E3/J2 |
| B18 | Independent fault family and anonymized trace review | P1 | 4–8 h | B12–13 | Data/domain | External-validity gaps documented | E1/E2/J4 |
| B19 | Infrastructure-as-code, real ticket connector | P1 | 3–6 h | B11 | Platform | Reproducible deploy; connector receipts/idempotency | R3/J2 |
| B20 | Semantic retrieval, real remediation or second model | P2 | 6+ h | passing P0 | AI/platform | Demonstrated need and separate safety/quality gates | R5/J5 |

Backlog estimates are task-level planning ranges and overlap milestone work; **do not add both tables**. B01 access work is part of M5 but should start immediately. A simple initial model check is P0; broad comparative bake-off is P1 unless the default fails quality gates.

Feature cuts in order: P2; embeddings/external connectors; BigQuery; live Monitoring adapter; advanced UI charts; secondary scenarios in live presentation. Preserve typed log/event ingestion, original dataset lane, bounded tools, ticket/runbook, simulation verification, GCP backend and honest evaluation. Cut decorative scope before cutting the full agentic loop.

## 20 Judging and demo

Lead with the payment retry cascade, not cloud logos. Show quiet healthy behavior, warning before the no-action incident onset, chosen tools/history and uncertainty, internal ticket/runbook, simulated intervention, verification/audit and baseline comparison. Show a normal traffic surge with no intervention. Root-cause/model quality cannot be claimed from the statistical experiment. [Demo strategy](demo_and_judging_strategy.md) provides timing, rubric coverage, technical explanation and fallback.
