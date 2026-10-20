from datetime import datetime, timedelta

import numpy as np
import pytest

from sentinel.datagen.generator import build
from sentinel.detect.engine import DetectorEngine, compute_signals, emit
from sentinel.detect.grouping import CASCADE_WINDOW_MIN, Grouper
from sentinel.eval.scorer import match
from sentinel.eval.splits import PS02_TEST
from sentinel.schemas import Candidate

T0 = datetime(2026, 8, 25, 12, 0)


@pytest.fixture(scope="module")
def ds():
    return build("ps02")


@pytest.fixture(scope="module")
def sig(ds):
    return compute_signals(ds, *PS02_TEST)


def _test_incidents(ds):
    return [e for e in ds.episodes if e.kind == "incident" and PS02_TEST[0] <= e.onset < PS02_TEST[1]]


def test_b0_silent_on_ps02(sig):
    assert emit(sig, "B0") == []


def test_b1_sanity_gate_recall_1_lead_0(ds, sig):
    inc = _test_incidents(ds)
    m = match(emit(sig, "B1"), inc)
    assert len(m["first"]) == len(inc) == 12
    assert all(abs((i.onset - m["first"][i.id]["ts"]).total_seconds()) < 60 for i in inc)


def test_s1_leads_on_bank_episode(ds, sig):
    bank = next(e for e in _test_incidents(ds) if e.code == "RC-BANK" and not e.abrupt)
    m = match(emit(sig, "S1"), [bank])
    assert (bank.onset - m["first"][bank.id]["ts"]) >= timedelta(minutes=10)


def test_segment_found_when_hidden_in_aggregate():
    """BANK_C timeouts at 12% while the platform-wide rate is ~1.5%: the segment series must alarm."""
    eng = DetectorEngine("S2", tau=0.45)
    out = []
    for k in range(20):
        pts = []
        for b, w in {"BANK_A": 0.3, "BANK_B": 0.25, "BANK_C": 0.2, "BANK_D": 0.15, "BANK_E": 0.1}.items():
            n = int(9000 * w)
            p = 0.12 if (b == "BANK_C" and k >= 5) else 0.004
            pts.append({"service": "PaymentGateway", "metric": "issuer_timeout_rate", "segment_key": f"bank={b}",
                        "direction": "higher_bad", "threshold": 0.02, "n_total": n, "n_bad": int(n * p), "value": p})
        out += eng.step(T0 + timedelta(minutes=k), pts)
    assert any(c.segment_key == "bank=BANK_C" and c.binom for c in out)
    assert not any(c.segment_key != "bank=BANK_C" for c in out)


def test_salary_surge_low_risk_or_flagged(ds, sig):
    """N1 surges ramp like incidents; S2 may raise them (the Skeptic's job), but never as a 'segment' alarm."""
    for e in (e for e in ds.episodes if e.code == "N1" and PS02_TEST[0] <= e.onset < PS02_TEST[1]):
        near = [a for a in emit(sig, "S2", 0.45) if abs((a["ts"] - e.onset).total_seconds()) < 3600 and a["service"] == e.service]
        assert all(a["segment"] == "*" for a in near)


def test_cascade_groups_auth_to_payment():
    g = Grouper()
    a = Candidate(ts=datetime(2026, 8, 1, 10, 30), service="PaymentGateway", metric="connection_pool", u=0.9, risk=0.6)
    b = Candidate(ts=datetime(2026, 8, 1, 10, 30) + timedelta(minutes=CASCADE_WINDOW_MIN - 4), service="AuthService",
                  metric="connection_pool", u=0.93, risk=0.7)
    inc, new = g.add(a)
    inc2, new2 = g.add(b)
    assert new and not new2 and inc.id == inc2.id
    assert inc.root_service == "AuthService" and inc.symptom_services == ["PaymentGateway"]


def test_unrelated_services_not_grouped():
    g = Grouper()
    g.add(Candidate(ts=T0, service="ReportGenerator", metric="disk_io", u=0.9, risk=0.6))
    _, new = g.add(Candidate(ts=T0 + timedelta(minutes=2), service="NotificationHub", metric="latency_p99", u=0.9, risk=0.6))
    assert new


def test_dedup_cooldown():
    eng = DetectorEngine("B1")
    opened = []
    for k in range(120):
        u = 0.97 if k < 60 else 0.5
        if k >= 100:
            u = 0.97
        pts = [{"service": "SearchAPI", "metric": "latency_p99", "direction": "higher_bad", "threshold": 1.0, "value": u}]
        opened += [(k, c) for c in eng.step(T0 + timedelta(minutes=k), pts)]
    assert [k for k, _ in opened] == [0, 100]  # one candidate for the 60-min breach; re-open only after clear + cooldown


def test_live_engine_matches_eval_driver(ds):
    """Same update path: the live engine reproduces the eval driver's B1 alert on an anchor episode."""
    e = next(x for x in _test_incidents(ds) if not x.abrupt)
    key = (e.service, e.metric, "*")
    s = ds.series[key]
    eng = DetectorEngine("B1")
    i0, i1 = ds.loc(e.precursor_start) - 30, ds.loc(e.end)
    hits = []
    for i in range(i0, i1):
        pts = [{"service": e.service, "metric": e.metric, "direction": "higher_bad", "threshold": s.threshold, "u": float(s.u[i])}]
        hits += eng.step(ds.index[i].to_pydatetime(), pts)
    assert hits and hits[0].ts == e.onset
    assert np.isclose(hits[0].u, s.u[ds.loc(e.onset)], atol=1e-4)
