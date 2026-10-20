"""Hand-weighted risk score (FINAL_PLAN §6). Only τ is grid-tuned, on the train split.

The weights were set once by inspecting the ps02 TRAIN split (Aug 1–20), never the test split: corroboration
(coupled metrics, novel logs, segment alarms, sick dependants) is what separates a real precursor from a
wobble toward a WARNING row, so it carries more weight than FINAL_PLAN's starting values (0.6 → 3.5).
See docs/test-evidence/phase-03-detection/README.md.
"""

from __future__ import annotations

import math

W = {"bias": -3.0, "pred": 1.0, "eta": 0.5, "z": 1.0, "corrob": 3.5, "band": 1.2, "binom": 1.3}


def risk(*, pred: bool, eta: float | None, z: float, corrob: float, band: bool, binom: bool) -> float:
    eta_term = 0.0 if eta is None else max(0.0, min(1.0, 1 - eta / 30))
    z_term = max(0.0, min(1.0, z / 4))
    s = (
        W["bias"]
        + W["pred"] * pred
        + W["eta"] * eta_term
        + W["z"] * z_term
        + W["corrob"] * corrob
        + W["band"] * band
        + W["binom"] * binom
    )
    return 1 / (1 + math.exp(-s))
