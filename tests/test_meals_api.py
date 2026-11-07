import pytest
from fastapi.testclient import TestClient

from backend.auth import User, get_current_user
from backend.config import Settings, get_settings
from backend.db import get_db
from backend.main import app
from backend.routers_analyze import get_provider
from backend.services.calc import recompute_item
from backend.services.foodref import FoodRef, build_food_row
from backend.services.llm import MockProvider
from tests.fakes import FakeDb

PROFILE = {"user_id": "A", "timezone": "Asia/Singapore", "target_kcal": 2000, "target_protein_g": 150,
           "target_carbs_g": 200, "target_fat_g": 67, "cap_sugar_g": 50, "cap_sodium_mg": 2000}


@pytest.fixture
def env():
    foods = [
        build_food_row("sgfoodid", "1", "Chicken rice", serving_g=300, per_serving={"kcal": 600.0, "carbs_g": 80.0}),
        build_food_row("usda", "2", "Rice, white, cooked", per_100g={"kcal": 130.0, "carbs_g": 28.0}),
        build_food_row("sgfoodid", "3", "Odd food", per_serving={"kcal": 1.0}),
    ]
    db = FakeDb(foods)
    db.t["profiles"] += [dict(PROFILE), {**PROFILE, "user_id": "B"}]
    cur = {"u": User("A", "a@x.com")}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: cur["u"]
    app.dependency_overrides[get_settings] = lambda: Settings(vision_models=["a"], text_models=["a"])
    app.dependency_overrides[get_provider] = lambda: MockProvider()
    yield TestClient(app), db, cur
    app.dependency_overrides.clear()


def log(c, text="chicken rice"):
    return c.post("/api/analyze/text", json={"text": text}).json()["meal"]


def test_day_summary_lists_meals_with_items(env):
    c, db, _ = env
    meal = log(c, "chicken rice + laksa")
    r = c.get(f"/api/days/{meal['local_date']}/summary")
    j = r.json()
    assert r.status_code == 200 and j["item_count"] == 2 and len(j["meals"]) == 1 and len(j["meals"][0]["items"]) == 2
    assert c.get("/api/days/2020-01-01/summary").json()["item_count"] == 0
    assert c.get("/api/days/not-a-date/summary").status_code == 422


def test_patch_meal_type_and_note(env):
    c, db, _ = env
    mid = log(c)["id"]
    r = c.patch(f"/api/meals/{mid}", json={"meal_type": "snack", "note": "late"})
    assert r.status_code == 200 and db.t["meals"][0]["meal_type"] == "snack" and db.t["meals"][0]["note"] == "late"
    assert c.patch(f"/api/meals/{mid}", json={"meal_type": "brunch"}).status_code == 422
    assert c.patch(f"/api/meals/{mid}", json={}).status_code == 200


def test_swap_food_recomputes_and_marks_edited(env):
    c, db, _ = env
    item = log(c)["items"][0]
    rice = db.t["food_reference"][1]["id"]
    r = c.patch(f"/api/meal-items/{item['id']}", json={"food_ref_id": rice, "grams": 200})
    assert r.status_code == 200
    row = db.t["meal_items"][0]
    assert row["name"] == "Rice, white, cooked" and row["source"] == "usda" and row["kcal"] == 260
    assert row["grams"] == 200 and row["user_edited"] is True and row["food_ref_id"] == rice
    assert r.json()["summary"]["totals"]["kcal"] == 260


def test_change_portion_with_existing_food_ref(env):
    c, db, _ = env
    chicken = db.t["food_reference"][0]["id"]
    mid = c.post("/api/meals/manual", json={"food_ref_id": chicken}).json()["meal"]["items"][0]["id"]
    assert db.t["meal_items"][0]["kcal"] == 600 and db.t["meal_items"][0]["servings"] == 1
    c.patch(f"/api/meal-items/{mid}", json={"servings": 2})
    assert db.t["meal_items"][0]["kcal"] == 1200 and db.t["meal_items"][0]["name"] == "Chicken rice"
    c.patch(f"/api/meal-items/{mid}", json={"name": "My lunch"})
    assert db.t["meal_items"][0]["name"] == "My lunch" and db.t["meal_items"][0]["kcal"] == 1200


def test_scale_estimated_item_without_food(env):
    c, db, _ = env
    item = log(c, "2 laksa")["items"][0]
    assert item["source"] == "estimated" and item["kcal"] == 600
    c.patch(f"/api/meal-items/{item['id']}", json={"servings": 1})
    assert db.t["meal_items"][0]["kcal"] == 300
    assert c.patch(f"/api/meal-items/{item['id']}", json={}).status_code == 422  # nothing to scale by


