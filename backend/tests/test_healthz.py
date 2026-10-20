from fastapi.testclient import TestClient


def test_health_reports_csv_rows(monkeypatch):
    monkeypatch.setenv("AUTOPLAY", "0")
    from sentinel.api.main import app

    with TestClient(app) as c:
        body = c.get("/health").json()
        assert body["status"] == "ok" and body["csv_rows"] == 500
        assert c.get("/scorecard").json()["configs"]["S2"]["recall"] == 1.0
        assert c.get("/incidents/nope").status_code == 404
