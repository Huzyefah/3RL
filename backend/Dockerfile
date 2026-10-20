# Built by Cloud Build from the REPO ROOT (see infra/cloudbuild/api.yaml) so data/ is in context.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY data/ps02_system_telemetry.csv /app/data/ps02_system_telemetry.csv
RUN uv sync --frozen --no-dev
ENV ENV=prod PS02_CSV_PATH=/app/data/ps02_system_telemetry.csv PORT=8080
CMD ["sh", "-c", "uv run --no-sync uvicorn sentinel.api.main:app --host 0.0.0.0 --port ${PORT}"]
