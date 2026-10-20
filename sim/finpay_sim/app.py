"""Placeholder sim so the image starts; Phase 5 replaces this with finpay-sim."""

from fastapi import FastAPI

app = FastAPI(title="finpay-sim")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "finpay-sim"}
