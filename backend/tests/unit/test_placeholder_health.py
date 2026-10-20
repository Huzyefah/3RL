import pytest
from fastapi.testclient import TestClient

from sentinel.api.main import app

pytestmark = pytest.mark.unit


def test_healthz():
    r = TestClient(app).get("/healthz")
    assert r.status_code == 200 and r.json()["service"] == "sentinel-api"