def test_item_validation_and_unknown_food(env):
    c, db, _ = env
    item = log(c)["items"][0]
    assert c.patch(f"/api/meal-items/{item['id']}", json={"grams": -5}).status_code == 422
    assert c.patch(f"/api/meal-items/{item['id']}", json={"food_ref_id": 9999}).status_code == 404
    odd = db.t["food_reference"][2]["id"]
    assert c.patch(f"/api/meal-items/{item['id']}", json={"food_ref_id": odd, "grams": 50}).status_code == 422


def test_delete_item_removes_empty_meal(env):
    c, db, _ = env
    meal = log(c, "chicken rice + laksa")
    ids = [i["id"] for i in meal["items"]]
    c.delete(f"/api/meal-items/{ids[0]}")
    assert len(db.t["meals"]) == 1 and len(db.t["meal_items"]) == 1
    r = c.delete(f"/api/meal-items/{ids[1]}")
    assert db.t["meals"] == [] and r.json()["summary"]["item_count"] == 0


def test_add_item_to_meal_and_manual_add_without_model_call(env):
    c, db, _ = env
    chicken, rice = (db.t["food_reference"][i]["id"] for i in (0, 1))
    r = c.post("/api/meals/manual", json={"food_ref_id": rice, "grams": 150, "meal_type": "dinner"})
    assert r.status_code == 200 and r.json()["meal"]["meal_type"] == "dinner" and db.t["usage_counters"] == []
    assert db.t["meal_items"][0]["kcal"] == pytest.approx(195) and db.t["meal_items"][0]["confidence"] is None
    mid = r.json()["meal"]["id"]
    c.post(f"/api/meals/{mid}/items", json={"food_ref_id": chicken})
    assert len(db.t["meal_items"]) == 2 and c.post(f"/api/meals/{mid}/items", json={"food_ref_id": 999}).status_code == 404
    odd = db.t["food_reference"][2]["id"]
    assert c.post("/api/meals/manual", json={"food_ref_id": odd, "grams": 10}).status_code == 422
    # default portion for a per-100g-only food is 100 g
    c.post("/api/meals/manual", json={"food_ref_id": rice})
    assert db.t["meal_items"][-1]["grams"] == 100


def test_manual_requires_profile(env):
    c, db, cur = env
    cur["u"] = User("Z", "z@x.com")
    assert c.post("/api/meals/manual", json={"food_ref_id": 1}).status_code == 409


def test_ownership_everywhere(env):
    c, db, cur = env
    meal = log(c)
    item = meal["items"][0]
    cur["u"] = User("B", "b@x.com")
    assert c.patch(f"/api/meals/{meal['id']}", json={"note": "x"}).status_code == 404
    assert c.delete(f"/api/meals/{meal['id']}").status_code == 404
    assert c.patch(f"/api/meal-items/{item['id']}", json={"grams": 10}).status_code == 404
    assert c.delete(f"/api/meal-items/{item['id']}").status_code == 404
    assert c.post(f"/api/meals/{meal['id']}/items", json={"food_ref_id": 1}).status_code == 404
    assert c.patch("/api/meal-items/nope", json={"grams": 1}).status_code == 404
    assert c.get(f"/api/days/{meal['local_date']}/summary").json()["item_count"] == 0
    assert len(db.t["meals"]) == 1 and len(db.t["meal_items"]) == 1  # untouched


def F(**k):
    d = dict(id=1, source="sgfoodid", source_id="x", name="f")
    return FoodRef(**{**d, **k})


def test_recompute_remaining_branches():
    # grams on per-serving-only food with serving_g
    r = recompute_item({}, F(per_serving={"kcal": 300.0}, serving_g=300), 150, None)
    assert r["kcal"] == 150 and r["servings"] == 0.5
    # servings on per-100g-only food with serving_g
    r = recompute_item({}, F(per_100g={"kcal": 100.0}, serving_g=40), None, 2)
    assert r["kcal"] == 80 and r["grams"] == 80
    # per-serving food without serving_g: grams unknown
    r = recompute_item({}, F(per_serving={"kcal": 50.0}), None, 2)
    assert r["kcal"] == 100 and r["grams"] is None
    # keep current servings when no portion given
    assert recompute_item({"servings": 3}, F(per_serving={"kcal": 10.0}), None, None)["kcal"] == 30
    # grams on a food that cannot support grams
    assert recompute_item({}, F(per_serving={"kcal": 1.0}), 10, None) is None
    # per-100g only food, no serving_g, servings given
    assert recompute_item({}, F(per_100g={"kcal": 1.0}), None, 2) is None
    # rescale: grams ratio, servings ratio
    cur = {"kcal": 200, "grams": 100, "servings": 1}
    r = recompute_item(cur, None, 50, None)
    assert r["kcal"] == 100 and r["grams"] == 50 and r["servings"] == 0.5
    assert recompute_item({"kcal": 200, "servings": 2}, None, None, 1)["grams"] is None
