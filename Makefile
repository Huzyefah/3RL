# Sentinel for NovaPay. Run `make help`. Python via uv only; never system python3.
SHELL := /bin/bash
PHASE ?= 00
STACK_STATE := .tmp
.DEFAULT_GOAL := help
.PHONY: help setup dev test lint types e2e e2e-live gate evidence fixtures compose-up compose-down eval deploy

help: ## list targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | column -t -s$$'\t'

setup: ## install python workspace, frontend and e2e deps, playwright browsers
	uv sync --all-packages
	@if [ -f frontend/package.json ]; then cd frontend && npm install; fi
	@if [ -f e2e/package.json ]; then cd e2e && npm install && npx playwright install chromium; fi
	@[ -f .env ] || { cp .env.example .env; echo "created .env from .env.example"; }

dev: ## run sentinel-api (8080), finpay-sim (8081), sentinel-web (3000); Ctrl-C stops all
	@if [ ! -d backend/sentinel/api ]; then echo "not implemented until Phase 6 (API); frontend only"; fi
	@set -a; [ -f .env ] && . ./.env; set +a; \
	trap 'kill 0' INT TERM EXIT; \
	if [ -d backend/sentinel/api ]; then uv run uvicorn sentinel.api.main:app --port 8080 --reload & fi; \
	if [ -f sim/finpay_sim/app.py ]; then uv run uvicorn finpay_sim.app:app --port 8081 --reload & fi; \
	if [ -f frontend/package.json ]; then (cd frontend && npm run dev -- --port 3000) & fi; \
	wait

lint: ## ruff + eslint
	uv run ruff check .
	uv run ruff format --check .
	@if [ -f frontend/package.json ]; then cd frontend && npm run lint; fi

test: ## unit + integration (python), vitest (frontend)
	uv run pytest -m unit --disable-socket --allow-unix-socket
	uv run pytest -m integration
	@if [ -f frontend/package.json ] && grep -q '"test"' frontend/package.json; then cd frontend && npm test; fi

e2e: ## playwright; EVIDENCE_PHASE=phase-NN-slug writes screenshots
	cd e2e && npx playwright test

e2e-live: ## @live specs with a real OpenAI key (not implemented until Phase 8)
	@echo "not implemented until Phase 8"

gate: ## phase gate: make gate PHASE=00
	PHASE=$(PHASE) bash scripts/gate.sh

evidence: ## rebuild evidence table: make evidence PHASE=00
	@slug=$$(uv run python -c "import json;print(json.load(open('scripts/phases.json'))['$(PHASE)']['slug'])") && \
	uv run python scripts/evidence_index.py phase-$(PHASE)-$$slug

types: ## regenerate frontend/lib/types.gen.ts from the OpenAPI snapshot (not implemented until Phase 6)
	@echo "not implemented until Phase 6"

fixtures: ## export backend outputs to frontend/fixtures (not implemented until Phase 3)
	@echo "not implemented until Phase 3"

compose-up: ## build and start the compose stack
	docker compose up --build -d

compose-down: ## stop the compose stack
	docker compose down

eval: ## run_eval.py scorecard (not implemented until Phase 3)
	@echo "not implemented until Phase 3"

deploy: ## infra/deploy.sh (not implemented until Phase 8b)
	@echo "not implemented until Phase 8b"
