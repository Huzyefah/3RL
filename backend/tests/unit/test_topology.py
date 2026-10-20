import csv
from pathlib import Path

import pytest

from sentinel.topology import Topology

pytestmark = pytest.mark.unit

CSV = Path(__file__).resolve().parents[3] / "data" / "ps02_system_telemetry.csv"


@pytest.fixture(scope="module")
def topo() -> Topology:
    return Topology.from_yaml()


def test_services_yaml_maps_all_8_csv_services(topo: Topology):
    with CSV.open() as f:
        csv_names = {row["service_name"] for row in csv.DictReader(f)}
    assert len(csv_names) == 8
    assert csv_names == set(topo.services)
    for name in csv_names:
        assert topo.csv_to_novapay(name)


def test_csv_to_novapay_names(topo: Topology):
    assert topo.csv_to_novapay("DataPipeline") == "LedgerSync"
    assert topo.csv_to_novapay("SearchAPI") == "TransactionSearchAPI"
    assert topo.csv_to_novapay("AnalyticsDashboard") == "FraudRiskAnalytics"


def test_blast_radius_ledgersync_includes_reporting(topo: Topology):
    radius = topo.blast_radius("DataPipeline")
    assert {"ReportGenerator", "SearchAPI", "AnalyticsDashboard", "PaymentGateway"} <= radius
    assert "DataPipeline" not in radius


def test_blast_radius_is_transitive(topo: Topology):
    # UserProfileService <- AuthService <- PaymentGateway
    assert topo.blast_radius("UserProfileService") == {"AuthService", "PaymentGateway"}
    assert topo.blast_radius("ReportGenerator") == set()


def test_novapay_alias_resolves(topo: Topology):
    assert topo.blast_radius("LedgerSync") == topo.blast_radius("DataPipeline")


def test_dependants_and_upstream_are_direct(topo: Topology):
    assert topo.upstream("PaymentGateway") == {"AuthService", "DataPipeline", "NotificationHub"}
    assert topo.upstream("AuthService") == {"UserProfileService"}
    assert topo.dependants("AuthService") == {"PaymentGateway"}
    assert topo.dependants("DataPipeline") == {
        "PaymentGateway",
        "SearchAPI",
        "AnalyticsDashboard",
        "ReportGenerator",
    }


def test_no_cycles(topo: Topology):
    for svc in topo.services:
        assert svc not in topo.blast_radius(svc)


def test_linked_auth_and_gateway_0801(topo: Topology):
    assert topo.linked("AuthService", "PaymentGateway")
    assert topo.linked("PaymentGateway", "AuthService")


def test_linked_transitive(topo: Topology):
    assert topo.linked("UserProfileService", "PaymentGateway")


def test_search_and_userprofile_not_linked_0816(topo: Topology):
    assert not topo.linked("SearchAPI", "UserProfileService")
    assert not topo.linked("UserProfileService", "SearchAPI")


def test_siblings_not_linked(topo: Topology):
    assert not topo.linked("SearchAPI", "ReportGenerator")


def test_owner_and_tier(topo: Topology):
    assert topo.owner("DataPipeline") == "Core Banking Ops"
    assert topo.owner("ReportGenerator") == "Risk & Compliance"
    assert topo.tier("PaymentGateway") == 0
    assert topo.tier("ReportGenerator") == 2


def test_segments_and_banks(topo: Topology):
    assert topo.banks == ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E"]
    assert topo.otp_providers == ["P1", "P2"]
    assert topo.services["PaymentGateway"].segments == {"bank": topo.banks}
    assert topo.services["NotificationHub"].segments == {"provider": ["P1", "P2"]}


def test_segment_metric_thresholds(topo: Topology):
    pg = topo.services["PaymentGateway"].segment_metrics
    assert pg["payment_success_rate"].threshold == 0.97
    assert pg["payment_success_rate"].direction == "lower_is_bad"
    assert pg["issuer_timeout_rate"].threshold == 0.02
    assert pg["issuer_timeout_rate"].direction == "higher_is_bad"
    nh = topo.services["NotificationHub"].segment_metrics
    assert nh["otp_delivery_rate"].threshold == 0.95
    au = topo.services["AuthService"].segment_metrics
    assert au["login_failure_rate"].threshold == 0.08


def test_ps02_metrics_present_and_higher_is_bad(topo: Topology):
    for svc in topo.services.values():
        assert len(svc.metrics) == 7
        assert all(m.direction == "higher_is_bad" and m.threshold > 0 for m in svc.metrics.values())


def test_unknown_service_raises(topo: Topology):
    with pytest.raises(KeyError):
        topo.owner("Nope")
