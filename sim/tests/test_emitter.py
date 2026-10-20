"""CES envelopes produced every 5 sim-seconds, one per service."""

import math
from datetime import datetime

from finpay_sim.engine import SimEngine

CES_KEYS = {
    "event_id",
    "ts",
    "source",
    "kind",
    "service",
    "segment_key",
    "metric",
    "value",
    "threshold",
    "direction",
    "n_total",
    "n_bad",
    "attributes",
    "redacted",
}
SERVICES = {"PaymentGateway", "NotificationHub", "AuthService", "DataPipeline"}


def _check_event(ev: dict) -> None:
    assert CES_KEYS <= set(ev), ev
    assert isinstance(ev["event_id"], str) and len(ev["event_id"]) == 32
    int(ev["event_id"], 16)
    ts = datetime.fromisoformat(ev["ts"])
    assert ts.tzinfo is not None
    assert ev["source"] == "finpay-sim"
    assert ev["kind"] == "metric"
    assert ev["service"] in SERVICES
    seg = ev["segment_key"]
    assert seg == "*" or seg.startswith("bank=BANK_") or seg in ("provider=P1", "provider=P2")
    assert isinstance(ev["metric"], str)
    assert isinstance(ev["value"], float) and math.isfinite(ev["value"])
    assert isinstance(ev["threshold"], float) and ev["threshold"] > 0
    assert ev["direction"] in ("higher_bad", "lower_bad")
    assert isinstance(ev["attributes"], dict)
    assert ev["redacted"] is True
    if ev["direction"] == "lower_bad":
        assert ev["threshold"] < 1
    nt, nb = ev["n_total"], ev["n_bad"]
    assert (nt is None) == (nb is None)
    if nt is not None:
        assert isinstance(nt, int) and isinstance(nb, int)
        assert 0 <= nb <= nt
        bad_frac = nb / nt if nt else 0.0
        expected = 1 - bad_frac if ev["direction"] == "lower_bad" else bad_frac
        assert math.isclose(ev["value"], expected, abs_tol=1e-9), ev


def test_emitter_ces_valid(engine: SimEngine):
    engine.trigger("bank_c_slow")
    engine.trigger("otp_p1_down")
    engine.trigger("ledger_pool_leak")
    engine.trigger("report_batch")
    envelopes = engine.step(120)
    assert len(envelopes) == 24 * len(SERVICES)  # every 5 s, one per service
    seen: dict[str, set] = {s: set() for s in SERVICES}
    for env in envelopes:
        assert set(env) >= {"service", "ts", "events"}
        assert env["service"] in SERVICES
        datetime.fromisoformat(env["ts"])
        assert env["events"]
        for ev in env["events"]:
            _check_event(ev)
            assert ev["service"] == env["service"]
            assert ev["ts"] == env["ts"]
            seen[ev["service"]].add((ev["metric"], ev["segment_key"]))
    pg = seen["PaymentGateway"]
    for b in "ABCDE":
        assert ("payment_success_rate", f"bank=BANK_{b}") in pg
        assert ("issuer_timeout_rate", f"bank=BANK_{b}") in pg
    assert {("latency_p99", "*"), ("error_rate", "*"), ("connection_pool", "*")} <= pg
    assert {("otp_delivery_rate", "provider=P1"), ("otp_delivery_rate", "provider=P2")} <= seen[
        "NotificationHub"
    ]
    assert ("latency_p99", "*") in seen["NotificationHub"]
    assert ("login_failure_rate", "*") in seen["AuthService"]
    assert {("queue_depth", "*"), ("disk_io", "*")} <= seen["DataPipeline"]
    ids = [ev["event_id"] for env in envelopes for ev in env["events"]]
    assert len(ids) == len(set(ids))


def test_emitter_ticks_align_across_uneven_steps(engine: SimEngine):
    envs = []
    for dt in (0.3, 1.7, 2.9, 0.1, 4.0, 1.0):  # 10.0 s total
        envs += engine.step(dt)
    assert len(envs) == 2 * len(SERVICES)
