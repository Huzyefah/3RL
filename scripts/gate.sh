#!/usr/bin/env bash
# Phase gate (plan "Phase gate protocol"). Usage: PHASE=00 bash scripts/gate.sh   (or: scripts/gate.sh 00)
# Automates steps 1-4 and prints a summary. Steps 5-8 (verify, review, close-out, user checkpoint) are manual.
set -uo pipefail
cd "$(dirname "$0")/.."

PHASE="${1:-${PHASE:-}}"
[ -n "$PHASE" ] || { echo "usage: PHASE=NN bash scripts/gate.sh" >&2; exit 2; }
SLUG=$(uv run python -c "import json,sys;print(json.load(open('scripts/phases.json'))[sys.argv[1]]['slug'])" "$PHASE" 2>/dev/null) \
  || { echo "unknown phase '$PHASE' (see scripts/phases.json)" >&2; exit 2; }
PHASE_ID="phase-${PHASE}-${SLUG}"
export EVIDENCE_PHASE="$PHASE_ID"
export LLM_PROVIDER="${LLM_PROVIDER:-scripted}"

RESULTS=()
FAILED=0
step() { # step "<label>" cmd...
  local label="$1"; shift
  echo; echo "=== $label ==="; echo "+ $*"
  if "$@"; then RESULTS+=("PASS  $label"); else RESULTS+=("FAIL  $label"); FAILED=1; fi
}
skip() { echo; echo "=== $1 === skipped: $2"; RESULTS+=("SKIP  $1 ($2)"); }
have() { [ -e "$1" ]; }

echo "Gate for $PHASE_ID (branch: $(git rev-parse --abbrev-ref HEAD))"

# 1. Static checks
if have pyproject.toml; then
  step "1 ruff check" uv run ruff check .
  step "1 ruff format --check" uv run ruff format --check .
  step "1 pyright" uv run pyright
else skip "1 python static" "no pyproject.toml"; fi
if have frontend/package.json && have frontend/node_modules; then
  step "1 frontend eslint" npm --prefix frontend run lint
  step "1 frontend tsc" bash -c 'cd frontend && npx tsc --noEmit'
else skip "1 frontend static" "frontend not installed (make setup)"; fi
if have e2e/package.json && have e2e/node_modules; then
  step "1 e2e tsc" bash -c 'cd e2e && npx tsc --noEmit'
else skip "1 e2e static" "e2e not installed (make setup)"; fi

# 2. Full regression (all phases so far)
if have pyproject.toml; then
  mkdir -p "test-evidence/$PHASE_ID/reports"
  step "2 pytest unit (no network)" uv run pytest -m unit --disable-socket --allow-unix-socket
  step "2 pytest integration + e2e_http" uv run pytest -m "integration or e2e_http" \
    --html="test-evidence/$PHASE_ID/reports/pytest.html" --self-contained-html
fi
if have frontend/package.json && grep -q '"test"' frontend/package.json 2>/dev/null && have frontend/node_modules; then
  step "2 vitest" npm --prefix frontend test
fi
# Earlier phases' Playwright specs run as regression: no evidence written.
EARLIER=$(ls -d e2e/specs/phase-* 2>/dev/null | grep -v "/$PHASE_ID\$" | xargs -n1 basename 2>/dev/null | sort || true)
if have e2e/playwright.config.ts && have e2e/node_modules; then
  PREV=()
  for d in $EARLIER; do
    # Only phases numerically before this one.
    n=${d#phase-}; n=${n%%-*}
    [[ "$n" < "$PHASE" ]] && PREV+=("specs/$d/")
  done
  if [ ${#PREV[@]} -gt 0 ]; then
    step "2 playwright regression (no evidence)" bash -c 'cd e2e && EVIDENCE_PHASE=regression npx playwright test "$@"' _ "${PREV[@]}"
  fi

  # 3. Current-phase specs, twice in a row (flake check); these write evidence.
  if have "e2e/specs/$PHASE_ID"; then
    step "3 playwright $PHASE_ID run 1" bash -c "cd e2e && npx playwright test specs/$PHASE_ID/"
    step "3 playwright $PHASE_ID run 2 (flake check)" bash -c "cd e2e && npx playwright test specs/$PHASE_ID/"
  else skip "3 playwright current phase" "no e2e/specs/$PHASE_ID"; fi
else skip "2-3 playwright" "e2e not installed (make setup)"; fi

# 4. Evidence check and REPORT.md table
step "4 evidence index" uv run python scripts/evidence_index.py "$PHASE_ID"

echo; echo "================ GATE SUMMARY: $PHASE_ID ================"
printf '%s\n' "${RESULTS[@]}"
if [ "$FAILED" -eq 0 ]; then
  echo "AUTOMATED STEPS 1-4: GREEN"
  echo "Remaining by hand: 5 verify (read the output above), 6 code-review sub-agent, 7 REPORT.md + PR (merge needs user go-ahead), 8 ask the user whether to continue."
else
  echo "AUTOMATED STEPS 1-4: RED (systematic-debugging; never skip or weaken a test)"
fi
exit "$FAILED"
