"""Sanity gate 1: static-rule baselines on the raw 500 PS-02 rows.

`python -m sentinel.eval.csv_bench [--out DIR]` writes rule_baselines.csv and csv_bench.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from sentinel.config import REPO_ROOT, settings
from sentinel.schemas import band, utilisation

RULES = {"B0": 1.0, "B1": 0.95}


def load_ps02(path: Path | None = None) -> pd.DataFrame:
    df = pd.read_csv(path or settings.ps02_csv_path, parse_dates=["timestamp"])
    df["u"] = [utilisation(v, t, "higher_bad") for v, t in zip(df["value"], df["threshold"])]
    return df


def run_bench(path: Path | None = None) -> dict:
    df = load_ps02(path)
    truth = df["is_incident"] == 1
    out: dict = {
        "rows": len(df),
        "incidents": int(truth.sum()),
        "band_mismatches": int((df["u"].map(band) != df["alert_level"]).sum()),
    }
    for name, cut in RULES.items():
        alert = df["u"] >= cut
        tp = int((alert & truth).sum())
        fp = int((alert & ~truth).sum())
        fn = int((~alert & truth).sum())
        out[name] = {
            "rule": f"u >= {cut}",
            "alerts": int(alert.sum()),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "analysis" / "outputs")
    args = ap.parse_args()
    res = run_bench()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = [{"config": k, **v} for k, v in res.items() if k in RULES]
    pd.DataFrame(rows).to_csv(args.out / "rule_baselines.csv", index=False)
    (args.out / "csv_bench.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
