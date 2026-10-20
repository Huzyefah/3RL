from fastapi.testclient import TestClient

from sentinel.api.main import app


def test_healthz_reports_csv_rows():
    body = TestClient(app).get("/health").json()
    assert body["status"] == "ok"
    assert body["csv_rows"] == 500
