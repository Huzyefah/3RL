import numpy as np

from sentinel.detect.binom import binom_alarm
from sentinel.detect.ewma import EwmaZ, Persistence
from sentinel.detect.holt import HoltState
from sentinel.detect.risk import risk


def _feed(us):
    h = HoltState()
    for u in us:
        h.update(u)
    return h


def test_eta_linear_ramp():
    h = _feed([0.70 + 0.005 * t for t in range(30)])  # evaluated at t = 29 → ETA ≈ 21
    assert h.eta() is not None and abs(h.eta() - 21) <= 3


def test_eta_none_flat_high():
    rng = np.random.default_rng(0)
    assert _feed(0.97 + rng.uniform(-0.002, 0.002, 30)).eta() is None


def test_eta_none_decreasing():
    assert _feed([0.9 - 0.004 * t for t in range(30)]).eta() is None


def test_predictive_trigger_on_ramp_not_on_noise():
    assert _feed([0.60 + 0.01 * t for t in range(25)]).predictive_trigger()
    rng = np.random.default_rng(1)
    assert not _feed(0.5 + rng.normal(0, 0.03, 200)).predictive_trigger()


def test_binom_low_volume_quiet():
    assert not binom_alarm(1, 4, 0.02)  # 25% raw rate, but n is tiny (Review Focus #1)


def test_binom_real_degradation():
    assert binom_alarm(40, 600, 0.02)


def test_binom_healthy_high_volume_quiet():
    assert not binom_alarm(12, 2700, 0.02)


def test_z_spike():
    z = EwmaZ()
    rng = np.random.default_rng(2)
    for u in 0.5 + rng.normal(0, 0.01, 100):
        z.update(u)
    assert z.update(0.7) >= 4


def test_persistence_only_on_z_triggers():
    p = Persistence(k=2, n=3)
    assert p.update(True) is False  # first z hit alone is not enough
    assert p.update(True) is True
    # The predictive trigger is not routed through persistence (engine test covers the wiring);
    # here: a single isolated hit after quiet never passes.
    p2 = Persistence(k=2, n=3)
    assert [p2.update(x) for x in (True, False, False, True)] == [False, False, False, False]


def test_risk_monotone():
    lo = risk(pred=False, eta=None, z=0, corrob=0, band=False, binom=False)
    hi = risk(pred=True, eta=8, z=5, corrob=0.8, band=False, binom=True)
    assert lo < 0.1
    assert hi > 0.8
