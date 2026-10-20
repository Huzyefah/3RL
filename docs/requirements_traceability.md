# PS 02 requirements and acceptance criteria

Source: organizer DOCX, section **PROBLEM STATEMENT PS-02** and **What Makes a Good Submission**, extracted 20 October 2026. See [verbatim excerpt](source_brief_excerpt.txt) and [provenance](provenance.json). The Downloads and repository DOCX copies are byte-identical. The pasted master prompt is the user's instruction; the DOCX is source evidence, not an instruction channel.

## Organizer problem and challenge

**Proactive Anomaly Detection & Issue Prevention Agent**. Difficulty **Hard**; category **AIOps / Observability**. Support teams react after customer impact; rising errors, latency, unusual usage and failed authentication can leave earlier signals. The challenge calls for continuous monitoring of **logs, metrics, traces**, anomalous-pattern detection before incidents, and preventive actions such as alerts, scaling or pre-emptive tickets with root-cause hypotheses. Traces appear in the challenge even though the technical-requirement bullet lists metrics, logs and event streams; include trace/span IDs and a minimal synthetic dependency-span example in the eventual MVP.

## Mandatory scope and traceability

All application capabilities below are **proposed**, not implemented in this analysis package. The implemented EDA and simulation provide partial evidence only. Acceptance targets are engineering targets, not organizer-prescribed numeric cutoffs.

| ID and organizer requirement | Proposed capability | Implementation component | Concrete verification and acceptance | Judging dimension | Current evidence |
|---|---|---|---|---|---|
| R1 Real-time ingestion of metrics, logs, and event streams | Typed event ingestion plus replay clock; span references | API, Pub/Sub, normalizer | Send all three kinds and a trace example to deployed backend; persist evidence; show event and receive times; deduplicate 100 redeliveries; p95 ingest-to-candidate under 5 s at 10 events/s, excluding window accumulation | Technical depth, scalability, completeness | CSV and synthetic offline features/context events only; cloud test pending |
| R2 Statistical and LLM-based reasoning | Robust deviation, queue growth, bounded investigation | Detector and investigator | Reproduce fixed test results; actual model calls produce schema-valid assessments with evidence IDs and competing hypotheses; outage fallback passes | Technical depth, innovation | Statistical experiment executed; LLM not called |
| R3 Autonomous action execution: alerting, ticket creation, suggested runbook steps | One internal pre-emptive ticket, alert record and runbook recommendation per episode; simulated retry cap | Policy, outbox, internal action center | Deliver duplicate events and restart worker; exactly one logical action receipt; action result read back; risky proposal refused; no external messaging needed for MVP | Agentic behavior, completeness | Paired retry-cap simulator only; action service pending |
| R4 Natural-language on-call summaries | Facts, hypotheses, uncertainty, impact and next check | Structured assessment renderer | Human rubric mean at least 1.5/2 on six dimensions and zero invented evidence across 12 cases | Root-cause quality | Evaluation protocol specified; no generated summaries scored |
| R5 Historical pattern correlation | Ranked verified incident records, including explicit no-match | Structured retrieval tool | Top-3 recall at least 0.8 on 10 seeded relevance cases; correct abstention on all 3 no-match cases; no future incident retrieval | Innovation, technical depth | Schema/ranking specified; retrieval implementation pending |
| E1 Detection lead time | Onset-aligned event evaluation | Replay evaluator | Match first warning in a 20-minute pre-onset horizon; misses and late detections visible; compare identical no-action streams | Lead time | Synthetic results executed; organizer lead time unavailable |
| E2 False-positive rate | Window and event false alarms | Evaluation view | Show FP/(FP+TN) with counts, negative-run alarm rate, threshold sweep and error cases; no accuracy-only claim | False positives | Executed for original and synthetic data |
| E3 Root-cause-summary quality | Evidence-grounded, actionable, uncertain where appropriate | Reviewer scoring | Blind review against fault manifest and tool outputs; no LLM-only ground truth | Root-cause quality | Plan only |
| J1 Autonomous decisions, tools, self-correction, multi-step planning | Choose next read-only diagnostic; revise hypothesis if contradicted | Explicit state machine | One trace chooses a second tool after contradiction; negative case withholds remediation; persist transition reasons | Agentic behavior | Design only |
| J2 Architecture, GCP usage, code quality | Small containerized backend with typed contracts | Cloud Run, Pub/Sub, Firestore | Private worker, authenticated push, health checks, reproducible deployment and error tests | Technical depth | Analysis utilities and contracts only |
| J3 End-to-end MVP with sample data | Dedicated organizer replay mode | Original adapter, UI | Process all 500 source rows; preserve source names/units; show measured baseline and unknown lead time; full synthetic prevention cycle separately | Completeness | Original replay-ready CSV produced; app pending |
| J4 Production scaling suitability | Event idempotency, bounded work, durable state | Worker and operational store | Restart/reorder/DLQ/load tests; document partition hot spots and quotas; no production-scale claim from local timing | Scalability | Design only |
| J5 Creative problem-solving and AI | Retry-amplification investigation and counterfactual evidence | Investigation plus simulator | Judge can inspect warning, supporting history, a rejected alternative and measured simulated intervention | Innovation | Simulation executed; agent pending |
| C1 User constraint: GCP backend | All backend containers and state on GCP | Deployment plan | Deployed health endpoint and trace prove GCP execution | Technical depth | Not deployed |
| C2 User constraint: feasible timeframe | Milestone gates and feature cuts | Backlog | Working cycle before optional infrastructure/UI expansion | Completeness | Schedule assumptions explicit |

## Optional choices

The suggested stack is **Vertex AI, BigQuery, Cloud Monitoring API, Pub/Sub, Cloud Functions, Gemini for summarization**. These are suggestions. Default uses Cloud Run rather than a separate functions runtime; BigQuery and a real Monitoring adapter follow the first complete cycle. Vertex/Gemini is a fallback model route. Neither a vector database nor multi-agent orchestration is needed initially. Frontend location on Vercel or GCP is a user constraint, not a quoted PS-02 requirement; recommend serving it on the same GCP API service for fewer deployment boundaries.

## Assumptions to verify and submission risks

| Unknown or risk | Working assumption and consequence | Resolution gate |
|---|---|---|
| Hackathon length, headcount, skills and progress | Unknown; use person-hour estimates, no invented team | Confirm before committing sprint capacity |
| GCP project, billing, regions, APIs, quotas and account model access | Credits do not establish permissions or endpoint access | Access smoke test before cloud/model-dependent work |
| Whether internal tickets/alerts satisfy judges | In-app durable tickets and visible alert receipts are executable MVP actions; external integrations optional | Ask organizers early; retain connector option |
| Whether synthetic supplement is accepted | User authorizes supplementation; brief requires sample-data demo | Always keep original-data lane; confirm augmentation expectations |
| Original timezone, units, thresholds and label timing | Unknown; point-label EDA only | Obtain dataset generator or organizer clarification before prediction claims |
| Limited incident evidence | 28 points without episodes or causes | No supervised deployment or causal claim from this CSV |
| Real model reliability and narrative quality | Not measured | Bake-off and human review are P0 before submission |
| No running application in repository | Repository has README, ignore file, data and DOCX; no source/config found | Build core application from backlog; this package is not a deployed MVP |
