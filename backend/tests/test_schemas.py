import pytest

from sentinel.schemas import CES, RCA, Candidate, band, utilisation


def test_u_higher_bad():
    assert utilisation(68.46, 71.39, "higher_bad") == pytest.approx(0.95896, abs=1e-5)


def test_u_lower_bad():
    assert utilisation(0.955, 0.97, "lower_bad") == pytest.approx(1.5)


def test_bands_match_ps02():
    assert band(0.7499) == "NORMAL"
    assert band(0.75) == "WARNING"
    assert band(0.9499) == "WARNING"
    assert band(0.95) == "CRITICAL"


def test_ces_u_property_and_defaults():
    e = CES(ts="2026-08-01T10:31:00Z", source="ps02_replay", kind="metric", service="PaymentGateway",
            metric="issuer_timeout_rate", value=0.031, threshold=0.02, direction="higher_bad", n_total=612, n_bad=19)
    assert e.segment_key == "*"
    assert e.u == pytest.approx(1.55)
    assert e.event_id  # idempotency key auto-generated


def test_candidate_and_rca_roundtrip():
    c = Candidate(ts="2026-08-01T10:31:00Z", service="PaymentGateway", metric="issuer_timeout_rate",
                  segment_key="bank=BANK_C", u=0.83, eta_minutes=11, risk=0.7, triggers=["holt"])
    assert Candidate.model_validate_json(c.model_dump_json()) == c
    rca = RCA.fallback_example()
    assert rca.generated_by == "statistical-fallback"
    assert RCA.model_validate(rca.model_dump()) == rca
