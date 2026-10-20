import json

import pandas as pd
import pytest

from sentinel.datagen.exporters import from_parquet, to_csv_metrics, to_json_fixture, to_parquet

from ._replay_fixtures import make_dataset

pytestmark = pytest.mark.unit


def test_exporters_roundtrip(tmp_path):
    ds = make_dataset()
    to_parquet(ds, tmp_path / "pq")
    back = from_parquet(tmp_path / "pq")
    pd.testing.assert_frame_equal(ds.metrics, back.metrics)
    pd.testing.assert_frame_equal(ds.logs, back.logs)
    pd.testing.assert_frame_equal(ds.events, back.events)
    assert str(back.metrics["ts"].dtype) == str(ds.metrics["ts"].dtype)
    assert (back.mode, back.seed, back.window) == (ds.mode, ds.seed, ds.window)
    assert back.ground_truth == ds.ground_truth


def test_csv_metrics(tmp_path):
    ds = make_dataset()
    p = tmp_path / "m.csv"
    to_csv_metrics(ds, p)
    df = pd.read_csv(p)
    assert list(df.columns) == list(ds.metrics.columns)
    assert len(df) == len(ds.metrics)


def test_json_fixture_window_and_compact(tmp_path):
    ds = make_dataset()
    p = tmp_path / "f.json"
    to_json_fixture(ds, "INC-0001", p)
    text = p.read_text()
    assert ": " not in text and ", " not in text  # compact separators
    data = json.loads(text)
    assert data["episode"]["episode_id"] == "INC-0001"
    ts = [r["ts"] for r in data["metrics"]]
    assert min(ts) == "2026-01-01T00:30:00" and max(ts) == "2026-01-01T03:10:00"
    assert data["logs"] == [] or all("ts" in r for r in data["logs"])
