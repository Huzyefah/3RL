"""Ablation B0 → S2 on the ps02 split (S3 / S3−Sk are added once agents exist, phase 4).

    uv run python -m sentinel.eval.ablation --configs B0,B1,S1,S2 --out ../analysis/outputs/scorecard.json

τ is tuned on the TRAIN split only (grid, maximise F2 then median lead) and then frozen for the TEST report.
F2 (recall-weighted) because S2 only proposes candidates: the Skeptic (S3) removes false alarms downstream,
but nothing can recover an incident S2 missed.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from sentinel.config import REPO_ROOT
from sentinel.datagen.generator import build
from sentinel.detect.engine import compute_signals, emit
from sentinel.detect.grouping import group_alerts
from sentinel.detect.risk import W
from sentinel.eval import splits
from sentinel.eval.csv_bench import run_bench
from sentinel.eval.scorer import match, score

TAU_GRID = [round(x, 2) for x in np.arange(0.30, 0.86, 0.05)]


def _incidents(ds, lo: datetime, hi: datetime) -> list:
    return [e for e in ds.episodes if e.kind == "incident" and lo <= e.onset < hi]


def _alerts(sig, config: str, tau: float) -> list[dict]:
    al = emit(sig, config, tau)
    return group_alerts(al) if config == "S2" else al


def tune_tau(ds) -> tuple[float, list[dict]]:
    sig = compute_signals(ds, *splits.PS02_TRAIN)
    inc = _incidents(ds, *splits.PS02_TRAIN)
    rows = []
    for tau in TAU_GRID:
        m = match(_alerts(sig, "S2", tau), inc)
        tp, fp = len(m["first"]), len(m["fps"])
        rec, prec = tp / len(inc), tp / (tp + fp) if tp + fp else 0.0
        f2 = 5 * rec * prec / (4 * prec + rec) if rec + prec else 0.0
        leads = [(i.onset - m["first"][i.id]["ts"]).total_seconds() / 60 for i in inc if i.id in m["first"]]
        rows.append(
            {
                "tau": tau,
                "f2": round(f2, 4),
                "recall": rec,
                "precision": prec,
                "fp": fp,
                "lead_median": float(np.median(leads)) if leads else 0.0,
            }
        )
    best = max(rows, key=lambda r: (r["f2"], r["lead_median"]))
    return best["tau"], rows


def run(configs: list[str], seed: int = 7) -> dict:
    ds = build("ps02", seed)
    tau, grid = tune_tau(ds)
    lo, hi = splits.PS02_TEST
    sig = compute_signals(ds, lo, hi)
    inc = _incidents(ds, lo, hi)
    days = sorted({d for d in (lo + timedelta(days=k) for k in range((hi - lo).days)) if d < hi})
    platform_tps = sum(ds.tps.values())

    def gmv_per_min(ts):
        return float(platform_tps[ds.loc(ts)] * 60 * 3200.0)

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "ps02",
        "seed": seed,
        "splits": splits.describe(),
        "test_window": [lo.isoformat(), hi.isoformat()],
        "test_incidents": len(inc),
        "test_hard_negatives": sum(1 for e in ds.episodes if e.kind == "negative" and lo <= e.onset < hi),
        "tau": tau,
        "tau_grid_train": grid,
        "risk_weights": W,
        "csv_bench": run_bench(),
        "configs": {},
    }
    for cfg in configs:
        alerts = _alerts(sig, cfg, tau)
        out["configs"][cfg] = score(alerts, inc, days, gmv_per_min=gmv_per_min)
    b1 = out["configs"].get("B1", {}).get("alerts")
    for cfg, r in out["configs"].items():
        r["pages_avoided_vs_B1"] = (b1 - r["alerts"]) if b1 is not None else None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="B0,B1,S1,S2")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "analysis" / "outputs" / "scorecard.json")
    args = ap.parse_args()
    res = run(args.configs.split(","))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2, default=str))
    for cfg, r in res["configs"].items():
        print(
            f"{cfg:>3}  recall {r['recall']:.2f}  precision {r['precision'] or 0:.2f}  FP {r['false_positives']:>3}  "
            f"lead median {r['lead_median']}  alerts {r['alerts']}  PKR protected {r['pkr_protected_est']:,}"
        )
    print("tau (train-tuned):", res["tau"])


if __name__ == "__main__":
    main()
