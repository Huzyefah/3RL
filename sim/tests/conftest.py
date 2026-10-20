import os

import pytest

os.environ.setdefault("SIM_AUTOSTART", "0")

from finpay_sim.engine import SimEngine


@pytest.fixture
def engine() -> SimEngine:
    return SimEngine(seed=7)
