# Sentinel for NovaPay: phased implementation plan (v2, final, post-audit)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans, task by task. Steps use `- [ ]`. Task 0.1 copies this file to `docs/superpowers/plans/2026-10-20-sentinel-implementation.md`, and progress is tracked there.

**Goal:** build the complete Sentinel PS-02 system in `docs/FINAL_PLAN.md` (P0 + P1 + P2) as 15 gated phases. A phase starts only after the previous one passes its gate: unit, integration, contract and E2E tests green, screenshots saved for each tested flow, a code review, and a merge.

**Spec:** `docs/FINAL_PLAN.md` is authoritative and is cited as "FP §n". The PS-02 brief is in `docs/hackathon_problem_statements_1.docx`. Where this plan adds a decision FP left open, it says so in the phase.

**Tech stack:**
- Backend and simulator: Python 3.12 uv workspace with FastAPI, `openai-agents` (pinned in Phase 0), numpy, scipy, pandas and pydantic v2.
- Frontend: Next.js 16, TypeScript, Tailwind and shadcn/ui.
- Tests: Playwright with axe-core.
- Local stack: Docker Compose with the Pub/Sub emulator and the BigQuery emulator.
- GCP (asia-south1): Cloud Run, Pub/Sub, BigQuery, Secret Manager, Cloud Scheduler and Cloud Monitoring, plus a Google Chat webhook.

---

## Context

The repo has only planning docs and the PS-02 CSV. FP merges two competing plans into one spec with P0/P1/P2 tiers and test lists for Tasks 1–13. There is no code yet, no CLAUDE.md, no test harness and no evidence structure. This plan:
- turns the spec into an executable sequence of gated phases;
- adds the scaffolding agents need (CLAUDE.md files, permissions, make targets, an evidence harness);
- fixes the gaps an independent audit found (see "Audit resolutions" at the end).

### Decisions taken with the user (2026-10-20)

- **Scope: P0 + P1 + P2, built in tier order.** P0 is frozen and tagged (Phase 8) before any P1 work starts.
- **GCP: local-only for now.** Everything runs and is tested locally, and the code is deploy-compatible from Phase 0.
  - **Phase 8b (conditional)** deploys the frozen P0 to Cloud Run as soon as GCP access exists. If access isn't ready, 8b is skipped with a note and its work joins Phase 12.
  - *Recommendation:* the user completes the manual GCP prerequisites (Phase 0, task 0.11) in parallel with the build. FP §12.4 marks deployment as never-cut, and the event is today.
- **Region and chat:** asia-south1, with a Google Chat incoming webhook.
- **E2E:** Playwright specs are the gate and write the screenshots. claude-in-chrome is used for exploratory visual QA and for GIF recordings of the hero flows.

### Repo facts (verified; do not re-derive)

**CSV (`data/ps02_system_telemetry.csv`)**
- 500 rows dated Aug 1–30 2026: 28 incidents and 50 CRITICAL rows (28 incident + 22 false).
- No row has value ≥ threshold, so B0 finds 0 true positives.
- Test split (Aug 21–30): 12 incidents and 9 false CRITICALs.
- Timestamps carry seconds. No service has two rows in the same minute.

**Calendar facts**
- 08-01 is a salary day, and it is also the date of the hero cascade:
  - AuthService `connection_pool` 10:38;
  - PaymentGateway `connection_pool` 10:59, **21 min later**.
- No false CRITICAL falls on Aug 1–3.
- False CRITICALs fall on 08-14 (Independence Day): 03:18 AnalyticsDashboard and 19:49 AuthService.
- 08-22 20:25 PaymentGateway `connection_pool` is a false CRITICAL in the test split.

**Missing files and tooling**
- `analysis/`, `docs/EDA_REPORT.md` and `docs/DATA_DESCRIPTION.md`, which FP cites, **do not exist**.
- System python is 3.9 (uv installs 3.12). Node is 26, and Docker, uv and gh are present. **gcloud and bq are not installed.**
- `.env.example` holds `OPEN_AI_KEY`, but the SDK reads `OPENAI_API_KEY`. Phase 0 renames it, and the user renames their local `.env` too.
- The remote is a shared GitHub repo (`Huzyefah/3RL`).

---

## Plan-level decisions (each fixes a gap or conflict in FP)

| # | Decision | Why |
|---|---|---|
| D1 | Root `data/` holds only the given CSV. All authored YAML, JSON and embeddings live in `backend/data/`. Docker build context is the repo root. | FP §5 and §11 disagree on where the files live. |
| D2 | The browser only talks to `sentinel-web`. A streaming Route Handler `app/api/[...path]/route.ts` proxies to `sentinel-api` with:<br>• `dynamic='force-dynamic'` and `runtime='nodejs'`<br>• `compress:false` in `next.config.ts`<br>• `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no`<br>• the request `signal` forwarded<br>• Last-Event-ID resume<br>On Cloud Run, the web service account mints an ID token for the private API, and both services use `--timeout=3600`. **Do not create `proxy.ts`**, which is Next 16's renamed middleware. | Same-origin SSE (FP §1.3 S4). |
| D3 | **B0 and B1 evaluate only the 7 PS-02 metric series.** Segment rate metrics feed S1 and above only. | At 03:00, one bad transaction out of 20 gives u ≈ 1.67, so segment metrics would break sanity gates 1 and 2. |
| D4 | **Timer clocks** are set by the timer table below. During replay, the replayer drops to 1× ("agent-paced replay") while any incident is between Planning and AwaitingApproval, then resumes. | At 60×, a 10 s LLM call would otherwise consume 10 event-minutes. |
| D5 | **Grouping:** a candidate attaches to an *open* incident on the same or a dependency-linked service with no time window. Otherwise it merges with candidates on linked services within 10 min of the most recent one. A 15-min cooldown follows close. | Makes the 21-minute 08-01 cascade group (FP §6, §13 Task 4). |
| D6 | **08-16 SearchAPI → UserProfileService is not grouped.** FP §3.1 has no edge between them, so it stays two incidents. This is recorded in `ps02_episode_map.yaml` and the data card. | Don't bend the topology to fit. |
| D7 | **The ps02 dataset is complete and frozen at P0.** Phase 2 generates the precursor shapes for every anchor-mappable code (RC-BANK, RC-DBPOOL, RC-OTP-PROVIDER, RC-QUEUE, RC-AUTH-ATTACK, RC-MEMLEAK, RC-ABRUPT) and all negatives N1–N6. RC-CERT has flat metrics, so it can't produce a CRITICAL anchor; it lives in seeded mode and sim chaos. P1 adds agent and action behaviour, not ps02 data. | Keeps the P0 scorecard stable. |
| D8 | **Calendar fitted to the anchors, and disclosed:** Azadi (Independence Day) sale on 08-14 from 17:00 to 23:00, and a weekend cashback campaign on 08-22 from 19:00 to 23:00. The demo N1 beat (FP 13b) uses **2026-08-22T20:25 PaymentGateway `connection_pool`**. The data card states that these calendar entries were authored to explain anchors. | August 2026 has no Aug 1–3 false alarm and no Eid. |
| D9 | **Incident IDs:**<br>• PS-02 ground-truth incidents: `INC-0001…INC-0028`, in chronological order.<br>• PS-02 false alarms: `FA-0001…FA-0022`.<br>• Runtime incidents: `INC-YYYY-MMDD-NNN` (event-clock date).<br>• Seeded episodes: `S{seed}-E{n}`. | FP uses two schemes. |
| D10 | **Google Chat card:** buttons are `openLink` to `/incidents/{id}`, and approval happens in the web UI. | Incoming webhooks can't carry interactive Approve buttons. |
| D11 | **The FakeLLM and the scripted LLM are SDK `Model` implementations** (`FakeModel`, `ScriptedModel`), supplied through `ModelProvider` in `RunConfig`. They emit real function-call items, so the SDK's tool loop runs exactly as in production. | Tests then cover the real orchestration, not a parallel port. |
| D12 | **RCA quality is P0:**<br>• top-1/top-3 code accuracy, root-service accuracy, groundedness % and Skeptic-induced misses are reported in Phase 8;<br>• the LLM judge and routing accuracy are P1. | FP §2 lists RCA quality as P0. |
| D13 | **Merging a phase PR into the shared `main` is outward-facing.** The gate opens the PR with `gh pr create`. Merging needs the user's go-ahead, unless they grant standing approval at the start of execution. | — |
| D15 | **OpenAI models only for every LLM use** (user instruction, 2026-10-20). No Vertex AI or Gemini. The fallback chain is OpenAI → deterministic template. The RCA judge is an OpenAI model of a different generation than the generators (`OPENAI_JUDGE_MODEL`), which replaces FP's "different model family" judge. This overrides FP §4.1, §7.2 I7 and §9 where they name Vertex Gemini. | User instruction. |
| D14 | **The user approves each phase transition.** After every phase gate (protocol step 8), ask whether to continue to the next phase, and wait for the answer. Instruction given by the user on 2026-10-20. | Keeps the user in control of a long build. |

