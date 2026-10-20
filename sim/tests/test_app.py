"""HTTP surface: chaos, admin, /pay, /login, /emitted (SIM_AUTOSTART=0)."""

import pytest
from fastapi.testclient import TestClient

from finpay_sim.app import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_admin_routing_idempotent(client: TestClient):
    r1 = client.post("/admin/routing", json={"bank": "BANK_C", "rail": "RAAST"})
    r2 = client.post("/admin/routing", json={"bank": "BANK_C", "rail": "RAAST"})
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()
    assert r1.json()["routing"]["BANK_C"] == "RAAST"
    assert r1.json()["routing"]["BANK_A"] == "IBFT"
    assert client.get("/admin/routing").json() == r1.json()


@pytest.mark.parametrize(
    "path,body",
    [
        ("/admin/routing", {"bank": "BANK_F", "rail": "RAAST"}),
        ("/admin/routing", {"bank": "BANK_C", "rail": "SWIFT"}),
        ("/admin/routing", {"bank": "BANK_C"}),
        ("/admin/otp", {"provider": "P3"}),
        ("/admin/otp", {}),
        ("/admin/workers", {"workers": 0}),
        ("/admin/workers", {"workers": 9}),
        ("/admin/workers", {"workers": "many"}),
    ],
)
def test_admin_validation(client: TestClient, path: str, body: dict):
    assert client.post(path, json=body).status_code == 422


def test_admin_otp_and_workers(client: TestClient):
    assert client.get("/admin/otp").json() == {"provider": "P1"}
    assert client.post("/admin/otp", json={"provider": "P2"}).json() == {"provider": "P2"}
    r = client.post("/admin/workers", json={"workers": 6})
    assert r.status_code == 200 and r.json()["workers"] == 6 and r.json()["tps"] == 60
    assert client.get("/admin/workers").json()["workers"] == 6


def test_chaos_routes(client: TestClient):
    assert client.post("/chaos/nope").status_code == 404
    r = client.post("/chaos/bank_c_slow")
    assert r.status_code == 200 and "bank_c_slow" in r.json()["active"]
    client.post("/admin/routing", json={"bank": "BANK_C", "rail": "RAAST"})
    state = client.get("/admin/state").json()
    assert "bank_c_slow" in state["chaos"] and state["routing"]["BANK_C"] == "RAAST"
    r = client.post("/chaos/reset")
    assert r.status_code == 200 and r.json()["active"] == []
    state = client.get("/admin/state").json()
    assert state["chaos"] == {} and state["routing"]["BANK_C"] == "IBFT"


def test_pay_and_login(client: TestClient):
    r = client.post("/pay", json={"bank": "BANK_B"})
    assert r.status_code == 200
    body = r.json()
    assert body["bank"] == "BANK_B" and body["rail"] == "IBFT"
    assert body["outcome"] in ("success", "timeout", "error") and body["latency_ms"] > 0
    assert client.post("/pay", json={"bank": "BANK_Z"}).status_code == 422
    assert client.post("/pay").status_code == 200
    r = client.post("/login")
    assert r.status_code == 200 and isinstance(r.json()["ok"], bool)


def test_emitted_ring_buffer(client: TestClient):
    runtime = client.app.state.runtime
    assert client.get("/emitted").json()["envelopes"] == []
    runtime.advance(10)
    envs = client.get("/emitted").json()["envelopes"]
    assert len(envs) == 8
    first_ts = envs[0]["ts"]
    later = client.get("/emitted", params={"since": first_ts}).json()["envelopes"]
    assert all(e["ts"] > first_ts for e in later) and len(later) == 4
    assert len(client.get("/emitted", params={"limit": 3}).json()["envelopes"]) == 3
