# Scripted demo backend (same SSE/REST contract as sentinel-api). Built from the repo root.
FROM node:22-slim
WORKDIR /app
COPY e2e/mock-api/server.mjs ./server.mjs
ENV NODE_ENV=production
CMD ["sh", "-c", "MOCK_PORT=${PORT:-8080} node server.mjs"]
