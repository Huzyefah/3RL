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
from sentinel.datagen.episode_map import events as map_events
from sentinel.datagen.episode_map import load_episode_map
from sentinel.datagen.generator import CSV_PATH, MIN_SEGMENT_N, PS02_METRICS, build
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
    map_ids = {e["event_id"] for e in map_events()}
    assert len(map_ids) == 4 and map_ids <= set(ev["event_id"])
    assert {"azadi_sale_0814", "cashback_weekend_0822"} <= set(ev["event_id"])
    assert (ev["kind"] == "cron").sum() == 30  # EOD batch every day
    assert (ev["kind"] == "maintenance").sum() == 5  # Sundays in Aug 2026: 2, 9, 16, 23, 30
    # FP 3.4: some DB-pool / memory-leak incidents follow the deploy that caused them
    causing = [g for g in ds.ground_truth if g.cause_event_id]
    assert causing
    by_id = ev.set_index("event_id")
    for g in causing:
        r = by_id.loc[g.cause_event_id]
        assert g.code in ("RC-DBPOOL", "RC-MEMLEAK") and r["ts"] < pd.Timestamp(g.precursor_start)
        assert r["kind"] == "deploy" and r["service"] == g.service
    assert all(g.kind == "incident" for g in causing)


def test_event_ids_and_texts_do_not_leak_labels(ds: Dataset) -> None:
    """Deploy ids/texts are opaque: no INC-/FA- ids, causing and benign deploys look alike."""
    ev: Any = ds.events
    for col in ("event_id", "text"):
        assert not ev[col].str.contains(r"INC-|FA-|synthetic", regex=True).any(), col
    dep = ev[ev["kind"] == "deploy"]
    assert dep["event_id"].str.fullmatch(r"deploy_[0-9a-f]{8}").all()
    assert dep["event_id"].is_unique


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
    sample = has[has["n_total"] >= MIN_SEGMENT_N].sample(2000, random_state=0)
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


# --- anti-leakage (FP 1.4 F4): construction artifacts must not label the episodes ---------------


def _precision(hit_inc: int, hit_neg: int) -> float:
    return hit_inc / (hit_inc + hit_neg) if hit_inc + hit_neg else 0.0


def _rule_hits(ds: Dataset, rule) -> tuple[int, int, int, int]:
    """(incident hits, negative hits, #incidents, #negatives) for a per-episode boolean rule."""
    inc = [g for g in ds.ground_truth if g.kind == "incident"]
    neg = [g for g in ds.ground_truth if g.kind == "negative"]
    return sum(map(rule, inc)), sum(map(rule, neg)), len(inc), len(neg)


def test_warn_log_before_onset_is_not_a_label(ds: Dataset) -> None:
    """'Any WARN/ERROR log on the service in the 3 h before onset' must not separate classes."""
    lg: Any = ds.logs
    bad = lg[lg["level"].isin(["WARN", "ERROR"])]

    def rule(g) -> bool:
        w = bad[
            (bad["service"] == g.service)
            & (bad["ts"] >= pd.Timestamp(g.onset - timedelta(hours=3)))
            & (bad["ts"] < pd.Timestamp(g.onset))
        ]
        return not w.empty

    hi, hn, ni, nn = _rule_hits(ds, rule)
    assert _precision(hi, hn) < 0.8, (hi, hn)
    assert hn / nn >= 0.4, (hn, nn)


def test_background_warn_noise_reuses_incident_templates(ds: Dataset) -> None:
    lg: Any = ds.logs
    bad = lg[lg["level"].isin(["WARN", "ERROR"])]
    near = np.zeros(len(bad), dtype=bool)
    ts = bad["ts"].to_numpy()
    svc = bad["service"].to_numpy()
    for g in ds.ground_truth:
        lo = np.datetime64(g.precursor_start - timedelta(hours=1))
        hi = np.datetime64(g.end + timedelta(hours=1))
        near |= (svc == g.service) & (ts >= lo) & (ts <= hi)
    background = bad[~near]
    per_service_day = len(background) / (8 * 30)
    assert 1.0 <= per_service_day <= 6.0, per_service_day
    assert {"hikari_timeout", "ibft_rc91"} <= set(background["template_id"])
    assert "ssl_handshake_cert_expired" not in set(lg["template_id"])


