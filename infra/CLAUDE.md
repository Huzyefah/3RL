# infra/: GCP (project mda-atomcamp #725314964496, us-central1)

| Script | Purpose |
|---|---|
| `preflight.sh` | Read-only checks: toolchain, account/owner, billing, CSV, OpenAI key, Chat webhook |
| `bootstrap.sh` | **Idempotent.** Enables the APIs, the Artifact Registry `sentinel`, the service accounts, BigQuery `sentinel` (+ `bq_schema.sql`), the Pub/Sub `telemetry`/`telemetry-dlq` topics and the `telemetry-bq` BigQuery subscription, the secrets, and the evidence bucket |
| `deploy.sh api\|sim\|web` | Cloud Build from the **repo root** (`cloudbuild/<svc>.yaml`), then `gcloud run deploy --image`. Image tag = git short SHA |

## Service accounts
| SA | Runs | Can call / access |
|---|---|---|
| `sa-api` | sentinel-api | invokes finpay-sim; BQ dataEditor + jobUser; Pub/Sub publisher; Vertex user; Monitoring viewer; secrets OPENAI_API_KEY, OPERATOR_TOKEN, CHAT_WEBHOOK_URL |
| `sa-web` | sentinel-web | invokes sentinel-api; secret OPERATOR_TOKEN |
| `sa-sim` | finpay-sim | Pub/Sub publisher |
| `sa-push` | Pub/Sub push subscription identity | invokes sentinel-api |

## Rules
- These scripts touch **only** `sentinel-api`, `sentinel-web`, `finpay-sim` and Sentinel resources. They do no list-driven or wildcard cleanup. `gcp-openai-demo` and `mda-atomcamp` are someone else's.
- Only `sentinel-web` is public (`--allow-unauthenticated`). Cloud Run IAM is per service, not per path, so the api and sim stay private.
- Secret values come from the gitignored `.env`. Never echo them, and redact `sk-…` in logs and evidence.
- Do not redeploy within 10 minutes of the demo, because a new revision wipes in-memory state.
- P1 scale action: `sa-api` gets `run.developer` **on the finpay-sim service only** and `iam.serviceAccountUser` on `sa-sim`. Added in Phase 8d.
