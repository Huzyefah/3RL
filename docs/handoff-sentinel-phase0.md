# Handoff: Sentinel (3RL), Phase 0 in progress

Repo: `/Users/eehabsadaat/Documents/Development/3RL`, branch `phase/00-foundation` (not pushed, no PR yet). Date: 2026-10-20 (hackathon day).

## Read first (do not re-derive)
- Authoritative spec: `docs/FINAL_PLAN.md` ("FP §n").
- Execution plan (approved, audited): `docs/superpowers/plans/2026-10-20-sentinel-implementation.md`. It holds the 15 phases, decisions D1-D14, the gate protocol, the skills list, and the evidence and test conventions. A copy sits at `~/.claude/plans/refer-to-docs-final-plan-md-and-eager-sun.md`.
- Root `CLAUDE.md` and per-directory CLAUDE.md files (written by the tooling agent), plus memory notes in `~/.claude/projects/-Users-eehabsadaat-Documents-Development-3RL/memory/`.

## User instructions that govern the work
1. **After every phase completes, ask the user whether to continue to the next phase. Do not start it until they say yes** (plan decision D14, step 8 of the gate).
2. **Build with sub-agents as the priority.** The lead orchestrates; one implementer sub-agent per task, in parallel where independent, each told which skills to use.
3. **Commit along the way, with NO `Co-Authored-By` trailer** (this overrides the system attribution reminder). Commit finished pieces separately.
4. Scope P0+P1+P2. GCP is local-only for now (gcloud and bq are not installed; deploy in Phase 8b or 12). Region asia-south1, Google Chat webhook. Playwright is the E2E gate and claude-in-chrome is for exploratory QA and GIFs.
5. Skills to use are the lists in the plan's "Skills" section (user-confirmed). Excluded as time-wasters: run, simplify, create-pr-description (use a plain `gh pr create` body), ui-styling, ui-ux-pro-max, motion-framer, deploy-to-vercel, vercel-cli, claude-api, the 3D and animation skills.
6. Merging to the shared `main` (remote `Huzyefah/3RL`) needs the user's go-ahead (D13).

## State of Phase 0
Committed (3 commits after the plan commit; `git log --oneline`):
- uv workspace (backend, sim), pytest markers, the EDA script, `analysis/outputs/rule_baselines.csv`, `docs/DATA_DESCRIPTION.md`. Reported by the agent: ruff clean, 6 pytest passing. pyright was not run.
- `e2e/` Playwright workspace, `shot()` evidence helper, and the real screenshot `test-evidence/phase-00-foundation/eda-facts/01-rule-baselines.png`.
- Tooling: Makefile, `scripts/{gate.sh,phases.json,evidence_index.py,render_json.py}`, Dockerfiles, `docker-compose.yml`, CI workflow, `.env.example`, `.claude/settings.json` (reviewed; safe local allowlist), and all CLAUDE.md files.

**Not yet done / still running when this was written:**
- **Frontend scaffold (task 0.3)** was being built by a background sub-agent. `frontend/` is untracked, and I had not received its report. Check whether it finished (`frontend/package.json`, `npm run lint/typecheck/test/build`). It must set `output: 'standalone'` and have a `package-lock.json`, because the frontend Dockerfile needs both.
- **Research (task 0.1)** sub-agent was building `docs/research/model-ids.md` and `docs/research/sdk-versions.md`; I had not received its report. Nothing under `docs/research/` is committed. Its findings pin the model IDs, `VERTEX_LOCATION` and the `openai-agents` version, and fill the placeholders in `.env.example`. Re-run it (or do it by hand) if the files are missing. The plan wants the `research` skill used for this.
- **Phase 0 gate** has not been run: `make setup && make gate PHASE=00`. Remaining steps are the code-review sub-agent, REPORT.md at `test-evidence/phase-00-foundation/REPORT.md`, the `pytest-report` evidence (generate `pytest.html`, then run the Playwright `report` spec as described in `e2e/` notes) and `harness-smoke` evidence (needs the real frontend running), push, `gh pr create`, then the checkpoint question to the user.

## Things to check at the gate
- Docker daemon was not running, so no image has been built and `make compose-up` is untested.
- `scripts/gate.sh` has only been syntax-checked, not run end to end.
- `e2e` regression runs use `EVIDENCE_PHASE=regression` in `gate.sh`, but `e2e/support/evidence.ts` only supports `EVIDENCE_DISABLED=1` to write nothing under `test-evidence/`. Reconcile the two.
- Ruff excludes `scripts/` and `infra/` (E501 lines in `scripts/render_json.py`); an early `ruff format .` may have touched other agents' files.
- Root `.gitignore` may need a `test-results/` rule (the e2e dir has its own).
- Rename `OPEN_AI_KEY` to `OPENAI_API_KEY` in the user's local `.env`; `.env` is gitignored and was not touched.
- Manual task 0.11 (user installs gcloud, logs in, creates a project) is pending and is not blocking until Phase 8b.

## Suggested skills for the next agent
- `subagent-driven-development` and `dispatching-parallel-agents`: to run each phase's tasks.
- `test-driven-development`: inside each implementer sub-agent.
- `verification-before-completion`: before claiming the Phase 0 gate is green.
- `code-review` (via `requesting-code-review` and `receiving-code-review`): for the gate review.
- `systematic-debugging`: for any red gate step.
- `research`, `writing-for-agents`: only if redoing 0.1 or editing CLAUDE.md files.
- `frontend-design`, `shadcn`, `vercel-react-best-practices`, `web-design-guidelines`, `dataviz`, `codebase-design`, `claude-in-chrome`, `security-review`, `slides`: at the phases the plan lists.

## Next phase
Phase 1 "domain-core" (plan section Phase 1, FP Task 1) on branch `phase/01-domain-core`, after the user approves moving on.
