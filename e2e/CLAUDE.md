# e2e (Playwright)

Browser flows are the gate and the source of screenshot evidence.

## Commands

```
cd e2e && npx playwright test                       # all specs, no evidence promotion without EVIDENCE_PHASE
EVIDENCE_PHASE=phase-NN-<slug> npx playwright test specs/phase-NN-<slug>/
npm run typecheck
```

## Contract

- One folder per phase: `specs/phase-NN-<slug>/<flow>.spec.ts`. Slugs: `scripts/phases.json`.
- Screenshots only via `shot(page, testInfo, idx, step)` from `support/evidence.ts`: writes `test-evidence/${EVIDENCE_PHASE}/${flowSlug}/${pad2(idx)}-${step}.png`. `flowSlug` is the kebab-case `describe` title; indices are explicit; shots promote only when the test passes.
- Only the current phase writes evidence. `scripts/gate.sh` runs earlier phases with `EVIDENCE_PHASE=regression`, which must write nothing under `test-evidence/`.
- Every spec starts with `POST /demo/reset`. Config: `workers: 1`, `fullyParallel: false`, `retries: 1`.
- Tags: `@live` (real OpenAI; skipped without a key), `@gcp` (Cloud Run URL). Default runs use `LLM_PROVIDER=scripted`.
- New browser flows must pass twice in a row at the gate.
