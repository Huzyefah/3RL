# Next 16 notes (from node_modules/next/dist/docs)

- `create-next-app` scaffolds `cacheComponents: true` + `partialPrefetching`; with Cache Components `dynamic`/`runtime`/`revalidate` segment config is removed, so we leave it off to keep D2's `force-dynamic` proxy.
- `middleware.ts` is renamed `proxy.ts` in Next 16; D2 forbids both.
- Route Handlers are uncached by default (non-GET never cached); `params` is a Promise and must be awaited.
- `compress: false` and `output: 'standalone'` are in next.config.ts (SSE must not be gzip-buffered).
- Scaffold uses `@tailwindcss/turbopack` (Tailwind 4); shadcn is `base-nova` style, neutral base color, lucide icons.
- `next dev` re-adds the AGENTS.md block; keep AGENTS.md.
