"""Speed-related behaviour: skip empty sources, parallel resolution, cached source check, env timeout."""
import threading
import time

from backend.config import get_settings
from backend.schemas import AnalysisResult, FoodItem
from backend.services import foodrepo
from backend.services.calc import CalcConfig
from backend.services.foodref import build_food_row
from backend.services.foodrepo import DbFoodRepo
from backend.services.pipeline import build_item_rows
from backend.services.resolver import Resolution, Resolver
from tests.fakes import FakeDb, FakeRepo


class NoSgRepo(FakeRepo):
    """Reports that SG FoodID is not loaded, like a database before HPB data is ingested."""
    def has_source(self, source):
        return source != "sgfoodid"


def test_resolver_skips_search_of_unloaded_source():
    repo = NoSgRepo([build_food_row("usda", "u1", "Rice, white, cooked", per_100g={"kcal": 130.0})])
    seen = []
    orig = repo.search
    repo.search = lambda q, source, *a: (seen.append(source), orig(q, source, *a))[1]
    res = Resolver(repo).resolve("rice white cooked")
    assert res.method == "usda_local" and "sgfoodid" not in seen


def test_resolver_still_searches_sg_when_source_unknown():
    repo = FakeRepo([build_food_row("sgfoodid", "s1", "Chicken rice", serving_g=300, per_serving={"kcal": 607.0})])
    assert Resolver(repo).resolve("Chicken rice").method == "sg_exact"  # repo without has_source: search as before


def test_has_source_is_cached_and_reflects_data():
    foodrepo._has_source_cache.clear()
    db = FakeDb()
    calls = []
    orig = db.select
    db.select = lambda table, **f: (calls.append(table), orig(table, **f))[1]
    repo = DbFoodRepo(db)
    assert repo.has_source("sgfoodid") is False
    assert repo.has_source("sgfoodid") is False
    assert calls == ["food_reference"]  # second call served from cache
    foodrepo._has_source_cache.clear()


def test_items_resolve_in_parallel_and_keep_order():
    names = ["Laksa", "Nasi lemak", "Teh tarik", "Kaya toast"]
    result = AnalysisResult(items=[FoodItem(name=n) for n in names])
    active, peak, lock = 0, 0, threading.Lock()

    class SlowResolver:
        def resolve(self, name, aliases=()):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return Resolution(None, "estimated")

    rows = build_item_rows(result, SlowResolver(), CalcConfig())
    assert [r["name"] for r in rows] == names
    assert peak > 1


def test_llm_timeout_comes_from_env(monkeypatch):
    assert get_settings().llm_timeout_s == 25
    monkeypatch.setenv("LLM_TIMEOUT_S", "40")
    assert get_settings().llm_timeout_s == 40
