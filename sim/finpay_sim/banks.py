"""Mock partner banks and payment rails (fictional; sandbox only)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

BANKS: tuple[str, ...] = ("BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E")
BANK_WEIGHTS: tuple[float, ...] = (0.30, 0.25, 0.20, 0.15, 0.10)
RAILS: tuple[str, ...] = ("IBFT", "RAAST")
DEFAULT_RAIL = "IBFT"
RAIL_TIMEOUT_MS = 3000.0


@dataclass(frozen=True)
class RailProfile:
    median_ms: float
    sigma: float  # lognormal shape; p99 = median * exp(2.326 * sigma)
    timeout_p: float
    error_p: float


# Healthy IBFT: median 250 ms, p99 ~600 ms, timeouts 0.4%. Raast: faster, timeouts 0.3%.
HEALTHY: dict[str, RailProfile] = {
    "IBFT": RailProfile(median_ms=250.0, sigma=math.log(2.4) / 2.326, timeout_p=0.004, error_p=0.001),
    "RAAST": RailProfile(median_ms=180.0, sigma=math.log(2.4) / 2.326, timeout_p=0.003, error_p=0.001),
}


def rail_outcome(rng: random.Random, profile: RailProfile) -> tuple[str, float]:
    """One rail call → (outcome, latency_ms)."""
    r = rng.random()
    if r < profile.timeout_p:
        return "timeout", RAIL_TIMEOUT_MS
    latency = rng.lognormvariate(math.log(profile.median_ms), profile.sigma)
    if r < profile.timeout_p + profile.error_p:
        return "error", latency
    if latency >= RAIL_TIMEOUT_MS:
        return "timeout", RAIL_TIMEOUT_MS
    return "success", latency
