# sentinel-api. Build context = repo root (D1):  docker build -f backend/Dockerfile .
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Workspace metadata first so the dependency layer caches.
COPY pyproject.toml uv.lock .python-version ./
COPY backend/pyproject.toml backend/pyproject.toml
COPY sim/pyproject.toml sim/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    mkdir -p backend/sentinel sim/finpay_sim && touch backend/sentinel/__init__.py sim/finpay_sim/__init__.py && \
    uv sync --frozen --no-dev --no-editable --package sentinel --no-install-workspace
COPY backend/ backend/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package sentinel

FROM python:3.12-slim AS runtime
RUN useradd --system --uid 10001 --no-create-home app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
WORKDIR /app/backend
COPY --from=build /app/.venv /app/.venv
COPY backend/data /app/backend/data
COPY backend/prompts /app/backend/prompts
COPY data /app/data
USER 10001
EXPOSE 8080
# Exec form; `exec` in sh makes uvicorn PID 1 so SIGTERM drains cleanly. Writes need a tmpfs at /tmp (read-only root fs).
CMD ["sh", "-c", "exec uvicorn sentinel.api.main:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-graceful-shutdown 10"]
