"""Shape library for the data generator (FP 3.3, 3.4, 5; FP 13 Task 2)."""

from datetime import datetime

import numpy as np
import pytest
from scipy.stats import spearmanr

from sentinel.datagen.episodes import (
    INCIDENT_CODES,
    LEAD_WINDOWS,
    NEGATIVE_CODES,
    Shape,
    daily_tps_factor,
    negative_shape,
    precursor_shape,
    rate_counts,
    render_log,
)
from sentinel.redact import contains_pii

RAMPING = ["RC-BANK", "RC-DBPOOL", "RC-OTP-PROVIDER", "RC-QUEUE", "RC-AUTH-ATTACK", "RC-MEMLEAK"]
SEEDS = range(30)


def _rho(y: np.ndarray) -> float:
    return float(spearmanr(np.arange(len(y)), y).statistic)  # pyright: ignore[reportAttributeAccessIssue]


def _same(a: Shape, b: Shape) -> bool:
    return (
        np.array_equal(a.u_offset, b.u_offset)
        and a.lead_minutes == b.lead_minutes
        and a.onset_index == b.onset_index
        and a.latency_lag_min == b.latency_lag_min
        and a.log_templates == b.log_templates
        and a.event_kinds == b.event_kinds
    )


@pytest.mark.unit
@pytest.mark.parametrize("code", INCIDENT_CODES)
def test_deterministic(code: str) -> None:
    a = precursor_shape(code, np.random.default_rng(7))
    b = precursor_shape(code, np.random.default_rng(7))
    assert _same(a, b)


@pytest.mark.unit
@pytest.mark.parametrize("code", NEGATIVE_CODES)
def test_deterministic_negatives(code: str) -> None:
    assert _same(
        negative_shape(code, np.random.default_rng(3)),
        negative_shape(code, np.random.default_rng(3)),
    )


@pytest.mark.unit
def test_different_seeds_differ() -> None:
    a = precursor_shape("RC-DBPOOL", np.random.default_rng(1))
    b = precursor_shape("RC-DBPOOL", np.random.default_rng(2))
    assert not _same(a, b)


@pytest.mark.unit
@pytest.mark.parametrize("code", RAMPING)
def test_precursor_rises(code: str) -> None:
    for seed in SEEDS:
        s = precursor_shape(code, np.random.default_rng(seed))
        assert _rho(s.u_offset) >= 0.7, (code, seed)
        assert s.u_offset[s.onset_index] == pytest.approx(1.0)
        assert s.onset_index == s.lead_minutes == len(s.u_offset) - 1
        assert s.u_offset.min() >= 0.0


@pytest.mark.unit
def test_abrupt_has_no_precursor() -> None:
    for seed in SEEDS:
        s = precursor_shape("RC-ABRUPT", np.random.default_rng(seed))
        assert s.lead_minutes == 0
        assert s.onset_index == 0
        assert s.u_offset.tolist() == [1.0]
        assert all(t.offset_min >= 0 for t in s.log_templates)


@pytest.mark.unit
def test_lead_windows_match_taxonomy() -> None:
    expected = {
        "RC-BANK": (20, 45),
        "RC-DBPOOL": (10, 40),
        "RC-OTP-PROVIDER": (10, 30),
        "RC-QUEUE": (60, 180),
        "RC-AUTH-ATTACK": (5, 20),
        "RC-MEMLEAK": (40, 120),
        "RC-ABRUPT": (0, 0),
    }
    for code, (lo, hi) in expected.items():
        assert LEAD_WINDOWS[code] == (lo, hi)
        leads = {precursor_shape(code, np.random.default_rng(s)).lead_minutes for s in range(60)}
        assert min(leads) >= lo and max(leads) <= hi, code
        if hi > lo:
            assert len(leads) > 1, code


@pytest.mark.unit
def test_duration_override() -> None:
    s = precursor_shape("RC-DBPOOL", np.random.default_rng(0), duration_min=25)
    assert s.lead_minutes == 25 and len(s.u_offset) == 26


@pytest.mark.unit
def test_rc_cert_has_flat_metrics() -> None:
    for seed in SEEDS:
        s = precursor_shape("RC-CERT", np.random.default_rng(seed))
        assert np.all(s.u_offset == 0.0)
        ids = {t.template_id for t in s.log_templates}
        assert "ssl_handshake_cert_expired" in ids
        assert any(t.offset_min < 0 for t in s.log_templates)  # the novel log leads the onset


@pytest.mark.unit
def test_n1_ramps_like_an_incident() -> None:
    for seed in SEEDS:
        s = negative_shape("N1", np.random.default_rng(seed))
        assert 20 <= s.lead_minutes <= 40
        ramp = s.u_offset[: s.onset_index + 1]
        assert _rho(ramp) >= 0.7, seed
        assert s.u_offset[s.onset_index] == pytest.approx(1.0)
        assert {"tps", "latency_p99", "queue_depth", "cpu_usage"} <= set(s.co_metrics)
        assert s.benign_evidence == ("calendar",)


