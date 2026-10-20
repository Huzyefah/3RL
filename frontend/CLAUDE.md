@AGENTS.md

# frontend/ → sentinel-web (Next.js 16.4, App Router, Tailwind 4)

**Read `node_modules/next/dist/docs/` before writing code.** This Next version has breaking changes, and `cacheComponents` is on. Wrap dynamic data in `<Suspense>`.

```
npm run dev      # :3000, expects SENTINEL_API_URL (default http://localhost:8080)
npm run lint && npm run build
```

## Rules
- **The browser talks only to this app.** Every API call goes through the same-origin proxy `app/api/[...path]/route.ts` → `${SENTINEL_API_URL}`. SSE is `/api/events`, streamed straight through.
  - `lib/upstream.ts` is server-only. On Cloud Run it attaches a Google ID token, because sentinel-api is private.
  - It also attaches `x-operator-token` on mutating requests. **The operator token must never reach client code or the bundle.** An E2E test greps the build output for it.
  - Server components call the api with `apiFetch()`.
- No `NEXT_PUBLIC_*` API URLs. The URL is a runtime env var (`SENTINEL_API_URL`).
- **Status colour always comes with an icon and a text label.** Layouts must work at a 390 px width with no horizontal scroll.
- Load the `dataviz` skill before writing any chart (Recharts). Use the `frontend-design` plugin for screen design.
- Interactive elements get `data-testid`s, which the Playwright specs in `e2e/tests/phase-NN/` rely on.
- `output: "standalone"`. The Dockerfile copies `.next/static` and `public`, and sets `HOSTNAME=0.0.0.0`.
