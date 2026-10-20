"""Holt linear trend on u with a prediction-interval time-to-breach trigger (FINAL_PLAN §6)."""

from __future__ import annotations

import math

from sentinel.schemas import CRITICAL_U

H = list(range(1, 31))
SQRT_H = [math.sqrt(h) for h in H]


class HoltState:
    __slots__ = ("alpha", "beta", "level", "n", "streak", "trend", "var", "warmup")

    def __init__(self, alpha: float = 0.3, beta: float = 0.1, warmup: int = 10) -> None:
        self.alpha, self.beta, self.warmup = alpha, beta, warmup
        self.level: float | None = None
        self.trend = 0.0
        self.var = 0.0
        self.n = 0
        self.streak = 0

    def update(self, u: float) -> None:
        self.n += 1
        if self.level is None:
            self.level = u
            return
        prev = self.level
        err = u - (self.level + self.trend)
        self.level = self.alpha * u + (1 - self.alpha) * (self.level + self.trend)
        self.trend = self.beta * (self.level - prev) + (1 - self.beta) * self.trend
        self.var = 0.9 * self.var + 0.1 * err * err
        self.streak = self.streak + 1 if self.level > prev else 0

    def forecast(self, h: float) -> float:
        return (self.level or 0.0) + h * self.trend

    def eta(self, target: float = CRITICAL_U) -> float | None:
        """Minutes until the level reaches `target`, or None when not rising / out of (0, 120]."""
        if self.n < self.warmup or self.level is None or self.trend <= 1e-4:
            return None
        e = (target - self.level) / self.trend
        return e if 0 < e <= 120 else None

    def predictive_trigger(self, target: float = CRITICAL_U, horizon: int = 30, z: float = 1.645) -> bool:
        """Rising streak ≥ 5 and the lower prediction bound reaches `target` within `horizon` minutes."""
        if self.n < self.warmup or self.streak < 5 or self.trend <= 0 or self.level is None:
            return False
        sigma = math.sqrt(self.var)
        return any(self.level + h * self.trend - z * sigma * sh >= target for h, sh in zip(H[:horizon], SQRT_H))
