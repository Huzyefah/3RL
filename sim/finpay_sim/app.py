"""finpay-sim HTTP surface (NovaPay sandbox; sandbox only, never a real system).

A background asyncio loop advances the pure ``SimEngine`` with wall-clock deltas and hands each
emitted envelope to the configured sinks. ``SIM_AUTOSTART=0`` disables the loop (tests).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Body, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from . import chaos
from .emitter import HttpSink, RingBufferSink, Sink
from .engine import SimEngine

log = logging.getLogger("finpay_sim")

Bank = Literal["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E"]
LOOP_INTERVAL_S = 0.25


class RoutingIn(BaseModel):
    bank: Bank
    rail: Literal["IBFT", "RAAST"]


class OtpIn(BaseModel):
    provider: Literal["P1", "P2"]


class WorkersIn(BaseModel):
    workers: int = Field(ge=1, le=8, strict=True)


class PayIn(BaseModel):
    bank: Bank | None = None


class Runtime:
    """Engine + sinks. ``advance`` is the only place envelopes leave the engine."""

    def __init__(self, engine: SimEngine, sinks: list[Sink], ring: RingBufferSink) -> None:
        self.engine = engine
        self.sinks = sinks
        self.ring = ring

    async def advance_async(self, dt: float) -> None:
        for env in self.engine.step(dt):
            for sink in self.sinks:
                try:
                    await sink.publish(env)
                except Exception as exc:  # noqa: BLE001
                    log.warning("sink %s failed: %s", type(sink).__name__, exc)

    def advance(self, dt: float) -> None:
        """Synchronous helper for tests (ring buffer only; no network sinks)."""
        for env in self.engine.step(dt):
            self.ring.buffer.append(env)

    async def run(self) -> None:
        last = time.monotonic()
        while True:
            await asyncio.sleep(LOOP_INTERVAL_S)
            now = time.monotonic()
            await self.advance_async(min(now - last, 30.0))
            last = now


def create_app() -> FastAPI:
    engine = SimEngine(seed=int(os.environ.get("SIM_SEED", "7")))
    ring = RingBufferSink(maxlen=2000)
    sinks: list[Sink] = [ring]
    http_sink = HttpSink(url) if (url := os.environ.get("SENTINEL_INGEST_URL")) else None
    if http_sink:
        sinks.append(http_sink)
    runtime = Runtime(engine, sinks, ring)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if os.environ.get("SIM_AUTOSTART", "1") != "0":
            task = asyncio.create_task(runtime.run())
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if http_sink:
            await http_sink.aclose()

    app = FastAPI(title="finpay-sim", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.runtime = runtime

    def _engine(request: Request) -> SimEngine:
        return request.app.state.runtime.engine

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "service": "finpay-sim"}

    @app.post("/chaos/{fault}")
    def post_chaos(fault: str, request: Request) -> dict:
        if fault not in (*chaos.FAULTS, chaos.RESET):
            raise HTTPException(404, f"unknown fault {fault!r}")
        return {"fault": fault, "active": _engine(request).trigger(fault)}

    @app.get("/admin/routing")
    def get_routing(request: Request) -> dict:
        return {"routing": dict(_engine(request).routing)}

    @app.post("/admin/routing")
    def post_routing(body: RoutingIn, request: Request) -> dict:
        return {"routing": _engine(request).set_routing(body.bank, body.rail)}

    @app.get("/admin/otp")
    def get_otp(request: Request) -> dict:
        return {"provider": _engine(request).otp_provider}

    @app.post("/admin/otp")
    def post_otp(body: OtpIn, request: Request) -> dict:
        return {"provider": _engine(request).set_otp_provider(body.provider)}

    @app.get("/admin/workers")
    def get_workers(request: Request) -> dict:
        e = _engine(request)
        return {"workers": e.workers, "tps": e.tps}

    @app.post("/admin/workers")
    def post_workers(body: WorkersIn, request: Request) -> dict:
        e = _engine(request)
        e.set_workers(body.workers)
        return {"workers": e.workers, "tps": e.tps}

    @app.get("/admin/state")
    def get_state(request: Request) -> dict:
        return _engine(request).state()

    @app.post("/pay")
    def post_pay(request: Request, body: Annotated[PayIn | None, Body()] = None) -> dict:
        return _engine(request).pay(body.bank if body else None)

    @app.post("/login")
    def post_login(request: Request) -> dict:
        return _engine(request).login()

    @app.get("/emitted")
    def get_emitted(
        request: Request,
        since: datetime | None = None,
        limit: Annotated[int, Query(ge=1, le=2000)] = 200,
    ) -> dict:
        envs = request.app.state.runtime.ring.since(since, limit)
        return {"envelopes": envs, "count": len(envs)}

    return app


app = create_app()
