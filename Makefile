# Sentinel — top-level commands. See CLAUDE.md for the phase gate protocol.
SHELL := /bin/bash
PROJECT ?= mda-atomcamp
REGION  ?= us-central1

.PHONY: test test-backend test-sim test-web e2e e2e-live lint dev dev-api dev-sim dev-web preflight bootstrap deploy-api deploy-sim deploy-web deploy

test: test-backend test-sim test-web

test-backend:
	cd backend && uv run pytest --junitxml=.results/junit.xml

test-sim:
	cd sim && uv run pytest --junitxml=.results/junit.xml

test-web:
	cd frontend && npm run lint && npm run build

e2e:
	cd e2e && npx playwright test --grep-invert @live

e2e-live:
	cd e2e && npx playwright test --grep @live

lint:
	cd backend && uv run ruff check . && cd ../sim && uv run ruff check .

dev-api:
	cd backend && uv run uvicorn sentinel.api.main:app --port 8080

dev-sim:
	cd sim && uv run uvicorn finpay_sim.app:app --port 8081

dev-web:
	cd frontend && SENTINEL_API_URL=http://localhost:8080 npm run dev

dev:
	$(MAKE) -j3 dev-api dev-sim dev-web

preflight:
	infra/preflight.sh

bootstrap:
	infra/bootstrap.sh

deploy-api:
	infra/deploy.sh api

deploy-sim:
	infra/deploy.sh sim

deploy-web:
	infra/deploy.sh web

deploy: deploy-sim deploy-api deploy-web
