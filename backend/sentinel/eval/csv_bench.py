"""B0/B1 rule baselines on the raw 500 PS-02 rows (D3: the 7 PS-02 metric series only)."""

import csv
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from sentinel.eval.splits import split_of
from sentinel.schemas import ScorecardRow
from sentinel.utilisation import utilisation

DEFAULT_CSV = Path(__file__).resolve().parents[3] / "data" / "ps02_system_telemetry.csv"
PS02_METRICS = frozenset(
    {
        "cpu_usage",
        "memory_usage",
        "disk_io",
        "latency_p99",
        "error_rate",
        "queue_depth",
        "connection_pool",
    }
)
RULES: dict[str, float] = {"B0": 1.0, "B1": 0.95}  # alert iff u >= cut


def _row(system: str, split: str, tp: int, fp: int, fn: int) -> ScorecardRow:
    return ScorecardRow(
        system=system,
        split=split,
        tp=tp,
        fp=fp,
        fn=fn,
        precision=tp / (tp + fp) if tp + fp else None,
        recall=tp / (tp + fn) if tp + fn else None,
        notes="raw 500 rows, PS-02 metrics only; alert iff u >= cut",
    )


def score_rows(rows: Iterable[dict[str, Any]], split: str = "all") -> list[ScorecardRow]:
    keep: Callable[[str], bool] = lambda ts: split == "all" or split_of(ts) == split  # noqa: E731
    sel = [r for r in rows if r["metric_type"] in PS02_METRICS and keep(r["timestamp"])]
    out = []
    for name, cut in RULES.items():
        tp = fp = fn = 0
        for r in sel:
            u = utilisation(float(r["value"]), float(r["threshold"]), "higher_bad")
            alert, inc = u >= cut, int(r["is_incident"]) == 1
            tp += alert and inc
            fp += alert and not inc
            fn += inc and not alert
        out.append(_row(name, split, tp, fp, fn))
    return out


def csv_bench(path: Path | str = DEFAULT_CSV, split: str = "all") -> list[ScorecardRow]:
    if split not in ("all", "train", "test"):
        raise ValueError(f"split must be all|train|test, got {split!r}")
    with Path(path).open(newline="") as f:
        return score_rows(csv.DictReader(f), split)
