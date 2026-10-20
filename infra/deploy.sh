#!/usr/bin/env bash
# Build (Cloud Build, repo-root context) and deploy ONE Sentinel service: api | sim | web.
# Never touches any other Cloud Run service in the project.
set -euo pipefail
SVC="${1:?usage: deploy.sh api|sim|web}"
PROJECT="${GCP_PROJECT:-mda-atomcamp}"
REGION="${GCP_REGION:-us-central1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PNUM="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
url() { echo "https://$1-$PNUM.$REGION.run.app"; }
envval() { grep -E "^$1=" "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d "'\"" || true; }
TAG="$(git -C "$ROOT" rev-parse --short HEAD)$(git -C "$ROOT" diff --quiet || echo -dirty)"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/sentinel/$SVC:$TAG"
g() { gcloud --project "$PROJECT" --quiet "$@"; }

case "$SVC" in
  api) NAME=sentinel-api ;; sim) NAME=finpay-sim ;; web) NAME=sentinel-web ;;
  *) echo "unknown service $SVC"; exit 2 ;;
esac

echo "== build $NAME → $IMAGE"
(cd "$ROOT" && g builds submit --config "infra/cloudbuild/$SVC.yaml" --substitutions "_IMAGE=$IMAGE" .)

echo "== deploy $NAME"
case "$SVC" in
  api)
    g run deploy sentinel-api --image "$IMAGE" --region "$REGION" --service-account "sa-api@$PROJECT.iam.gserviceaccount.com" \
      --no-allow-unauthenticated --min-instances 1 --max-instances 1 --no-cpu-throttling \
      --concurrency 250 --timeout 3600 --memory 2Gi --cpu 2 \
      --set-env-vars "ENV=prod,GCP_PROJECT=$PROJECT,GCP_REGION=$REGION,SIM_BASE_URL=$(url finpay-sim),OPENAI_FAST_MODEL=$(envval OPENAI_FAST_MODEL),OPENAI_SMART_MODEL=$(envval OPENAI_SMART_MODEL),OPENAI_EMBED_MODEL=$(envval OPENAI_EMBED_MODEL),OPENAI_AGENTS_DISABLE_TRACING=1" \
      --set-secrets "OPENAI_API_KEY=OPENAI_API_KEY:latest,OPERATOR_TOKEN=OPERATOR_TOKEN:latest"
    for sa in sa-web sa-push; do
      g run services add-iam-policy-binding sentinel-api --region "$REGION" \
        --member "serviceAccount:$sa@$PROJECT.iam.gserviceaccount.com" --role roles/run.invoker >/dev/null
    done ;;
  sim)
    g run deploy finpay-sim --image "$IMAGE" --region "$REGION" --service-account "sa-sim@$PROJECT.iam.gserviceaccount.com" \
      --no-allow-unauthenticated --min-instances 1 --max-instances 1 --no-cpu-throttling --memory 1Gi \
      --set-env-vars "GCP_PROJECT=$PROJECT"
    g run services add-iam-policy-binding finpay-sim --region "$REGION" \
      --member "serviceAccount:sa-api@$PROJECT.iam.gserviceaccount.com" --role roles/run.invoker >/dev/null ;;
  web)
    g run deploy sentinel-web --image "$IMAGE" --region "$REGION" --service-account "sa-web@$PROJECT.iam.gserviceaccount.com" \
      --allow-unauthenticated --min-instances 1 --max-instances 2 --timeout 3600 --memory 1Gi \
      --set-env-vars "SENTINEL_API_URL=$(url sentinel-api)" \
      --set-secrets "OPERATOR_TOKEN=OPERATOR_TOKEN:latest" ;;
esac
echo "== $NAME → $(url "$NAME")"
