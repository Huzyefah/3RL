# Research sources and decision ledger

Access date for all web sources: **20 October 2026**, client timezone Asia/Karachi. Current documentation/pricing can change. Sources establish capabilities or operational principles; none establishes this product's real-world detection quality. Repeated links elsewhere refer to this ledger. No external dataset was downloaded.

## Primary sources

| ID | Source | Verified fact or relevance | Design consequence / limit |
|---|---|---|---|
| S01 | [Cloud Run authenticated Pub/Sub tutorial](https://docs.cloud.google.com/run/docs/tutorials/pubsub) | Pub/Sub can invoke Cloud Run with a push identity | Private worker and explicit invoker IAM |
| S02 | [Pub/Sub exactly-once delivery](https://docs.cloud.google.com/pubsub/docs/exactly-once-delivery) | Exactly-once support is for pull subscriptions | Push processing needs application dedup/idempotency |
| S03 | [Pub/Sub dead-letter topics](https://docs.cloud.google.com/pubsub/docs/dead-letter-topics) | Dead-letter forwarding has configuration and permission requirements | Preserve poison events and monitor failures; do not assume a DLQ appears automatically |
| S04 | [Cloud Monitoring API](https://docs.cloud.google.com/monitoring/api/v3) | Metric access is project/scoping-project aware | Read-only bounded adapter; preserve source timestamps; no live integration claim |
| S05 | [Firestore transactions](https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions) | Transactional updates support coordinated state; retry semantics matter | Atomically claim state/outbox; effects outside transaction callbacks |
| S06 | [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets) | Secret Manager integration and versioned environment references | Server-only API credential, scoped accessor and rotation plan |
| S07 | [OpenAI GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini) | Responses API, function calling and structured output listed; $0.75/$4.50 per million standard input/output text tokens | Reasoning default candidate; not proof of account access, latency or quality |
| S08 | [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | Typed output/function contracts supported within documented schema constraints | Validate shape plus grounding/permissions in code; handle refusal/incomplete output |
| S09 | [GCP function calling](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling) | Model can request tools through declared function interfaces | Provider adapter for fallback; tools still executed by the application |
| S10 | [GCP structured output](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/control-generated-output) | Response schema controls supported structure | Test common schema subset across providers |
| S11 | [Gemini 3.8 Flash guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-8-flash) | Current GCP guide identifies the candidate model family | Verify exact ID/location/access; old Vertex URLs now redirect to newer documentation surface |
| S12 | [Google SRE alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) | Conventional alerting has explicit precision/recall/detection/reset tradeoffs | Add a tuned SLO/burn-rate comparator; avoid claiming conventional monitoring only uses naive thresholds |
| S13 | [Stripe advanced error handling](https://docs.stripe.com/error-low-level) | Network/API error handling and retry/idempotency distinctions matter | Model operational retry load; never equate duplicate/failed attempts with lost money |
| S14 | [Kim et al Towards a Rigorous Evaluation of Time-series Anomaly Detection](https://arxiv.org/abs/2109.05257) | Research questions misleading point-adjusted evaluation | Report actual detected windows and onset-aligned event matches |
| S15 | [Cloud Run pricing](https://cloud.google.com/run/pricing) | Region/billing configuration affect compute, memory and request rates | Use explicit request-billed small-demo scenario; credits/free tiers separate |
| S16 | [Pub/Sub pricing](https://cloud.google.com/pubsub/pricing) | Basic delivery throughput has 10 GiB billing-account allowance then $40/TiB | Count publish and delivery bytes; distinguish export subscription pricing |
| S17 | [Firestore pricing](https://cloud.google.com/firestore/pricing) | Reads, writes, storage and region drive cost; displayed rates included $0.03/$0.09 per 100k reads/writes | Estimate operation counts and recheck selected location |
| S18 | [GCP generative model pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) | Gemini 3.8 Flash temporary global $0.75/$3.75 input/output per million, through 31 Dec 2026; announced rates change afterward | Date the fallback estimate; output includes billed reasoning; regional pricing differs |
| S19 | [BigQuery pricing](https://cloud.google.com/bigquery/pricing?authuser=1) | Official search result listed $6.25/TiB and first 1 TiB/month allowance | Full page fetch failed due size; indexed fact only, verify before deployment; BigQuery deferred |
| S20 | [Cloud Run billing configuration](https://docs.cloud.google.com/run/docs/configuring/billing-settings) | Request-billed CPU is allocated during request processing | Use persisted jobs/scheduled sweep; no assumed free-running background worker after response |

OpenAI pricing/model guidance was researched with the **OpenAI Docs** skill. Model capabilities are sourced from fetched official pages. No independent bake-off has been run. Google's current model pages were opened through official URLs, not third-party summaries. S19 has weaker verification status and is explicitly excluded from the core numerical cost estimate.

## Local source evidence

The organizer DOCX provides the exact five PS-02 technical requirements, three evaluation criteria and broader five judging dimensions. A relevant verbatim excerpt is in `source_brief_excerpt.txt`. The original CSV provides all reported descriptive counts, baseline confusion matrices and label diagnostics. SHA-256 values and paths are in `provenance.json`. The master prompt supplies user constraints and output requirements; additional fintech positioning is a recommendation, not organizer wording.

## Decision ledger

| Decision | Evidence type | Rationale | What would change it |
|---|---|---|---|
| Payment retry-cascade niche | Dataset names + explicit product judgment | Clear business-operation narrative with coherent simulator and safe action | Short timeframe/domain uncertainty favors general queue fallback |
| No original-data forecasting or lead-time claim | Computed EDA | Sparse series, missing onset, unknown timing/units | Dense labeled episodes with ex-ante feature availability |
| Statistical detector before LLM | Experiment and engineering tradeoff | Deterministic signals measurable cheaply; language reasoning adds evidence synthesis | Model-specific anomaly task would need independent benchmark |
| Backlog gate | Preserved exploratory failure | Latency alone over-alerted on nonincident slowdowns | Validation from another system may require new indicators/constants |
| Two Cloud Run roles and durable outbox | Official delivery/runtime docs + engineering judgment | Clear ingress/worker boundary, recoverable effects | Load/state tests may require a stream processor or relational outbox |
| No vector DB or multi-agent framework | Current small casebook/workflow scope | No measured need; fewer deployment surfaces | Proven retrieval/branching complexity beyond simple structured scan/state machine |
| OpenAI default, GCP model fallback | Official feature docs + credit context | Both support typed reasoning workflows; avoid routine double inference | Access, human quality, latency and cost bake-off results |
| Simulated infrastructure action only | User scope + operational risk | Demonstrates prevention without granting financial authority | Service-owner authorization, independent validation and guarded real-action tests |

## Hypotheses still requiring experiments

Payment teams will prefer an investigation/action workflow to existing alert triage; simulator parameters approximate a real adapter; robust queue signals transfer to unseen fault families; history improves summary/action quality; extra model calls improve outcomes enough to justify latency; GCP resource settings meet target processing latency. These are not verified external facts. The backlog contains the measurements needed to test them.
