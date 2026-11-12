import io

import pytest
from fastapi.testclient import TestClient

from backend.auth import User, get_current_user
from backend.config import Settings, get_settings
from backend.db import get_db
from backend.main import app
from backend.routers_analyze import get_provider, sniff_image
from backend.services.foodref import build_food_row
from backend.services.llm import LLMTransient, MockProvider
from tests.fakes import FakeDb

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100
PROFILE = {"user_id": "A", "timezone": "Asia/Singapore", "target_kcal": 2000, "target_protein_g": 150,
           "target_carbs_g": 200, "target_fat_g": 67, "cap_sugar_g": 50, "cap_sodium_mg": 2000}


@pytest.fixture
def env():
    foods = [build_food_row("sgfoodid", "1", "Chicken rice", aliases=["Hainanese chicken rice"], serving_g=300,
                            per_serving={"kcal": 607.0, "carbs_g": 80.0})]
    db = FakeDb(foods)
    db.t["profiles"].append(dict(PROFILE))
    db.t["profiles"].append({**PROFILE, "user_id": "B"})
    cur, settings = {"u": User("A", "a@x.com")}, {"s": Settings(limit_per_user=3, limit_global=5, vision_models=["a", "b"], text_models=["a", "b"])}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: cur["u"]
    app.dependency_overrides[get_settings] = lambda: settings["s"]
    app.dependency_overrides[get_provider] = lambda: MockProvider()
    yield TestClient(app), db, cur
    app.dependency_overrides.clear()


def photo(c, data=JPEG, name="m.jpg", ctype="image/jpeg", **form):
    return c.post("/api/analyze/photo", files={"image": (name, io.BytesIO(data), ctype)}, data=form)


def test_photo_auto_saves_with_hpb_style_match_and_summary(env):
    c, db, _ = env
    r = photo(c, note="lunch")
    assert r.status_code == 200
    j = r.json()
    item = j["meal"]["items"][0]
    assert item["source"] == "sgfoodid" and item["kcal"] == 607 and j["meal"]["input_type"] == "photo"
    assert j["summary"]["totals"]["kcal"] == 607 and j["summary"]["item_count"] == 1
    assert j["usage"]["remaining"] == 2  # 3 per-user cap, this call already counted
    assert len(db.t["meals"]) == 1 and "model_raw_json" in db.t["meal_items"][0]


def test_text_analyze_estimates_when_no_reference_match(env):
    c, db, _ = env
    r = c.post("/api/analyze/text", json={"text": "2 roti prata + teh tarik"})
    assert r.status_code == 200
    items = r.json()["meal"]["items"]
    assert [i["name"] for i in items] == ["roti prata", "teh tarik"] and all(i["source"] == "estimated" for i in items)
    assert r.json()["summary"]["item_count"] == 2
    assert c.post("/api/analyze/text", json={"text": "a"}).status_code == 422


def test_photo_validation(env):
    c, db, _ = env
    assert photo(c, data=b"hello", name="a.txt", ctype="text/plain").status_code == 415
    assert photo(c, data=b"GIF89a" + b"0" * 50, ctype="image/jpeg").status_code == 415  # header lies
    assert photo(c, data=JPEG + b"0" * 1_500_000).status_code == 413
    assert db.t["usage_counters"] == []  # rejected before any model call


def test_requires_profile_and_auth(env):
    c, db, cur = env
    cur["u"] = User("Z", "z@x.com")
    assert c.post("/api/analyze/text", json={"text": "laksa"}).status_code == 409
    app.dependency_overrides.pop(get_current_user)
    assert c.post("/api/analyze/text", json={"text": "laksa"}).status_code == 401


def test_quota_cap_returns_clear_error_and_search_still_works(env):
    c, db, _ = env
    for _ in range(3):
        assert c.post("/api/analyze/text", json={"text": "laksa"}).status_code == 200
    r = c.post("/api/analyze/text", json={"text": "laksa"})
    assert r.status_code == 429 and "Daily AI limit reached" in r.json()["detail"]
    assert c.get("/api/usage").json()["remaining"] == 0
    assert c.get("/api/foods/search", params={"q": "chicken rice"}).status_code == 200  # no model call


