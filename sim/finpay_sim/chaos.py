"""Fault catalogue and the deterministic shape of each fault as a function of elapsed sim-time."""

from __future__ import annotations

FAULTS: tuple[str, ...] = ("bank_c_slow", "ledger_pool_leak", "otp_p1_down", "report_batch")
RESET = "reset"

# bank_c_slow: BANK_C's IBFT switch degrades (RC-BANK). Step, then creep over ~3 sim-minutes.
BANK_C_RAMP_S = 180.0
BANK_C_TIMEOUT_START = 0.005
BANK_C_TIMEOUT_END = 0.25
# ledger_pool_leak: one leaked connection every 10 s (RC-DBPOOL).
LEAK_PER_S = 0.1
# otp_p1_down: P1 delivery degrades 0.99 → 0.60 over 2 sim-minutes (RC-OTP-PROVIDER).
OTP_RAMP_S = 120.0
OTP_DELIVERY_END = 0.60
# report_batch: benign DataPipeline plateau (hard negative N3).
BATCH_RAMP_S = 60.0
BATCH_HOLD_S = 600.0


def _frac(elapsed: float, ramp: float) -> float:
    return max(0.0, min(1.0, elapsed / ramp))


def bank_c_ibft(elapsed: float) -> tuple[float, float]:
    """→ (latency multiplier, timeout probability) for BANK_C on IBFT."""
    f = _frac(elapsed, BANK_C_RAMP_S)
    latency_mult = 1.6 + 1.4 * f  # step to 1.6x, creep to 3x
    timeout_p = BANK_C_TIMEOUT_START + (BANK_C_TIMEOUT_END - BANK_C_TIMEOUT_START) * f
    return latency_mult, timeout_p


def leaked_connections(elapsed: float, pool_size: int) -> float:
    return min(float(pool_size), elapsed * LEAK_PER_S)


def otp_p1(elapsed: float, healthy: float) -> tuple[float, float]:
    """→ (delivery probability, latency multiplier) for P1."""
    f = _frac(elapsed, OTP_RAMP_S)
    return healthy - (healthy - OTP_DELIVERY_END) * f, 1.0 + 2.0 * f


def report_batch_level(elapsed: float) -> float:
    """0 → 1 ramp, plateau, then 1 → 0 ramp-down; 0 after the batch ends."""
    if elapsed < BATCH_RAMP_S:
        return elapsed / BATCH_RAMP_S
    if elapsed < BATCH_RAMP_S + BATCH_HOLD_S:
        return 1.0
    return max(0.0, 1.0 - (elapsed - BATCH_RAMP_S - BATCH_HOLD_S) / BATCH_RAMP_S)
