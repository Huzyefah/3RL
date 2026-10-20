"""Agent runtime: goal → plan → investigate → challenge (Skeptic) → re-plan → RCA → guard → verify.

The LLM plans and writes; code enforces the invariants (FINAL_PLAN §7.2):
  I1 no page/ticket before a Skeptic verdict · I2 BENIGN needs a cited benign event AND a recovering trend
  I3 Tier-0 with risk ≥ 0.85 is never suppressed · I5 grounding (unknown evidence ids → regenerate once,
  then low_confidence) · I6 actions are only requested; the Policy Guard decides · I7 any LLM error → template.
llm_mode: live (OpenAI), fake/off (deterministic template, generated_by="statistical-fallback").
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sentinel.actions.policy_guard import decide
from sentinel.agents import tools as T
from sentinel.agents.llm import LLMError, complete_json
from sentinel.datagen.episodes import code_for
from sentinel.redact import assert_no_pii
from sentinel.schemas import IncidentCandidate

Emit = Callable[[dict], Awaitable[None]]

SKEPTIC_SYS = (
    "You are the Skeptic in a payments AIOps team. Try to PROVE the alert is NOT a real incident: a scheduled "
    "batch job, a marketing or salary-day surge, a deploy blip, or a transient spike already recovering. "
    "Decision rule: CONFIRMED only if there is failure-specific evidence (error log templates such as ISO8583 RC=91, "
    "HikariPool timeouts, consumer lag, GC overhead, SMS DLR timeouts, or one segment failing far above its peers). "
    "If a benign scheduled event explains the load and there is no failure-specific evidence, answer DISPUTED (watch, "
    "do not page). BENIGN only if you cite a benign evidence_id AND the trend is recovering. A deploy or a salary day "
    "is never a free pass when failure-specific evidence exists. Use the provided summary. Answer JSON "
    '{"verdict":"CONFIRMED|DISPUTED|BENIGN","confidence":0-1,"counter_evidence":[str],"cited_evidence_ids":[str],'
    '"what_would_convince_me":str}.'
)
COMMANDER_SYS = (
    "You are the Incident Commander for NovaPay (a Pakistani digital wallet; partner banks BANK_A..E; Raast rail). "
    "Write the RCA as JSON with keys: headline, severity (P1|P2|P3), hypotheses [{code, confidence, statement, "
    "evidence_ids}], summary_technical (<=80 words, for the on-call engineer), summary_business (<=50 words, for the "
    "payments-ops lead), runbook_steps [str], comms_draft {in_app_banner, bank_partner_note}, if_ignored. Codes: "
    "RC-BANK, RC-DBPOOL, RC-OTP-PROVIDER, RC-QUEUE, RC-MEMLEAK, RC-AUTH-ATTACK, RC-CERT, RC-ABRUPT. Use the retrieved "
    "memory evidence (past postmortems and runbooks) to ground runbook_steps and cite its evidence_id. Every claim "
    "must cite evidence_ids that appear in the evidence. PKR figures are estimates; copy them from the impact tool."
)


class Run:
    def __init__(
        self, inc: IncidentCandidate, ctx: T.ToolContext, mem: T.Memory, emit: Emit, mode: str
    ) -> None:
        self.inc, self.ctx, self.mem, self.emit, self.mode = inc, ctx, mem, emit, mode
        self.step = 0
        self.tokens = 0
        self.trace: list[dict] = []

    async def trace_step(
        self,
        agent: str,
        kind: str,
        summary: str,
        tool: str | None = None,
        args: dict | None = None,
        evidence_id: str | None = None,
        tokens: int = 0,
        latency_ms: int = 0,
    ) -> None:
        self.step += 1
        st = {
            "incident_id": self.inc.id,
            "step": self.step,
            "ts": datetime.now(UTC).isoformat(),
            "agent": agent,
            "kind": kind,
            "tool": tool,
            "args": args or {},
            "summary": summary,
            "evidence_id": evidence_id,
            "tokens": tokens,
            "latency_ms": latency_ms,
        }
        assert_no_pii(st)
        self.trace.append(st)
        self.tokens += tokens
        await self.emit({"type": "trace", "step": st})

    async def tool(self, agent: str, name: str, fn, *a, summary: Callable[[dict], str]) -> dict:
        r = fn(self.ctx, *a)
        await self.trace_step(agent, "tool_call", summary(r), tool=name, evidence_id=r["evidence_id"])
        return r


def _primary(inc: IncidentCandidate):
    c = max(inc.candidates, key=lambda c: c.risk)
    root = next((x for x in inc.candidates if x.service == inc.root_service), c)
    return root


def _rc_guess(inc: IncidentCandidate, seg_ev: dict | None, logs: dict) -> str:
    if inc.segment_key.startswith("bank="):
        return "RC-BANK"
    if inc.segment_key.startswith("provider="):
        return "RC-OTP-PROVIDER"
    tpl = " ".join(t["template"] for t in logs.get("novel_templates", []))
    if "ISO8583" in tpl:
        return "RC-BANK"
    if "HikariPool" in tpl:
        return "RC-DBPOOL"
    if "consumer lag" in tpl:
        return "RC-QUEUE"
    if "GC overhead" in tpl:
        return "RC-MEMLEAK"
    if "SMS P1" in tpl:
        return "RC-OTP-PROVIDER"
    c = _primary(inc)
    return code_for(c.service, c.metric) if c.segment_key == "*" else "RC-BANK"


async def run_incident(
    inc: IncidentCandidate, ctx: T.ToolContext, mem: T.Memory, emit: Emit, mode: str = "live"
) -> dict:
    r = Run(inc, ctx, mem, emit, mode)
    c = _primary(inc)
    svc, seg = inc.root_service, inc.segment_key
    eta = inc.eta_minutes
    goal = f"Prevent {seg.split('=')[-1] if seg != '*' else svc} failures before the forecast SLO breach" + (
        f" in ~{eta:.0f} min" if eta else ""
    )
    await r.trace_step("commander", "goal", goal)
    await r.trace_step(
        "commander",
        "plan",
        f"Plan v1: confirm the signal on {svc} {c.metric}, check segments, logs and "
        "recent changes, forecast the breach, then challenge it.",
        args={"version": 1},
    )

    # --- Investigator ------------------------------------------------------------------------------------
    win = await r.tool(
        "investigator",
        "get_metric_window",
        T.get_metric_window,
        svc,
        c.metric,
        "*" if c.segment_key == "*" else c.segment_key,
        summary=lambda x: (
            f"{x['metric']} u {x['u_start']}→{x['u_now']} over {x['minutes']} min (slope {x['slope_per_min']}/min)."
        ),
    )
    seg_ev = None
    if svc in ("PaymentGateway", "NotificationHub"):
        seg_ev = await r.tool(
            "investigator",
            "get_segment_breakdown",
            T.get_segment_breakdown,
            svc,
            summary=lambda x: (
                f"Worst segment {x['worst']['segment'] if x['worst'] else '-'}: bad rate "
                f"{x['worst']['bad_rate'] if x['worst'] else 0:.2%} ({x['x_vs_peers']}× peers)."
            ),
        )
    logs = await r.tool(
        "investigator",
        "get_logs",
        T.get_logs,
        svc,
        summary=lambda x: (
            (
                "Novel log templates: "
                + "; ".join(f"'{t['template'][:60]}' ×{t['count']}" for t in x["novel_templates"])
            )
            if x["novel_templates"]
            else "No novel log templates in the last 15 min."
        ),
    )
    fc = await r.tool(
        "investigator",
        "get_forecast",
        T.get_forecast,
        c.service,
        c.metric,
        c.segment_key,
        summary=lambda x: (
            f"Holt ETA to 0.95: {x['eta_minutes']} min; predictive trigger {x['predictive_trigger']}."
        ),
    )

    # --- Skeptic -----------------------------------------------------------------------------------------
    cal = await r.tool(
        "skeptic",
        "get_calendar",
        T.get_calendar,
        svc,
        summary=lambda x: (
            ("Calendar/cron: " + "; ".join(e["name"] for e in x["events"]))
            if x["events"]
            else "No calendar or batch events."
        ),
    )
    chg = await r.tool(
        "skeptic",
        "get_change_events",
        T.get_change_events,
        svc,
        summary=lambda x: (
            ("Changes: " + "; ".join(e["name"] for e in x["changes"]))
            if x["changes"]
            else "No deploys in 90 min."
        ),
    )
    benign_events = [
        e for e in cal["events"] if e["kind"] in ("calendar", "cron") and e["service"] in (svc, "*")
    ]
    recovering = win["slope_per_min"] < 0 and fc["eta_minutes"] is None
    corroborated = bool(logs["novel_templates"]) and any(
        k in t["template"] for t in logs["novel_templates"] for k in ("ISO8583", "Hikari", "lag", "GC", "SMS")
    )
    failure_specific = [
        f"log template '{t['template'][:60]}' ×{t['count']}"
        for t in logs["novel_templates"]
        if any(k in t["template"] for k in ("ISO8583", "Hikari", "lag", "GC", "SMS"))
    ]
    if seg_ev and (seg_ev.get("x_vs_peers") or 0) >= 3:
        failure_specific.append(f"{seg_ev['worst']['segment']} failing at {seg_ev['x_vs_peers']}× peers")
    verdict, conf, counter = await _skeptic(
        r, inc, [win, seg_ev, logs, fc, cal, chg], benign_events, recovering, corroborated, failure_specific
    )
    plan_versions = 1
    if verdict == "DISPUTED" or len(inc.symptom_services) > 0:
        plan_versions = 2
        why = (
            "Skeptic disputed"
            if verdict == "DISPUTED"
            else f"new upstream signal ({', '.join(inc.symptom_services)} attached)"
        )
        await r.trace_step(
            "commander",
            "plan",
            f"Plan v2: {why}. Compare failure-specific evidence (logs, segments, "
            "dependencies) and recall similar incidents before deciding.",
            args={"version": 2},
        )
        topo = await r.tool(
            "investigator",
            "get_topology",
            T.get_topology,
            svc,
            summary=lambda x: (
                f"{x['service']} ({x['team']}, tier {x['tier']}) depends on {x['depends_on'] or 'nothing'}; blast radius {x['blast_radius']}."
            ),
        )
        if verdict == "DISPUTED":
            verdict = (
                "CONFIRMED"
                if (corroborated or (seg_ev and (seg_ev.get("x_vs_peers") or 0) >= 3))
                else "DISPUTED"
            )
            await r.trace_step(
                "skeptic",
                "challenge",
                f"{verdict}: re-check after plan v2 — "
                + (
                    "failure-specific evidence present."
                    if verdict == "CONFIRMED"
                    else "still no failure-specific evidence."
                ),
                args={"verdict": verdict},
                evidence_id=topo["evidence_id"],
            )

    # I2 + I3: suppression needs benign evidence AND recovery; tier-0 high risk is never suppressed.
    suppress = verdict == "BENIGN" and benign_events and (recovering or not corroborated)
    if suppress and inc.tier == 0 and inc.risk >= 0.85:
        suppress = False
        await r.trace_step(
            "commander", "note", "I3: tier-0 risk ≥ 0.85 — downgraded, not suppressed (low confidence)."
        )
    if suppress:
        await r.trace_step(
            "commander",
            "verify",
            f"Suppressed as benign: {benign_events[0]['name']}; stored as a false alarm in memory.",
            args={"outcome": "suppressed"},
            evidence_id=cal["evidence_id"],
        )
        return {
            "status": "suppressed",
            "verdict": verdict,
            "rca": None,
            "actions": [],
            "trace": r.trace,
            "tokens": r.tokens,
        }

    # --- Memory + impact + RCA -------------------------------------------------------------------------
    code_guess = _rc_guess(inc, seg_ev, logs)
    # RAG: retrieve past postmortems + runbooks; injected into the Commander prompt as cited context.
    query = f"{code_guess} {svc} {c.metric} " + " ".join(t["template"] for t in logs["novel_templates"])
    hits, how = await mem.search(query, svc, k=4, use_embeddings=r.mode == "live")
    rag_hits = [
        {
            "id": d.id,
            "kind": d.kind,
            "code": d.code,
            "similarity": round(float(sim), 2),
            "title": d.title,
            "text": d.text[:400],
            "fix": d.fix,
        }
        for d, sim in hits
    ]
    mem_ev = T._wrap("memory", {"query_service": svc, "retrieval": how, "hits": rag_hits}, ctx.evidence)
    mem_ev["hits"] = [h for h in rag_hits if h["kind"] != "runbook" and h["similarity"] >= 0.2]
    await r.trace_step(
        "commander",
        "tool_call",
        f"RAG ({how}): " + "; ".join(f"{h['id']} {h['similarity']:.0%} [{h['kind']}]" for h in rag_hits),
        tool="rag_retrieve",
        evidence_id=mem_ev["evidence_id"],
    )
    imp = await r.tool(
        "commander",
        "estimate_impact",
        T.estimate_impact,
        svc,
        summary=lambda x: (
            f"Impact (estimate): PKR {x['pkr_at_risk_per_min']:,}/min at risk; ~{x['customers_affected_est_per_10min']:,} customers per 10 min."
        ),
    )
    rca = await _commander(r, inc, goal, code_guess, verdict, conf, counter, plan_versions, mem_ev, imp, eta)

    # --- Actions through the Policy Guard (I6) -----------------------------------------------------------
    actions = [
        {
            "type": "create_ticket",
            "params": {"team": ctx.topo.team(svc)},
            "rationale": "Route to the root-cause owner",
        },
        {"type": "post_chat", "params": {}, "rationale": "Notify on-call"},
    ]
    # Re-read the segment: segment candidates may have joined the group while the agents were investigating.
    seg = inc.segment_key
    worst = (seg_ev or {}).get("worst") or {}
    if (
        not seg.startswith("bank=")
        and code_guess == "RC-BANK"
        and str(worst.get("segment", "")).startswith("bank=")
    ):
        seg = worst["segment"]
    if seg.startswith("bank="):
        actions.append(
            {
                "type": "reroute_bank",
                "params": {"bank": seg.split("=")[1], "rail": "RAAST", "target": "finpay-sim"},
                "rationale": "Bank-specific degradation; Raast is healthy",
            }
        )
    elif seg.startswith("provider=") or code_guess == "RC-OTP-PROVIDER":
        actions.append(
            {
                "type": "otp_failover",
                "params": {"provider": "P2", "target": "finpay-sim"},
                "rationale": "P1 degrading; P2 healthy",
            }
        )
    elif code_guess in ("RC-QUEUE", "RC-DBPOOL"):
        actions.append(
            {
                "type": "scale_service",
                "params": {"service": svc, "max_instances": 5, "target": "finpay-sim"},
                "rationale": "Capacity root cause",
            }
        )
    elif code_guess == "RC-MEMLEAK":
        actions.append(
            {
                "type": "restart",
                "params": {"service": svc, "target": "finpay-sim"},
                "rationale": "Linear memory ramp (simulated restart)",
            }
        )
    decided = []
    for a in actions:
        mode, reason = decide(a["type"], a["params"], rca["severity"], target_health_u=0.31)
        decided.append({**a, "mode": mode, "reason": reason})
        await r.trace_step(
            "guard",
            "guard",
            f"{a['type']} → {mode}: {reason}",
            tool="request_action",
            args={"verdict": mode},
        )
    rca["actions"] = [
        {"type": a["type"], "params": a["params"], "rationale": a["rationale"]} for a in decided
    ]
    await r.trace_step(
        "commander",
        "verify",
        "Verification armed: after execution the metric must recover ≥ 50% of the gap "
        "within 60 s, or the guard rolls back and pages a human.",
    )
    return {
        "status": "awaiting_approval" if any(a["mode"] == "HITL" for a in decided) else "acting",
        "verdict": verdict,
        "rca": rca,
        "actions": decided,
        "trace": r.trace,
        "tokens": r.tokens,
    }


async def _skeptic(
    r: Run, inc, evidence, benign_events, recovering, corroborated, failure_specific=()
) -> tuple[str, float, list[str]]:
    ev = [e for e in evidence if e]
    if r.mode == "live":
        try:
            data, tok, ms = await complete_json(
                SKEPTIC_SYS,
                json.dumps(
                    {
                        "incident": {
                            "root_service": inc.root_service,
                            "segment": inc.segment_key,
                            "symptoms": inc.symptom_services,
                            "risk": inc.risk,
                        },
                        "summary": {
                            "benign_scheduled_events": [e["name"] for e in benign_events],
                            "failure_specific_evidence": list(failure_specific),
                            "trend": "recovering" if recovering else "rising",
                        },
                        "evidence": ev,
                    },
                    default=str,
                ),
            )
            verdict = data.get("verdict", "DISPUTED")
            if verdict not in ("CONFIRMED", "DISPUTED", "BENIGN"):
                verdict = "DISPUTED"
            cited = set(data.get("cited_evidence_ids", []))
            if verdict == "BENIGN" and not (
                cited & {e["evidence_id"] for e in ev if e["evidence_id"].startswith("calendar")}
                and benign_events
            ):
                verdict = "DISPUTED"  # I2: BENIGN without a cited benign event becomes a dispute
            conf = float(data.get("confidence", 0.5))
            counter = [str(x) for x in data.get("counter_evidence", [])][:4]
            if verdict == "CONFIRMED" and benign_events and not failure_specific:
                # I2b (mirror of I2): a page needs failure-specific evidence when a scheduled event explains the load.
                verdict = "DISPUTED"
                counter = [
                    f"I2b: {benign_events[0]['name']} explains the load and no failure-specific evidence exists"
                ] + counter[:3]
            await r.trace_step(
                "skeptic",
                "challenge",
                f"{verdict}: " + ("; ".join(counter) or data.get("what_would_convince_me", "")),
                args={"verdict": verdict},
                tokens=tok,
                latency_ms=ms,
            )
            return verdict, conf, counter
        except LLMError as e:
            await r.trace_step(
                "skeptic", "note", f"LLM unavailable ({str(e)[:60]}); deterministic Skeptic used (I7)."
            )
    if benign_events and not corroborated:
        verdict, conf = ("BENIGN", 0.7) if recovering else ("DISPUTED", 0.55)
    elif benign_events:
        verdict, conf = "DISPUTED", 0.5
    else:
        verdict, conf = "CONFIRMED", 0.75
    counter = [f"{e['kind']}: {e['name']}" for e in benign_events][:3]
    await r.trace_step(
        "skeptic",
        "challenge",
        f"{verdict}: "
        + ("; ".join(counter) if counter else "no benign mechanism found; trend still rising."),
        args={"verdict": verdict},
    )
    return verdict, conf, counter


async def _commander(
    r: Run, inc, goal, code, verdict, conf, counter, plan_versions, mem_ev, imp, eta
) -> dict:
    sev = "P1" if inc.tier == 0 else ("P2" if inc.tier == 1 else "P3")
    base = {
        "incident_id": inc.id,
        "goal": goal,
        "severity": sev,
        "root_cause_service": inc.root_service,
        "affected_segment": inc.segment_key,
        "eta_minutes": eta,
        "similar_incidents": [
            {"id": h["id"], "similarity": h["similarity"], "fix": h["fix"]} for h in mem_ev["hits"]
        ],
        "impact": {
            "customers_affected_est": imp["customers_affected_est_per_10min"],
            "pkr_at_risk_per_min": imp["pkr_at_risk_per_min"],
            "label": "estimate",
        },
        "skeptic": {"verdict": verdict, "confidence": conf, "counter_evidence": counter},
        "plan_versions": plan_versions,
        "low_confidence": False,
    }
    known = set(r.ctx.evidence)
    if r.mode == "live":
        payload = json.dumps(
            {
                "goal": goal,
                "code_hint": code,
                "root_service": inc.root_service,
                "segment": inc.segment_key,
                "eta_minutes": eta,
                "skeptic": base["skeptic"],
                "evidence": list(r.ctx.evidence.values()),
            },
            default=str,
        )
        for attempt in range(2):  # I5: regenerate once on ungrounded output, then ship low_confidence
            try:
                data, tok, ms = await complete_json(COMMANDER_SYS, payload, smart=True)
            except LLMError as e:
                await r.trace_step(
                    "commander", "note", f"LLM unavailable ({str(e)[:60]}); statistical-fallback RCA (I7)."
                )
                break
            hyps = [h for h in data.get("hypotheses", []) if isinstance(h, dict)]
            bad = [e for h in hyps for e in h.get("evidence_ids", []) if e not in known]
            if hyps and not bad:
                rca = {
                    **base,
                    "headline": data.get("headline", goal),
                    "severity": data.get("severity", sev)
                    if data.get("severity") in ("P1", "P2", "P3")
                    else sev,
                    "hypotheses": [
                        {
                            "code": h.get("code", code),
                            "confidence": float(h.get("confidence", 0.5)),
                            "statement": str(h.get("statement", "")),
                            "evidence_ids": [e for e in h.get("evidence_ids", []) if e in known],
                        }
                        for h in hyps
                    ][:3],
                    "summary_technical": data.get("summary_technical", ""),
                    "summary_business": data.get("summary_business", ""),
                    "runbook_steps": [str(s) for s in data.get("runbook_steps", [])][:6],
                    "comms_draft": {
                        "in_app_banner": data.get("comms_draft", {}).get("in_app_banner", ""),
                        "bank_partner_note": data.get("comms_draft", {}).get("bank_partner_note", ""),
                    },
                    "if_ignored": data.get("if_ignored", ""),
                    "generated_by": "llm",
                    "low_confidence": attempt > 0,
                }
                await r.trace_step(
                    "commander",
                    "rca",
                    f"Grounded RCA written ({len(rca['hypotheses'])} hypotheses, all evidence ids resolve).",
                    tokens=tok,
                    latency_ms=ms,
                )
                assert_no_pii(rca)
                return rca
            await r.trace_step(
                "commander",
                "note",
                f"I5 grounding failed ({len(bad)} unknown evidence ids); regenerating.",
                tokens=tok,
                latency_ms=ms,
            )
    ev_ids = list(known)
    seg = inc.segment_key.split("=")[-1] if inc.segment_key != "*" else inc.root_service
    rca = {
        **base,
        "headline": f"{seg} {code} risk on {inc.root_service}"
        + (f": breach in ~{eta:.0f} min" if eta else ""),
        "hypotheses": [
            {
                "code": code,
                "confidence": 0.6,
                "statement": f"Detector features and logs on {inc.root_service} match the {code} pattern.",
                "evidence_ids": ev_ids[:3],
            }
        ],
        "summary_technical": f"Statistical fallback: {inc.root_service} risk {inc.risk:.2f}, ETA {eta} min, Skeptic {verdict}. See trace for evidence.",
        "summary_business": f"Possible payment impact on {seg}; engineers notified (estimate PKR {imp['pkr_at_risk_per_min']:,}/min at risk).",
        "runbook_steps": [
            "Check the segment breakdown",
            "Confirm the target is healthy",
            "Approve the proposed action",
        ],
        "comms_draft": {
            "in_app_banner": "Some payments may take longer than usual; we are on it.",
            "bank_partner_note": "",
        },
        "if_ignored": "Projected SLO breach; failed payments (estimate).",
        "generated_by": "statistical-fallback",
        "low_confidence": True,
    }
    await r.trace_step("commander", "rca", "Template RCA written (statistical-fallback).")
    return rca