def _rising_20(series, emap):
    def rule(g) -> bool:
        s = series[(g.service, emap[g.episode_id].metric)]
        w = _window(s, g.onset - timedelta(minutes=20), g.onset - timedelta(minutes=1))
        return _rho(w) >= 0.9 and float(w.iloc[-1] - w.iloc[0]) >= 0.08

    return rule


def test_precursor_length_is_not_a_label(ds: Dataset, series, emap) -> None:
    """'Rising for >= 20 min before onset' fires on a sizeable share of negatives too."""
    hi, hn, ni, nn = _rule_hits(ds, _rising_20(series, emap))
    assert hn / nn >= 0.35, (hn, nn)
    assert _precision(hi, hn) < 0.8, (hi, hn)


def test_level_15_min_before_onset_is_not_a_label(ds: Dataset, series, emap) -> None:
    def rule(g) -> bool:
        s = series[(g.service, emap[g.episode_id].metric)]
        return float(s.loc[pd.Timestamp(g.onset - timedelta(minutes=15))]) > 0.6

    hi, hn, ni, nn = _rule_hits(ds, rule)
    assert hn / nn >= 0.35, (hn, nn)
    assert _precision(hi, hn) < 0.8, (hi, hn)


def test_deploy_nearby_is_not_a_label(ds: Dataset) -> None:
    """Benign deploys land near negatives and abrupt incidents too, not only near N4 / causes."""
    ev: Any = ds.events
    dep = ev[ev["kind"] == "deploy"]

    def rule(g) -> bool:
        w = dep[
            (dep["service"] == g.service)
            & (dep["ts"] >= pd.Timestamp(g.onset - timedelta(hours=3)))
            & (dep["ts"] <= pd.Timestamp(g.onset))
        ]
        return not w.empty

    hi, hn, _, _ = _rule_hits(ds, rule)
    assert 0.2 < _precision(hi, hn) < 0.8, (hi, hn)
    other_neg = [g for g in ds.ground_truth if g.kind == "negative" and g.code not in ("N4", "N6")]
    assert sum(map(rule, other_neg)) >= 2
    uncaused = [g for g in ds.ground_truth if g.kind == "incident" and not g.cause_event_id]
    assert sum(map(rule, uncaused)) >= 3
    assert any(rule(g) for g in ds.ground_truth if g.abrupt)


# --- segment volume floor ------------------------------------------------------------------------


def test_segment_u_neutral_below_min_volume(ds: Dataset) -> None:
    m: Any = ds.metrics
    seg = m[~m["metric"].isin(_PS)]
    low = seg[seg["n_total"] < MIN_SEGMENT_N]
    assert len(low) > 0 and (low["u"] == 0.0).all()
    assert MIN_SEGMENT_N == 30


def test_segment_u_rarely_breaches_outside_episodes(ds: Dataset) -> None:
    m: Any = ds.metrics
    seg = m[~m["metric"].isin(_PS) & (m["n_total"] >= MIN_SEGMENT_N)]
    inside = np.zeros(len(seg), dtype=bool)
    ts, svc = seg["ts"].to_numpy(), seg["service"].to_numpy()
    for g in ds.ground_truth:
        inside |= (
            (svc == g.service)
            & (ts >= np.datetime64(g.precursor_start))
            & (ts <= np.datetime64(g.end))
        )
    out = seg[~inside]
    assert (out["u"] >= 1.0).mean() < 0.005


# --- anchors keep their original timestamp ------------------------------------------------------


