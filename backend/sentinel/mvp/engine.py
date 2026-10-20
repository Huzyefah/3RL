"""MVP demo engine: detector (Holt), grouping, agents (OpenAI w/ fallback), guard, finpay mini-sim."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import statistics
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

from sentinel.calendar import events_at
from sentinel.config import get_settings
from sentinel.datagen.corpus import docs_before
from sentinel.datagen.episode_map import load_episode_map
from sentinel.schemas import RCA
from sentinel.topology import Topology
from sentinel.utilisation import band

ROOT = Path(__file__).resolve().parents[3]
RUNBOOKS = Path(__file__).resolve().parents[2] / "data" / "runbooks"
FORBIDDEN = {
    "change_ledger_balances", "delete_data", "block_all_logins", "change_limits",
    "failover_to_unhealthy_target", "act_on_non_sandbox_target",
}  # fmt: skip
GMV_PER_MIN_PKR = 2_500_000.0  # assumption, labelled estimate
BANKS = ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E"]
BANK_FLOOR = 0.90  # success-rate floor (lower_bad threshold)


def _api_key() -> str:
    s = get_settings()
    if s.openai_api_key:
        return s.openai_api_key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    return os.environ.get("OPENAI_API_KEY", "")


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    if v:
        return v
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"')
    return default


# ---------------------------------------------------------------- detector
class Holt:
    def __init__(self, alpha: float = 0.5, beta: float = 0.3) -> None:
        self.a, self.b = alpha, beta
        self.level: float | None = None
        self.trend = 0.0
        self.streak = 0
        self.last: float | None = None

    def update(self, u: float) -> tuple[float | None, bool]:
        if self.level is None:
            self.level = u
        else:
            prev = self.level
            self.level = self.a * u + (1 - self.a) * (self.level + self.trend)
            self.trend = self.b * (self.level - prev) + (1 - self.b) * self.trend
        self.streak = self.streak + 1 if (self.last is not None and u > self.last) else 0
        self.last = u
        eta = None
        if self.trend > 1e-4 and self.level < 0.95:
            eta = (0.95 - self.level) / self.trend
        elif self.level >= 0.95:
            eta = 0.0
        trigger = u >= 0.95 or (self.streak >= 5 and eta is not None and eta <= 30)
        return eta, trigger


def detect_series(us: list[float]) -> int | None:
    h = Holt()
    for i, u in enumerate(us):
        _, trig = h.update(u)
        if trig:
            return i
    return None


# ---------------------------------------------------------------- recall_similar
def _tok(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def recall_similar(query: str, ts: datetime, exclude: str | None, k: int = 3) -> list[dict]:
    docs = docs_before(ts.replace(tzinfo=None) if ts.tzinfo else ts, exclude_id=exclude, include_test=True)
    if not docs:
        return []
    df = Counter(t for d in docs for t in set(_tok(d.text + " " + d.code + " " + d.service)))
    n = len(docs)
    q = Counter(_tok(query))
    out = []
    for d in docs:
        dt = Counter(_tok(d.text + " " + d.code + " " + d.service))
        num = sum(q[t] * dt[t] * math.log(1 + n / df[t]) ** 2 for t in q if t in dt)
        den = math.sqrt(sum(v * v for v in q.values())) * math.sqrt(sum(v * v for v in dt.values())) or 1
        out.append({"id": d.doc_id, "similarity": round(num / den, 3), "fix": d.fix, "code": d.code, "text": d.text[:240]})
    return sorted(out, key=lambda x: -x["similarity"])[:k]


# ---------------------------------------------------------------- engine
class Engine:
    def __init__(self) -> None:
        self.topo = Topology.from_yaml()
        self.llm_ok = bool(_api_key())
        self.fast = _env("OPENAI_FAST_MODEL", get_settings().openai_fast_model)
        self.smart = _env("OPENAI_SMART_MODEL", get_settings().openai_smart_model)
        self.subs: list[asyncio.Queue] = []
        self._scorecard: dict | None = None
        self.tasks: list[asyncio.Task] = []
        self.reset_state()

    def reset_state(self) -> None:
        for t in getattr(self, "tasks", []):
            t.cancel()
        self.tasks = []
        self.sim_time = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
        self.replaying = False
        self.rng = np.random.default_rng(7)
        self.svc_u = {k: 0.35 + 0.1 * self.rng.random() for k in self.topo.services}
        self.override: dict[str, float] = {}
        self.det: dict[str, Holt] = {}
        self.eta: dict[str, float | None] = {}
        self.bank_sr = {b: 0.985 for b in BANKS}
        self.bank_mode = {b: "ok" for b in BANKS}
        self.rail_healthy = {"RAAST": True, "IBFT": True}
        self.incidents: dict[str, dict] = {}
        self.approvals: dict[str, dict] = {}
        self.kpis = {"pre_empted_today": 0, "fp_avoided": 0, "leads": []}
        self.inc_seq = 0

    # -- events
    def publish(self, kind: str, data: Any) -> None:
        for q in list(self.subs):
            try:
                q.put_nowait({"event": kind, "data": data})
            except asyncio.QueueFull:
                pass

    def spawn(self, coro) -> None:
        self.tasks.append(asyncio.create_task(coro))

    # -- state
    def state(self) -> dict:
        services = []
        for k, s in self.topo.services.items():
            u = self.override.get(k, self.svc_u[k])
            services.append({"name": k, "display": s.novapay_name, "u": round(u, 3), "status": band(u),
                             "eta_min": _r(self.eta.get(k))})
        banks = []
        for b in BANKS:
            u = (1 - self.bank_sr[b]) / (1 - BANK_FLOOR)
            banks.append({"bank": b, "success_rate": round(self.bank_sr[b], 4), "u": round(u, 3), "status": band(u),
                          "routed_via": "RAAST" if self.bank_mode[b] == "rerouted" else "IBFT"})
        now = time.time()
        approvals = [
            {"id": a["id"], "action": a["action"], "params": a["params"], "expires_in_s": int(a["expires"] - now),
             "incident_id": a["incident_id"]}
            for a in self.approvals.values() if a["status"] == "pending" and a["expires"] > now
        ]
        incs = [{"id": i["id"], "headline": i["headline"], "severity": i["severity"], "service": i["service"],
                 "eta_min": _r(i["eta_min"]), "status": i["status"], "verdict": i["verdict"]}
                for i in self.incidents.values()]
        leads = self.kpis["leads"]
        return {
            "time": self.sim_time.isoformat(), "replaying": self.replaying,
            "llm": "openai" if self.llm_ok else "fallback",
            "kpis": {"pre_empted_today": self.kpis["pre_empted_today"], "fp_avoided": self.kpis["fp_avoided"],
                     "median_lead_min": round(statistics.median(leads), 1) if leads else None,
                     "open_incidents": sum(1 for i in self.incidents.values() if i["status"] in ("open", "watching"))},
            "services": services, "banks": banks, "approvals": approvals, "incidents": incs,
        }

    def trace(self, inc: dict, step: str, detail: Any) -> None:
        e = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "step": step, "detail": detail}
        inc["trace"].append(e)
        self.publish("trace", {"incident_id": inc["id"], **e})

    # -- ticker: background noise + bank sim
    async def ticker(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            for k in self.svc_u:
                self.svc_u[k] = min(0.6, max(0.2, self.svc_u[k] + self.rng.normal(0, 0.01)))
            for b in BANKS:
                m = self.bank_mode[b]
                if m == "degrading":
                    self.bank_sr[b] = max(0.88, self.bank_sr[b] - 0.006)
                elif m == "rerouted":
                    self.bank_sr[b] = min(0.985, self.bank_sr[b] + 0.012)
                else:
                    self.bank_sr[b] = min(0.99, max(0.975, self.bank_sr[b] + self.rng.normal(0, 0.001)))
                key = f"PaymentGateway|bank={b}"
                u = (1 - self.bank_sr[b]) / (1 - BANK_FLOOR)
                if m == "degrading":
                    self.observe(key, u, "PaymentGateway", f"bank={b}", "RC-BANK", None)
            if not self.replaying:
                self.sim_time = datetime.now(timezone.utc)
            self.publish("state", {"time": self.sim_time.isoformat()})
            self.expire()

    def expire(self) -> None:
        now = time.time()
        for a in self.approvals.values():
            if a["status"] == "pending" and a["expires"] <= now:
                a["status"] = "expired"

    # -- detection + grouping
    def observe(self, key: str, u: float, service: str, segment: str, code: str, episode: Any) -> None:
        h = self.det.setdefault(key, Holt())
        eta, trig = h.update(u)
        self.eta[service] = eta if trig or eta is not None and eta < 60 else None
        if not trig:
            return
        if any(i["key"] == key and i["status"] in ("open", "watching", "suppressed") for i in self.incidents.values()):
            return
        for inc in self.incidents.values():
            if inc["status"] in ("open", "watching") and any(c["key"] == key for c in inc["members"]):
                return
        cand = {"key": key, "service": service, "segment": segment, "u": round(u, 3), "eta_min": _r(eta),
                "trend": round(h.trend, 4), "ts": self.sim_time.isoformat()}
        self.publish("candidate", cand)
        for inc in self.incidents.values():
            if inc["status"] in ("open", "watching") and ("bank=" in inc["segment"]) == ("bank=" in segment) and (inc["service"] == service or self.topo.linked(inc["service"], service)):
                inc["members"].append(cand)
                self.trace(inc, "grouped", f"candidate on {service} attached (dependency-linked to {inc['service']})")
                return
        self.inc_seq += 1
        iid = f"LIVE-{self.inc_seq:04d}"
        inc = {"id": iid, "key": key, "headline": f"{service} {segment} trending to breach", "severity": "P2",
               "service": service, "segment": segment, "eta_min": eta, "status": "open", "verdict": "CONFIRMED",
               "trace": [], "actions": [], "ticket": None, "rca": None, "members": [cand], "code": code,
               "episode": episode, "u_hist": [u], "trend": h.trend, "sim_ts": self.sim_time, "chat_card": None}
        self.incidents[iid] = inc
        self.trace(inc, "detector", cand)
        self.spawn(self.run_agents(inc))

    # -- replay
    async def replay(self, episode_id: str, speed: float = 30.0) -> dict:
        ep = next((e for e in load_episode_map() if e.episode_id == episode_id), None)
        if ep is None:
            raise KeyError(episode_id)
        series = self._series(ep)
        self.spawn(self._replay(ep, series, speed))
        return {"episode_id": episode_id, "points": len(series), "service": ep.service}

    def _series(self, ep) -> list[tuple[datetime, str, float]]:
        onset = datetime.fromisoformat(ep.onset_ts)
        try:
            from sentinel.datagen.generator import build

            ds = build("ps02", seed=0)
            m = ds.metrics
            lo, hi = onset - timedelta(minutes=45), onset + timedelta(minutes=3)
            sel = m[(m["ts"] >= lo) & (m["ts"] <= hi) & (m["metric"] == ep.metric)]
            keep = {ep.service}
            if ep.cascade_parent is None:
                keep |= {e.service for e in load_episode_map() if e.cascade_parent == ep.episode_id}
            else:
                keep.add(next(e.service for e in load_episode_map() if e.episode_id == ep.cascade_parent))
            sel = sel[sel["service"].astype(str).isin(keep)]
            if ep.segment_key and ep.segment_key != "*":
                sel = sel[sel["segment_key"].astype(str).isin([ep.segment_key, "*"])]
            sel = sel.groupby(["ts", "service"], observed=True)["u"].max().reset_index().sort_values("ts")
            out = [(pd_ts.to_pydatetime(), str(s), float(u)) for pd_ts, s, u in sel.itertuples(index=False)]
            if out:
                return out
        except Exception:  # noqa: BLE001
            pass
        from sentinel.datagen.episodes import negative_shape, precursor_shape

        rng = np.random.default_rng(1)
        sh = precursor_shape(ep.code, rng) if ep.kind == "incident" else negative_shape(ep.code, rng)
        base, tgt = 0.45, 1.0
        start = onset - timedelta(minutes=sh.onset_index)
        return [(start + timedelta(minutes=i), ep.service, base + float(v) * (tgt - base))
                for i, v in enumerate(sh.u_offset[: sh.onset_index + 3])]

    async def _replay(self, ep, series, speed: float) -> None:
        self.replaying = True
        try:
            prev = None
            for ts, svc, u in series:
                if prev is not None and ts != prev:
                    await asyncio.sleep(max(0.02, (ts - prev).total_seconds() / speed))
                prev = ts
                self.sim_time = ts.replace(tzinfo=timezone.utc)
                self.override[svc] = u
                self.observe(f"{svc}|{ep.metric}|{ep.episode_id}", u, svc, ep.segment_key or "*", ep.code, ep)
        finally:
            self.replaying = False
            await asyncio.sleep(5)
            self.override.clear()

    # -- chaos
    def chaos_bank_c(self) -> None:
        self.bank_mode["BANK_C"] = "degrading"
        self.det.pop("PaymentGateway|bank=BANK_C", None)

    # -- agents
    async def _llm(self, model: str, system: str, user: str, schema: dict, name: str, timeout: float = 20.0) -> dict:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=_api_key(), timeout=timeout)
        r = await asyncio.wait_for(client.chat.completions.create(
            model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
        ), timeout=timeout)
        return json.loads(r.choices[0].message.content)

    async def run_agents(self, inc: dict) -> None:
        try:
            await self._run_agents(inc)
        except Exception as e:  # noqa: BLE001
            self.trace(inc, "error", f"agent pipeline error: {type(e).__name__}")

    async def _run_agents(self, inc: dict) -> None:
        ts = inc["sim_ts"]
        svc, seg, code = inc["service"], inc["segment"], inc["code"]
        tier = self.topo.tier(svc)
        cal = [f"{e.id}: {e.name}" if hasattr(e, "name") else str(e.id) for e in events_at(ts.replace(tzinfo=None))]
        similar = recall_similar(f"{svc} {seg} {code} {inc['headline']}", ts,
                                 inc["episode"].episode_id if inc["episode"] else None)
        fas = [s for s in similar if s["id"].startswith("FA-")]
        rb_path = RUNBOOKS / f"{code}.md"
        runbook = rb_path.read_text()[:1500] if rb_path.exists() else ""
        gmv_share = 0.2 if "bank=" in seg else 0.5 if tier == 0 else 0.1
        impact = {"customers_affected_est": int(12000 * gmv_share), "pkr_at_risk_per_min": GMV_PER_MIN_PKR * gmv_share,
                  "label": "estimate"}
        self.trace(inc, "goal", f"Prevent {svc} ({seg}) breaching SLO; ETA {_r(inc['eta_min'])} min")
        self.trace(inc, "plan_v1", ["query_metrics", "recall_similar", "calendar_lookup", "skeptic", "commander_rca"])
        self.trace(inc, "tool_call", {"tool": "calendar_lookup", "result": cal})
        self.trace(inc, "tool_call", {"tool": "recall_similar", "result": [{k: s[k] for k in ("id", "similarity")} for s in similar]})
        trend = inc["trend"]
        ctx = (f"service={svc} tier={tier} segment={seg} candidate_code={code} u_now={inc['members'][-1]['u']} "
               f"holt_trend_per_min={trend:.4f} eta_min={_r(inc['eta_min'])} sim_time={ts.isoformat()}\n"
               f"calendar_events_active={cal}\nsimilar_past={json.dumps(similar)}\n"
               f"upstream={sorted(self.topo.upstream(svc))} dependants={sorted(self.topo.dependants(svc))}")
        # Skeptic
        sk_schema = {"type": "object", "additionalProperties": False, "required": ["verdict", "confidence", "counter_evidence", "cited_calendar_ids"],
                     "properties": {"verdict": {"type": "string", "enum": ["CONFIRMED", "DISPUTED", "BENIGN"]},
                                    "confidence": {"type": "number"}, "counter_evidence": {"type": "string"},
                                    "cited_calendar_ids": {"type": "array", "items": {"type": "string"}}}}
        try:
            sk = await self._llm(self.fast, "You are the Skeptic SRE agent for NovaPay (Pakistani fintech). Argue against the alert. "
                                 "Return BENIGN only if a calendar event explains the load and the trend is flat or recovering; "
                                 "DISPUTED if the root-cause hypothesis is doubtful; else CONFIRMED.", ctx, sk_schema, "skeptic")
            self.llm_ok = True
        except Exception as e:  # noqa: BLE001
            self.trace(inc, "llm_error", f"skeptic: {type(e).__name__}; statistical fallback")
            sk = {"verdict": "BENIGN" if cal and trend < 0.02 else "CONFIRMED", "confidence": 0.6,
                  "counter_evidence": f"calendar={cal}, false-alarm analogues={[f['id'] for f in fas]}",
                  "cited_calendar_ids": [c.split(":")[0] for c in cal]}
        # invariants I2/I3
        verdict = sk["verdict"]
        if verdict == "BENIGN" and not (sk.get("cited_calendar_ids") and cal and trend < 0.03):
            verdict = "DISPUTED"
            self.trace(inc, "guard", "I2: BENIGN without calendar evidence + flat trend -> DISPUTED")
        if verdict == "BENIGN" and tier == 0 and inc["members"][-1]["u"] >= 0.9:
            verdict = "DISPUTED"
            self.trace(inc, "guard", "I3: Tier-0 high risk never suppressed")
        inc["verdict"] = verdict
        self.trace(inc, "skeptic", {**sk, "final_verdict": verdict})
        if verdict == "BENIGN":
            inc["status"] = "suppressed"
            inc["headline"] = f"{svc} load explained by {', '.join(cal)} - suppressed"
            self.kpis["fp_avoided"] += 1
            self.publish("incident", {"id": inc["id"], "status": "suppressed"})
            return
        # Commander
        plan_versions = 1
        rca = await self._commander(inc, ctx, runbook, impact, sk, verdict, 1)
        if verdict == "DISPUTED":
            self.trace(inc, "plan_v2", "Skeptic disputed; re-plan with counter-evidence")
            plan_versions = 2
            rca = await self._commander(inc, ctx + f"\nSKEPTIC DISPUTE: {sk['counter_evidence']}", runbook, impact, sk, verdict, 2)
        rca["plan_versions"] = plan_versions
        inc["rca"] = rca
        inc["headline"], inc["severity"] = rca["headline"], rca["severity"]
        if inc["eta_min"] is not None and inc["eta_min"] > 0:
            self.kpis["pre_empted_today"] += 1
            self.kpis["leads"].append(float(inc["eta_min"]))
        # ticket + chat card
        inc["ticket"] = {"id": f"TCK-{inc['id']}", "title": rca["headline"], "severity": rca["severity"],
                         "owner": self.topo.owner(svc), "body": rca["summary_technical"], "status": "open"}
        inc["actions"].append({"type": "create_ticket", "mode": "AUTO", "status": "executed"})
        card = {"cardsV2": [{"cardId": inc["id"], "card": {"header": {"title": rca["headline"], "subtitle": f"{rca['severity']} | ETA {_r(inc['eta_min'])} min"},
                "sections": [{"widgets": [{"textParagraph": {"text": rca["summary_business"]}}]}]}}]}
        inc["chat_card"] = card
        hook = get_settings().chat_webhook_url
        if hook:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=5) as c:
                    await c.post(hook, json=card)
                inc["actions"].append({"type": "notify_channel", "mode": "AUTO", "status": "executed"})
            except Exception:  # noqa: BLE001
                pass
        self.trace(inc, "action", "create_ticket + notify_channel (AUTO)")
        # HITL actions via guard
        acts = list(rca["actions"])
        if code == "RC-BANK" and not any(a["type"] == "reroute_bank" for a in acts):
            acts.append({"type": "reroute_bank", "params": {"bank": seg.split("=")[-1], "rail": "RAAST"}, "rationale": "runbook"})
        for a in acts:
            g = self.guard(a)
            self.trace(inc, "guard", {"action": a["type"], **g})
            if g["mode"] == "HITL" and a["type"] == "reroute_bank":
                aid = "APR-" + uuid.uuid4().hex[:8]
                params = {k: v for k, v in a["params"].items() if v is not None}
                self.approvals[aid] = {"id": aid, "action": "reroute_bank", "params": params, "incident_id": inc["id"],
                                       "expires": time.time() + 600, "status": "pending"}
                self.publish("approval", {"id": aid, "incident_id": inc["id"], "params": params})
        self.publish("incident", {"id": inc["id"], "status": inc["status"]})

    async def _commander(self, inc, ctx, runbook, impact, sk, verdict, version) -> dict:
        try:
            schema = RCA.model_json_schema()
            out = await self._llm(self.smart, "You are the Incident Commander for NovaPay. Produce a grounded RCA. "
                                  f"incident_id must be {inc['id']}. impact.label='estimate'. generated_by='llm'. "
                                  "Only propose actions from the runbook; reroute_bank needs params.bank and rail RAAST.",
                                  f"{ctx}\nRUNBOOK:\n{runbook}\nIMPACT_ESTIMATE={json.dumps(impact)}\n"
                                  f"SKEPTIC={verdict} {sk['counter_evidence']}\nplan_version={version}", schema, "rca",
                                  timeout=float(_env("SENTINEL_COMMANDER_TIMEOUT_S", "45")))
            rca = RCA.model_validate(out).model_dump()
            rca["generated_by"] = "llm"
            self.trace(inc, "commander", f"plan v{version}: RCA via {self.smart}")
            return rca
        except Exception as e:  # noqa: BLE001
            self.trace(inc, "llm_error", f"commander v{version}: {type(e).__name__}; statistical fallback")
            return self.fallback_rca(inc, impact, sk, verdict, version)

    def fallback_rca(self, inc, impact, sk, verdict, version) -> dict:
        svc, seg, code = inc["service"], inc["segment"], inc["code"]
        bank = seg.split("=")[-1] if "bank=" in seg else None
        actions = [{"type": "create_ticket", "params": _params(service=svc), "rationale": "track incident"}]
        if code == "RC-BANK" and bank:
            actions.append({"type": "reroute_bank", "params": _params(bank=bank, rail="RAAST"), "rationale": "issuer timeouts; RAAST healthy"})
        rca = {"incident_id": inc["id"], "goal": f"Prevent {svc} SLO breach", "headline": f"{svc} {seg}: {code} predicted breach",
               "severity": "P1" if self.topo.tier(svc) == 0 else "P2", "root_cause_service": svc, "affected_segment": seg,
               "eta_minutes": _r(inc["eta_min"]),
               "hypotheses": [{"code": code, "confidence": 0.6, "statement": f"Utilisation trend matches {code}", "evidence_ids": [inc["key"]]}],
               "similar_incidents": [], "runbook_steps": [f"See runbook {code}"], "impact": impact, "actions": actions,
               "summary_technical": f"Holt trend {inc['trend']:.4f}/min on {svc} {seg}.",
               "summary_business": f"Est. PKR {impact['pkr_at_risk_per_min']:,.0f}/min at risk (estimate).",
               "comms_draft": {"in_app_banner": "Some payments may be slower than usual.", "bank_partner_note": f"Investigating elevated failures ({seg})."},
               "if_ignored": "SLO breach expected at ETA.", "skeptic": {"verdict": verdict, "confidence": sk.get("confidence", 0.5)},
               "plan_versions": version, "generated_by": "statistical-fallback", "low_confidence": True}
        return RCA.model_validate(rca).model_dump()

    def guard(self, a: dict) -> dict:
        t = a["type"]
        if t in FORBIDDEN:
            return {"mode": "DENY", "reason": "forbidden by policy"}
        if t == "reroute_bank":
            rail = (a.get("params") or {}).get("rail") or "RAAST"
            if not self.rail_healthy.get(rail, False):
                return {"mode": "DENY", "reason": f"target {rail} unhealthy"}
            return {"mode": "HITL", "reason": "customer-facing routing change needs approval"}
        if t in ("create_ticket", "notify_channel", "attach_rca_runbook", "page_oncall", "schedule_recheck", "send_reminder", "escalate"):
            return {"mode": "AUTO", "reason": "low risk"}
        return {"mode": "HITL", "reason": "default"}

    async def approve(self, aid: str, approve: bool) -> dict:
        a = self.approvals.get(aid)
        if a is None:
            raise KeyError(aid)
        if a["status"] != "pending":
            return {"conflict": True, "status": a["status"]}
        inc = self.incidents[a["incident_id"]]
        if not approve:
            a["status"] = "rejected"
            self.trace(inc, "action", f"{aid} rejected by human")
            self.publish("action", {"id": aid, "status": "rejected"})
            return {"id": aid, "status": "rejected"}
        a["status"] = "approved"
        bank = a["params"].get("bank", "BANK_C")
        self.bank_mode[bank] = "rerouted"
        inc["actions"].append({"type": "reroute_bank", "params": a["params"], "mode": "HITL", "status": "executed"})
        self.trace(inc, "action", f"reroute {bank} via RAAST executed (approved)")
        self.publish("action", {"id": aid, "status": "executed"})
        self.spawn(self._verify(inc, bank))
        return {"id": aid, "status": "executed"}

    async def _verify(self, inc, bank) -> None:
        for _ in range(30):
            await asyncio.sleep(1)
            if self.bank_sr[bank] >= 0.97:
                self.trace(inc, "verification", f"{bank} success_rate {self.bank_sr[bank]:.3f} >= 0.97: recovered")
                inc["status"] = "resolved"
                self.det.pop(f"PaymentGateway|bank={bank}", None)
                self.eta["PaymentGateway"] = None
                self.publish("incident", {"id": inc["id"], "status": "resolved"})
                return
        self.trace(inc, "verification", f"{bank} not recovered in 30 s")

    # -- scorecard
    def scorecard(self) -> dict:
        if self._scorecard is None:
            from sentinel.mvp.scorecard import compute

            self._scorecard = compute()
        return self._scorecard


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 1)


def _params(**kw: Any) -> dict:
    base = dict.fromkeys(["bank", "rail", "provider", "service", "instances", "change_id", "source_ids", "team",
                          "ttl_minutes", "delay_minutes"])
    base.update(kw)
    return base


ENGINE: Engine | None = None


def engine() -> Engine:
    global ENGINE
    if ENGINE is None:
        ENGINE = Engine()
    return ENGINE
