"""Tiny synthetic Datasets for replay/exporter tests (the real generator is a separate module)."""

from datetime import datetime

import pandas as pd

from sentinel.datagen.types import (
    EVENT_COLUMNS,
    LOG_COLUMNS,
    METRIC_COLUMNS,
    Dataset,
    GroundTruthEpisode,
)

T0 = datetime(2026, 1, 1, 0, 0)


def make_dataset() -> Dataset:
    rows = []
    for m in range(240):
        ts = pd.Timestamp(T0) + pd.Timedelta(minutes=m)
        for svc, metrics in (("svc-a", ["latency", "errors"]), ("svc-b", ["latency"])):
            for metric in metrics:
                rows.append(
                    (ts, svc, metric, "*", float(m), 100.0, "higher_bad", 0, 0, m / 100, False,
                     "ps02_replay")
                )  # fmt: skip
        if m % 2 == 0:  # a segment series on svc-a on even minutes
            rows.append(
                (ts, "svc-a", "fail_rate", "bank=BANK_C", 0.1, 0.5, "higher_bad", 50, 5, 0.2,
                 False, "ps02_replay")
            )  # fmt: skip
    metrics = pd.DataFrame(rows, columns=METRIC_COLUMNS)
    logs = pd.DataFrame(
        [(pd.Timestamp(T0) + pd.Timedelta(minutes=100), "svc-a", "ERROR", "T1", "boom")],
        columns=LOG_COLUMNS,
    )
    events = pd.DataFrame(
        [(pd.Timestamp(T0) + pd.Timedelta(minutes=101), "deploy", "svc-a", "v2", "EV-1")],
        columns=EVENT_COLUMNS,
    )
    gt = GroundTruthEpisode(
        episode_id="INC-0001", kind="incident", code="RC-BANK", service="svc-a",
        segment_key="bank=BANK_C", precursor_start=datetime(2026, 1, 1, 2, 0),
        onset=datetime(2026, 1, 1, 2, 30), end=datetime(2026, 1, 1, 2, 40), abrupt=False,
        anchor_ts="2026-01-01 02:30:15", benign_evidence=("EV-1",),
    )  # fmt: skip
    return Dataset(
        mode="seeded", seed=7, window=(T0, datetime(2026, 1, 1, 3, 59)),
        metrics=metrics, logs=logs, events=events, ground_truth=[gt],
    )  # fmt: skip
