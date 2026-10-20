from fastapi import FastAPI

from sentinel.config import settings


app = FastAPI(
    title="sentinel-api",
    docs_url="/docs" if settings.env != "prod" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.env != "prod" else None,
)


def _csv_rows() -> int:
    try:
        with settings.ps02_csv_path.open() as f:
            return sum(1 for _ in f) - 1
    except FileNotFoundError:
        return 0


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "sentinel-api", "env": settings.env, "csv_rows": _csv_rows()}