@pytest.mark.unit
def test_n6_has_no_benign_evidence() -> None:
    for seed in SEEDS:
        s = negative_shape("N6", np.random.default_rng(seed))
        assert s.benign_evidence == ()
        assert s.event_kinds == ()
        assert s.u_offset.max() == pytest.approx(1.0)


@pytest.mark.unit
@pytest.mark.parametrize("code", ["N1", "N2", "N3", "N4", "N5"])
def test_other_negatives_carry_benign_evidence(code: str) -> None:
    assert negative_shape(code, np.random.default_rng(0)).benign_evidence


@pytest.mark.unit
def test_n4_and_n5_recover() -> None:
    for seed in SEEDS:
        n4 = negative_shape("N4", np.random.default_rng(seed))
        assert 5 <= len(n4.u_offset) <= 10
        assert n4.u_offset[-1] < 0.5 and n4.event_kinds == ("deploy",)
        n5 = negative_shape("N5", np.random.default_rng(seed))
        touch = int((n5.u_offset >= 1.0 - 1e-9).sum())
        assert 1 <= touch <= 3
        assert n5.u_offset[-1] < 0.5


@pytest.mark.unit
def test_n3_plateau_on_disk_io_and_queue() -> None:
    s = negative_shape("N3", np.random.default_rng(0))
    assert {"disk_io", "queue_depth"} <= set(s.co_metrics)
    assert s.event_kinds == ("cron",)
    peak = s.u_offset >= 0.9
    assert peak.sum() >= 15  # a plateau, not a spike


@pytest.mark.unit
def test_unknown_code_rejected() -> None:
    with pytest.raises(ValueError):
        precursor_shape("RC-NOPE", np.random.default_rng(0))
    with pytest.raises(ValueError):
        negative_shape("N9", np.random.default_rng(0))


@pytest.mark.unit
def test_binomial_counts_consistent() -> None:
    rng = np.random.default_rng(0)
    draws = [rate_counts(0.03, 2000, rng) for _ in range(2000)]
    assert all(0 <= bad <= tot == 2000 for tot, bad in draws)
    assert np.mean([bad / tot for tot, bad in draws]) == pytest.approx(0.03, abs=0.002)
    assert rate_counts(0.5, 0, rng) == (0, 0)
    with pytest.raises(ValueError):
        rate_counts(1.5, 10, rng)


@pytest.mark.unit
def test_salary_day_multiplier() -> None:
    salary = daily_tps_factor(datetime(2026, 8, 1, 13, 0))
    normal = daily_tps_factor(datetime(2026, 8, 5, 13, 0))
    assert salary / normal == pytest.approx(1.6)


@pytest.mark.unit
def test_campaign_multiplier_from_calendar() -> None:
    campaign = daily_tps_factor(datetime(2026, 8, 22, 20, 0))
    normal = daily_tps_factor(datetime(2026, 8, 21, 20, 0))
    assert campaign / normal == pytest.approx(1.5)  # calendar.yaml cashback_weekend_0822


@pytest.mark.unit
def test_daily_seasonality_shape() -> None:
    day = datetime(2026, 8, 5)
    f = {h: daily_tps_factor(day.replace(hour=h)) for h in range(24)}
    trough = max(f[h] for h in range(2, 6))
    assert trough < min(f[h] for h in (12, 13, 20, 21, 22))
    assert min(f, key=lambda h: f[h]) in range(2, 6)


@pytest.mark.unit
def test_no_pii_in_log_templates() -> None:
    shapes = [
        precursor_shape(c, np.random.default_rng(s)) for c in INCIDENT_CODES for s in range(10)
    ]
    shapes += [
        negative_shape(c, np.random.default_rng(s)) for c in NEGATIVE_CODES for s in range(10)
    ]
    seen = 0
    for shape in shapes:
        for t in shape.log_templates:
            for bank, provider in (("BANK_C", "P1"), ("BANK_A", "P2")):
                msg = render_log(t, bank=bank, provider=provider)
                assert "{" not in msg
                assert not contains_pii(msg), msg
                seen += 1
    assert seen > 0


@pytest.mark.unit
def test_fp5_example_templates_present() -> None:
    msgs = set()
    for c in INCIDENT_CODES:
        for t in precursor_shape(c, np.random.default_rng(0)).log_templates:
            msgs.add(render_log(t, bank="BANK_C", provider="P1"))
    assert "IBFT BANK_C: ISO8583 0210 RC=91 issuer unavailable" in msgs
    assert "HikariPool-1 - Connection is not available, request timed out after 30000ms" in msgs
    assert "SMS P1 DLR timeout" in msgs
    assert "SSL handshake failed: certificate expired" in msgs