def test_anchor_floor_keeps_original_ts(ds: Dataset, csv: Any) -> None:
    m: Any = ds.metrics
    assert (m.loc[~m["is_anchor"], "anchor_ts"] == "").all()
    anchors = m[m["is_anchor"]]
    assert len(anchors) == 500
    j = csv.merge(
        anchors,
        left_on=["minute", "service_name", "metric_type"],
        right_on=["ts", "service", "metric"],
        validate="one_to_one",
    )
    assert len(j) == 500
    orig = j["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
    assert (j["anchor_ts"].astype(str) == orig).all()
    assert (pd.to_datetime(j["anchor_ts"].astype(str)).dt.floor("min") == j["ts"]).all()
    assert (j["timestamp"].dt.second > 0).any()  # the floor actually dropped seconds


def test_n1_anchor_2026_08_22_on_calendar(ds: Dataset, emap) -> None:
    a = next(
        a
        for a in emap.values()
        if (a.anchor_ts, a.service, a.metric)
        == ("2026-08-22T20:25:48", "PaymentGateway", "connection_pool")
    )
    g = ds.episode(a.episode_id)
    assert (g.kind, g.code) == ("negative", "N1")
    assert g.anchor_ts == "2026-08-22T20:25:48" and g.onset == datetime(2026, 8, 22, 20, 25)
    active = {e.id for e in events_at(g.onset, load_calendar())}
    assert "cashback_weekend_0822" in active
    assert "cashback_weekend_0822" in g.benign_evidence
    assert "cashback_weekend_0822" in set(ds.events["event_id"])


def test_n3_only_on_its_benign_for_metrics(emap) -> None:
    """eod_settlement is benign_for disk_io/queue_depth only; other metrics fall back."""
    eod = next(e for e in load_calendar() if e.id == "eod_settlement")
    assert eod.benign_for
    for a in emap.values():
        if a.code == "N3":
            assert a.metric in eod.benign_for, a.episode_id
    nh = next(
        a
        for a in emap.values()
        if (a.anchor_ts, a.service) == ("2026-08-20T16:27:07", "NotificationHub")
    )
    assert nh.code in ("N5", "N6") and "eod_settlement" not in nh.benign_evidence


# --- custom windows -----------------------------------------------------------------------------


def test_window_keeps_episodes_overlapping_it(ds: Dataset, emap) -> None:
    """An episode whose onset is past the window end but whose precursor overlaps it is kept."""
    g = next(
        g
        for g in sorted(ds.ground_truth, key=lambda g: g.onset)
        if g.kind == "incident" and g.onset - g.precursor_start >= timedelta(minutes=60)
    )
    hi = g.onset - timedelta(minutes=10)
    lo = g.precursor_start - timedelta(hours=2)
    part = build("ps02", seed=0, window=(lo, hi), use_cache=False)
    kept = part.episode(g.episode_id)
    assert (kept.precursor_start, kept.onset, kept.end) == (g.precursor_start, g.onset, g.end)
    m: Any = part.metrics
    s = (
        m[(m["service"] == g.service) & (m["metric"] == emap[g.episode_id].metric)]
        .set_index("ts")["u"]
        .sort_index()
    )
    pre = _window(s, g.precursor_start, hi)
    assert pre.iloc[-3:].mean() - pre.iloc[:3].mean() > 0.05
    # episodes entirely outside the window are not reported
    for e in part.ground_truth:
        assert e.precursor_start <= hi and e.end >= lo


def test_deterministic_across_hashseed() -> None:
    import os
    import subprocess
    import sys

    code = (
        "import hashlib, pandas as pd; from datetime import datetime;"
        "from sentinel.datagen.generator import build;"
        "ds = build('ps02', seed=0, window=(datetime(2026, 8, 1), datetime(2026, 8, 1, 23, 59)));"
        "h = hashlib.sha1();"
        "[h.update(pd.util.hash_pandas_object(d, index=False).values.tobytes())"
        " for d in (ds.metrics, ds.logs, ds.events)];"
        "h.update(repr(ds.ground_truth).encode()); print(h.hexdigest())"
    )
    out = {
        subprocess.run(
            [sys.executable, "-c", code],
            env={**os.environ, "PYTHONHASHSEED": hs},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for hs in ("1", "4242")
    }
    assert len(out) == 1


def test_parquet_roundtrip_keeps_anchor_ts(tmp_path) -> None:
    from sentinel.datagen.exporters import from_parquet, to_parquet

    win = (datetime(2026, 8, 1), datetime(2026, 8, 1, 23, 59))
    ds = build("ps02", seed=0, window=win)
    to_parquet(ds, tmp_path)
    back = from_parquet(tmp_path)
    pd.testing.assert_frame_equal(ds.metrics, back.metrics)
    assert (back.metrics["anchor_ts"] != "").sum() == ds.metrics["is_anchor"].sum() > 0
    assert back.ground_truth == ds.ground_truth
