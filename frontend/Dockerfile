# Built by Cloud Build from the REPO ROOT (see infra/cloudbuild/web.yaml).
FROM node:22-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=8080
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
CMD ["node", "server.js"]
