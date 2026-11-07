import csv
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.auth import User, get_current_user
from api.db import get_db
from api.index import app
from api.services import history as H
from tests.fakes import FakeDb

PROFILE = {"user_id": "A", "timezone": "Asia/Singapore", "target_kcal": 2000, "target_protein_g": 150,
           "target_carbs_g": 200, "target_fat_g": 67, "cap_sugar_g": 50, "cap_sodium_mg": 2000}


def seed(db, uid, day, mtype, kcal, name="Laksa", **extra):
    m = db.insert("meals", [{"user_id": uid, "local_date": day, "meal_type": mtype, "input_type": "text",
                             "eaten_at_utc": f"{day}T05:00:00+00:00"}])[0]
    return db.insert("meal_items", [{"meal_id": m["id"], "name": name, "source": "usda", "kcal": kcal,
                                     "protein_g": 10, "grams": 100.0, "servings": None, "confidence": 0.9,
                                     "user_edited": False, **extra}])[0]


@pytest.fixture
def env():
    db = FakeDb()
    db.t["profiles"] += [dict(PROFILE), {**PROFILE, "user_id": "B"}]
    cur = {"u": User("A", "a@x.com")}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: cur["u"]
    yield TestClient(app), db, cur
    app.dependency_overrides.clear()


def test_date_range_and_build_history_zero_fills_and_averages_logged_days():
    meals = [{"id": "m1", "local_date": "2026-11-02"}, {"id": "m2", "local_date": "2026-11-02"},
             {"id": "m3", "local_date": "2026-11-04"}, {"id": "mx", "local_date": "2026-12-01"}]
    items = [{"meal_id": "m1", "kcal": 600}, {"meal_id": "m2", "kcal": 400}, {"meal_id": "m3", "kcal": 1000, "protein_g": 30},
             {"meal_id": "mx", "kcal": 9999}, {"meal_id": "orphan", "kcal": 5}]
    h = H.build_history(meals, items, date(2026, 11, 1), date(2026, 11, 5), PROFILE)
    assert [d["date"] for d in h["days"]] == ["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"]
    assert [d["kcal"] for d in h["days"]] == [0, 1000, 0, 1000, 0]
    assert [d["logged"] for d in h["days"]] == [False, True, False, True, False]
    assert h["days_logged"] == 2 and h["averages"]["kcal"] == 1000 and h["averages"]["protein_g"] == 15
    assert h["targets"]["kcal"] == 2000 and h["targets"]["sugar_g"] == 50
    empty = H.build_history([], [], date(2026, 11, 1), date(2026, 11, 1), None)
    assert empty["averages"]["kcal"] == 0 and empty["targets"]["kcal"] is None and empty["days_logged"] == 0


def test_history_endpoint_scoped_and_ranged(env):
    c, db, cur = env
    seed(db, "A", "2026-11-05", "lunch", 600)
    seed(db, "A", "2026-11-07", "dinner", 800)
    seed(db, "A", "2026-10-01", "dinner", 999)   # outside range
    seed(db, "B", "2026-11-05", "lunch", 5000)   # other user
    r = c.get("/api/history", params={"from": "2026-11-01", "to": "2026-11-07"})
    j = r.json()
    assert r.status_code == 200 and len(j["days"]) == 7
    assert {d["date"]: d["kcal"] for d in j["days"] if d["logged"]} == {"2026-11-05": 600, "2026-11-07": 800}
    assert j["averages"]["kcal"] == 700 and j["days_logged"] == 2
    cur["u"] = User("B", "b@x.com")
    assert c.get("/api/history", params={"from": "2026-11-05", "to": "2026-11-05"}).json()["days"][0]["kcal"] == 5000


def test_history_defaults_validation_and_limits(env):
    c, _, _ = env
    assert len(c.get("/api/history").json()["days"]) == 7  # default: last 7 days
    assert c.get("/api/history", params={"from": "nope"}).status_code == 422
    assert c.get("/api/history", params={"from": "2026-11-07", "to": "2026-11-01"}).status_code == 422
    assert c.get("/api/history", params={"from": "2026-01-01", "to": "2026-11-01"}).status_code == 422
    assert c.get("/api/history", params={"from": "2026-09-01", "to": "2026-11-29"}).status_code == 200  # 90 days ok


def test_history_requires_auth():
    app.dependency_overrides.clear()
    assert TestClient(app).get("/api/history").status_code == 401
    assert TestClient(app).get("/api/export.csv").status_code == 401


def test_load_range_chunks_and_paginates():
    db = FakeDb()
    for i in range(130):  # > CHUNK meals, and > 1 page for a small page size
        seed(db, "A", "2026-11-03", "snack", 10)
    meals, items = H.load_range(db, "A", date(2026, 11, 1), date(2026, 11, 7))
    assert len(meals) == 130 and len(items) == 130
    assert len(db.select_all("meals", order="id.asc", page=7)) == 130


def test_export_csv_content_and_injection_guard(env):
    c, db, cur = env
    seed(db, "A", "2026-11-05", "lunch", 612.345, name='=HYPERLINK("http://evil")', sugar_g=3)
    seed(db, "A", "2026-11-06", "dinner", 400, name="Chicken, rice")
    seed(db, "B", "2026-11-05", "lunch", 777, name="Secret")
    r = c.get("/api/export.csv", params={"from": "2026-11-01", "to": "2026-11-30"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="calorific_2026-11-01_2026-11-30.csv"' in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert [x["date"] for x in rows] == ["2026-11-05", "2026-11-06"] and "Secret" not in r.text
    assert rows[0]["food"].startswith("'=") and rows[0]["kcal"] == "612.35" and rows[0]["sugar_g"] == "3.0"
    assert rows[1]["food"] == "Chicken, rice" and rows[1]["servings"] == "" and rows[1]["edited"] == "no"
    assert list(rows[0].keys())[:4] == ["date", "meal_type", "input", "food"]
    assert c.get("/api/export.csv", params={"from": "2025-01-01", "to": "2026-11-01"}).status_code == 422
    assert c.get("/api/export.csv", params={"from": "2025-11-01", "to": "2026-10-31"}).status_code == 200  # 365 days
    assert H.export_csv([], []).strip().split(",")[0] == "date"
