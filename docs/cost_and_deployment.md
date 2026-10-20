# Cost and deployment plan

Nothing has been provisioned, billed or deployed by this assignment. Prices below were checked against official pages on **20 October 2026**. USD list-price estimates exclude tax, credits, existing billing-account usage, egress and additional paid features. Region, account access, quota and model response-token usage remain unknown. Recheck rates at deployment.

## Bounded inference cost

Assume two model calls per incident, **total** 6,000 input and 1,200 billable output tokens. Output assumptions must include any billed reasoning tokens; do not use only displayed summary length. Formula: incidents × (input_tokens × input_price + output_tokens × output_price) / 1,000,000. This is an estimate, not an observed bill.

| Route | Official text price per million input / output tokens | 100 incidents | 10,000 incidents | Qualification |
|---|---|---:|---:|---|
| GPT-5.4 mini | $0.75 / $4.50 | $0.99 | $99 | [Official model pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini); uncached, standard API |
| Gemini 3.8 Flash global | $0.75 / $3.75 | $0.90 | $90 | [Official GCP pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing); temporary rates through 31 December 2026; non-global rates differ |

The same Gemini page lists global $1.50/$7.50 starting 1 January 2027, doubling this token scenario to $1.80/$180. Neither route has a measured quality, reliability or latency advantage in this package. Credits do not establish model access or zero marginal production cost. No embeddings or external built-in model tools are necessary initially.

## Infrastructure estimate

Small-demo workload assumptions: 100,000 total events, approximately 1 KiB billable publish payload, one delivery each, 110,000 HTTP requests including UI/jobs, 20,000 active vCPU-seconds and 10,000 active GiB-seconds across both services. Redelivery, batching minimums, schema envelopes, window state and investigations can change these numbers substantially.

| Driver | Rate and calculation | Gross illustrative cost |
|---|---|---:|
| Cloud Run request-billed CPU | 20,000 × $0.000024/vCPU-second | $0.48 |
| Cloud Run active memory | 10,000 × $0.0000025/GiB-second | $0.025 |
| Cloud Run requests | 110,000 / 1M × $0.40 | $0.044 |
| Pub/Sub basic throughput | 200,000 KiB publish + delivery / 1 TiB × $40 | about $0.0075 |
| Firestore writes | Assumed 400,000 writes / 100,000 × $0.09 | $0.36 |
| Firestore reads | Assumed 800,000 reads / 100,000 × $0.03 | $0.24 |
| Model | 100 episodes at above OpenAI token budget | $0.99 |

About **$2.15 before free allowances** for these listed usage assumptions only. This is not an all-in quote. Sources: [Cloud Run pricing](https://cloud.google.com/run/pricing), [Pub/Sub pricing](https://cloud.google.com/pubsub/pricing), [Firestore pricing](https://cloud.google.com/firestore/pricing). Use the region selector for deployment pricing. Storage, artifact builds/registry, Secret Manager, Scheduler, logs, network, indexes and any extra model reasoning are excluded. Set a separate $10–25 planning reserve for small-demo extras and mistakes; that reserve is a budget choice, not a sourced service-price estimate. Cloud Run and Pub/Sub have billing-account free allowances, but do not assume they remain available.

BigQuery is optional and omitted from the MVP estimate. Its [official pricing result](https://cloud.google.com/bigquery/pricing?authuser=1) listed on-demand $6.25/TiB and a first 1 TiB/month allowance; full page fetch failed, so treat that value as a search-index check requiring deployment-time confirmation. Do not add analytical storage/ingestion charges into a falsely exact total.

## Controls

Filter statistically before model invocation; merge incidents and cache stable dependency/runbook context. Maximum two model turns, four reads, concise 3,000-token input per call target and explicit output/reasoning budget. Record actual usage and estimated cost by incident/model/version; stop nonessential model investigations at a configurable daily ceiling. Concurrency semaphore, max instances and bounded replay speed limit burst costs. Billing alerts warn; they are not a guaranteed hard spend cap.

Do not retain every healthy event in verbose application logs. Keep raw artifacts 30 days and demo window state seven days, review policy before real data. P1 BigQuery queries need partitions, maximum bytes billed and bounded scan windows. Benchmark batched ingestion versus one push per event; batching is useful only when it meets warning latency and source payload limits. Avoid a minimum instance by default; selectively warm the demo service if a measured cold start harms the presentation.

## Reproducible deployment sequence

This is a build/deploy **plan**, not a claim that runnable app or infrastructure files already exist.

1. Confirm project ID, billing, credit expiry, permissible region, model access and team roles. Prefer one region for backend, Firestore and artifact bucket; do not choose a data-residency region without requirements.
2. Enable Run, Artifact Registry, Cloud Build, Pub/Sub, Firestore, Storage, Secret Manager, Scheduler and Monitoring APIs. Enable the GCP model API only if the fallback is used. Provision Firestore in the selected mode/location before loading data.
3. Create separate API, worker, producer, push-invoker and scheduler identities. Scope publish, Run invoke, store access and secret access; no broad Owner/Editor runtime role. Grant Pub/Sub service-agent permissions for authenticated delivery and dead-letter forwarding as documented.
4. Build a pinned image from a locked application dependency file, add health checks, scan for secrets and deploy by digest. API/frontend accepts authenticated UI traffic; worker requires IAM. Start min instances 0, max 3, worker concurrency 8, memory 512 MiB, 1 vCPU; load-test and adjust rather than asserting these fit all traffic.
5. Configure server-side secret reference using an explicit version and a model/provider setting. No secrets in image, browser bundle or source. Keep deterministic fallback enabled and record fallback state.
6. Create telemetry/jobs topics, authenticated push subscriptions, DLQ and retention/retry policy. Use canonical event IDs and tenant/replay namespace. Configure the scheduler to call authenticated outbox/verification sweep endpoints. Avoid an unawaited background loop after HTTP response on request-billed Cloud Run.
7. Load only curated synthetic training history, versioned runbooks, service graph and demo fixtures. Save artifact hashes and model/detector/policy versions. Deploy API and worker with the same contract version.
8. Smoke test accepted/rejected ingestion, duplicate delivery, original CSV replay, synthetic full cycle, model outage, DLQ, unauthorized action, action reconciliation and verification timeout. Capture GCP execution evidence, not merely local screenshots.
9. Load test 10 events/s then a 100 events/s burst; measure p95 source-receive-to-candidate latency, backlog and model invocation rate. Window accumulation time is separate from processing latency. Do not claim production readiness from these targets.
10. Tag the passing revision and export configuration/IAM inventory. Rollback deploys prior image/config and disables new action claims; preserve incident/action ledger to avoid replayed effects. Shut down replay, remove minimum instances and review logs/billing after the event.

Application implementation should provide `infra/deploy` and `infra/rollback` scripts with explicit project/region arguments, fail-fast validation, no interactive assumptions and no destructive defaults. They are backlog items. Infrastructure-as-code is P1 after a working deployment unless time allows it earlier.
