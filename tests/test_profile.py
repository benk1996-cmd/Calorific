import pytest
from fastapi.testclient import TestClient

from api.auth import User, get_current_user
from api.db import get_db
from api.index import app


class FakeDb:
    def __init__(self):
        self.rows: dict[str, dict] = {}

    def select(self, table, **filters):
        uid = filters["user_id"].removeprefix("eq.")
        return [self.rows[uid]] if uid in self.rows else []

    def upsert(self, table, row, on_conflict):
        self.rows[row["user_id"]] = row
        return row


BODY = dict(sex="male", birth_year=1996, height_cm=175, weight_kg=70,
            activity_level="moderate", goal="maintain")


@pytest.fixture
def env():
    db, current = FakeDb(), {"u": User("A", "a@x.com")}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: current["u"]
    yield TestClient(app), db, current
    app.dependency_overrides.clear()


def test_requires_auth():
    assert TestClient(app).get("/api/profile").status_code == 401


def test_empty_then_put_calculates(env):
    c, _, _ = env
    assert c.get("/api/profile").json()["profile"] is None
    r = c.put("/api/profile", json=BODY)
    assert r.status_code == 200
    p = r.json()["profile"]
    assert p["target_kcal"] > 1500 and p["target_protein_g"] > 0


def test_override(env):
    c, _, _ = env
    r = c.put("/api/profile", json={**BODY, "target_override": True, "target_kcal": 2000})
    assert r.json()["profile"]["target_kcal"] == 2000
    assert c.put("/api/profile", json={**BODY, "target_override": True}).status_code == 422


def test_validation(env):
    c, _, _ = env
    assert c.put("/api/profile", json={**BODY, "timezone": "Nope/Zone"}).status_code == 422
    assert c.put("/api/profile", json={**BODY, "birth_year": 2999}).status_code == 422
    assert c.put("/api/profile", json={**BODY, "height_cm": 5}).status_code == 422


def test_user_isolation(env):
    c, _, current = env
    c.put("/api/profile", json=BODY)
    current["u"] = User("B", "b@x.com")
    assert c.get("/api/profile").json()["profile"] is None
