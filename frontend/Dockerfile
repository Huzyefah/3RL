# sentinel-web (Next standalone output). Build context = repo root:  docker build -f frontend/Dockerfile .
# Requires `output: 'standalone'` in frontend/next.config.ts.
FROM node:26-slim AS deps
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:26-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules node_modules
COPY frontend/ ./
RUN npm run build

FROM node:26-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
# Exec form: node is PID 1 and receives SIGTERM directly. Next's server needs a writable /app/.next/cache or a tmpfs.
CMD ["node", "server.js"]
