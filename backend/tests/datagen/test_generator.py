from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

from sentinel.bus import InMemoryBus
from sentinel.datagen.corpus import corpus
from sentinel.datagen.episodes import build_episode_map, load_map
from sentinel.datagen.exporters import envelopes_at, episode_window, replay
from sentinel.datagen.generator import INFRA_METRICS, _build_ps02, alert_runs, build
from sentinel.eval.csv_bench import load_ps02
from sentinel.redact import assert_no_pii
from sentinel.schemas import CES, band


@pytest.fixture(scope="module")
def ds():
    return build("ps02")


def _infra(ds):
    return {k: s for k, s in ds.series.items() if k[2] == "*" and k[1] in INFRA_METRICS}


def test_deterministic():
    _build_ps02.cache_clear()
    a = build("ps02")
    _build_ps02.cache_clear()
    b = build("ps02")
    for k in a.series:
        np.testing.assert_array_equal(a.series[k].u, b.series[k].u)
    pd.testing.assert_frame_equal(a.events, b.events)


def test_episode_map_is_committed_and_reproducible():
    assert [e.__dict__ for e in build_episode_map()] == [e.__dict__ for e in load_map()]


def test_all_28_anchors_mapped():
    eps = load_map()
    inc = [e for e in eps if e.kind == "incident"]
    neg = [e for e in eps if e.kind == "negative"]
    assert len(inc) == 28 and len(neg) == 22
    csv = load_ps02()
    assert {e.anchor_row for e in inc} == set(csv.index[csv.is_incident == 1])
    assert {e.code for e in neg} == {"N1", "N3", "N5", "N6"}
    assert {e.code for e in inc} <= {"RC-BANK", "RC-DBPOOL", "RC-OTP-PROVIDER", "RC-QUEUE", "RC-MEMLEAK"}


def test_anchors_preserved_in_u_space(ds):
    for r in load_ps02().itertuples():
        s = ds.series[(r.service_name, r.metric_type, "*")]
        i = ds.loc(r.timestamp)
        assert s.u[i] == pytest.approx(r.u, abs=1e-6)
        assert s.value_at(i) == pytest.approx(r.value, abs=1e-6)
        assert band(s.u[i]) == r.alert_level


def test_b1_reproduces_csv_on_ps02_mode(ds):
    crit = {(r.service_name, r.metric_type, ds.loc(r.timestamp)) for r in load_ps02().itertuples() if r.alert_level == "CRITICAL"}
    runs = [(k, a, b) for k, s in _infra(ds).items() for a, b in alert_runs(s.u)]
    assert len(runs) == 50
    for (svc, metric, _), a, b in runs:  # every run contains exactly one CRITICAL anchor
        assert sum(1 for c in crit if c[0] == svc and c[1] == metric and a <= c[2] <= b) == 1
    assert all((s.u < 1.0).all() for s in _infra(ds).values())  # B0 stays silent, like the CSV


def test_onset_at_anchor(ds):
    for e in (e for e in ds.episodes if e.kind == "incident"):
        u = ds.series[(e.service, e.metric, "*")].u
        i_on, i_pre = ds.loc(e.onset), ds.loc(e.precursor_start)
        first = i_pre + int(np.argmax(u[i_pre : i_on + 1] >= 0.95))
        assert first == i_on, e.id


def test_precursor_rises(ds):
    for e in ds.episodes:
        if e.kind != "incident" or e.abrupt or e.lead_min < 5:
            continue
        u = ds.series[(e.service, e.metric, "*")].u[ds.loc(e.precursor_start) : ds.loc(e.onset)]
        rho = spearmanr(np.arange(len(u)), u).statistic
        assert rho >= 0.7, (e.id, rho)


def test_abrupt_share(ds):
    inc = [e for e in ds.episodes if e.kind == "incident"]
    assert 5 <= sum(e.abrupt for e in inc) <= 7  # ≈20%


def test_n1_ramps_like_an_incident(ds):
    n1 = [e for e in ds.episodes if e.code == "N1"]
    assert n1
    for e in n1:
        u = ds.series[(e.service, e.metric, "*")].u[ds.loc(e.precursor_start) : ds.loc(e.onset)]
        assert spearmanr(np.arange(len(u)), u).statistic >= 0.7
        others = [ds.series[(e.service, m, "*")].u[ds.loc(e.onset)] for m in INFRA_METRICS if m != e.metric]
        assert np.median(others) >= 0.7  # everything rises together during a surge


def test_n6_has_no_benign_evidence(ds):
    for e in (e for e in ds.episodes if e.code == "N6"):
        lo, hi = e.precursor_start - timedelta(minutes=60), e.end + timedelta(minutes=15)
        ev = ds.events
        near = ev[(ev.ts < hi) & (ev.end > lo) & (ev.service == e.service)]
        allday = ev[(ev.ts < hi) & (ev.end > lo) & (ev.service == "*")]
        assert near.empty and allday.empty, (e.id, near.name.tolist(), allday.name.tolist())


def test_binomial_counts_consistent(ds):
    for s in ds.series.values():
        if s.n_total is None:
            continue
        assert (s.n_bad >= 0).all() and (s.n_bad <= s.n_total).all()
        i = 1000
        frac = s.n_bad[i] / s.n_total[i]
        assert s.value_at(i) == pytest.approx(1 - frac if s.direction == "lower_bad" else frac)


def test_rc_bank_segment_precursor(ds):
    for e in (e for e in ds.episodes if e.code == "RC-BANK" and not e.abrupt):
        s = ds.series[("PaymentGateway", "issuer_timeout_rate", e.segment)]
        i_pre, i_on = ds.loc(e.precursor_start), ds.loc(e.onset)
        assert s.u[i_on - 3 : i_on].mean() > 3 * s.u[i_pre - 30 : i_pre].mean()


def test_salary_day_multiplier(ds):
    tps = sum(ds.tps.values())
    day = lambda d: tps[(ds.index.day == d) & (ds.index.month == 8)].mean()
    assert day(1) / ((day(16) + day(17)) / 2) == pytest.approx(1.6, abs=0.1)


def test_no_pii_in_logs(ds):
    assert len(ds.logs) > 0
    assert_no_pii(ds.logs.message.tolist())


def test_envelopes_are_valid_ces(ds):
    envs = envelopes_at(ds, ds.loc(load_map()[0].onset))
    assert {e["service"] for e in envs} == {"PaymentGateway", "AuthService", "NotificationHub", "DataPipeline",
                                             "UserProfileService", "SearchAPI", "AnalyticsDashboard", "ReportGenerator"}
    for env in envs:
        for ev in env["events"]:
            CES.model_validate(ev)


async def test_replay_single_episode_inmemory(ds):
    bus = InMemoryBus(maxsize=100_000)
    ticks = await replay(ds, bus, speed=0, episode_id="INC-PS02-0001")
    start, end = episode_window(ds, "INC-PS02-0001")
    assert ticks == int((end - start).total_seconds() // 60)
    assert bus.qsize() == ticks * 8


def test_corpus_split_excludes_test_incidents():
    train, test = corpus("train"), corpus("test")
    assert len(train) + len(test) == 50
    assert all(d.ts < "2026-08-21" for d in train) and all(d.ts >= "2026-08-21" for d in test)
    assert sum(d.label == "incident" for d in test) == 12 and sum(d.label == "false_alarm" for d in test) == 9
    assert_no_pii([d.text for d in train + test])
