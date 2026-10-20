"""Deterministic fault/recovery behaviour of the SimEngine (tests drive step(), never sleep)."""

from finpay_sim.engine import SimEngine


def test_healthy_baseline(engine: SimEngine):
    engine.step(60)
    for bank in ("BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E"):
        assert engine.payment_success_rate(bank, last_s=60) >= 0.97
    assert engine.otp_delivery_rate("P1", last_s=60) >= 0.95
    assert engine.login_failure_rate(last_s=60) < 0.08
    assert engine.pool_utilisation() < 0.5


def test_same_seed_is_deterministic():
    a, b = SimEngine(seed=11), SimEngine(seed=11)
    ea, eb = a.step(30), b.step(30)
    strip = lambda envs: [
        [(e["metric"], e["segment_key"], e["value"]) for e in env["events"]] for env in envs
    ]
    assert strip(ea) == strip(eb)


def test_reroute_restores_success_rate(engine: SimEngine):
    engine.step(60)
    assert engine.payment_success_rate("BANK_C", last_s=30) >= 0.97
    engine.trigger("bank_c_slow")
    engine.step(240)
    assert engine.payment_success_rate("BANK_C", last_s=30) < 0.97
    # other banks unaffected
    assert engine.payment_success_rate("BANK_A", last_s=30) >= 0.97
    engine.set_routing("BANK_C", "RAAST")
    engine.step(60)
    assert engine.payment_success_rate("BANK_C", last_s=30) >= 0.97


def test_bank_c_slow_only_affects_ibft(engine: SimEngine):
    engine.set_routing("BANK_C", "RAAST")
    engine.trigger("bank_c_slow")
    engine.step(240)
    assert engine.payment_success_rate("BANK_C", last_s=30) >= 0.97


def test_otp_failover(engine: SimEngine):
    engine.step(30)
    engine.trigger("otp_p1_down")
    engine.step(150)
    assert engine.otp_delivery_rate("P1", last_s=30) < 0.95
    engine.set_otp_provider("P2")
    engine.step(60)
    assert engine.otp_delivery_rate("P2", last_s=30) >= 0.95
    assert engine.otp_customer_delivery_rate(last_s=30) >= 0.95  # what customers experience
    assert engine.otp_delivery_rate("P1", last_s=30) < 0.95  # standby probes still see P1 broken


def test_ledger_pool_leak_raises_pool_utilisation(engine: SimEngine):
    engine.step(30)
    before = engine.pool_utilisation()
    engine.trigger("ledger_pool_leak")
    engine.step(100)
    mid = engine.pool_utilisation()
    engine.step(120)
    after = engine.pool_utilisation()
    assert before < 0.4
    assert before < mid < after
    assert after >= 0.95
    assert engine.payment_error_rate(last_s=30) > 0.01  # saturation causes errors


def test_chaos_reset(engine: SimEngine):
    engine.step(30)
    for fault in ("bank_c_slow", "ledger_pool_leak", "otp_p1_down", "report_batch"):
        engine.trigger(fault)
    engine.set_routing("BANK_C", "RAAST")
    engine.set_otp_provider("P2")
    engine.set_workers(8)
    engine.step(240)
    assert engine.pool_utilisation() >= 0.95
    engine.trigger("reset")
    state = engine.state()
    assert state["chaos"] == {}
    assert state["routing"] == {b: "IBFT" for b in ("BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E")}
    assert state["otp_provider"] == "P1"
    assert state["workers"] == 4
    assert state["ledger_pool"]["leaked"] == 0
    engine.step(60)
    for bank in ("BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E"):
        assert engine.payment_success_rate(bank, last_s=30) >= 0.97
    assert engine.otp_delivery_rate("P1", last_s=30) >= 0.95
    assert engine.pool_utilisation() < 0.4
    assert engine.payment_error_rate(last_s=30) < 0.01


def test_unknown_fault_raises(engine: SimEngine):
    import pytest

    with pytest.raises(KeyError):
        engine.trigger("nope")


def test_workers_scale_throughput(engine: SimEngine):
    engine.set_workers(8)
    assert engine.tps == 80
    engine.set_workers(1)
    assert engine.tps == 20
