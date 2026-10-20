"""Placeholder API so the image starts; Phase 6 replaces this with the real app."""

from fastapi import FastAPI

app = FastAPI(title="sentinel-api")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "sentinel-api"}
