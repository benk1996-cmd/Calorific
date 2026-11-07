import httpx
import pytest

from api.services.foodref import build_food_row
from api.services.resolver import Resolver
from api.services.usda import UsdaClient
from tests.fakes import FakeRepo

SG_DISHES = [
    ("Chicken rice", ["Hainanese chicken rice"], 607), ("Char kway teow", ["CKT"], 744),
    ("Nasi lemak", [], 494), ("Laksa", ["Curry laksa"], 589), ("Roti prata, plain", ["Roti prata"], 209),
    ("Teh tarik", [], 125), ("Kopi", ["Coffee with milk and sugar"], 110), ("Kopi O kosong", ["Black coffee no sugar"], 5),
    ("Wanton mee", ["Wonton noodles"], 409), ("Bak chor mee", ["Minced meat noodles"], 450),
    ("Fish ball noodle soup", [], 320), ("Mee goreng", [], 650), ("Carrot cake, fried", ["Chai tow kway"], 400),
    ("Satay, chicken", [], 35), ("Hokkien mee", ["Fried Hokkien prawn mee"], 580),
    ("Bee hoon, fried", [], 420), ("Ice kachang", [], 200), ("Kaya toast", [], 150),
    ("Soft boiled egg", [], 70), ("Teh O kosong", [], 2),
]
USDA = [("Chicken, broilers or fryers, breast, meat only, roasted", 165), ("Rice, white, cooked", 130)]


def make_repo():
    rows = []
    for i, (n, al, kcal) in enumerate(SG_DISHES):
        rows.append(build_food_row("sgfoodid", f"sg{i}", n, aliases=al, serving_g=300, per_serving={"kcal": float(kcal)}))
    for i, (n, kcal) in enumerate(USDA):
        rows.append(build_food_row("usda", f"u{i}", n, per_100g={"kcal": float(kcal)}))
    return FakeRepo(rows)


@pytest.mark.parametrize("query,expected,method", [
    ("Chicken rice", "Chicken rice", "sg_exact"),
    ("hainanese chicken rice", "Chicken rice", "sg_exact"),  # alias, case-insensitive
    ("CKT", "Char kway teow", "sg_exact"),
    ("Chai tow kway", "Carrot cake, fried", "sg_exact"),
    ("char kuay teow", "Char kway teow", "sg_fuzzy"),
    ("nasi lemak with egg", "Nasi lemak", "sg_fuzzy"),
    ("curry laksa soup", "Laksa", "sg_fuzzy"),
    ("roti prata plain", "Roti prata, plain", "sg_fuzzy"),
    ("teh tarik", "Teh tarik", "sg_exact"),
    ("kopi o kosong", "Kopi O kosong", "sg_exact"),
    ("wonton noodles", "Wanton mee", "sg_exact"),
    ("minced meat noodles", "Bak chor mee", "sg_exact"),
    ("fish ball noodles soup", "Fish ball noodle soup", "sg_fuzzy"),
    ("mee goreng", "Mee goreng", "sg_exact"),
    ("chicken satay", "Satay, chicken", "sg_fuzzy"),
    ("fried hokkien prawn mee", "Hokkien mee", "sg_exact"),
    ("fried bee hoon", "Bee hoon, fried", "sg_fuzzy"),
    ("ice kachang", "Ice kachang", "sg_exact"),
    ("kaya toast", "Kaya toast", "sg_exact"),
    ("teh o kosong", "Teh O kosong", "sg_exact"),
])
def test_sg_dishes_resolve(query, expected, method):
    res = Resolver(make_repo()).resolve(query)
    assert res.food is not None and res.food.name == expected
    assert res.method == method


def test_alias_list_from_model_used():
    res = Resolver(make_repo()).resolve("Mystery noodle", aliases=["Wanton mee"])
    assert res.food.name == "Wanton mee" and res.method == "sg_exact"


def test_sg_preferred_over_usda_and_usda_local_fallback():
    r = Resolver(make_repo(), threshold=0.4)
    assert r.resolve("rice white cooked").method == "usda_local"
    assert r.resolve("rice white cooked").food.source == "usda"


def test_estimated_when_nothing_matches_and_empty():
    r = Resolver(make_repo())
    assert r.resolve("zzzz qqqq") == r.resolve("zzzz qqqq") and r.resolve("zzzz qqqq").method == "estimated"
    assert r.resolve("   ").method == "estimated"
    assert r.resolve("zzzz", aliases=[""]).food is None


def test_llm_pick_hook_only_when_enabled():
    calls = []

    def pick(name, cands):
        calls.append((name, [c.name for c in cands]))
        return cands[1]

    repo = make_repo()
    plain = Resolver(repo, threshold=0.4).resolve("teh kosong")
    assert plain.food.name == "Teh O kosong" and not calls
    picked = Resolver(repo, threshold=0.4, llm_pick=pick).resolve("teh kosong")
    assert picked.food.name == "Kopi O kosong" and picked.method == "sg_fuzzy" and calls


def usda_payload():
    return {"foods": [
        {"fdcId": 1, "description": "No energy", "foodNutrients": [{"nutrientId": 1003, "value": 1}]},
        {"fdcId": 170, "description": "Egg, whole, raw", "foodNutrients": [
            {"nutrientId": 1008, "value": 143}, {"nutrientId": 1003, "value": 12.6}]},
    ]}


def test_usda_api_fallback_caches_and_skips_unusable():
    seen = {}
    def handler(req):
        seen["params"] = dict(req.url.params)
        return httpx.Response(200, json=usda_payload())
    repo = make_repo()
    usda = UsdaClient("KEY", repo, http=httpx.Client(transport=httpx.MockTransport(handler)))
    res = Resolver(repo, usda).resolve("raw whole egg")
    assert res.method == "usda_api" and res.food.name == "Egg, whole, raw"
    assert res.food.per_100g["kcal"] == 143
    assert repo.saved and repo.saved[0]["source_id"] == "170"
    assert "Branded" not in seen["params"]["dataType"] and seen["params"]["api_key"] == "KEY"


def test_usda_backoff_on_429_then_success():
    n = {"c": 0}; sleeps = []
    def handler(req):
        n["c"] += 1
        return httpx.Response(429) if n["c"] < 3 else httpx.Response(200, json=usda_payload())
    c = UsdaClient("K", http=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append)
    assert c.lookup("egg").name == "Egg, whole, raw" and sleeps == [1, 2]


def test_usda_gives_up_and_handles_no_key_and_errors():
    c = UsdaClient("K", http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429))), sleep=lambda s: None)
    assert c.lookup("egg") is None
    assert UsdaClient("").lookup("egg") is None
    assert UsdaClient("K", http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))).lookup("x") is None
    def boom(req): raise httpx.ConnectError("down")
    assert UsdaClient("K", http=httpx.Client(transport=httpx.MockTransport(boom))).lookup("x") is None
    empty = UsdaClient("K", http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))))
    assert empty.lookup("x") is None
