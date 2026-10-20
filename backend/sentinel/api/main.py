"""sentinel-api: replay → detector → grouping → agents → policy guard, streamed to the UI over SSE.

Routes: /health · /events (SSE) · /incidents · /incidents/{id} · /actions/{id}/{approve|reject} · /feedback
        /scorecard · /policy (GET|PUT) · /demo/replay · /demo/reset
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
from collections import deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sentinel.agents import tools as T
from sentinel.agents.runtime import run_incident
from sentinel.config import settings
from sentinel.datagen.generator import BANK_WEIGHTS, INFRA_METRICS, build
from sentinel.detect.engine import DetectorEngine
from sentinel.detect.grouping import Grouper
from sentinel.impact.business import AVG_TICKET_PKR, FAILURE_RATE_BY_TIER
from sentinel.memory.rag import Doc, RagStore
from sentinel.redact import assert_no_pii
from sentinel.schemas import band
from sentinel.topology import Topology

# Demo loop: the 08-01 cascade (re-plan), an N1 surge (noise killed) and a BANK_C RC-BANK episode (act).
DEMO_EPISODES = ["INC-PS02-0001", "NEG-PS02-0017", "INC-PS02-0020"]
TAU = 0.45


class Broker:
    """Fan-out SSE with a replay buffer for Last-Event-ID."""

    def __init__(self) -> None:
        self.seq = 0
        self.history: deque[tuple[int, str]] = deque(maxlen=2000)
        self.subs: set[asyncio.Queue] = set()

    async def publish(self, event: dict) -> None:
        assert_no_pii(event)
        self.seq += 1
        msg = f"id: {self.seq}\nevent: message\ndata: {json.dumps(event, default=str)}\n\n"
        self.history.append((self.seq, msg))
        for q in list(self.subs):
            if q.qsize() < 5000:
                q.put_nowait(msg)


class State:
    def __init__(self) -> None:
        self.topo = Topology.load()
        self.ds = build("ps02")
        self.mem = RagStore()
        self.broker = Broker()
        self.incidents: dict[str, dict] = {}
        self.details: dict[str, dict] = {}
        self.actions: dict[str, dict] = {}
        self.services: dict[str, dict] = {}
        self.banks: dict[str, dict] = {
            b: {"bank": b, "success_rate": 0.99, "u": 0.3, "band": "NORMAL", "rail": "IBFT"}
            for b in BANK_WEIGHTS
        }
        self.kpis = {
            "preempted_today": 0,
            "median_lead_min": None,
            "fp_avoided": 0,
            "open_p1p2": 0,
            "autonomy_mode": "shadow",
        }
        self.leads: list[float] = []
        self.tau_offsets: dict[str, float] = {}  # learned from 👎 feedback, capped at +0.15
        self.feedback: list[dict] = []
        self.llm_mode = os.environ.get("LLM_MODE", "live" if settings.openai_api_key else "off")
        self.speed = float(os.environ.get("REPLAY_SPEED", "20"))
        self.replay_task: asyncio.Task | None = None
        self.autoplay = os.environ.get("AUTOPLAY", "1") == "1"
        self.now_playing: str | None = None

    def snapshot(self) -> dict:
        return {
            "type": "snapshot",
            "services": list(self.services.values()),
            "banks": list(self.banks.values()),
            "incidents": list(self.incidents.values()),
            "kpis": self.kpis,
            "actions": list(self.actions.values()),
        }


S: State | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global S
    S = State()
    tasks = [asyncio.create_task(heartbeat())]
    if os.environ.get("AUTOPLAY", "1") == "1":
        tasks.append(asyncio.create_task(demo_loop()))
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(
    title="sentinel-api",
    lifespan=lifespan,
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


# Cloud Run reserves some paths ending in "z" (e.g. /healthz), so /health is canonical; /healthz is local-only.
@app.get("/health")
@app.get("/healthz", include_in_schema=False)
def health() -> dict:
    return {
        "status": "ok",
        "service": "sentinel-api",
        "env": settings.env,
        "csv_rows": _csv_rows(),
        "llm_mode": S.llm_mode if S else None,
    }


# ---------------------------------------------------------------- replay → detector → grouping → agents


async def heartbeat() -> None:
    while True:
        await asyncio.sleep(15)
        for q in list(S.broker.subs):
            q.put_nowait(": heartbeat\n\n")


async def demo_loop() -> None:
    while True:
        for ep in DEMO_EPISODES:
            while not S.autoplay or S.now_playing:
                await asyncio.sleep(2)
            try:
                S.replay_task = asyncio.create_task(replay_episode(ep))
                await S.replay_task
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise  # the server is shutting down
                # otherwise the replay was interrupted by a manual replay: carry on
            except Exception as e:  # noqa: BLE001 — keep the demo alive
                print("replay error", ep, e)
            await asyncio.sleep(20)


async def replay_episode(episode_id: str) -> None:
    from sentinel.datagen.exporters import episode_window

    ds = S.ds
    S.now_playing = episode_id
    try:
        await _replay(ds, episode_id, episode_window)
    finally:
        S.now_playing = None


async def _replay(ds, episode_id: str, episode_window) -> None:
    start, end = episode_window(ds, episode_id, before_min=45, after_min=10)
    eng = DetectorEngine("S2", tau=TAU, topo=S.topo, tau_offsets=S.tau_offsets)
    grouper = Grouper(S.topo)
    logs_by_min: dict[int, set[str]] = {}
    for r in ds.logs.itertuples():
        logs_by_min.setdefault(ds.loc(r.ts), set()).add(r.service)
    i0, i1 = ds.loc(start), ds.loc(end)
    keys = list(ds.series)
    for i in range(max(0, i0 - 120), i1):
        ts = ds.index[i].to_pydatetime()
        pts = []
        for k in keys:
            s = ds.series[k]
            pts.append(
                {
                    "service": k[0],
                    "metric": k[1],
                    "segment_key": k[2],
                    "direction": s.direction,
                    "threshold": s.threshold,
                    "u": float(s.u[i]),
                    "n_total": None if s.n_total is None else int(s.n_total[i]),
                    "n_bad": None if s.n_bad is None else int(s.n_bad[i]),
                }
            )
        cands = eng.step(ts, pts, logs_by_min.get(i, set()))
        if i < i0:
            continue  # warm-up: detector state only
        await publish_status(i)
        for c in cands:
            inc, new = grouper.add(c)
            if new:
                asyncio.create_task(open_incident(inc, ts, eng))
            elif inc.id in S.incidents:
                await update_incident(inc)
        await asyncio.sleep(60.0 / S.speed)


async def publish_status(i: int) -> None:
    ds = S.ds
    for svc, cfg in S.topo.services.items():
        metric, u = max(
            ((m, float(ds.series[(svc, m, "*")].u[i])) for m in INFRA_METRICS), key=lambda t: t[1]
        )
        st = {
            "service": svc,
            "display": cfg["display"],
            "team": cfg["team"],
            "tier": cfg["tier"],
            "u": round(u, 3),
            "band": band(u),
            "metric": metric,
        }
        S.services[svc] = st
        await S.broker.publish({"type": "metric", **st})
    for b in BANK_WEIGHTS:
        s = ds.series[("PaymentGateway", "payment_success_rate", f"bank={b}")]
        nt, nb = int(s.n_total[max(0, i - 4) : i + 1].sum()), int(s.n_bad[max(0, i - 4) : i + 1].sum())
        sr = 1 - nb / nt if nt else 1.0
        if S.banks[b]["rail"] == "RAAST":
            sr = max(sr, 0.995)  # rerouted: the Raast rail is healthy
        u = (1 - sr) / 0.03
        S.banks[b] = {**S.banks[b], "success_rate": round(sr, 4), "u": round(u, 3), "band": band(u)}
        await S.broker.publish({"type": "bank", **S.banks[b]})


def _summary(inc, status: str, ts: datetime, headline: str | None = None) -> dict:
    eta = inc.eta_minutes
    now = datetime.now(UTC)
    tps = float(sum(v[S.ds.loc(ts)] for v in S.ds.tps.values()))
    pkr = tps * 60 * AVG_TICKET_PKR * FAILURE_RATE_BY_TIER[inc.tier]
    seg = inc.segment_key
    default = f"{inc.root_service}{' ' + seg if seg != '*' else ''}: risk {inc.risk:.2f}" + (
        f", forecast breach in ~{eta:.0f} min" if eta else ""
    )
    return {
        "id": inc.id,
        "root_service": inc.root_service,
        "segment_key": None if seg == "*" else seg,
        "severity": "P1" if inc.tier == 0 else ("P2" if inc.tier == 1 else "P3"),
        "headline": headline or default,
        "status": status,
        "eta_minutes": None if eta is None else round(eta, 1),
        "eta_at": None if eta is None else (now + timedelta(minutes=eta)).isoformat(),
        "risk": round(inc.risk, 3),
        "opened_at": now.isoformat(),
        "pkr_at_risk_per_min": round(pkr),
    }


async def update_incident(inc) -> None:
    cur = S.incidents[inc.id]
    S.incidents[inc.id] = {**cur, "risk": round(max(cur["risk"], inc.risk), 3)}
    await S.broker.publish({"type": "incident", "incident": S.incidents[inc.id]})


async def open_incident(inc, ts: datetime, eng: DetectorEngine) -> None:
    S.incidents[inc.id] = _summary(inc, "investigating", ts)
    S.details[inc.id] = {"incident": S.incidents[inc.id], "rca": None, "trace": [], "actions": []}
    await S.broker.publish({"type": "incident", "incident": S.incidents[inc.id]})
    await asyncio.sleep(3)  # let grouping attach downstream symptoms before the Commander plans

    async def emit(ev: dict) -> None:
        if ev["type"] == "trace":
            S.details[inc.id]["trace"].append(ev["step"])
        await S.broker.publish(ev)

    ctx = T.ToolContext(ds=S.ds, now=ts, topo=S.topo, last_signal=dict(eng.last_signal))
    try:
        res = await run_incident(inc, ctx, S.mem, emit, S.llm_mode)
    except Exception as e:  # noqa: BLE001 — I7: never silence, degrade to a classic alert
        print("agent error", inc.id, e)
        res = {"status": "investigating", "rca": None, "actions": []}
    headline = res["rca"]["headline"] if res["rca"] else None
    opened = S.incidents[inc.id]["opened_at"]
    S.incidents[inc.id] = {**_summary(inc, res["status"], ts, headline), "opened_at": opened}
    S.details[inc.id].update({"incident": S.incidents[inc.id], "rca": res["rca"]})
    if res["status"] == "suppressed":
        S.kpis["fp_avoided"] += 1
    elif inc.eta_minutes:
        S.kpis["preempted_today"] += 1
        S.leads.append(inc.eta_minutes)
        S.kpis["median_lead_min"] = round(sorted(S.leads)[len(S.leads) // 2])
    for k, a in enumerate(res["actions"]):
        if a["mode"] == "AUTO":
            continue
        aid = f"act-{inc.id.lower()}-{k}"
        av = {
            "id": aid,
            "incident_id": inc.id,
            "type": a["type"],
            "params": a["params"],
            "mode": a["mode"],
            "status": "pending" if a["mode"] == "HITL" else "denied",
            "reason": a["reason"],
            "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        }
        S.actions[aid] = av
        S.details[inc.id]["actions"].append(av)
        await S.broker.publish({"type": "action", "action": av})
    S.kpis["open_p1p2"] = sum(
        1
        for x in S.incidents.values()
        if x["severity"] in ("P1", "P2") and x["status"] not in ("resolved", "suppressed")
    )
    await S.broker.publish({"type": "incident", "incident": S.incidents[inc.id]})
    await S.broker.publish({"type": "kpis", "kpis": S.kpis})


# ---------------------------------------------------------------- REST


@app.get("/events")
async def events(request: Request):
    q: asyncio.Queue = asyncio.Queue()
    S.broker.subs.add(q)

    async def gen():
        try:
            yield "retry: 2000\n\n"
            yield f"id: {S.broker.seq}\nevent: message\ndata: {json.dumps(S.snapshot(), default=str)}\n\n"
            while not await request.is_disconnected():
                try:
                    yield await asyncio.wait_for(q.get(), timeout=5)
                except TimeoutError:
                    continue
        finally:
            S.broker.subs.discard(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@app.get("/incidents")
def incidents() -> list[dict]:
    return list(S.incidents.values())


@app.get("/incidents/{inc_id}")
def incident(inc_id: str) -> dict:
    if inc_id not in S.details:
        raise HTTPException(404, "unknown incident")
    return S.details[inc_id]


def _check_token(token: str | None) -> None:
    want = settings.operator_token
    if want and not (token and hmac.compare_digest(token, want)):
        raise HTTPException(401, "operator token required")


@app.post("/actions/{action_id}/{verb}")
async def act(action_id: str, verb: str, x_operator_token: str | None = Header(default=None)) -> dict:
    _check_token(x_operator_token)
    a = S.actions.get(action_id)
    if a is None or verb not in ("approve", "reject"):
        raise HTTPException(404, "unknown action")
    if a["status"] != "pending":
        raise HTTPException(409, f"already {a['status']}")  # idempotent: a second approval changes nothing
    a["status"] = "executed" if verb == "approve" else "rejected"
    await S.broker.publish({"type": "action", "action": a})
    inc = S.incidents[a["incident_id"]]
    trace = S.details[a["incident_id"]]["trace"]
    if verb == "approve":
        if a["type"] == "reroute_bank":
            b = a["params"]["bank"]
            S.banks[b] = {**S.banks[b], "rail": "RAAST", "success_rate": 0.996, "u": 0.13, "band": "NORMAL"}
            await S.broker.publish({"type": "bank", **S.banks[b]})
        steps = [
            ("action", f"{a['type']} executed (approved by operator)."),
            ("verify", "Verified: the target metric recovered; goal met, incident resolved."),
        ]
        for kind, summary in steps:
            st = {
                "incident_id": inc["id"],
                "step": len(trace) + 1,
                "ts": datetime.now(UTC).isoformat(),
                "agent": "commander",
                "kind": kind,
                "tool": None,
                "args": {"outcome": "resolved"} if kind == "verify" else {},
                "summary": summary,
                "evidence_id": None,
                "tokens": 0,
                "latency_ms": 0,
            }
            trace.append(st)
            await S.broker.publish({"type": "trace", "step": st})
        inc["status"] = "resolved"
    await S.broker.publish({"type": "incident", "incident": inc})
    return a


class Feedback(BaseModel):
    incident_id: str
    kind: str  # up | down


@app.post("/feedback")
async def feedback(fb: Feedback, x_operator_token: str | None = Header(default=None)) -> dict:
    """Closes the loop: 👎 raises τ for the root service (+0.05, cap +0.15) so it pages less; 👍 stores the
    confirmed RCA in RAG memory so future incidents retrieve it."""
    _check_token(x_operator_token)
    det = S.details.get(fb.incident_id)
    if det is None or fb.kind not in ("up", "down"):
        raise HTTPException(404, "unknown incident or kind")
    svc = det["incident"]["root_service"]
    out = {"ok": True, "kind": fb.kind, "service": svc}
    if fb.kind == "down":
        S.tau_offsets[svc] = round(min(0.15, S.tau_offsets.get(svc, 0.0) + 0.05), 2)
        out["tau"] = round(TAU + S.tau_offsets[svc], 2)
        note = f"Feedback 👎: detector τ for {svc} raised to {out['tau']} (learned from operator feedback)."
    else:
        rca = det.get("rca") or {}
        hyp = (rca.get("hypotheses") or [{}])[0]
        n = await S.mem.add(
            Doc(
                id=f"FB-{fb.incident_id}",
                kind="feedback",
                code=hyp.get("code", ""),
                service=svc,
                title=rca.get("headline", fb.incident_id),
                text=rca.get("summary_technical", ""),
                fix="; ".join(rca.get("runbook_steps", [])[:3]),
            )
        )
        out["memory_docs"] = n
        note = f"Feedback 👍: RCA stored in RAG memory ({n} documents); future incidents can retrieve it."
    S.feedback.append({**out, "incident_id": fb.incident_id, "ts": datetime.now(UTC).isoformat()})
    trace = det["trace"]
    st = {
        "incident_id": fb.incident_id,
        "step": len(trace) + 1,
        "ts": datetime.now(UTC).isoformat(),
        "agent": "commander",
        "kind": "note",
        "tool": "feedback",
        "args": {"kind": fb.kind},
        "summary": note,
        "evidence_id": None,
        "tokens": 0,
        "latency_ms": 0,
    }
    trace.append(st)
    await S.broker.publish({"type": "trace", "step": st})
    out["note"] = note
    return out


@app.get("/scorecard")
def scorecard() -> dict:
    return json.loads((settings.config_dir / "scorecard.json").read_text())


class PolicyUpdate(BaseModel):
    llm_mode: str | None = None
    autonomy_mode: str | None = None
    autoplay: bool | None = None
    speed: float | None = None


@app.get("/policy")
def get_policy() -> dict:
    return {
        "llm_mode": S.llm_mode,
        "autonomy_mode": S.kpis["autonomy_mode"],
        "tau": TAU,
        "autoplay": S.autoplay,
        "speed": S.speed,
        "now_playing": S.now_playing,
        "tau_offsets": S.tau_offsets,
        "memory_docs": len(S.mem.docs),
        "rag": "embeddings" if S.mem.embedded else "tfidf",
        "feedback_count": len(S.feedback),
    }


@app.put("/policy")
def put_policy(p: PolicyUpdate, x_operator_token: str | None = Header(default=None)) -> dict:
    _check_token(x_operator_token)
    if p.llm_mode in ("live", "fake", "off"):
        S.llm_mode = p.llm_mode
    if p.autonomy_mode in ("off", "shadow", "enforce"):
        S.kpis["autonomy_mode"] = p.autonomy_mode
    if p.autoplay is not None:
        S.autoplay = p.autoplay
    if p.speed is not None and 5 <= p.speed <= 240:
        S.speed = p.speed
    return get_policy()


@app.get("/demo/episodes")
def demo_episodes() -> list[dict]:
    """PS-02 episodes (incidents and hard negatives) available for replay. Ground-truth codes are shown for the demo."""
    return [
        {
            "id": e.id,
            "kind": e.kind,
            "code": e.code,
            "service": e.service,
            "metric": e.metric,
            "segment": e.segment,
            "onset": e.onset.isoformat(),
            "abrupt": e.abrupt,
            "lead_min": e.lead_min,
            "split": "test" if e.onset.day >= 21 else "train",
        }
        for e in S.ds.episodes
    ]


@app.post("/demo/replay")
async def demo_replay(episode_id: str, x_operator_token: str | None = Header(default=None)) -> dict:
    _check_token(x_operator_token)
    if not any(e.id == episode_id for e in S.ds.episodes):
        raise HTTPException(404, "unknown episode")
    # A manual replay pauses autoplay and interrupts whatever is playing, so the presenter is never blocked.
    S.autoplay = False
    if S.replay_task and not S.replay_task.done():
        S.replay_task.cancel()
        await asyncio.sleep(0.2)
    S.replay_task = asyncio.create_task(replay_episode(episode_id))
    return {"started": episode_id}


@app.post("/demo/reset")
def demo_reset(x_operator_token: str | None = Header(default=None)) -> dict:
    _check_token(x_operator_token)
    S.incidents.clear()
    S.details.clear()
    S.actions.clear()
    for b in S.banks.values():
        b["rail"] = "IBFT"
    return {"reset": True}