### Timer table (enforced through `Clock`; test `test_timer_clock_assignment`)

| Timer | Clock | Value |
|---|---|---|
| Holt warm-up, rising streak, z windows, binomial window, corroboration window, grouping window, cooldown | Event | 10 min, 5 min, —, 5 min, 5 min, 10 min, 15 min |
| `schedule_recheck` | Event (replay is agent-paced, D4) | 3 min, at most 2 |
| Approval expiry | Wall | 10 min |
| Containment TTL | Wall | 15 min (throttle), 30 min (MFA) |
| Post-action verification | Wall | +60 s (sim time is scaled by `SIM_SPEED`) |
| Circuit breaker; page limit | Wall | 5 per hour; 6 per team per hour |
| Feedback half-life | Wall | 24 h |
| UI ETA countdown | Event clock, rendered at the current replay speed | — |

### Risk features (FP §6 leaves these undefined)

The risk score is `σ(−3 + 1.5·pred + 1.0·eta_term + 1.0·z_term + 0.6·corrob + 1.2·band + 1.3·binom)`, where:
- `pred` ∈ {0, 1}: the Holt predictive trigger fired.
- `eta_term = clip(1 − eta_min/120, 0, 1)`, or 0 when there is no ETA.
- `z_term = clip((z − 2)/2, 0, 1)`.
- `corrob` ∈ [0, 1].
- `band = 1[u ≥ 0.95]`.
- `binom = 1[binomial alarm]`.

All detector parameters are defined **per minute** and converted with `per_tick(param, tick_seconds)`. For example, `α_tick = 1 − (1 − α)^(tick_s/60)`, and window lengths are expressed in ticks. Replay uses `tick_seconds=60` and the sim uses 5.

---

## Skills: where each is used

**Skills are chosen by the user (2026-10-20) and must be used as listed.** Sub-agent building stays the priority: the lead orchestrates, and implementer sub-agents (one per task, in parallel where independent) do the work, each told which skills to invoke.

| Skill | Phase(s) | Use |
|---|---|---|
| writing-plans | 0 | Plan copied to `docs/superpowers/plans/`; task format for any sub-plan |
| writing-for-agents | 0, plus any phase that adds a directory | Authoring every CLAUDE.md |
| research | 0 | `docs/research/model-ids.md` and `docs/research/sdk-versions.md` (see 0.1) |
| fewer-permission-prompts, update-config | 0 | `.claude/settings.json` allowlist |
| using-git-worktrees, finishing-a-development-branch | Every phase | One branch `phase/NN-slug` per phase |
| subagent-driven-development | Every phase | One implementer subagent per task, each followed by a review |
| dispatching-parallel-agents | 3, 4, 5, 7, 9, 10, 11 | Independent tasks inside a phase (listed per phase). Each merges into the phase branch only when green, in FP §12.3 order. |
| test-driven-development | Every task, inside each implementer sub-agent | Red, green, commit, using FP §13's named tests |
| systematic-debugging | Any red test or failed gate | Find the root cause before fixing |
| verification-before-completion | Every gate | Read the actual output before claiming green |
| requesting-code-review, code-review, receiving-code-review | Every gate | Standards and spec review of the phase diff |
| codebase-design | 1, 4 | Port seams: `Bus`, `Store`, `Clock`, `DataSource`, `Embedder`, `Executor`, SDK `ModelProvider` |
| frontend-design, shadcn | 3, 7, 9-11 | Visual direction, components and tokens |
| vercel-react-best-practices | 3, 7+ | Server/client split, the SSE hook, avoiding request waterfalls |
| web-design-guidelines | 7 gate | UI audit (status colour always comes with an icon and a text label, FP §10) |

Additional skills the user confirmed (2026-10-20), used at the phases shown:

| Skill | Phase(s) | Use |
|---|---|---|
| dataviz | 2, 3, 5 | Evidence plots |
| claude-in-chrome | 7, 12 | Exploratory QA, GIFs and GCP console screenshots |
| security-review | 8b or 12 (once, on the deployed surface), and before enabling AUTO security in 9 | Public surface and IAM |
| slides | 13 | The 7-minute deck from FP §14 |

Only the skills the user flagged as irrelevant and time-consuming stay out: run, simplify, create-pr-description (use a plain `gh pr create` body), ui-styling, ui-ux-pro-max, motion-framer, deploy-to-vercel, vercel-cli, claude-api and the 3D and animation skills.

---

## Target repository layout

```
CLAUDE.md  Makefile  pyproject.toml (uv workspace)  .nvmrc (26)  .env.example
.claude/settings.json  .github/workflows/ci.yml  docker-compose.yml
analysis/        CLAUDE.md  eda.py (standalone, no sentinel import)  outputs/rule_baselines.csv
data/ps02_system_telemetry.csv
backend/
  CLAUDE.md  Dockerfile  pyproject.toml
  data/      services.yaml calendar.yaml policies.yaml allowlists.yaml ps02_episode_map.yaml
             tau.json scorecard.json corpus_embeddings.npz runbooks/RC-*.md
  prompts/   commander.md investigator.md skeptic.md log_analyst.md security.md followup.md
  sentinel/  config.py schemas.py ids.py topology.py bus.py redact.py clock.py store.py scheduler.py pipeline.py
             datagen/ detect/ agents/ memory/ actions/ impact/ eval/ connectors/ api/
  tests/     unit/ integration/ e2e_http/ live/ gcp/ fixtures/{candidates,scripted_llm,golden}/
sim/
  CLAUDE.md  Dockerfile  pyproject.toml
  finpay_sim/  model.py (pure SimModel.step) banks.py otp.py auth.py traffic.py chaos.py admin.py emitter.py app.py
  tests/
frontend/
  CLAUDE.md  Dockerfile  package.json  next.config.ts
  app/  page.tsx  incidents/[id]/  scorecard/  demo/  security/  data/  analytics/  platform/  api/[...path]/route.ts
  components/  lib/{api.ts, sse.ts, types.gen.ts, data-mode.ts}  fixtures/*.json  tests/ (vitest)
e2e/
  CLAUDE.md  package.json  playwright.config.ts (workers:1, fullyParallel:false, retries:1)
  support/{evidence.ts, stack.ts, axe.ts, api.ts}  specs/phase-NN-<slug>/<flow>.spec.ts
functions/connector-webhook/   (Phase 11)
infra/  CLAUDE.md  bootstrap.sh  deploy.sh  iam.sh  scheduler.sh  bq_schema.sql   (DRY_RUN=1 supported)
scripts/  gate.sh  evidence_index.py  render_json.py  plot_*.py
test-evidence/  README.md  phase-NN-<slug>/{REPORT.md, <flow-slug>/NN-<step>.png, reports/}
docs/  FINAL_PLAN.md  superpowers/plans/…  research/  ARCHITECTURE.md  DATA_CARD.md  DATA_DESCRIPTION.md  demo/  slides/
```

