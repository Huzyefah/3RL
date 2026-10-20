"""Utilisation ``u`` and the PS-02 bands. Single definition (FP 3.2); import it."""

from typing import Literal

Direction = Literal["higher_bad", "lower_bad"]
Band = Literal["NORMAL", "WARNING", "CRITICAL"]

WARNING_AT = 0.75
CRITICAL_AT = 0.95


def utilisation(value: float, threshold: float, direction: Direction) -> float:
    """Fraction of the error budget used; 1.0 means the SLO is breached.

    ``higher_bad``: ``value / threshold``. ``lower_bad``: ``(1 - value) / (1 - floor)`` where
    ``threshold`` is the floor.
    """
    if direction == "higher_bad":
        if threshold <= 0:
            raise ValueError("higher_bad threshold must be > 0")
        return value / threshold
    if threshold >= 1:
        raise ValueError("lower_bad floor must be < 1")
    return (1.0 - value) / (1.0 - threshold)


def band(u: float) -> Band:
    """NORMAL < 0.75 <= WARNING < 0.95 <= CRITICAL."""
    if u >= CRITICAL_AT:
        return "CRITICAL"
    if u >= WARNING_AT:
        return "WARNING"
    return "NORMAL"
