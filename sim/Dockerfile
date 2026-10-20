# Built by Cloud Build from the REPO ROOT (see infra/cloudbuild/sim.yaml).
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app/sim
COPY sim/pyproject.toml sim/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY sim/ ./
RUN uv sync --frozen --no-dev
ENV PORT=8080
CMD ["sh", "-c", "uv run --no-sync uvicorn finpay_sim.app:app --host 0.0.0.0 --port ${PORT}"]