**Phase slugs** (used in branch names, evidence folders and spec folders, and enforced by `evidence_index.py`):

| Phase | Slug |
|---|---|
| 00 | `foundation` |
| 01 | `domain-core` |
| 02 | `datagen` |
| 03 | `detection` |
| 04 | `agents` |
| 05 | `actions-sim` |
| 06 | `api-pipeline` |
| 07 | `frontend-p0` |
| 08 | `p0-freeze` |
| 08b | `p0-cloudrun` |
| 09 | `p1-autonomy-logs` |
| 10 | `p1-breadth` |
| 11 | `p2` |
| 12 | `gcp` |
| 13 | `submission` |

---

## Test and evidence conventions (apply to every phase)

### Test layers

| Layer | Tool and location | When it runs |
|---|---|---|
| Unit | `pytest -m unit` (no network; enforced by `pytest-socket`); `vitest` | Every commit |
| Integration | `pytest -m integration`: in-process API (`httpx.ASGITransport`), in-process sim, the real runtime on `ScriptedModel` | Every gate |
| HTTP E2E | `pytest -m e2e_http`: real uvicorn processes on free ports, talking over sockets | From Phase 5 |
| Contract | OpenAPI snapshot; `openapi-typescript` drift check on `types.gen.ts`; sim output validated against `schemas.CES` | From Phase 6 |
| Eval gates | pytest. Sanity gates 1 and 2 (FP §9) are tests with **literal** expected numbers. | From Phase 2 |
| Browser E2E | Playwright `e2e/specs/phase-NN-<slug>/` | Phase 0, then from Phase 3 |
| Accessibility | `@axe-core/playwright`: no serious or critical violations | From Phase 7 |
| Live | `pytest -m live` and Playwright `@live`: real OpenAI. Reported as *skipped*, never as passed, when there is no key. | 4, 8, 12 |
| GCP | `pytest -m gcp` and Playwright `@gcp` | 8b, 12 |

### LLM modes (`LLM_PROVIDER`)

- `openai`: real calls.
- `scripted`: `ScriptedModel` replays fixture responses keyed by incident fingerprint. Used for integration, E2E and CI.
- `fake`: unit tests only.

When `scripted` is active, the UI shows a persistent **"LLM: scripted (test)"** badge, so no screenshot can pass for live reasoning. Every hero flow also has an `@live` variant.

### Demo and test control routes (needed for deterministic E2E)

These routes are enabled when `DEMO_CONTROLS=1`. On Cloud Run they need the `X-Demo-Passcode` header.
- `POST /demo/reset`: clears stores and the detector state, and calls the sim's `/chaos/reset`.
- `POST /demo/llm {mode: "normal" | "broken"}`: injects LLM faults for the FP 13d fallback flow without restarting the API.
- `SIM_SPEED`: a simulated-time multiplier, so that "recovers within 60 s" takes about 6 s of wall time at 10×.

### Screenshot evidence

`e2e/support/evidence.ts` exports `shot(page, testInfo, idx: number, step: string)`. It writes `test-evidence/${EVIDENCE_PHASE}/${flowSlug}/${pad2(idx)}-${step}.png`.
- `flowSlug` is the kebab-case title of the spec's `describe`.
- Step indices are explicit (never auto-incremented), so retries overwrite rather than duplicate.
- Shots are written to a temp folder and promoted only when the test passes, so a flaky first attempt leaves no partial evidence.

Further rules:
- Playwright runs with `workers: 1` and `fullyParallel: false`. Each spec starts with `POST /demo/reset`.
- **Only the current phase writes evidence** (`EVIDENCE_PHASE=phase-NN-<slug>`). Earlier phases' specs run as regression into the gitignored `test-results/`. **Earlier evidence folders are read-only.**
- **Backend phases (1, 2, 5, 6):** evidence comes from three sources:
  - dataviz PNGs from `scripts/plot_*.py`;
  - `scripts/render_json.py`, which renders JSON (traces, RCAs, guard verdicts) to a small HTML page that a Playwright `report` spec screenshots;
  - a screenshot of the `pytest --html` report.
  
  From Phase 3 on, the **UI shell in fixtures mode** (`DATA_MODE=fixtures`, reading `frontend/fixtures/*.json` that backend phases export) gives backend outputs a real UI rendering.
- **GIFs** from claude-in-chrome go to `<flow>/recording.gif` for the hero flows.
- PNGs, GIFs, REPORT.md and small JSON/XML reports are committed. Traces, videos and HTML reports are gitignored.

### Phase gate protocol (`make gate PHASE=NN`, implemented in `scripts/gate.sh`)

