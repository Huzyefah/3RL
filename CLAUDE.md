# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Monorepo of two independent, currently empty scaffolds: a Next.js frontend (`frontend/`) and a FastAPI backend (`backend/`). There are no custom routes, pages, tests, or frontend-to-backend wiring yet (no CORS config, API client, or shared types).

## Commands

Frontend (`cd frontend`; Node 20.9+, npm):
- `npm install`
- `npm run dev` — dev server at http://localhost:3000
- `npm run build` / `npm run start`
- `npm run lint` — ESLint (flat config in `eslint.config.mjs`)

Backend (`cd backend`; Python 3.12+, [uv](https://docs.astral.sh/uv/)):
- `uv sync`
- `uv run fastapi dev main.py` — dev server at http://localhost:8000, API docs at `/docs`
- Add dependencies with `uv add <pkg>` (updates `pyproject.toml` and `uv.lock`)

No test framework is configured in either project.

## Architecture notes

- **Backend**: single entrypoint `backend/main.py` exposing `app = FastAPI(title="3RL API")`. The `fastapi[standard]` extra provides the `fastapi` CLI.
- **Frontend**: Next.js 16 / React 19 App Router under `frontend/src/app/` (`layout.tsx`, `page.tsx`). `next.config.ts` enables `cacheComponents` and `partialPrefetching`, which change caching and prefetching behavior compared with older Next.js versions.

## Next.js caveat

`frontend/AGENTS.md` warns that this Next.js version has breaking changes relative to common training data. Before writing frontend code, read the relevant guide in `frontend/node_modules/next/dist/docs/` (run `npm install` first) and heed deprecation notices. `next dev` re-adds that AGENTS.md block if it is removed.
