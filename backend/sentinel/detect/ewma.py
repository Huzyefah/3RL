"""EWMA baseline + z-score on u, and k-of-n persistence for z-only triggers (FINAL_PLAN §6, §1.4 F7)."""

from __future__ import annotations

import math
from collections import deque


class EwmaZ:
    __slots__ = ("lam", "mean", "n", "var", "warmup")

    def __init__(self, lam: float = 0.05, warmup: int = 30) -> None:
        self.lam, self.warmup = lam, warmup
        self.mean: float | None = None
        self.var = 0.0
        self.n = 0

    def update(self, x: float) -> float:
        """Returns z of `x` against the baseline *before* absorbing it (0 during warm-up)."""
        self.n += 1
        if self.mean is None:
            self.mean = x
            return 0.0
        d = x - self.mean
        z = d / math.sqrt(self.var + 1e-6) if self.n > self.warmup else 0.0
        self.mean += self.lam * d
        self.var = (1 - self.lam) * (self.var + self.lam * d * d)
        return z


class Persistence:
    """True once at least k of the last n observations were hits."""

    __slots__ = ("buf", "k")

    def __init__(self, k: int = 2, n: int = 3) -> None:
        self.k = k
        self.buf: deque[bool] = deque(maxlen=n)

    def update(self, hit: bool) -> bool:
        self.buf.append(hit)
        return hit and sum(self.buf) >= self.k
