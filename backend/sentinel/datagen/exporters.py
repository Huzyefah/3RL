"""Dataset exporters: parquet (exact roundtrip), metrics CSV, compact frontend JSON fixture."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from sentinel.datagen.types import Dataset, GroundTruthEpisode

_META = "meta.json"
_GT_DT = ("precursor_start", "onset", "end")


def _gt_to_json(e: GroundTruthEpisode) -> dict[str, Any]:
    d = asdict(e)
    for k in _GT_DT:
        d[k] = d[k].isoformat()
    d["benign_evidence"] = list(d["benign_evidence"])
    return d


def _gt_from_json(d: dict[str, Any]) -> GroundTruthEpisode:
    d = dict(d)
    for k in _GT_DT:
        d[k] = datetime.fromisoformat(d[k])
    d["benign_evidence"] = tuple(d["benign_evidence"])
    return GroundTruthEpisode(**d)


def to_parquet(ds: Dataset, dir: str | Path) -> None:
    out = Path(dir)
    out.mkdir(parents=True, exist_ok=True)
    ds.metrics.to_parquet(out / "metrics.parquet", index=False)
    ds.logs.to_parquet(out / "logs.parquet", index=False)
    ds.events.to_parquet(out / "events.parquet", index=False)
    meta = {
        "mode": ds.mode,
        "seed": ds.seed,
        "window": [ds.window[0].isoformat(), ds.window[1].isoformat()],
        "ground_truth": [_gt_to_json(e) for e in ds.ground_truth],
    }
    (out / _META).write_text(json.dumps(meta, indent=1))


def from_parquet(dir: str | Path) -> Dataset:
    src = Path(dir)
    meta = json.loads((src / _META).read_text())
    return Dataset(
        mode=meta["mode"],
        seed=meta["seed"],
        window=(
            datetime.fromisoformat(meta["window"][0]),
            datetime.fromisoformat(meta["window"][1]),
        ),
        metrics=pd.read_parquet(src / "metrics.parquet"),
        logs=pd.read_parquet(src / "logs.parquet"),
        events=pd.read_parquet(src / "events.parquet"),
        ground_truth=[_gt_from_json(d) for d in meta["ground_truth"]],
    )


def to_csv_metrics(ds: Dataset, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ds.metrics.to_csv(p, index=False)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    out = df.copy()
    out["ts"] = out["ts"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    return json.loads(out.to_json(orient="records") or "[]")


def to_json_fixture(
    ds: Dataset, episode_id: str, path: str | Path, lead_in_min: int = 90, tail_min: int = 30
) -> None:
    """Compact JSON of the replay window of one ground-truth episode (same bounds as Replayer)."""
    ep = ds.episode(episode_id)
    lo = ep.precursor_start - timedelta(minutes=lead_in_min)
    hi = ep.end + timedelta(minutes=tail_min)

    def win(df: pd.DataFrame) -> pd.DataFrame:
        return df.loc[(df["ts"] >= lo) & (df["ts"] <= hi)].copy()

    doc = {
        "episode": _gt_to_json(ep),
        "window": [lo.isoformat(), hi.isoformat()],
        "metrics": _records(win(ds.metrics)),
        "logs": _records(win(ds.logs)),
        "events": _records(win(ds.events)),
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, separators=(",", ":")))
