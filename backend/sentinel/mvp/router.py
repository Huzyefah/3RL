"""HTTP surface for the MVP demo."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sentinel.mvp.engine import engine

router = APIRouter()


class ReplayReq(BaseModel):
    episode_id: str
    speed: float = 30.0


@router.get("/state")
def state() -> dict:
    return engine().state()


@router.post("/demo/replay")
async def replay(req: ReplayReq) -> dict:
    try:
        return await engine().replay(req.episode_id, req.speed)
    except KeyError:
        raise HTTPException(404, f"unknown episode {req.episode_id}") from None


@router.post("/demo/chaos/bank_c_slow")
def chaos() -> dict:
    engine().chaos_bank_c()
    return {"ok": True, "bank": "BANK_C", "mode": "degrading"}


@router.post("/demo/reset")
def reset() -> dict:
    engine().reset_state()
    return {"ok": True}


@router.get("/incidents/{iid}")
def incident(iid: str) -> dict:
    inc = engine().incidents.get(iid)
    if inc is None:
        raise HTTPException(404, "unknown incident")
    rca = dict(inc["rca"] or {"incident_id": iid, "headline": inc["headline"]})
    rca.update({"status": inc["status"], "verdict": inc["verdict"], "trace": inc["trace"], "actions": inc["actions"],
                "ticket": inc["ticket"], "chat_card": inc["chat_card"], "members": inc["members"]})
    return rca


async def _decide(aid: str, ok: bool) -> dict:
    try:
        r = await engine().approve(aid, ok)
    except KeyError:
        raise HTTPException(404, "unknown approval") from None
    if r.get("conflict"):
        raise HTTPException(409, f"approval already {r['status']}")
    return r


@router.post("/actions/{aid}/approve")
async def approve(aid: str) -> dict:
    return await _decide(aid, True)


@router.post("/actions/{aid}/reject")
async def reject(aid: str) -> dict:
    return await _decide(aid, False)


@router.get("/scorecard")
async def scorecard() -> dict:
    return await asyncio.to_thread(engine().scorecard)


@router.get("/events")
async def events() -> StreamingResponse:
    eng = engine()
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    eng.subs.append(q)

    async def gen():
        try:
            yield "event: hello\ndata: {}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], default=str)}\n\n"
                except TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            eng.subs.remove(q)

    return StreamingResponse(gen(), media_type="text/event-stream")
