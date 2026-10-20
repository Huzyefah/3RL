#!/usr/bin/env bash
# Idempotent GCP bootstrap for Sentinel. Touches ONLY Sentinel resources (never other Cloud Run services).
set -euo pipefail
# gcloud storage commands crash under Python 3.14; pin a supported interpreter when available.
command -v python3.12 >/dev/null && export CLOUDSDK_PYTHON="${CLOUDSDK_PYTHON:-$(command -v python3.12)}"
PROJECT="${GCP_PROJECT:-mda-atomcamp}"
REGION="${GCP_REGION:-us-central1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PNUM="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
PUBSUB_AGENT="service-${PNUM}@gcp-sa-pubsub.iam.gserviceaccount.com"
g() { gcloud --project "$PROJECT" --quiet "$@"; }
say() { printf '\n== %s\n' "$1"; }

say "APIs"
g services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  pubsub.googleapis.com bigquery.googleapis.com secretmanager.googleapis.com aiplatform.googleapis.com \
  monitoring.googleapis.com cloudscheduler.googleapis.com iamcredentials.googleapis.com

say "Artifact Registry"
g artifacts repositories describe sentinel --location "$REGION" >/dev/null 2>&1 \
  || g artifacts repositories create sentinel --location "$REGION" --repository-format docker

say "Service accounts"
for sa in sa-api sa-web sa-sim sa-push; do
  g iam service-accounts describe "$sa@$PROJECT.iam.gserviceaccount.com" >/dev/null 2>&1 \
    || g iam service-accounts create "$sa" --display-name "Sentinel $sa"
done
SA_API="sa-api@$PROJECT.iam.gserviceaccount.com"

say "Project roles for sa-api (BigQuery writes, Pub/Sub publish, Vertex, Monitoring read)"
for role in roles/bigquery.dataEditor roles/bigquery.jobUser roles/pubsub.publisher roles/aiplatform.user roles/monitoring.viewer; do
  g projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA_API" --role "$role" --condition=None >/dev/null
done
g projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:sa-sim@$PROJECT.iam.gserviceaccount.com" \
  --role roles/pubsub.publisher --condition=None >/dev/null

say "BigQuery dataset + tables"
bq --project_id "$PROJECT" show --dataset "$PROJECT:sentinel" >/dev/null 2>&1 \
  || bq --project_id "$PROJECT" mk --dataset --location US "$PROJECT:sentinel"
bq --project_id "$PROJECT" query --nouse_legacy_sql --quiet < "$ROOT/infra/bq_schema.sql" >/dev/null
# Pub/Sub service agent needs WRITER on the dataset for the BigQuery subscription (dataset ACL, least privilege).
DS_JSON="$(mktemp)"
bq --project_id "$PROJECT" show --format=prettyjson "$PROJECT:sentinel" > "$DS_JSON"
if ! jq -e --arg a "$PUBSUB_AGENT" '.access[] | select(.userByEmail == $a and .role == "WRITER")' "$DS_JSON" >/dev/null; then
  jq --arg a "$PUBSUB_AGENT" '.access += [{"role":"WRITER","userByEmail":$a}]' "$DS_JSON" > "$DS_JSON.new"
  bq --project_id "$PROJECT" update --source "$DS_JSON.new" "$PROJECT:sentinel" >/dev/null
  echo "  granted WRITER on sentinel to $PUBSUB_AGENT"
fi
rm -f "$DS_JSON" "$DS_JSON.new"

say "Pub/Sub topics + BigQuery subscription"
for t in telemetry telemetry-dlq; do
  g pubsub topics describe "$t" >/dev/null 2>&1 || g pubsub topics create "$t"
done
g pubsub topics add-iam-policy-binding telemetry-dlq --member "serviceAccount:$PUBSUB_AGENT" --role roles/pubsub.publisher >/dev/null
g pubsub subscriptions describe telemetry-bq >/dev/null 2>&1 \
  || g pubsub subscriptions create telemetry-bq --topic telemetry \
       --bigquery-table "$PROJECT:sentinel.events_raw" --write-metadata

say "Secrets"
envval() { grep -E "^$1=" "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d "'\"" || true; }
if ! grep -qE '^OPERATOR_TOKEN=.+' "$ROOT/.env" 2>/dev/null; then
  (umask 077; echo "OPERATOR_TOKEN=$(openssl rand -hex 24)" >> "$ROOT/.env")
fi
put_secret() {  # name value accessor-sa...
  local name="$1" val="$2"; shift 2
  [ -z "$val" ] && { echo "  skip $name (no value)"; return; }
  g secrets describe "$name" >/dev/null 2>&1 || g secrets create "$name" --replication-policy automatic
  local cur; cur="$(g secrets versions access latest --secret "$name" 2>/dev/null || true)"
  [ "$cur" = "$val" ] || printf '%s' "$val" | g secrets versions add "$name" --data-file=- >/dev/null
  for sa in "$@"; do
    g secrets add-iam-policy-binding "$name" --member "serviceAccount:$sa@$PROJECT.iam.gserviceaccount.com" \
      --role roles/secretmanager.secretAccessor >/dev/null
  done
  echo "  $name ok"
}
put_secret OPENAI_API_KEY "$(envval OPENAI_API_KEY)" sa-api
put_secret OPERATOR_TOKEN "$(envval OPERATOR_TOKEN)" sa-api sa-web
put_secret CHAT_WEBHOOK_URL "$(envval CHAT_WEBHOOK_URL)" sa-api

say "Evidence bucket"
gcloud storage buckets describe "gs://$PROJECT-sentinel-evidence" >/dev/null 2>&1 \
  || gcloud storage buckets create "gs://$PROJECT-sentinel-evidence" --project "$PROJECT" --location "$REGION" --uniform-bucket-level-access

echo; echo "BOOTSTRAP: DONE (project $PROJECT #$PNUM)"
