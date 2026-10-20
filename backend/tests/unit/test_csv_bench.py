import csv
from pathlib import Path

import pytest

from sentinel.eval.csv_bench import DEFAULT_CSV, csv_bench, score_rows

ROOT = Path(__file__).resolve().parents[3]


def by_system(rows):
    return {r.system: r for r in rows}


@pytest.mark.unit
def test_csv_bench_matches_eda() -> None:
    all_ = by_system(csv_bench(split="all"))
    assert (all_["B0"].tp, all_["B0"].fp, all_["B0"].fn) == (0, 0, 28)
    assert (all_["B1"].tp, all_["B1"].fp, all_["B1"].fn) == (28, 22, 0)
    assert all_["B1"].precision == pytest.approx(0.56)
    assert all_["B1"].recall == pytest.approx(1.0)
    assert all_["B1"].split == "all"
    test = by_system(csv_bench(split="test"))
    assert (test["B1"].tp, test["B1"].fp, test["B1"].fn) == (12, 9, 0)
    assert test["B1"].precision == pytest.approx(0.571, abs=1e-3)
    assert (test["B0"].tp, test["B0"].fp, test["B0"].fn) == (0, 0, 12)


@pytest.mark.unit
def test_csv_bench_train_plus_test_is_all() -> None:
    tr = by_system(csv_bench(split="train"))["B1"]
    te = by_system(csv_bench(split="test"))["B1"]
    assert (tr.tp + te.tp, tr.fp + te.fp) == (28, 22)


@pytest.mark.unit
def test_csv_bench_matches_rule_baselines_file() -> None:
    with (ROOT / "analysis" / "outputs" / "rule_baselines.csv").open() as f:
        expected = {r["config"]: r for r in csv.DictReader(f)}
    got = {}
    for split, suffix in (("all", ""), ("test", "_test_split")):
        for r in csv_bench(split=split):
            got[r.system + suffix] = r
    assert set(expected) == set(got)
    for k, e in expected.items():
        assert (got[k].tp, got[k].fp, got[k].fn) == (int(e["tp"]), int(e["fp"]), int(e["fn"]))
        assert (got[k].precision or 0.0) == pytest.approx(float(e["precision"]), abs=0.005)
        assert (got[k].recall or 0.0) == pytest.approx(float(e["recall"]), abs=0.005)


@pytest.mark.unit
def test_b0_b1_ignore_segment_metrics() -> None:
    base = {
        "timestamp": "2026-08-22T03:00:00",
        "service_name": "PaymentGateway",
        "is_incident": "0",
    }
    rows = [
        {**base, "metric_type": "payment_success_rate", "value": "0.5", "threshold": "0.97"},
        {**base, "metric_type": "cpu_usage", "value": "10", "threshold": "80"},
    ]
    res = by_system(score_rows(rows, "all"))
    assert (res["B1"].tp, res["B1"].fp, res["B1"].fn) == (0, 0, 0)
    assert (res["B0"].tp, res["B0"].fp, res["B0"].fn) == (0, 0, 0)
    assert DEFAULT_CSV.name == "ps02_system_telemetry.csv"
