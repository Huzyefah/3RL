#!/usr/bin/env bash
# Read-only preflight for Sentinel. Safe to re-run. Exits non-zero if a blocking check fails.
set -uo pipefail

PROJECT="${GCP_PROJECT:-mda-atomcamp}"
REGION="${GCP_REGION:-us-central1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0

ok()   { printf '  [ OK ] %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; fail=1; }
warn() { printf '  [WARN] %s\n' "$1"; }

echo "Sentinel preflight — project=$PROJECT region=$REGION — $(date -u +%FT%TZ)"

echo "1. Toolchain"
for t in gcloud uv node npm python3.12; do
  if command -v "$t" >/dev/null 2>&1; then ok "$t: $(command -v "$t")"; else bad "$t missing"; fi
done

echo "2. gcloud identity and project"
acct="$(gcloud config get-value account 2>/dev/null)"
[ -n "$acct" ] && ok "account: $acct" || bad "no gcloud account"
proj="$(gcloud config get-value project 2>/dev/null)"
[ "$proj" = "$PROJECT" ] && ok "active project: $proj" || warn "active project is '$proj', expected $PROJECT"
if gcloud projects get-iam-policy "$PROJECT" --flatten=bindings[].members \
     --filter="bindings.members:user:$acct AND bindings.role:roles/owner" --format='value(bindings.role)' 2>/dev/null | grep -q owner; then
  ok "$acct has roles/owner"
else
  warn "$acct is not owner (deploy may still work with narrower roles)"
fi

echo "3. Billing"
billing="$(gcloud billing projects describe "$PROJECT" --format='value(billingEnabled,billingAccountName)' 2>/dev/null)"
if [[ "$billing" == True* ]]; then ok "billing enabled: $billing"; else bad "billing NOT enabled: '$billing'"; fi

echo "4. Data"
rows=$(($(wc -l < "$ROOT/data/ps02_system_telemetry.csv") - 1))
[ "$rows" -eq 500 ] && ok "PS-02 CSV rows: $rows" || bad "PS-02 CSV rows: $rows (expected 500)"

echo "5. OpenAI key"
key="${OPENAI_API_KEY:-}"
if [ -z "$key" ] && [ -f "$ROOT/.env" ]; then key="$(grep -E '^OPENAI_API_KEY=' "$ROOT/.env" | cut -d= -f2- | tr -d "'\"")"; fi
if [ -z "$key" ]; then
  bad "OPENAI_API_KEY not set (env or .env)"
else
  code=$(curl -s --retry 2 --max-time 20 -o /dev/null -w '%{http_code}' https://api.openai.com/v1/models -H "Authorization: Bearer $key")
  [ "$code" = "200" ] && ok "OpenAI key valid (GET /v1/models → 200)" || bad "OpenAI key check → HTTP $code"
fi

echo "6. Google Chat webhook (optional)"
[ -n "${CHAT_WEBHOOK_URL:-}" ] || grep -qE '^CHAT_WEBHOOK_URL=.+' "$ROOT/.env" 2>/dev/null \
  && ok "CHAT_WEBHOOK_URL present" || warn "CHAT_WEBHOOK_URL absent → UI 'Chat card' panel fallback"

echo
[ $fail -eq 0 ] && echo "PREFLIGHT: PASS" || echo "PREFLIGHT: FAIL"
exit $fail