1. **Static checks:** ruff check, ruff format --check and pyright (backend, sim); eslint and `tsc --noEmit` (frontend, e2e).
2. **Full regression:** every unit, integration and HTTP E2E test from all phases so far, plus all earlier Playwright specs (they don't write evidence).
3. **Current-phase specs:** run the current phase's Playwright and report specs, which do write evidence. Every new browser flow must pass **twice in a row** (flake check).
4. **Evidence check:** `scripts/evidence_index.py phase-NN-<slug>` checks that every flow in the phase's "Evidence flows" list has at least one PNG, then writes a table into REPORT.md.
5. **Verify:** follow verification-before-completion. Any red result goes to systematic-debugging; a test is never skipped or weakened.
6. **Review:** run the code-review skill through one reviewer sub-agent on `git diff main...phase/NN-<slug>` (standards, plus spec against this plan and FP). Apply the fixes, then re-run steps 1–4.
7. **Close out:**
   - Fill in REPORT.md and commit.
   - Push, then run `gh pr create` with a short body (summary, evidence folder link, REPORT.md).
   - Merge after the user's go-ahead (D13) and tag `phase-NN`.
8. **Checkpoint with the user (mandatory, every phase):** stop after close-out. Report the gate result, the evidence folder, any skipped or deferred items, and the PR link. Then ask the user whether to continue to the next phase. **Do not start the next phase, create its branch or touch its files until the user says yes.** The user may also ask for changes to the finished phase first. This applies to Phase 8b and the conditional phases too. If 8b is skipped for lack of GCP access, say so at the Phase 8 checkpoint and ask how to proceed.

**Time limits.** Each phase has an indicative time limit, listed with the phase. If a phase overruns its limit by more than 50%, stop and apply FP §12.4's cut order to that phase's scope. Record the cut in REPORT.md under "Skipped / deferred".

### REPORT.md template

```
# Phase NN (<slug>): gate record
Commit: <sha> · Date: <iso> · Branch: phase/NN-<slug> · Tag: phase-NN · PR: <url>
## Commands run (verbatim) and results  | Command | pass / fail / skip |
## Evidence flows                        | Flow | Screenshots | What it proves |
## Exit criteria                         - [x] … (copied from this plan)
## Interface changes since last freeze   (schemas snapshot diffs, with reasons)
## Skipped / deferred (with reason)
## Review findings and resolutions
```

---

## Phase 0: foundation (workspace, agent guides, toolchain, evidence harness) · about 45 min

- [ ] **0.1** Copy this plan to `docs/superpowers/plans/2026-10-20-sentinel-implementation.md`. Dispatch one research sub-agent (web, primary sources) to produce:
  - `docs/research/model-ids.md`, covering:
    - OpenAI fast, smart and embedding IDs as of today;
    - (Vertex/Gemini research was done but is no longer used, see D15);
    - whether BQML `AI.DETECT_ANOMALIES` and `ARIMA_PLUS` are available in asia-south1.
  - `docs/research/sdk-versions.md`, covering:
    - the `openai-agents` version on PyPI today: `Agent.as_tool`, `output_type`, `AgentOutputSchema(strict_json_schema=False)`, `ModelProvider`/`Model`, `RunHooks`, `MaxTurnsExceeded`, and how to disable tracing;
    - Next.js 16 breaking changes (from `frontend/node_modules/next/dist/docs/` after install), including the `middleware` → `proxy.ts` rename and Route Handler streaming;
    - whether the Pub/Sub emulator supports push subscriptions;
    - the `goccy/bigquery-emulator` feature limits.
- [ ] **0.2** Set up the uv workspace:
  - a root `pyproject.toml` with workspace members `backend` and `sim`;
  - `uv python pin 3.12`;
  - dev dependencies: pytest, pytest-asyncio, pytest-html, pytest-cov, pytest-socket, hypothesis, ruff, pyright and httpx;
  - package stubs with one trivial test each.
- [ ] **0.3** Create the frontend:
  - run `npx create-next-app@<pinned> frontend` (TypeScript, App Router, Tailwind, ESLint), then `shadcn init`;
  - add vitest and testing-library;
  - add a placeholder `/` page;
  - add the D2 proxy Route Handler stub;
  - pin Node with `.nvmrc` 26, `engines >=20.9`, and the `node:26-slim` base image.
- [ ] **0.4** Create the `e2e/` workspace:
  - Playwright and axe;
  - `support/evidence.ts`, implementing the promotion-on-pass and explicit-index rules;
  - `specs/phase-00-foundation/{harness,report}.spec.ts`.
- [ ] **0.5** Write `analysis/eda.py` as a standalone script that does not import `sentinel`. It writes:
  - `analysis/outputs/rule_baselines.csv`;
  - `docs/DATA_DESCRIPTION.md` (columns, counts, splits, and the calendar facts listed above).

  The test pins the literal values: B0 TP 0 / FP 0; B1 TP 28 / FP 22 / precision 0.56; test split 12 incidents and 9 false CRITICALs.
- [ ] **0.6** Write Dockerfiles for backend, sim and frontend:
  - multi-stage, non-root, honouring `PORT`, clean shutdown on SIGTERM, and able to run with a read-only root filesystem;
  - plus a `docker-compose.yml` skeleton.
- [ ] **0.7** Add the build tooling:
  - `Makefile` targets: `setup`, `dev`, `test`, `e2e`, `gate`, `types`, `evidence`, `compose-up`, `compose-down`, `eval`, `deploy`;
  - `scripts/gate.sh`, `scripts/evidence_index.py`, `scripts/render_json.py`;
  - `test-evidence/README.md`;
  - `.github/workflows/ci.yml`: lint, types, unit, integration, and Playwright with `LLM_PROVIDER=scripted`.
- [ ] **0.8** Rewrite `.env.example` so every variable is documented and no secret is included:
  - LLM: `OPENAI_API_KEY`, `OPENAI_{FAST,SMART,EMBED}_MODEL`, `OPENAI_JUDGE_MODEL`, `LLM_PROVIDER`;
  - GCP: `GCP_PROJECT`, `GCP_REGION=asia-south1`;
  - infrastructure: `BUS=memory|pubsub`, `STORE=memory|bigquery`, `CHAT_WEBHOOK_URL`;
  - policy and demo: `SECURITY_AUTONOMY=shadow`, `KILL_SWITCH=0`, `DEMO_CONTROLS`, `DEMO_PASSCODE`;
  - sim: `SIM_BASE_URL`, `SIM_ADMIN_TOKEN`, `SIM_SPEED`, `EMIT_MODE`;
  - wiring and tests: `API_INTERNAL_URL`, `EVIDENCE_PHASE`, `EVAL_MAX_USD`, `PUBSUB_VERIFY_OIDC`.
  
  Also extend `.gitignore`.
- [ ] **0.9** Write the **CLAUDE.md files** with the writing-for-agents skill, using one sub-agent. Each has commands first, uses pointers instead of duplicating content, and stays under about 150 lines.
  - **`/CLAUDE.md`** covers:
    - the 3-line product summary;
    - that FP is authoritative and this plan sets the execution order;
    - the gate protocol, make targets, phase slugs, and a map of the sub-guides.
    
    **Hard rules:**
    1. Never type a scorecard number by hand; only `run_eval.py` produces them.
    2. Model IDs live only in env vars. OpenAI models only (D15): no Vertex or Gemini calls anywhere.
    3. No PII in prompts (the test pins the `03\d{9}` pattern).
    4. Test-split incidents never enter memory during evaluation, and `recall_similar` never returns the future or the incident itself.
    5. The scripted LLM is test-only and always shows its badge.
    6. Evidence is written only via `shot()`, and earlier phases' evidence folders are read-only.
    7. Never call system `python3`; always `uv run`.
    8. Never rename or weaken an FP §13 test or its acceptance numbers.
    9. Never hard-code the time-of-day finding (FP §5).
    10. SDK guardrails trip; they do not regenerate. Regeneration lives in `runtime.py`.
    11. LLM calls happen only on grouped candidates and log-novelty batches.
    12. Changing `schemas.py` after Phase 1 requires a snapshot update and a note in REPORT.md.
    13. Unit tests make no network calls.
    14. Commit at least every 30 min.
    15. Merging to `main` needs the user's go-ahead.
  - **`backend/CLAUDE.md`**: uv commands, pytest markers, the package map, the u formula, the evidence_id regex `^[a-z_]+:[0-9a-f]{8}$`, D3/D4/D5/D11, the timer table, the risk features, where I1–I8 live (one test each), and that `policy_guard.py` needs a test per rule.
  - **`frontend/CLAUDE.md`**: read `node_modules/next/dist/docs/` first; the D2 proxy rules (no `proxy.ts`); `DATA_MODE=fixtures|live`; status colour always paired with an icon and text; `make types`; the scripted badge.
  - **`sim/CLAUDE.md`**: the pure `SimModel.step(dt, rng)` versus the async loop, `SIM_SPEED`, chaos and admin endpoints, the admin token, and the CES contract.
  - **`e2e/CLAUDE.md`**: folder per phase, the `shot()` contract, `EVIDENCE_PHASE`, reset at the start of every spec, the `@live` and `@gcp` tags, and serial runs.
  - **`infra/CLAUDE.md`** and **`analysis/CLAUDE.md`**: short.
- [ ] **0.10** Write `.claude/settings.json` with an allowlist for uv, pytest, ruff, pyright, npm, npx playwright, docker compose, make and gh pr.
- [ ] **0.11 (manual, by the user, in parallel with the build)**: install the gcloud SDK, run `gcloud auth login` and `gcloud auth application-default login`, create the project with billing, and set `GCP_PROJECT`. Nothing blocks on this until Phase 8b.

**Exit criteria:** `make setup && make gate PHASE=00` is green; CI is green on the PR; all three images build and start under compose.

**Evidence flows:** `harness-smoke`, `pytest-report`, `eda-facts`.

---

## Phase 1: domain core (FP Task 1) · about 30 min

**Files:**
- `backend/sentinel/{config,schemas,ids,topology,bus,redact,clock,store,scheduler}.py`
- `backend/data/{services,calendar,policies,allowlists}.yaml` (`policies.yaml` follows `docs/foresight_blueprint.md` §8.3 plus FP §8.3's edits; `calendar.yaml` includes the D8 entries)
- `backend/data/runbooks/RC-*.md`

**Interfaces** (frozen at this gate):
- `schemas.py`: `CES`, `MetricPoint`, `LogRecord`, `ChangeEvent`, `Candidate`, `IncidentCandidate`, `Hypothesis`, `RCA` (FP §7.5, using typed sub-models for `actions[].params`, `comms_draft` and `impact` so the output schema stays strict), `ActionRequest`, `ActionRecord`, `GuardVerdict`, `TraceStep`, `IncidentResult`, `ScorecardRow`, `Approval`, `PolicyState`.
- `ids.py`: the D9 ID schemes, plus `evidence_id(kind, payload)`.
- `utilisation(value, threshold, direction)` and `band(u)`.
- `Topology` with `dependants`, `upstream`, `linked`, `blast_radius` and `owner`.
- `Bus` (`InMemoryBus`, bounded, with backpressure).
- `Clock` (`WallClock`, `EventClock`, `FrozenClock`; each timer declares which clock it uses).
- `Store` (`MemoryStore`).
- `Scheduler`: a Clock-driven, in-process scheduler for rechecks, TTLs, expiry and verification. It calls the same handler as `/jobs/tick`.
- `redact()`.

**Tests:**
- the FP §13 Task 1 list;
- `test_band_edges`;
- `test_event_clock_monotonic`;
- `test_timer_clock_assignment`;
- `test_scheduler_fires_in_event_time`;
- `test_policies_yaml_schema_valid`;
- `test_services_yaml_maps_all_8_csv_services`;
- `test_schema_snapshot`, against `tests/fixtures/schema_snapshot.json`.

**Evidence flows:** `pytest-report`, `topology-graph` (the dependency graph with segments and owners).

---

## Phase 2: generator in `ps02` mode, corpus, replay, CSV bench (FP Task 2 P0 + D7) · about 60 min

**Files:**
- `backend/sentinel/datagen/{calendar,episodes,generator,corpus,exporters,replay}.py`
- `backend/data/ps02_episode_map.yaml`
- `backend/sentinel/eval/{splits,csv_bench}.py`
- `scripts/plot_episodes.py`

**Interfaces:**
- `build(mode, seed, window) -> Dataset(metrics, logs, events, ground_truth)`
- `corpus(split, include_test=False) -> list[MemoryDoc]`
- `Replayer(ds, bus, clock, speed).run(window | episode_id)`, which supports agent pacing (D4)
- `csv_bench(path) -> list[ScorecardRow]`
- the split constants

**Episode map rule** (seeded and committed):
1. A seeded draw marks 20% of incidents as RC-ABRUPT.
2. Otherwise, service-specific rules come first:
   - PaymentGateway → RC-BANK, except `connection_pool` → RC-DBPOOL;
   - NotificationHub → RC-OTP-PROVIDER, except `connection_pool` → RC-DBPOOL;
   - AuthService `error_rate` → RC-AUTH-ATTACK.
3. Then metric-based rules: `connection_pool` → RC-DBPOOL, `queue_depth` → RC-QUEUE, `memory_usage` → RC-MEMLEAK, and everything else → the closest shape, chosen by the rule table in the YAML.

Further rules:
- The 22 false CRITICALs map to N1–N6. They include the D8 N1 anchors and at least 3 N6 (unexplained).
- The 08-01 pair is a cascade. 08-16 is not (D6).
- Anchors are floored to the minute, keeping `attributes.anchor_ts`.

**Tests:**
- the FP §13 Task 2 P0 list;
- `test_csv_bench_matches_eda` (literal values);
- `test_b0_b1_ignore_segment_metrics` (D3);
- `test_episode_map_covers_all_50_critical_rows`;
- `test_rc_cert_not_anchor_mapped`;
- `test_anchor_floor_keeps_original_ts`;
- `test_replay_by_episode_id`;
- `test_replay_agent_paced`;
- `test_n1_anchor_2026_08_22_on_calendar`.

**Exit criteria:** sanity gate 1 is green, and the Aug 1–30 dataset builds in under 60 s.

**Evidence flows:**
- `anchors-preserved` (dense u-series with all 500 anchors and band shading);
- `episode-gallery` (one plot per RC code and per N1–N6);
- `csv-bench`;
- `pytest-report`.

---

## Phase 3: detection, grouping, scorer, ablation, UI shell (FP Tasks 3, 4, 9) · about 75 min

**Parallel tasks:**
- **3A:** detector primitives and the engine.
- **3B:** scorer and ablation. It depends on 3A's `Candidate` output, which is already frozen in the schemas.
- **3C:** UI shell in fixtures mode (frontend-design, shadcn):
  - tokens, light and dark mode, and the app shell;
  - Live Ops (service grid, bank heat-strip, ETA list) and Incident (header, hypotheses, trace timeline);
  - both read `frontend/fixtures/*.json`;
  - `make fixtures` exports fixtures from backend runs.

**Files:**
- `backend/sentinel/detect/{holt,ewma,binom,corroborate,risk,grouping,engine}.py`
- `backend/sentinel/eval/{scorer,ablation,run_eval,rca_eval}.py` (P0 part of `rca_eval`: top-1/top-3, root-service accuracy, groundedness, Skeptic-induced misses)
- `scripts/plot_eval.py`
- `frontend/app/{page.tsx, incidents/[id]/page.tsx}`, `frontend/components/*`, `frontend/lib/data-mode.ts`

**Interfaces:**
- `HoltState`, `EwmaZ`, `binom_alarm`, `corroboration`, `risk` (features as defined above), `per_tick`;
- `DetectorEngine(config ∈ {B0,B1,S1,S2}, tau, tick_seconds).process(event) -> list[Candidate]`;
- `Grouper(topology, clock).add(c) -> IncidentCandidate` (D5);
- `score(...)` with bootstrap CIs (seeded);
- `ablation(mode, split, configs)`.

**Tests:**
- the FP §13 Task 3, 4 and 9 lists;
- `test_eta_scales_with_tick_seconds` (a ramp sampled at 5 s and at 60 s gives ETAs within 10% of each other, and the warm-up, streak and window lengths are equal in minutes);
- `test_risk_feature_definitions`;
- `test_group_attaches_to_open_incident_beyond_10min` (the 21-min 08-01 case);
- `test_0816_pair_not_grouped`;
- `test_tau_tuned_on_train_only`;
- `test_bootstrap_ci_deterministic`;
- vitest for the heat-strip thresholds and the status badge (icon plus text).

**Exit criteria:** sanity gate 2 holds: B1 recall ≈ 1.0 and lead ≈ 0 on the ps02 test split. S1 and S2 show lead > 0 on the non-abrupt test incidents.

**Evidence flows:**
- `holt-eta`;
- `segment-hidden-in-aggregate`;
- `cascade-grouping-08-01`;
- `ablation-b0-s2` (table plus lead histogram);
- `ui-shell-live-ops` and `ui-shell-incident` (Playwright on fixtures exported from this phase's detector run);
- `pytest-report`.

---

## Phase 4: tools, memory, impact, agent runtime, grounding (FP Tasks 5, 6, 7) · about 90 min

**Parallel tasks:**
- **4A:** tools, memory and impact.
- **4B:** the model seam and a runtime skeleton.

**Sequential tasks:**
- **4C:** Commander, Investigator and Skeptic.
- **4D:** grounding and the regeneration loop.
- **4E:** fixtures export for the UI.

**Files:**
- `backend/sentinel/agents/{models,tools,specialists,commander,runtime,grounding,hooks}.py`
- `backend/sentinel/memory/store.py`
- `backend/sentinel/impact/business.py`
- `backend/prompts/{commander,investigator,skeptic}.md`
- `backend/tests/fixtures/{candidates,scripted_llm,golden}/`

**SDK seams (D11):**
- `FakeModel` and `ScriptedModel` implement the SDK `Model`, provided via `ModelProvider` in `RunConfig`.
- Specialists are wired with `Agent.as_tool()`.
- `RunHooks` and `AgentHooks` emit a `TraceStep` for every agent start or end, tool call and plan version, including nested specialist calls, and publish it to the bus as it happens.
- `RunContextWrapper[IncidentContext]` carries:
  - `skeptic_verdict` (I1 is enforced inside `request_action`);
  - the evidence registry (I5);
  - budgets (I8).
- `request_action` only records requests (I6).
- `MaxTurnsExceeded`, `asyncio.wait_for` (20 s per LLM call, 60 s per Commander cycle), 429/5xx errors and invalid JSON after one retry all go to the I7 fallback.
- Tracing export is disabled when no key is set.
- The Commander's `output_type` is `RCA` (strict), with a `strict_json_schema=False` fallback if the research in 0.1 shows it's needed.

**Memory:**
- `recall_similar` pre-filters by metadata, then returns the top 3 with similarity of at least `MIN_SIM[embedder]`.
- It **excludes** documents with `ts ≥ clock.now()`, the incident's own ID, and, during evaluation, the test split.
- Embeddings:
  - `OpenAIEmbedder` (computed once with `--live`, then committed to `backend/data/corpus_embeddings.npz`);
  - `TfidfEmbedder` (deterministic, with its own `MIN_SIM`), used when no key is present;
  - tests use the committed npz when it exists.

**Tests:**
- the FP §13 Task 5, 6 and 7 lists (I1–I8, re-plan, grounding);
- `test_scripted_model_drives_replan_08_01` (plan_versions == 2, root = AuthService, routed to Identity & Security);
- `test_0801_salary_day_not_benign` (I3 plus a Skeptic fixture: a cascade on a salary day is still CONFIRMED or DISPUTED);
- `test_recall_excludes_future_and_self`;
- `test_nested_tool_calls_in_trace`;
- `test_trace_streamed_before_rca_complete`;
- `test_token_and_cost_accounting`;
- `test_no_pii_in_prompts`;
- `test_rca_eval_top1_groundedness`.

**Live** (skipped without a key): `uv run python -m sentinel.agents.runtime --mode ps02 --episode INC-0001 --live` prints the RCA, the trace and the cost. It also writes `corpus_embeddings.npz`.

**Exit criteria:** FP Checkpoint 1 holds locally: a fixture incident runs from candidate → RCA → stub policy → ticket.

**Evidence flows:**
- `replan-trace-08-01` (the Incident page in fixtures mode, showing the real exported trace);
- `benign-suppression-n1`;
- `grounding-regenerate`;
- `fallback-rca-i7`;
- `live-rca` (if a key is present);
- `pytest-report`.

---

## Phase 5: Policy Guard, executors and `finpay-sim` (FP Tasks 8 P0 and 11) · about 75 min

**Parallel tasks:**
- **5A:** Policy Guard and executors.
- **5B:** the simulator.

**Sequential task:**
- **5C:** HTTP E2E: the executors against a real uvicorn sim.

**Files:**
- `backend/sentinel/actions/{policy_guard,executors,audit,verify}.py`
- `sim/finpay_sim/*`
- `scripts/plot_sim_recovery.py`

**Behaviour:**
- **P0 action rows** (FP §8.1): ticket, Chat card (D10, cardsV2 with `openLink`), page (at most 6 per team per hour), attach RCA, recheck, reroute_bank (HITL), otp_failover (HITL), and the DENY list.
- **HITL envelope** (FP §8.2):
  - an idempotency key, with a 409 on a second approval;
  - expiry after 10 min of wall time;
  - one-click revert;
  - an audit row;
  - **guard-run verification at +60 s:** if failures fall by less than 50%, or legitimate success drops below baseline − 1%, the action auto-reverts and pages a human.
- With no `CHAT_WEBHOOK_URL`, the Chat card is stored and shown in the UI.
- **Simulator:**
  - a pure `SimModel.step(dt, rng)` wrapped in an async loop that is scaled by `SIM_SPEED`;
  - `/pay`, `/login`, banks A–E, OTP providers P1 and P2, and traffic at 20–80 TPS;
  - chaos endpoints `{bank_c_slow, ledger_pool_leak, otp_p1_down, report_batch, reset}` (`cred_stuffing` comes in Phase 9);
  - admin endpoints `{routing, otp, throttle, workers}`, guarded by `SIM_ADMIN_TOKEN`;
  - the emitter sends every 5 s of simulated time, with `EMIT_MODE=http|pubsub`.

**Tests:**
- the FP §13 Task 8 P0 list and the Task 11 list;
- `test_every_policy_rule_has_a_test` (a meta-test that checks every `policies.yaml` key is referenced);
- `test_page_rate_limit_6_per_team_hour`;
- `test_hitl_verify_fail_auto_reverts_and_pages`;
- `test_revert_restores_previous_routing`;
- `test_sim_emits_valid_ces`;
- `test_admin_requires_token`;
- `e2e_http/test_reroute_over_http.py` (a real uvicorn sim at `SIM_SPEED=10`).

**Exit criteria:** under `bank_c_slow`, the executor-driven reroute restores success to at least 0.97 within 60 s of simulated time, and the DENY list is provably unreachable.

**Evidence flows:**
- `reroute-recovery` (success-rate curve);
- `otp-failover`;
- `hitl-verify-auto-revert`;
- `policy-matrix` (rendered guard verdicts for every action type);
- `pytest-report`.

---

## Phase 6: API, SSE, replayer and full local pipeline (FP Task 10) · about 60 min

**Files:**
- `backend/sentinel/api/{main,sse,deps,auth}.py`
- `backend/sentinel/api/routes/{ingest,events,incidents,approvals,actions,feedback,scorecard,demo,policy,jobs}.py`
- `backend/sentinel/pipeline.py`

**Routes:**
- All of FP §10, plus:
  - `GET /approvals` (pending, with expiry);
  - `GET /policy` → `{security_autonomy, kill_switch, tau, demo_controls}`;
  - `PUT /policy {security_autonomy?, kill_switch?}`;
  - `POST /demo/reset` and `POST /demo/llm`;
  - `GET /healthz`.
- Mutating `/demo/*`, `/actions/*` and `/policy` routes check `X-Demo-Passcode` when `DEMO_PASSCODE` is set.
- `/ingest/pubsub` verifies OIDC only when `PUBSUB_VERIFY_OIDC=1`, because the emulator sends none.
- `/jobs/tick` calls the same handler as the in-process `Scheduler`.

**SSE:**
- event types `metric|candidate|incident|trace|action|approval|policy|scorecard`;
- metric points throttled to 10 per second per service;
- a 15 s heartbeat and Last-Event-ID resume.

**Tests:**
- the FP §13 Task 10 list;
- `test_openapi_snapshot`;
- `test_pipeline_end_to_end_scripted_08_01`;
- `test_one_commander_run_per_incident_lock`;
- `test_replay_60x_rechecks_in_event_time`;
- `test_sse_resume_last_event_id`;
- `test_demo_routes_require_passcode_when_set`;
- `e2e_http/test_api_sim_sockets.py` (uvicorn API and sim: `bank_c_slow` → candidate with an ETA → approval → recovery → a verification TraceStep).

**Contract:** `make types` regenerates `frontend/lib/types.gen.ts`, and CI fails on drift.

**Exit criteria:** `make dev` runs the API and the sim, and `curl -N localhost:8080/events` streams during a replay.

**Evidence flows:**
- `sse-stream`;
- `pipeline-08-01-cascade`;
- `api-bank-c-loop` (a rendered event log from the HTTP E2E test);
- `openapi` (Swagger UI);
- `pytest-report`.

---

## Phase 7: frontend P0 on live data and local acceptance (FP Tasks 12, 13a–d) · about 90 min

**Sequential task:**
- **7A:** switch the shell to `DATA_MODE=live` (the SSE hook through the D2 proxy).

**Parallel tasks:**
- **7B:** Live Ops: the KPI strip, the PKR-at-risk ticker and the inline approvals inbox.
- **7C:** Incident: the technical/business toggle, evidence chips, the Skeptic panel, similar incidents, Approve/Reject, the comms draft, 👍/👎 and the live trace.
- **7D:** Scorecard: the ablation with CIs, the lead histogram, Skeptic on/off, RCA quality, PKR protected, cost, and the raw-CSV panel.
- **7E:** Demo control: replay, chaos buttons, the live success-rate chart, the kill switch, and shadow/enforce.

**Sequential task:**
- **7F:** the Playwright flows.

Every replay is labelled "synthetic replay".

**Tests:**
- vitest: the countdown, the SSE reconnect and the scripted badge;
- `npm run lint && npm run build`;
- axe on every P0 screen.

**E2E flows** (`LLM_PROVIDER=scripted`, each step is a `shot`):

| Flow slug | Steps |
|---|---|
| `live-ops-overview` | load → service grid → bank heat-strip → KPI strip |
| `ps02-cascade-replan` (13a) | start the 08-01 replay → candidate with ETA → incident page → plan v1 → Skeptic DISPUTED → plan v2 → routed to Identity & Security → "similar to INC-…" |
| `salary-surge-suppressed` (13b) | replay the 08-22 20:25 N1 anchor → Skeptic BENIGN citing the calendar → "FP avoided" goes up |
| `bank-c-reroute-recovery` (13c) | `bank_c_slow` → only BANK_C turns amber → ETA → Chat card recorded with a link → approve in the UI → success ≥ 0.97 → verification step in the trace |
| `fallback-no-key` (13d) | `POST /demo/llm broken` → `bank_c_slow` → fallback ticket marked `statistical-fallback` |
| `approval-idempotent-expiry` | approve twice → 409 shown; an expired approval is disabled (FrozenClock offset through the demo route) |
| `sse-latency` | an event reaches the UI within 2 s of a replay tick through the proxy; the incident page renders before the RCA completes |
| `scorecard` | ablation → histogram → raw-CSV panel showing 0/28 → 28/28 at 0.56 |
| `demo-controls` | kill switch → shadow/enforce → reset |
| `a11y` | axe results for each screen |

**Exploratory QA:**
- a claude-in-chrome pass at 1440 px and 390 px (console errors, layout);
- GIFs for `bank-c-reroute-recovery` and `ps02-cascade-replan`;
- fixes for anything the exploratory pass finds, made before the gate.

**Exit criteria:** every flow passes twice in a row; no console errors; axe is clean.

---

## Phase 8: containerised stack, live LLM, P0 freeze · about 60 min

- [ ] **8.1** Add the `PubSubBus` adapter and the full compose stack:
  - the Pub/Sub emulator and the BigQuery emulator;
  - `sentinel-api` (push endpoint, `STORE=bigquery` against the emulator to validate `bq_schema.sql` and `BigQueryStore`);
  - `finpay-sim` (`EMIT_MODE=pubsub`);
  - `sentinel-web`.

  If Phase 0 research found the emulator lacks push support, add a dev-only pull-to-push forwarder container, labelled as emulator-only. BigQuery subscriptions can't be emulated; they are covered in 8b/12.
- [ ] **8.2** Prove Cloud Run parity in compose:
  - read-only root filesystem, `PORT` and SIGTERM handling;
  - a forced SSE connection drop at 300 s, after which the client reconnects;
  - a Pub/Sub redelivery test: duplicate deliveries create no duplicate incidents or actions.
- [ ] **8.3** Re-run all Phase 7 specs against compose.
- [ ] **8.4** Run the `@live` variants of 13a, 13b and 13c with real OpenAI:
  - tighten the prompts on exactly these episodes;
  - the 08-01 verdict must not be BENIGN;
  - record tokens and USD per incident.
- [ ] **8.5** Tune τ on Aug 1–20 only. Then run the final evaluation on Aug 21–30 for B0, B1, S1, S2, S3 and S3−Sk, with RCA top-1/top-3, groundedness and Skeptic-induced misses.
  - The S3 rows are live. Without a key they say "not run".
  - The run is capped by `EVAL_MAX_USD`, and the sample size is printed.
  - Commit `backend/data/scorecard.json` with the split constants in its header.
- [ ] **8.6** Run `infra/*.sh` with `DRY_RUN=1` plus shellcheck, then re-run the gate.
- [ ] **8.7** Tag **`v0.1.0-p0`**. This is the fallback demo build.

**Evidence flows:** `compose-stack`, `pubsub-redelivery-dedupe`, `sse-reconnect`, `live-cascade-replan`, `live-reroute`, `final-scorecard`, `cost-per-incident`.

**Exit criteria:** every item on FP §12.4's never-cut list is demonstrably present.

## Phase 8b (conditional on GCP access): P0 on Cloud Run · about 45 min

Run `infra/bootstrap.sh` and `infra/deploy.sh` for the P0 units only (FP §4.1 P0 rows):
- Pub/Sub topics plus push and BigQuery subscriptions;
- BigQuery tables, Secret Manager, least-privilege service accounts, and Artifact Registry;
- `sentinel-api` (min 1, max 1, CPU always allocated, `--timeout=3600`);
- `finpay-sim` and `sentinel-web`;
- `DEMO_PASSCODE` set.

Then run the 13a–d specs as `@gcp` against the `sentinel-web` URL, and run security-review on the public surface.

**Evidence flows:** `gcp-p0-services` (claude-in-chrome console shots, or rendered `gcloud … --format=json`), `gcp-13a`, `gcp-13c`, `gcp-13d`.

**If there is no GCP access:** record "skipped: no GCP access" in REPORT.md and fold all of this into Phase 12.

---

## Phase 9: P1-A, safe autonomy and LLM-based detection (FP §12.3 items 1–2) · about 75 min

**Parallel tasks:**

**9A: Security Sentinel and the throttle envelope**
- `cred_stuffing` chaos in the sim and the `login_failure_rate` path.
- `agents/security.py` and `prompts/security.md`.
- The full FP §8.2 envelope:
  - shadow and enforce modes;
  - a TTL sweeper driven by the `Scheduler` and `/jobs/tick`;
  - guard-run verification at +60 s with auto-rollback and a page;
  - a circuit breaker (5 per hour) and a kill switch;
  - an audit trail with a "Rollback now" button.
- A Security page with the auth-failure chart and TTL countdowns.
- security-review runs before `enforce` is allowed.

**9B: Log Analyst and RC-CERT**
- A template miner with novelty counts (more than 5× baseline, in 30 s batches).
- `agents/log_analyst.py`.
- An RC-CERT injection through sim chaos `cert_expiry`, with flat metrics. The Log Analyst raises its own candidate.

**Tests:**
- the FP Task 8 P1 list;
- `test_ttl_expires_without_agent`;
- `test_log_analyst_detects_cert_expiry_flat_metrics`;
- `test_template_novelty_threshold`.

**Evidence flows:** `cred-stuffing-shadow`, `cred-stuffing-enforce-ttl-rollback` (with GIF), `kill-switch-blocks-auto`, `cert-expiry-log-detection`.

## Phase 10: P1-B, data breadth, judge, feedback, scale, rollback, data card (FP §12.3 items 3–5) · about 90 min

**Parallel tasks:**

**10A: seeded mode**
- Episodes for every code.
- Confounders: 25% of incidents are deploy-caused, and 15% happen during a surge.
- A history corpus from seeds 0–9, embedded and committed.
- `test_b1_precision_calibrated` (in [0.50, 0.62] over 5 seeds × 7 days).
- Evaluation on seeds 100–129, live S3 sampled under `EVAL_MAX_USD`.
- Skeptic-induced misses on the surge-overlap episodes.

**10B: judge and fallback chain**
- The judge is an OpenAI model from a different generation than the generators (`OPENAI_JUDGE_MODEL`, default `gpt-5.5`), and the fallback chain is OpenAI → template (D15). A fake judge client is used in unit tests.
- `rca_eval` adds the judge mean and routing accuracy.
- Tested locally with a fake. Live judge scores are produced with the real key as soon as it is available, so no GCP dependency remains for this row.

**10C: feedback loop**
- 👍/👎 adjusts τ (+0.05 per 👎, capped at +0.15, with a 24 h half-life on the wall clock).

**10D: scale and rollback actions**
- `scale_service` (HITL): locally changes the sim's worker count; the `CloudRunScaler` adapter (max 5 instances) is tested with a mock.
- **rollback and restart** (HITL, simulated): allowed only when a change event happened within 30 min.

**10E: data card**
- `docs/DATA_CARD.md` and the `/data` page: what is real versus generated, the episode map, the per-mode counts, and the D6/D8 disclosures.

**Tests:**
- the tests named above;
- `test_rollback_requires_change_within_30min`;
- `test_feedback_tau_cap_and_decay`;
- `test_fallback_chain_order`.

**Evidence flows:** `seeded-calibration`, `scorecard-seeded-breadth`, `feedback-raises-tau`, `scale-action-approve`, `rollback-restart`, `data-card`, `fallback-chain-openai-template`.

## Phase 11: P2 extensions (FP §12.3 item 7) · about 90 min

**Parallel tasks:**
- **11A:** the Follow-up & Escalation agent, with a code-enforced SLA floor, and close-ticket (HITL, proposed after 15 min back in band).
- **11B:** step-up MFA (skipped when OTP is degraded; TTL 30 min).
- **11C:** the Analytics page (MTTD, MTTA, MTTR, pre-emptive ratio, department filter) and the Platform ops page (throughput, bus backlog, agent latency).
- **11D:** `functions/connector-webhook`, which turns Alertmanager and Datadog payloads into CES and publishes them to Pub/Sub. Tested with functions-framework.
- **11E:** a minute-of-week baseline behind a flag that is off by default, plus the BigQuery ML comparison row (`AI.DETECT_ANOMALIES` or `ARIMA_PLUS`, available only on GCP).

**Tests:**
- `test_sla_floor_always_escalates`;
- `test_close_ticket_after_15min_in_band`;
- `test_mfa_skipped_when_otp_degraded`;
- `test_webhook_{alertmanager,datadog}_to_ces`;
- `test_minute_of_week_flag_off_by_default`;
- the analytics metric definitions.

**Evidence flows:** `followup-escalation`, `close-ticket`, `step-up-mfa`, `analytics-page`, `platform-ops-page`, `webhook-connector`.

---

## Phase 12: GCP deployment of everything, and live acceptance · about 90 min

- [ ] **12.1** Complete the work from 8b if it was skipped. Then run `bootstrap.sh` and `deploy.sh` for the P1 and P2 units:
  - Cloud Scheduler `/jobs/tick` with OIDC;
  - the webhook Cloud Function (2nd gen);
  - the Cloud Monitoring connector (the sim's request count and latency, plus the Pub/Sub backlog);
  - the `CloudRunScaler` service account, scoped to `finpay-sim` only.
- [ ] **12.2** Switch on the live adapters:
  - `BigQueryStore` write-through;
  - the `VECTOR_SEARCH` memory backend;
  - the `CloudRunScaler`;
  - the live OpenAI judge;
  - the BigQuery ML row.

  The "pending GCP" scorecard rows are now filled by `run_eval.py`.
- [ ] **12.3** Run every browser flow from Phases 7 and 9–11 as `@gcp` against the Cloud Run URL. This includes FP 13a–d (13d with the key really revoked in Secret Manager) and SSE through the web proxy on Cloud Run.
- [ ] **12.4** Run security-review on the deployed surface (IAM, secrets, public routes, passcode).

**Evidence flows:** `gcp-services`, `gcp-ps02-cascade-replan`, `gcp-bank-c-reroute-recovery`, `gcp-fallback-key-revoked`, `gcp-cred-stuffing`, `gcp-scale-real`, `gcp-scorecard-final`.

## Phase 13: submission package and rehearsal · about 45 min

- README:
  - how to run locally, run with compose, and deploy;
  - the synthetic-data honesty note;
  - team names.
- `docs/ARCHITECTURE.md`, with Mermaid diagrams rendered to PNG by mermaid-cli.
- The final `docs/DATA_CARD.md`.
- Slides made with the **slides** skill, following FP §14. Every number comes from `scorecard.json`; `scripts/check_deck_numbers.py` diffs the deck against it.
- The Q&A sheet from FP §15.
- A backup recording, labelled as a recording.
- A final code review of `main`.

**Evidence flows:**
- `submission-checklist` (README, deck, and live URLs returning 200);
- `demo-rehearsal` (the full 7-minute script run on Cloud Run, or locally on compose if there is no GCP access, with one screenshot per FP §14 beat).

---

## Review focus (failure modes with a pinned test in the owning phase)

1. SSE stalls behind the proxy or Cloud Run buffering. Tests: `sse-latency` (Phase 7), `sse-reconnect` (Phase 8), and the Phase 12 `@gcp` run.
2. Timers run on the wrong clock during fast replay. Tests: `test_timer_clock_assignment` (Phase 1) and `test_replay_60x_rechecks_in_event_time` (Phase 6).
3. The Skeptic suppresses a real incident on a salary day. Tests: `test_0801_salary_day_not_benign` (Phase 4), the live check in Phase 8, and the confounder misses row in Phase 10.
4. Duplicate deliveries create duplicate incidents or actions. Tests: event_id dedupe (Phase 6), idempotency (Phase 5), and the redelivery test (Phase 8).
5. LLM latency freezes the UI. Tests: `test_trace_streamed_before_rca_complete` (Phase 4) and the `sse-latency` incident-page assertion (Phase 7).

## Audit resolutions (an independent subagent audited v1; every finding was addressed)

| Finding | Resolved by |
|---|---|
| GCP comes last with no time limits | 0.11 manual prerequisites; conditional Phase 8b; per-phase time limits with an overrun rule; compose parity, emulators and `DRY_RUN` in Phase 8 |
| B0/B1 break on segment metrics | D3 plus `test_b0_b1_ignore_segment_metrics` |
| E2E not executable (restart, state, retries) | `/demo/reset`, `/demo/llm`, serial workers, promotion of evidence on pass, explicit indices, `SIM_SPEED` |
| Event time collides with wall time | Timer table, D4 agent-paced replay, `Scheduler` |
| 08-01 cascade 21 min apart; 08-16 has no edge | D5 and D6, with tests |
| Episode map incomplete at P0 | D7 plus the map rule in Phase 2 |
| No salary-day false alarm | D8 calendar anchors, disclosed |
| RCA quality tier | D12; `rca_eval` P0 in Phase 3/4, reported in Phase 8 |
| Missing rollback/restart, page limit, HITL verification | Phase 5 and Phase 10D |
| Agents SDK specifics | D11 and Phase 4 SDK seams |
| No local driver for rechecks and TTLs | Clock-driven `Scheduler` (Phase 1) |
| UI arrives too late | UI shell in fixtures mode in Phase 3; Phase 4 renders real traces |
| Risk features and tick scaling undefined | Risk-feature definitions and `per_tick` |
| Memory leakage, self-match, hash embedder | Time and self exclusion; committed embeddings; TF-IDF fallback with its own cut-off |
| SSE proxy and Cloud Run details | D2 |
| Chat card can't approve | D10 |
| Minor: slug naming, PR flow, console shots, IDs, routes, circular gate, Node pin, eval cost, Vertex location, skills trim, CLAUDE.md rules | Phase slugs table; D13; claude-in-chrome or rendered gcloud JSON; D9; Phase 6 routes; standalone `eda.py` with literal values; `.nvmrc` and base image; `EVAL_MAX_USD`; research in 0.1; trimmed skills table; 15 hard rules |

## Verification (end to end)

- **Per phase:** `make gate PHASE=NN` runs the static checks, the full regression, the phase's E2E specs with screenshots, the evidence index and REPORT.md. Evidence lands in `test-evidence/phase-NN-<slug>/<flow>/`.
- **Local product:** run `make dev` and open `http://localhost:3000`, or run `make compose-up`.
- **P0 release:** the `v0.1.0-p0` tag; `make e2e-live` with an OpenAI key; `backend/data/scorecard.json` produced by `run_eval.py`.
- **Final:** the `@gcp` suite against the Cloud Run URLs (Phase 12), and the rehearsal evidence (Phase 13).
