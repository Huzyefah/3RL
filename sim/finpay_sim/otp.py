"""Fictional SMS/OTP providers P1 and P2."""

from __future__ import annotations

import math
import random

PROVIDERS: tuple[str, ...] = ("P1", "P2")
DEFAULT_PROVIDER = "P1"
HEALTHY_DELIVERY = 0.99
MEDIAN_LATENCY_MS = 1200.0
SIGMA = 0.35


def send_otp(rng: random.Random, delivery_p: float, latency_mult: float) -> tuple[bool, float]:
    """One OTP send → (delivered, latency_ms)."""
    delivered = rng.random() < delivery_p
    latency = rng.lognormvariate(math.log(MEDIAN_LATENCY_MS * latency_mult), SIGMA)
    return delivered, latency
