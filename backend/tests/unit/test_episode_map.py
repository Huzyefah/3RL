"""Episode map (Phase 2, D5-D9): every PS-02 CRITICAL anchor is explained exactly once."""

import csv
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import get_args

import pytest

from sentinel.datagen.episode_map import by_anchor, events, incidents, load_episode_map, negatives
from sentinel.datagen.types import NegCode, RCCode

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
CSV = ROOT / "data" / "ps02_system_telemetry.csv"
YAML_PATH = ROOT / "backend" / "data" / "ps02_episode_map.yaml"
SCRIPT = ROOT / "scripts" / "build_episode_map.py"


def _critical() -> set[tuple[str, str, str]]:
    with CSV.open() as f:
        return {
            (r["timestamp"], r["service_name"], r["metric_type"])
            for r in csv.DictReader(f)
            if r["alert_level"] == "CRITICAL"
        }


def test_episode_map_covers_all_50_critical_rows() -> None:
    m = load_episode_map()
    assert len(m) == 50
    assert {(a.anchor_ts, a.service, a.metric) for a in m} == _critical()


def test_28_incidents_22_negatives() -> None:
    assert len(incidents()) == 28
    assert len(negatives()) == 22


def test_ids_unique_and_chronological() -> None:
    inc = sorted(incidents(), key=lambda a: a.anchor_ts)
    fa = sorted(negatives(), key=lambda a: a.anchor_ts)
    assert [a.episode_id for a in inc] == [f"INC-{n:04d}" for n in range(1, 29)]
    assert [a.episode_id for a in fa] == [f"FA-{n:04d}" for n in range(1, 23)]
    assert len({a.episode_id for a in load_episode_map()}) == 50


def test_abrupt_share() -> None:
    abrupt = [a for a in incidents() if a.abrupt]
    assert len(abrupt) == 6
    assert all(a.code == "RC-ABRUPT" for a in abrupt)
    assert all(a.code != "RC-ABRUPT" for a in incidents() if not a.abrupt)
    assert not any(a.abrupt for a in negatives())


def test_rc_cert_not_anchor_mapped() -> None:
    assert all(a.code != "RC-CERT" for a in load_episode_map())


def test_codes_valid() -> None:
    assert all(a.code in get_args(RCCode) for a in incidents())
    assert all(a.code in get_args(NegCode) for a in negatives())


def test_onset_is_minute_floor_of_anchor() -> None:
    for a in load_episode_map():
        assert a.onset_ts == datetime.fromisoformat(a.anchor_ts).replace(second=0).isoformat()


def test_segment_keys() -> None:
    bank = [a for a in incidents() if a.code == "RC-BANK"]
    assert bank and all(a.segment_key.startswith("bank=BANK_") for a in bank)
    assert any(a.segment_key == "bank=BANK_C" for a in bank)
    otp = [a for a in incidents() if a.code == "RC-OTP-PROVIDER"]
    assert otp and all(a.segment_key in ("provider=P1", "provider=P2") for a in otp)


def test_0801_cascade_pair() -> None:
    up = by_anchor("2026-08-01T10:38:14", "AuthService", "connection_pool")
    down = by_anchor("2026-08-01T10:59:06", "PaymentGateway", "connection_pool")
    assert (up.code, down.code) == ("RC-DBPOOL", "RC-DBPOOL")
    assert not up.abrupt and not down.abrupt
    assert up.cascade_parent is None
    assert down.cascade_parent == up.episode_id == "INC-0001"
    assert [a for a in load_episode_map() if a.cascade_parent] == [down]


def test_0816_pair_not_cascade() -> None:
    a = by_anchor("2026-08-16T06:20:01", "SearchAPI", "cpu_usage")
    b = by_anchor("2026-08-16T06:32:07", "UserProfileService", "disk_io")
    assert a.cascade_parent is None and b.cascade_parent is None
    assert "D6" in YAML_PATH.read_text()


def test_0822_cashback_is_n1_with_evidence() -> None:
    a = by_anchor("2026-08-22T20:25:48", "PaymentGateway", "connection_pool")
    assert (a.kind, a.code) == ("negative", "N1")
    assert "cashback_weekend_0822" in a.benign_evidence


def test_0814_0318_is_n6_without_evidence() -> None:
    a = by_anchor("2026-08-14T03:18:43", "AnalyticsDashboard", "disk_io")
    assert a.code == "N6"
    assert a.benign_evidence == ()


def test_at_least_3_n6_and_all_have_no_evidence() -> None:
    n6 = [a for a in negatives() if a.code == "N6"]
    assert len(n6) >= 3
    assert all(a.benign_evidence == () for a in n6)


def test_n4_rows_reference_synthetic_deploy_events() -> None:
    ids = {e["event_id"] for e in events()}
    n4 = [a for a in negatives() if a.code == "N4"]
    assert n4
    for a in n4:
        assert a.benign_evidence and set(a.benign_evidence) <= ids


def test_yaml_regenerates_identically() -> None:
    spec = importlib.util.spec_from_file_location("build_episode_map", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.build() == YAML_PATH.read_text()
