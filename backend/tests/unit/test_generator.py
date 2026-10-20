"""Generator in ps02 mode (FP 5, FP 13 Task 2, plan Phase 2 + D3 D7 D8 D9)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

from sentinel.calendar import events_at, load_calendar
from sentinel.datagen.episode_map import load_episode_map
from sentinel.datagen.generator import CSV_PATH, PS02_METRICS, build
from sentinel.datagen.types import EVENT_COLUMNS, LOG_COLUMNS, METRIC_COLUMNS, Dataset
from sentinel.redact import contains_pii
from sentinel.utilisation import band, utilisation

pytestmark = pytest.mark.unit
_PS = sorted(PS02_METRICS)


@pytest.fixture(scope="session")
def ds() -> Dataset:
    return build("ps02", seed=0)


@pytest.fixture(scope="session")
def ps02(ds: Dataset) -> Any:
    m: Any = ds.metrics
    return m[m["metric"].isin(_PS) & (m["segment_key"] == "*")]


@pytest.fixture(scope="session")
def series(ps02: Any) -> dict[tuple[str, str], Any]:
    """(service, metric) -> u indexed by ts."""
    return {
        (str(s), str(m)): g.set_index("ts")["u"].sort_index()
        for (s, m), g in ps02.groupby(["service", "metric"], observed=True)
    }


@pytest.fixture(scope="session")
def csv() -> Any:
    d: Any = pd.read_csv(CSV_PATH, parse_dates=["timestamp"])
    d["minute"] = d["timestamp"].dt.floor("min")
    return d


@pytest.fixture(scope="session")
def emap():
    return {a.episode_id: a for a in load_episode_map()}


def _rho(s: Any) -> float:
    res: Any = spearmanr(np.arange(len(s)), s.to_numpy())
    return float(res.statistic)


def _window(s: Any, lo: datetime, hi: datetime) -> Any:
    return s[(s.index >= pd.Timestamp(lo)) & (s.index <= pd.Timestamp(hi))]


# --- shape of the output -----------------------------------------------------------------------


def test_columns_and_window(ds: Dataset) -> None:
    assert list(ds.metrics.columns) == METRIC_COLUMNS
    assert list(ds.logs.columns) == LOG_COLUMNS
    assert list(ds.events.columns) == EVENT_COLUMNS
    assert ds.window == (datetime(2026, 8, 1, 0, 0), datetime(2026, 8, 30, 23, 59))
    assert ds.metrics["ts"].min() == pd.Timestamp("2026-08-01 00:00")
    assert ds.metrics["ts"].max() == pd.Timestamp("2026-08-30 23:59")
    assert set(ds.metrics["source"]) == {"ps02_replay"}


def test_dense_one_minute_series(ps02: Any) -> None:
    minutes = 30 * 24 * 60
    counts = ps02.groupby(["service", "metric"], observed=True).size()
    assert len(counts) == 8 * 7
    assert (counts == minutes).all()


def test_seeded_mode_not_yet() -> None:
    with pytest.raises(NotImplementedError):
        build("seeded", seed=0)


def test_deterministic() -> None:
    win = (datetime(2026, 8, 1), datetime(2026, 8, 2, 23, 59))
    a = build("ps02", seed=3, window=win, use_cache=False)
    b = build("ps02", seed=3, window=win, use_cache=False)
    pd.testing.assert_frame_equal(a.metrics, b.metrics)
    pd.testing.assert_frame_equal(a.logs, b.logs)
    pd.testing.assert_frame_equal(a.events, b.events)
    assert a.ground_truth == b.ground_truth
    c = build("ps02", seed=4, window=win, use_cache=False)
    assert not np.allclose(a.metrics["u"].to_numpy(), c.metrics["u"].to_numpy())


def test_cache_returns_same_object() -> None:
    assert build("ps02", seed=0) is build("ps02", seed=0)


def test_build_under_60s() -> None:
    t0 = time.perf_counter()
    build("ps02", seed=11, use_cache=False)
    assert time.perf_counter() - t0 < 60


# --- anchors -----------------------------------------------------------------------------------


def test_anchors_preserved_in_u_space(ps02: Any, csv: Any) -> None:
    anchors = ps02[ps02["is_anchor"]]
    assert len(anchors) == 500
    j = csv.merge(
        anchors,
        left_on=["minute", "service_name", "metric_type"],
        right_on=["ts", "service", "metric"],
        how="left",
        validate="one_to_one",
    )
    assert j["u"].notna().all()
    csv_u = j["value_x"] / j["threshold_x"]
    assert np.abs(j["u"] - csv_u).max() < 1e-6
    assert [band(float(u)) for u in j["u"]] == list(j["alert_level"])
    for r in j.itertuples(index=False):
        assert abs(utilisation(r.value_y, r.threshold_y, r.direction) - r.u) < 1e-9


def test_b1_reproduces_csv_on_ps02_mode(series: dict[tuple[str, str], Any], csv: Any) -> None:
    """B1 (u >= 0.95) over the dense data: exactly the 50 CSV CRITICAL minutes, one run each."""
    episodes: set[tuple[pd.Timestamp, str, str]] = set()
    for (svc, metric), s in series.items():
        crit = (s.to_numpy() >= 0.95).astype(np.int8)
        starts = np.flatnonzero(np.diff(np.concatenate([[0], crit])) == 1)
        ends = np.flatnonzero(np.diff(np.concatenate([crit, [0]])) == -1)
        for a, b in zip(starts, ends, strict=True):
            assert a == b, f"{svc}/{metric} CRITICAL run longer than one minute at {s.index[a]}"
            episodes.add((s.index[a], svc, metric))
    crit_rows = csv[csv["alert_level"] == "CRITICAL"]
    expected = set(
        zip(crit_rows["minute"], crit_rows["service_name"], crit_rows["metric_type"], strict=True)
    )
    assert len(episodes) == 50
    assert episodes == expected


def test_b0_finds_nothing_on_ps02_series(ps02: Any) -> None:
    """No minute of the 7 PS-02 series reaches u >= 1.0 (the CSV max is 0.996)."""
    assert (ps02["u"] < 1.0).all()


def test_onset_at_anchor(ds: Dataset, ps02: Any, emap) -> None:
    idx = ps02.set_index(["ts", "service", "metric"])
    assert len(ds.ground_truth) == 50
    for gt in ds.ground_truth:
        a = emap[gt.episode_id]
        assert gt.anchor_ts == a.anchor_ts
        assert gt.onset == datetime.fromisoformat(a.anchor_ts).replace(second=0)
        assert gt.onset == datetime.fromisoformat(a.onset_ts)
        row = idx.loc[(pd.Timestamp(gt.onset), gt.service, a.metric)]
        assert bool(row["is_anchor"]) and band(float(row["u"])) == "CRITICAL"
        assert gt.precursor_start <= gt.onset < gt.end
        assert gt.segment_key == a.segment_key and gt.code == a.code and gt.kind == a.kind


def test_precursor_rises(ds: Dataset, series, emap) -> None:
    checked = 0
    for gt in ds.ground_truth:
        if gt.kind != "incident" or gt.abrupt:
            continue
        s = _window(series[(gt.service, emap[gt.episode_id].metric)], gt.precursor_start, gt.onset)
        assert len(s) >= 6
        rho = _rho(s)
        assert rho >= 0.7, (gt.episode_id, gt.code, rho)
        checked += 1
    assert checked == 22


def test_abrupt_share(ds: Dataset, series, emap) -> None:
    inc = [g for g in ds.ground_truth if g.kind == "incident"]
    abrupt = [g for g in inc if g.abrupt]
    assert (len(inc), len(abrupt)) == (28, 6)
    for g in abrupt:
        assert g.code == "RC-ABRUPT" and g.precursor_start == g.onset
        s = series[(g.service, emap[g.episode_id].metric)]
        before = _window(s, g.onset - timedelta(minutes=2), g.onset - timedelta(minutes=1))
        assert (before < 0.90).all(), g.episode_id


def test_n1_ramps_like_an_incident(ds: Dataset, series, emap) -> None:
    n1 = [g for g in ds.ground_truth if g.code == "N1"]
    assert len(n1) == 3
    for g in n1:
        s = _window(series[(g.service, emap[g.episode_id].metric)], g.precursor_start, g.onset)
        assert len(s) >= 20
        assert _rho(s) >= 0.7
        # co-metrics ramp together (FP 3.4): at least two other series rise into the onset
        risen = 0
        for m in ("latency_p99", "queue_depth", "cpu_usage"):
            if m == emap[g.episode_id].metric:
                continue
            c = _window(series[(g.service, m)], g.precursor_start, g.onset + timedelta(minutes=3))
            if c.iloc[-5:].mean() - c.iloc[:5].mean() > 0.1:
                risen += 1
        assert risen >= 2, g.episode_id


def test_n6_has_no_benign_evidence(ds: Dataset) -> None:
    cal = load_calendar()
    n6 = [g for g in ds.ground_truth if g.code == "N6"]
    assert len(n6) >= 3
    ev: Any = ds.events
    for g in n6:
        assert g.benign_evidence == ()
        assert events_at(g.onset, cal) == []
        near = ev[
            (ev["service"] == g.service)
            & (ev["ts"] >= pd.Timestamp(g.precursor_start - timedelta(hours=3)))
            & (ev["ts"] <= pd.Timestamp(g.end))
        ]
        assert near.empty, g.episode_id


def test_benign_evidence_resolvable(ds: Dataset) -> None:
    ids = set(ds.events["event_id"]) | {e.id for e in load_calendar()}
    for g in ds.ground_truth:
        for e in g.benign_evidence:
            assert e in ids, (g.episode_id, e)


def test_rc_cert_absent(ds: Dataset) -> None:
    assert all(g.code != "RC-CERT" for g in ds.ground_truth)
    assert "ssl_handshake_cert_expired" not in set(ds.logs["template_id"])


def test_cascade_0801_pair_ground_truth(ds: Dataset) -> None:
    a, b = ds.episode("INC-0001"), ds.episode("INC-0002")
    assert (a.service, a.onset) == ("AuthService", datetime(2026, 8, 1, 10, 38))
    assert (b.service, b.onset) == ("PaymentGateway", datetime(2026, 8, 1, 10, 59))
    assert b.cascade_parent == "INC-0001" and a.cascade_parent is None
    assert a.code == b.code == "RC-DBPOOL"


def test_background_below_090_outside_episodes(ds: Dataset, series) -> None:
    for (svc, _metric), s in series.items():
        mask = np.ones(len(s), dtype=bool)
        for g in ds.ground_truth:
            if g.service == svc:
                mask &= ~((s.index >= pd.Timestamp(g.precursor_start)) & (s.index <= g.end))
        anchors = ds.metrics.loc[
            ds.metrics["is_anchor"] & (ds.metrics["service"] == svc), "ts"
        ].to_numpy()
        mask &= ~np.isin(s.index.to_numpy(), anchors)
        assert (s.to_numpy()[mask] < 0.90).all(), (svc, _metric)


def test_episode_logs_emitted(ds: Dataset) -> None:
    lg: Any = ds.logs
    for g in ds.ground_truth:
        if g.kind != "incident":
            continue
        at = lg[(lg["service"] == g.service) & (lg["ts"] == pd.Timestamp(g.onset))]
        assert (at["level"] == "ERROR").any(), g.episode_id
    bank = ds.episode(next(g.episode_id for g in ds.ground_truth if g.code == "RC-BANK"))
    b = bank.segment_key.split("=")[1]
    assert lg["message"].str.contains(f"IBFT {b}: ISO8583 0210 RC=91").any()


def test_no_pii_in_logs(ds: Dataset) -> None:
    assert not any(contains_pii(str(m)) for m in ds.logs["message"])
    assert not any(contains_pii(str(t)) for t in ds.events["text"])


def test_events_cover_map_calendar_and_confounders(ds: Dataset) -> None:
    ev: Any = ds.events
    assert set(ev["kind"]) <= {"deploy", "maintenance", "campaign", "cron"}
    assert {"deploy_FA-0003", "deploy_FA-0006", "deploy_FA-0016", "deploy_FA-0022"} <= set(
        ev["event_id"]
    )
    assert {"azadi_sale_0814", "cashback_weekend_0822"} <= set(ev["event_id"])
    assert (ev["kind"] == "cron").sum() == 30  # EOD batch every day
    assert (ev["kind"] == "maintenance").sum() == 5  # Sundays in Aug 2026: 2, 9, 16, 23, 30
    # FP 3.4: some DB-pool / memory-leak incidents follow the deploy that caused them
    causing = ev[ev["event_id"].str.startswith("deploy_INC-")]
    for r in causing.itertuples(index=False):
        g = ds.episode(str(r.event_id).removeprefix("deploy_"))
        assert g.code in ("RC-DBPOOL", "RC-MEMLEAK") and r.ts < pd.Timestamp(g.precursor_start)


# --- segment rate metrics ----------------------------------------------------------------------


def test_segment_metrics_present(ds: Dataset) -> None:
    seg: Any = ds.metrics[~ds.metrics["metric"].isin(_PS)]
    keys = set(zip(seg["service"], seg["metric"], seg["segment_key"], strict=True))
    banks = [f"bank=BANK_{c}" for c in "ABCDE"]
    for b in banks:
        assert ("PaymentGateway", "payment_success_rate", b) in keys
        assert ("PaymentGateway", "issuer_timeout_rate", b) in keys
    assert ("NotificationHub", "otp_delivery_rate", "provider=P1") in keys
    assert ("NotificationHub", "otp_delivery_rate", "provider=P2") in keys
    assert ("AuthService", "login_failure_rate", "*") in keys
    assert len(keys) == 13


def test_binomial_counts_consistent(ds: Dataset) -> None:
    m: Any = ds.metrics
    is_ps = m["metric"].isin(_PS)
    ps = m[is_ps]
    assert (ps["n_total"] == 0).all() and (ps["n_bad"] == 0).all()
    assert (ps["segment_key"] == "*").all()
    seg = m[~is_ps]
    assert ((seg["n_bad"] >= 0) & (seg["n_bad"] <= seg["n_total"])).all()
    has = seg[seg["n_total"] > 0]
    frac = has["n_bad"] / has["n_total"]
    expect = np.where(has["direction"] == "lower_bad", 1 - frac, frac)
    assert np.allclose(has["value"], expect)
    sample = has.sample(2000, random_state=0)
    got = [utilisation(r.value, r.threshold, r.direction) for r in sample.itertuples(index=False)]
    assert np.allclose(sample["u"], got)
    # an RC-BANK episode degrades its bank's issuer timeouts around onset, not other banks'
    g = next(g for g in ds.ground_truth if g.code == "RC-BANK")
    win = (m["ts"] >= pd.Timestamp(g.onset - timedelta(minutes=5))) & (
        m["ts"] <= pd.Timestamp(g.onset)
    )
    to = m[win & (m["metric"] == "issuer_timeout_rate")]
    rate = to.groupby("segment_key")["n_bad"].sum() / to.groupby("segment_key")["n_total"].sum()
    assert rate[g.segment_key] > 0.03
    assert rate.drop(g.segment_key).max() < 0.02


def test_salary_day_multiplier(ds: Dataset) -> None:
    m: Any = ds.metrics
    vol = m[m["metric"] == "payment_success_rate"].groupby(m["ts"].dt.date)["n_total"].sum()
    ratio = vol[datetime(2026, 8, 2).date()] / vol[datetime(2026, 8, 5).date()]
    assert 1.5 < ratio < 1.7
