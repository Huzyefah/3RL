# frontend (sentinel-web)

Next.js 16, TypeScript, Tailwind, shadcn/ui. Next 16 differs from older training data: read `node_modules/next/dist/docs/` before writing routing, caching or Route Handler code.

## Commands

```
npm install && npm run dev    # :3000
npm run lint && npx tsc --noEmit && npm run build
npm test                       # vitest (Phase 0.3 adds it)
make types                     # regenerate lib/types.gen.ts from the OpenAPI snapshot (Phase 6+); never hand-edit
```

## Rules

- The browser talks only to sentinel-web. `app/api/[...path]/route.ts` streams to sentinel-api (D2): `dynamic='force-dynamic'`, `runtime='nodejs'`, `compress:false` in `next.config.ts`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`, forward the request `signal`, support Last-Event-ID. **Never create `proxy.ts`** (Next 16's renamed middleware).
- `output: 'standalone'` stays set; `frontend/Dockerfile` depends on it.
- `DATA_MODE=fixtures|live` (`lib/data-mode.ts`). Fixtures come from `frontend/fixtures/*.json` exported by backend runs (`make fixtures`, Phase 3+).
- Status colour is always paired with an icon and text.
- When `LLM_PROVIDER=scripted`, show the persistent "LLM: scripted (test)" badge. Replays are labelled "synthetic replay".
- Pages are added per phase (plan Phases 3, 7, 9-11); axe must show no serious or critical violations from Phase 7.
