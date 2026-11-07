from fastapi.testclient import TestClient

from backend.main import app


def test_health():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert len(r.json()["vision_models"]) == 4
