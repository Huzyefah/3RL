from sentinel.topology import Topology


def test_blast_radius_ledgersync_includes_reporting():
    t = Topology.load()
    radius = t.blast_radius("DataPipeline")
    assert {"ReportGenerator", "AnalyticsDashboard", "SearchAPI", "PaymentGateway"} <= set(radius)
    assert "DataPipeline" not in radius


def test_cascade_edges_from_csv_pairs_are_linked():
    t = Topology.load()
    assert t.linked("AuthService", "PaymentGateway")  # 08-01 10:38 → 10:59
    assert t.linked("SearchAPI", "UserProfileService")  # 08-16 06:20 → 06:32 (added edge)
    assert not t.linked("ReportGenerator", "NotificationHub")


def test_owner_team_and_tier():
    t = Topology.load()
    assert t.team("AuthService") == "Identity & Security"
    assert t.tier("PaymentGateway") == 0
