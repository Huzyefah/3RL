import pytest

from sentinel.impact.business import impact, pkr_protected


def test_zero_failure_rate_zero_impact():
    assert impact(100, 0.0, 10).gmv_at_risk_pkr == 0


def test_linear_scaling():
    assert impact(100, 0.05, 20).failed_txns == pytest.approx(2 * impact(100, 0.05, 10).failed_txns)


def test_pkr_protected_caps_lead_at_duration():
    assert pkr_protected(40, 15, 1000, 0.1) == pkr_protected(15, 15, 1000, 0.1) == 1500
    assert pkr_protected(-3, 15, 1000, 0.1) == 0
