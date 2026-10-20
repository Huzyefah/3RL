#!/usr/bin/env bash
# Deploy the scripted demo backend (sentinel-demo-api, public) and point sentinel-web at API_URL (default: demo).
set -euo pipefail
command -v python3.12 >/dev/null && export CLOUDSDK_PYTHON="$(command -v python3.12)"
P=mda-atomcamp; R=us-central1; ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
WEB="$R-docker.pkg.dev/$P/sentinel/web:$(git rev-parse --short=12 HEAD:frontend)"
DEMO="$R-docker.pkg.dev/$P/sentinel/demo:$(git rev-parse --short=12 HEAD:e2e)"
API_URL="${API_URL:-https://sentinel-demo-api-725314964496.$R.run.app}"
build() { gcloud --project $P --quiet artifacts docker images describe "$2" >/dev/null 2>&1 && { echo "exists $2"; return; }
  id=$(gcloud --project $P --quiet builds submit --async --format='value(id)' --config "infra/cloudbuild/$1.yaml" --substitutions "_IMAGE=$2" .)
  while :; do s=$(gcloud --project $P builds describe "$id" --format='value(status)'); echo "$1 $s"
    case "$s" in SUCCESS) return;; FAILURE|INTERNAL_ERROR|TIMEOUT|CANCELLED) exit 1;; esac; sleep 15; done; }
build web "$WEB" & build demo "$DEMO" & wait
gcloud --project $P --quiet run deploy sentinel-demo-api --image "$DEMO" --region $R --allow-unauthenticated \
  --min-instances 1 --max-instances 1 --no-cpu-throttling --timeout 3600 --concurrency 250 2>&1 | grep -E "URL|ERROR"
gcloud --project $P --quiet run deploy sentinel-web --image "$WEB" --region $R --service-account "sa-web@$P.iam.gserviceaccount.com" \
  --allow-unauthenticated --min-instances 1 --max-instances 2 --timeout 3600 --memory 1Gi \
  --set-env-vars "SENTINEL_API_URL=$API_URL" --set-secrets OPERATOR_TOKEN=OPERATOR_TOKEN:latest 2>&1 | grep -E "URL|ERROR"
