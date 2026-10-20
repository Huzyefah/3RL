"""Business impact in PKR (labelled as an estimate everywhere it is shown) (FINAL_PLAN §9)."""

from __future__ import annotations

from dataclasses import dataclass

AVG_TICKET_PKR = 3200.0
# Share of payments that fail while an incident on a service of this tier is active (assumption, labelled).
FAILURE_RATE_BY_TIER = {0: 0.06, 1: 0.01, 2: 0.002}


@dataclass(frozen=True)
class Impact:
    failed_txns: float
    gmv_at_risk_pkr: float
    customers_affected_est: int
    label: str = "estimate"


def impact(segment_tps: float, failure_rate: float, minutes: float, avg_ticket_pkr: float = AVG_TICKET_PKR) -> Impact:
    failed = segment_tps * 60 * minutes * failure_rate
    return Impact(failed_txns=failed, gmv_at_risk_pkr=failed * avg_ticket_pkr, customers_affected_est=round(failed * 0.85))


def pkr_protected(lead_min: float, incident_min: float, gmv_per_min: float, failure_rate: float) -> float:
    """Value of acting `lead_min` early: the protected window can never exceed the incident's duration."""
    return max(0.0, min(lead_min, incident_min)) * gmv_per_min * failure_rate
