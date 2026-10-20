# Model IDs (research for Task 0.1)

Checked 2026-10-20 against primary docs. Every row cites its source. UNVERIFIED = not confirmed from a primary page.
Note: fetched pages were summarised by a tool; the exact quoted values below are what the pages returned.

## 1. OpenAI

Sources: pricing https://developers.openai.com/api/docs/pricing ; model page https://developers.openai.com/api/docs/models/gpt-6-luna ; models index https://developers.openai.com/api/docs/models

| Env var | Chosen default | Price / 1M tokens (Standard, in / out) | Why |
|---|---|---|---|
| OPENAI_FAST_MODEL | `gpt-6-luna` | $0.10 / $0.50 (cached in $0.01) | Models index: "most efficient model for focused, high-volume tasks". 1.05M ctx, structured outputs + function calling supported. Function calling on Chat Completions only when `reasoning.effort=none`; Responses API supports it generally (model page). |
| OPENAI_SMART_MODEL | `gpt-6.1-sol` | $2.00 / $10.00 | Models index: "balances intelligence and cost". Flagship `gpt-6-astra` is $10 / $50 (too costly for the demo loop). |
| OPENAI_EMBED_MODEL | `text-embedding-3-small` | $0.02 input | Pricing page embeddings table (also `-3-large` $0.13, `ada-002` $0.10). |

Other IDs on the pricing page (alternates): `gpt-6-sol` $2/$10, `gpt-5.4-mini` $0.75/$4.50, `gpt-5.4-nano` $0.20/$1.25, `gpt-5-mini` $0.25/$2, `gpt-4.1-mini` $0.40/$1.60.

UNVERIFIED: embedding dimensions (embeddings guide fetch failed); whether `gpt-6-luna` / `gpt-6.1-sol` work well via openai-agents `OpenAIResponsesModel` (not tested; the SDK passes the model name through as a string). The `gpt-6.1-sol` model page was not fetched (only the pricing page + index list it).
Fallback if a chosen ID 404s for the key: `gpt-5.4-mini` (fast), `gpt-5.5` (smart; $5/$30).

## 2. Vertex AI Gemini (now branded "Gemini Enterprise Agent Platform" in docs)

Sources: model list https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/models ; lifecycle https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions ; locations https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/locations ; per-model pages `.../docs/models/gemini/<slug>`.

### GA models and retirement (model-versions page)

| API ID | Released | Retires | Notes |
|---|---|---|---|
| `gemini-4-argon` | 2026-10-13 | >= 2027-10-13 | GA; regions: global/us/eu only (model page) |
| `gemini-3.8-flash` | 2026-09-02 | >= 2027-09-02 | GA; structured output + function calling supported; regions: global/us/eu only (model page) |
| `gemini-3.5-flash` | 2026-05-19 | >= 2027-05-19 | GA; `asia-south1` in "Model availability" but NOT in Standard PayGo (see below) |
| `gemini-3.5-flash-lite` | 2026-07-21 | >= 2027-07-21 | GA; `asia-south1` in "Model availability"; Standard PayGo excludes it |
| `gemini-3.1-flash-lite` | 2026-05-07 | >= 2027-05-07 | GA; global/us/eu |
| `gemini-3.7-flash` | 2026-08-13 | 2027-01-28 | GA but scheduled for retirement; avoid |
| `gemini-3.6-flash` | 2026-07-21 | 2026-11-19 | GA but retires in a month; avoid |
| `gemini-3.1-pro-preview`, `gemini-3-flash-preview` | - | - | Preview only; avoid for the demo |

**RETIRED / AVOID: `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`** all retire 2026-10-20 (today) per the model-versions page (replacement `gemini-3.8-flash` / `gemini-3.5-flash(-lite)`). The page still lists them as available today, but they must not be used. `gemini-live-2.5-flash-native-audio` retires 2026-12-13; `gemini-2.5-flash-image` 2027-03-15; `gemini-2.0-flash(-lite)` retired 2026-06-01.

