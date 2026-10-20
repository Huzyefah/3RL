"""Sentinel API: healthz + MVP demo router."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sentinel.mvp.engine import engine
from sentinel.mvp.router import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(engine().ticker())
    yield
    task.cancel()


app = FastAPI(title="sentinel-api", lifespan=lifespan)
app.include_router(router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "sentinel-api"}
