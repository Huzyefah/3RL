"""S3 = S2 + agents. Each S2 incident group on the TEST split is run through the agent runtime.

Outcome per group (FINAL_PLAN §7.2):
  CONFIRMED → page at the alert time · BENIGN (I2/I3 satisfied) → suppressed
  DISPUTED  → watch; re-check at +3 and +6 min (I4). Confirmed on a re-check → page at that time;
              otherwise escalated as a P3 ticket (not a page).
Pages = CONFIRMED (incl. on re-check). We also report "all escalations" = pages + P3 watch tickets.

    uv run python -m sentinel.eval.s3 --mode off     # deterministic (fallback agents), free, reproducible
    uv run python -m sentinel.eval.s3 --mode live    # gpt-6-luna Skeptic + Commander
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timedelta

import numpy as np

from sentinel.agents import tools as T
from sentinel.agents.runtime import run_incident
from sentinel.config import settings
from sentinel.datagen.generator import build
from sentinel.detect.engine import Signals, compute_signals, emit
from sentinel.detect.grouping import Grouper
from sentinel.eval import splits
from sentinel.eval.scorer import match, score
from sentinel.schemas import Candidate
from sentinel.topology import Topology

RECHECKS_MIN = (3, 6)


def _groups(sig: Signals, tau: float, topo: Topology):
    g = Grouper(topo)
    groups = {}
    for a in emit(sig, "S2", tau):
        c = Candidate(
            ts=a["ts"],
            service=a["service"],
            metric=a["metric"],
            segment_key=a["segment"],
            u=0.0,
            risk=a["risk"],
            eta_minutes=a["eta"],
        )
        inc, _ = g.add(c)
        groups.setdefault(inc.id, (inc, a))
    return list(groups.values())


def _last_signal(sig: Signals, ts: datetime) -> dict:
    j = sig.index.index(ts) if ts in sig.index else len(sig.index) - 1
    out = {}
    for a, k in enumerate(sig.keys):
        eta = sig.eta[a, j]
        out[k] = {
            "u": float(sig.u[a, j]),
            "pred": bool(sig.pred[a, j]),
            "eta": None if np.isnan(eta) else float(eta),
        }
    return out


async def _noop(_ev: dict) -> None:
    return None


async def _judge(ds, sig, inc, ts, mem, topo, mode) -> dict:
    ctx = T.ToolContext(ds=ds, now=ts, topo=topo, last_signal=_last_signal(sig, ts))
    return await run_incident(inc, ctx, mem, _noop, mode)


async def evaluate(mode: str, tau: float, concurrency: int = 6, split: str = "test") -> dict:
    ds = build("ps02")
    lo, hi = splits.PS02_TEST if split == "test" else splits.PS02_TRAIN
    sig = compute_signals(ds, lo, hi)
    topo = Topology.load()
    mem = T.Memory()  # train-split corpus only: test incidents are never recalled
    groups = _groups(sig, tau, topo)
    sem = asyncio.Semaphore(concurrency)

    async def one(inc, alert):
        async with sem:
            res = await _judge(ds, sig, inc, alert["ts"], mem, topo, mode)
            outcome, at, rechecks = None, alert["ts"], 0
            if res["status"] == "suppressed":
                outcome = "suppressed"
            elif res["verdict"] == "CONFIRMED":
                outcome = "page"
            else:  # DISPUTED → watch + re-checks (I4)
                outcome = "p3_watch"
                for dm in RECHECKS_MIN:
                    t2 = alert["ts"] + timedelta(minutes=dm)
                    if t2 >= hi:
                        break
                    rechecks += 1
                    r2 = await _judge(ds, sig, inc, t2, mem, topo, mode)
                    if r2["status"] == "suppressed":
                        outcome, res = "suppressed", r2
                        break
                    if r2["verdict"] == "CONFIRMED":
                        outcome, at, res = "page", t2, r2
                        break
            rca = res.get("rca") or {}
            hyps = rca.get("hypotheses") or [{}]
            return {
                "alert": alert,
                "group_root": inc.root_service,
                "outcome": outcome,
                "page_ts": at,
                "rechecks": rechecks,
                "verdict": res["verdict"],
                "top1_code": hyps[0].get("code"),
                "generated_by": rca.get("generated_by"),
                "tokens": res.get("tokens", 0),
                "grounded": all(e in rca.get("_known", e) for h in hyps for e in h.get("evidence_ids", [])),
            }

    results = await asyncio.gather(*(one(inc, a) for inc, a in groups))
    inc_gt = [e for e in ds.episodes if e.kind == "incident" and lo <= e.onset < hi]
    days = [lo + timedelta(days=k) for k in range((hi - lo).days)]
    platform_tps = sum(ds.tps.values())

    def gmv(ts):
        return float(platform_tps[ds.loc(ts)] * 60 * 3200.0)

    pages = [dict(r["alert"], ts=r["page_ts"]) for r in results if r["outcome"] == "page"]
    escal = pages + [r["alert"] for r in results if r["outcome"] == "p3_watch"]
    s3_pages = score(pages, inc_gt, days, gmv_per_min=gmv)
    s3_all = score(escal, inc_gt, days, gmv_per_min=gmv)
    s2 = score([a for _, a in groups], inc_gt, days, gmv_per_min=gmv)

    # RCA quality on groups matched to a ground-truth incident.
    m = match([r["alert"] for r in results], inc_gt)
    by_alert = {id(r["alert"]): r for r in results}
    code_hits, root_hits, n = 0, 0, 0
    for i in inc_gt:
        if i.id in m["first"]:
            r = by_alert[id(m["first"][i.id])]
            n += 1
            code_hits += r["top1_code"] == i.code
            root_hits += r["group_root"] == i.service or topo.linked(r["group_root"], i.service)
    # Skeptic-induced misses: incidents S2 detected that S3 pages no longer detect.
    s2m, s3m = match([a for _, a in groups], inc_gt), match(pages, inc_gt)
    skeptic_misses = [i.id for i in inc_gt if i.id in s2m["first"] and i.id not in s3m["first"]]
    fps_s2 = {id(a) for a in s2m["fps"]}
    suppressed_fp = sum(1 for r in results if r["outcome"] == "suppressed" and id(r["alert"]) in fps_s2)
    outcomes = {k: sum(r["outcome"] == k for r in results) for k in ("page", "p3_watch", "suppressed")}
    return {
        "mode": mode,
        "model": settings.openai_fast_model if mode == "live" else "deterministic fallback agents",
        "tau": tau,
        "groups": len(results),
        "outcomes": outcomes,
        "false_alarms_suppressed": suppressed_fp,
        "skeptic_induced_misses": skeptic_misses,
        "rca_top1_code_accuracy": round(code_hits / n, 3) if n else None,
        "root_service_accuracy": round(root_hits / n, 3) if n else None,
        "rca_generated_by": {
            g: sum(r["generated_by"] == g for r in results) for g in ("llm", "statistical-fallback", None)
        },
        "tokens_total": sum(r["tokens"] for r in results),
        "S2": {k: s2[k] for k in ("recall", "precision", "false_positives", "alerts", "lead_median")},
        "S3_pages": s3_pages,
        "S3_all_escalations": {
            k: s3_all[k] for k in ("recall", "precision", "false_positives", "alerts", "lead_median")
        },
        "per_group": [
            {
                "ts": r["alert"]["ts"],
                "service": r["alert"]["service"],
                "segment": r["alert"]["segment"],
                "outcome": r["outcome"],
                "verdict": r["verdict"],
                "top1": r["top1_code"],
                "rechecks": r["rechecks"],
            }
            for r in sorted(results, key=lambda r: r["alert"]["ts"])
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["off", "live"], default="off")
    ap.add_argument("--tau", type=float, default=None)
    ap.add_argument("--split", choices=["test", "train"], default="test")
    args = ap.parse_args()
    sc_path = settings.config_dir / "scorecard.json"
    sc = json.loads(sc_path.read_text())
    tau = args.tau if args.tau is not None else sc["tau"]
    res = asyncio.run(evaluate(args.mode, tau, split=args.split))
    res["split"] = args.split
    key = ("S3" if args.mode == "live" else "S3_deterministic") + ("" if args.split == "test" else "_train")
    sc.setdefault("agents", {})[key] = res
    sc_path.write_text(json.dumps(sc, indent=2, default=str))
    p = res["S3_pages"]
    print(
        json.dumps(
            {
                k: res[k]
                for k in (
                    "mode",
                    "groups",
                    "outcomes",
                    "false_alarms_suppressed",
                    "skeptic_induced_misses",
                    "rca_top1_code_accuracy",
                    "root_service_accuracy",
                    "tokens_total",
                )
            },
            indent=1,
            default=str,
        )
    )
    print(
        f"S2  : recall {res['S2']['recall']:.2f} precision {res['S2']['precision']:.2f} FP {res['S2']['false_positives']} alerts {res['S2']['alerts']} lead {res['S2']['lead_median']}"
    )
    print(
        f"S3p : recall {p['recall']:.2f} precision {p['precision'] or 0:.2f} FP {p['false_positives']} pages {p['alerts']} lead {p['lead_median']} "
        f"(non-abrupt {p['lead_median_non_abrupt']}, %>0 {p['pct_lead_gt0_non_abrupt']}) PKR {p['pkr_protected_est']:,}"
    )
    a = res["S3_all_escalations"]
    print(
        f"S3+P3: recall {a['recall']:.2f} precision {a['precision'] or 0:.2f} FP {a['false_positives']} escalations {a['alerts']}"
    )


if __name__ == "__main__":
    main()