def test_not_food_not_saved(env):
    c, db, _ = env
    class NotFood:
        def complete(self, **k): return '{"not_food": true, "items": []}'
    app.dependency_overrides[get_provider] = lambda: NotFood()
    r = c.post("/api/analyze/text", json={"text": "my cat"})
    assert r.json()["not_food"] is True and r.json()["meal"] is None and db.t["meals"] == []


def test_all_models_down_is_friendly_503(env):
    c, _, _ = env
    class Down:
        def complete(self, **k): raise LLMTransient("x")
    app.dependency_overrides[get_provider] = lambda: Down()
    r = c.post("/api/analyze/text", json={"text": "laksa"})
    assert r.status_code == 503 and "busy" in r.json()["detail"]


def test_bad_model_output_is_502(env):
    c, _, _ = env
    class Junk:
        def complete(self, **k): return "I cannot help"
    app.dependency_overrides[get_provider] = lambda: Junk()
    assert c.post("/api/analyze/text", json={"text": "laksa"}).status_code == 502


def test_delete_meal_scoped_to_owner(env):
    c, db, cur = env
    mid = c.post("/api/analyze/text", json={"text": "chicken rice"}).json()["meal"]["id"]
    cur["u"] = User("B", "b@x.com")
    assert c.delete(f"/api/meals/{mid}").status_code == 404 and len(db.t["meals"]) == 1
    cur["u"] = User("A", "a@x.com")
    r = c.delete(f"/api/meals/{mid}")
    assert r.status_code == 200 and r.json()["summary"]["item_count"] == 0 and db.t["meal_items"] == []


def test_user_cannot_see_other_users_summary_after_logging(env):
    c, db, cur = env
    c.post("/api/analyze/text", json={"text": "chicken rice"})
    cur["u"] = User("B", "b@x.com")
    r = c.post("/api/analyze/text", json={"text": "laksa"})
    assert r.json()["summary"]["item_count"] == 1  # only B's own item


def test_failed_item_insert_rolls_back_meal(env):
    c, db, _ = env
    orig = db.insert
    def flaky(table, rows):
        if table == "meal_items":
            raise RuntimeError("db down")
        return orig(table, rows)
    db.insert = flaky
    with pytest.raises(RuntimeError):
        c.post("/api/analyze/text", json={"text": "laksa"})
    assert db.t["meals"] == []


def test_provider_selection():
    s = Settings(llm_mock=False, openrouter_api_key="")
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        get_provider(s)
    from backend.services.llm import OpenRouterProvider
    assert isinstance(get_provider(Settings(llm_mock=False, openrouter_api_key="k")), OpenRouterProvider)
    assert isinstance(get_provider(Settings(llm_mock=True)), MockProvider)


def test_sniff_image():
    assert sniff_image(b"\x89PNG\r\n\x1a\n....") == "image/png"
    assert sniff_image(b"RIFF1234WEBPxxxx") == "image/webp"
    assert sniff_image(b"nope") is None


def test_no_models_configured_is_clean_error():
    from backend.services.analyzer import Analyzer, AnalysisError
    with pytest.raises(AnalysisError):
        Analyzer(MockProvider(), lambda: True).analyze_text("x", [])


def test_slow_photo_analysis_does_not_block_other_requests(env):
    """The photo endpoint's blocking work must run off the event loop (health stays responsive)."""
    import asyncio
    import time

    import httpx

    class SlowProvider(MockProvider):
        def complete(self, **kw):
            time.sleep(0.6)  # a blocking model call
            return super().complete(**kw)

    app.dependency_overrides[get_provider] = lambda: SlowProvider()

    async def go() -> float:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            t = time.perf_counter()
            slow = asyncio.create_task(c.post("/api/analyze/photo", files={"image": ("m.jpg", JPEG, "image/jpeg")}))
            await asyncio.sleep(0.1)  # let the slow request reach its blocking model call
            assert (await c.get("/api/health")).status_code == 200
            health_time = time.perf_counter() - t
            assert (await slow).status_code == 200
            return health_time

    assert asyncio.run(go()) < 0.3
