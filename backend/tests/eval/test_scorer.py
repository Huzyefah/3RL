from dataclasses import dataclass
from datetime import datetime, timedelta

from sentinel.eval import splits
from sentinel.eval.scorer import match, score

T = datetime(2026, 8, 25, 10, 30)


@dataclass
class Inc:
    id: str
    service: str
    onset: datetime
    lead_min: int = 20
    duration_min: int = 20
    segment: str = "*"
    abrupt: bool = False

    @property
    def precursor_start(self):
        return self.onset - timedelta(minutes=self.lead_min)


def A(minutes_before, service="SearchAPI", segment="*"):
    return {"ts": T - timedelta(minutes=minutes_before), "service": service, "metric": "latency_p99", "segment": segment, "risk": 0.6}


def test_lead_time_definition():
    r = score([A(14)], [Inc("I1", "SearchAPI", T)], [datetime(2026, 8, 25)], n_boot=10)
    assert r["leads"]["I1"] == 14


def test_late_alert_zero_lead():
    r = score([A(-3)], [Inc("I1", "SearchAPI", T)], [datetime(2026, 8, 25)], n_boot=10)
    assert r["leads"]["I1"] == 0


def test_outside_window_fp():
    m = match([A(300)], [Inc("I1", "SearchAPI", T)])
    assert len(m["fps"]) == 1 and not m["first"]


def test_duplicates_not_fp():
    m = match([A(14), A(10), A(5)], [Inc("I1", "SearchAPI", T)])
    assert len(m["fps"]) == 0 and len(m["dups"]) == 2


def test_cascade_dependant_counts_as_detection():
    m = match([A(5, service="PaymentGateway")], [Inc("I1", "AuthService", T)])
    assert "I1" in m["first"]


def test_segment_alert_matches_segment_incident():
    m = match([A(12, service="PaymentGateway", segment="bank=BANK_C")], [Inc("I1", "PaymentGateway", T, segment="bank=BANK_C")])
    assert "I1" in m["first"]


def test_split_constants_printed():
    d = splits.describe()
    assert "train Aug 01–Aug 21" in d and "test Aug 21" in d and "test 100–129" in d
