from fastapi.testclient import TestClient

from finpay_sim.app import app


def test_healthz():
    assert TestClient(app).get("/health").json()["status"] == "ok"
