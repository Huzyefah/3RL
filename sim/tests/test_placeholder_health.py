import pytest
from fastapi.testclient import TestClient

from finpay_sim.app import app

pytestmark = pytest.mark.unit


def test_healthz():
    r = TestClient(app).get("/healthz")
    assert r.status_code == 200 and r.json()["service"] == "finpay-sim"