### Region availability: asia-south1 vs global

- Locations page lists Mumbai (`asia-south1`) under one shared "Asia Pacific" block of Gemini IDs; the page does not distinguish Mumbai from the other APAC cities, so it over-states availability. The per-model pages are more specific and should be trusted.
- `gemini-3.5-flash` model page: Model availability includes `asia-south1`; Provisioned Throughput includes `asia-south1` (single-zone only); **Standard PayGo = `global`, `us`, `eu` only**. So pay-as-you-go calls cannot use `asia-south1`.
- `gemini-3.5-flash-lite` page: `asia-south1` in Model availability but "Standard PayGo doesn't include asia-south1".
- `gemini-3.8-flash`, `gemini-4-argon`, `gemini-3.1-flash-lite` pages: only `global`, `us`, `eu`; no `asia-south1`.
- Global endpoint caveats (locations page): "doesn't support data residency requirements"; "Don't use the global endpoint if you have ML processing requirements"; improves availability and reduces 429s.

**Recommendation:** `VERTEX_LOCATION=global`, `VERTEX_MODEL=gemini-3.8-flash` (the current GA Flash, not retiring soon, structured output + function calling). Keep Cloud Run / BigQuery in asia-south1 independently; the LLM call location is separate from them. UNVERIFIED: whether Cloud Run in asia-south1 can call the global endpoint with extra latency (expected to work; no doc quoted). Vertex pricing for Gemini not obtained (pricing pages link-only): UNVERIFIED.

Embedding on Vertex (plan says P1 only): `gemini-embedding-2` page exists in nav, ID/regions UNVERIFIED. Plan keeps OpenAI embeddings in P0, so no action.

## 3. BigQuery ML in asia-south1

- `asia-south1` (Mumbai) is a supported BigQuery region: https://docs.cloud.google.com/bigquery/docs/locations (Asia Pacific table).
- AI.DETECT_ANOMALIES (uses the built-in TimesFM model, defaults TimesFM 2.5; 3.0 is Preview): doc says "`AI.DETECT_ANOMALIES` and the TimesFM model are available in all supported BigQuery ML locations." https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-ai-detect-anomalies . Limits: only the latest 1,024 points evaluated; min 3 points; `ANOMALY_PROB_THRESHOLD` in [0,1) default 0.95. So available in asia-south1 only to the extent asia-south1 is a "supported BigQuery ML location" (the locations table shows Mumbai with markers for built-in/non-remote models, but the flattened text could not be mapped to columns): treat as **likely yes, UNVERIFIED per-column**. Verify with one real query in the project's dataset location at 0:00.
- ARIMA_PLUS (`CREATE MODEL ... model_type='ARIMA_PLUS'`) is a built-in trained model; the CREATE MODEL reference shows no location restriction (only `HOLIDAY_REGION`, unrelated). https://docs.cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-create-time-series . Per-region support: UNVERIFIED, same smoke-test advice.
- Older function `ML.DETECT_ANOMALIES` is the ARIMA_PLUS path; `AI.DETECT_ANOMALIES` is the TimesFM path (search result snippet of the ML.DETECT_ANOMALIES doc page).
- Emulator note: goccy/bigquery-emulator does NOT support BigQuery ML (see sdk-versions.md), so these need a live check or must be mocked in tests.

## 4. Copy-paste `.env` defaults

```env
# --- LLM models (confirmed against provider docs 2026-10-20) ---
OPENAI_FAST_MODEL=gpt-6-luna
OPENAI_SMART_MODEL=gpt-6.1-sol
OPENAI_EMBED_MODEL=text-embedding-3-small
# --- Vertex AI Gemini (never gemini-2.5-*; retired 2026-10-20) ---
VERTEX_MODEL=gemini-3.8-flash
VERTEX_LOCATION=global
# Optional cheaper Vertex fallback: gemini-3.5-flash-lite (global)
# --- Region for the rest of GCP (BigQuery dataset / Cloud Run / Pub/Sub) ---
GCP_REGION=asia-south1
```
