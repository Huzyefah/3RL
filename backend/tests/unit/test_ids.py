import re

import pytest

from sentinel import ids


@pytest.mark.unit
def test_ps02_incident_and_false_alarm_ids() -> None:
    assert ids.ps02_incident_id(1) == "INC-0001"
    assert ids.ps02_incident_id(28) == "INC-0028"
    assert ids.false_alarm_id(22) == "FA-0022"
    for bad in (0, 29):
        with pytest.raises(ValueError):
            ids.ps02_incident_id(bad)
    with pytest.raises(ValueError):
        ids.false_alarm_id(23)


@pytest.mark.unit
def test_runtime_and_seeded_ids() -> None:
    from datetime import UTC, datetime

    assert ids.runtime_incident_id(datetime(2026, 10, 20, 9, tzinfo=UTC), 4) == "INC-2026-1020-004"
    assert ids.seeded_episode_id(100, 3) == "S100-E3"


@pytest.mark.unit
def test_evidence_id_regex_and_determinism() -> None:
    a = ids.evidence_id("segment", {"b": 1, "a": [1, 2]})
    b = ids.evidence_id("segment", {"a": [1, 2], "b": 1})
    assert a == b
    assert re.fullmatch(r"^[a-z_]+:[0-9a-f]{8}$", a)
    assert ids.evidence_id("log", "x") != ids.evidence_id("segment", "x")
    assert ids.evidence_id("log", "x") != ids.evidence_id("log", "y")


@pytest.mark.unit
def test_evidence_id_rejects_bad_kind() -> None:
    with pytest.raises(ValueError):
        ids.evidence_id("Bad-Kind", "x")


@pytest.mark.unit
def test_idempotency_key_stable() -> None:
    k = ids.idempotency_key("reroute_bank", "bank=BANK_C", "2026-10-20T10:00")
    assert k == ids.idempotency_key("reroute_bank", "bank=BANK_C", "2026-10-20T10:00")
    assert k != ids.idempotency_key("reroute_bank", "bank=BANK_D", "2026-10-20T10:00")
