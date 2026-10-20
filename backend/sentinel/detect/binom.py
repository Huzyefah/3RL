"""One-sided binomial test per segment: robust to low volume (BANK_E at 03:00) (FINAL_PLAN §6)."""

from __future__ import annotations

from scipy.stats import binom


def binom_alarm(n_bad: int, n_total: int, p_slo: float, alpha: float = 1e-3, min_n: int = 30) -> bool:
    if n_total < min_n or n_bad <= p_slo * n_total:
        return False
    return float(binom.sf(n_bad - 1, n_total, p_slo)) < alpha
