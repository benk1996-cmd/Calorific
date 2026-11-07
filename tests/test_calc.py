import pytest

from api.schemas import EstNutrients, FoodItem, Portion
from api.services.calc import CalcConfig, apply_modifiers, compute_item, config_from_env, round_kcal
from api.services.foodref import FoodRef

N = lambda **k: {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "sugar_g": 0.0, "sodium_mg": 0.0, "fibre_g": 0.0, **k}  # noqa: E731


def item(amount=1, unit="serving", grams=None, composite=False, mods=(), est=None, name="X"):
    return FoodItem(name=name, is_composite_dish=composite, modifiers=list(mods),
                    portion=Portion(amount=amount, unit=unit, est_grams=grams), est_nutrients=est)


def food(ps=None, p100=None, sg=None, name="Food", source="sgfoodid"):
    return FoodRef(id=1, source=source, source_id="1", name=name, serving_g=sg, per_serving=ps, per_100g=p100)


def test_round_kcal():
    assert round_kcal(612) == 610 and round_kcal(613) == 615 and round_kcal(2) == 0


def test_composite_uses_per_serving_scaled_by_amount():
    n = compute_item(item(2, "plate", 700, composite=True), food(ps=N(kcal=600), p100=N(kcal=200), sg=300))
    assert n.nutrients["kcal"] == 1200 and n.servings == 2 and n.grams == 600 and n.source == "sgfoodid"


def test_per_serving_only_without_serving_g_uses_est_grams():
    n = compute_item(item(1, "plate", 350), food(ps=N(kcal=500)))
    assert n.nutrients["kcal"] == 500 and n.grams == 350


def test_non_composite_uses_per_100g_with_est_grams():
    n = compute_item(item(1, "piece", 150), food(ps=N(kcal=100), p100=N(kcal=200), sg=50, source="usda"))
    assert n.nutrients["kcal"] == 300 and n.grams == 150 and n.servings == 3 and n.source == "usda"


def test_per_100g_mass_unit_and_no_serving_g():
    n = compute_item(item(200, "g"), food(p100=N(kcal=50)))
    assert n.nutrients["kcal"] == 100 and n.grams == 200 and n.servings is None


def test_per_100g_grams_from_serving_g_when_no_est():
    n = compute_item(item(2, "piece"), food(p100=N(kcal=100), sg=40))
    assert n.nutrients["kcal"] == 80 and n.grams == 80


def test_per_100g_unknown_grams_falls_back_to_serving_or_estimate():
    f_ps = food(ps=N(kcal=90), p100=N(kcal=100))
    assert compute_item(item(2, "piece", composite=False), f_ps).nutrients["kcal"] == 180
    est = EstNutrients(kcal=77)
    n = compute_item(item(1, "piece", est=est), food(p100=N(kcal=100)))
    assert n.source == "estimated" and n.nutrients["kcal"] == 77


def test_per_serving_only_with_mass_unit():
    assert compute_item(item(150, "g"), food(ps=N(kcal=300), sg=300)).nutrients["kcal"] == 150
    n = compute_item(item(150, "g"), food(ps=N(kcal=300)))
    assert n.nutrients["kcal"] == 300 and n.grams == 150


def test_food_without_nutrients_falls_back_to_estimate():
    n = compute_item(item(1, "plate", est=EstNutrients(kcal=420)), food())
    assert n.source == "estimated" and n.nutrients["kcal"] == 420


def test_estimate_no_nutrients_and_mass():
    n = compute_item(item(100, "ml"), None)
    assert n.source == "estimated" and n.nutrients["kcal"] == 0 and n.grams == 100 and n.servings is None
    n = compute_item(item(2, "bowl", 400, est=EstNutrients(kcal=500)), None)
    assert n.grams == 400 and n.servings == 2


def test_less_rice_and_variant_guard():
    f = food(ps=N(kcal=600, carbs_g=80, fibre_g=4), name="Chicken rice")
    n = compute_item(item(1, "plate", composite=True, mods=["less rice"]), f)
    assert n.nutrients["kcal"] == pytest.approx(450) and n.nutrients["carbs_g"] == pytest.approx(60)
    v = food(ps=N(kcal=500), name="Chicken rice, less rice")
    assert compute_item(item(1, "plate", composite=True, mods=["less rice"]), v).nutrients["kcal"] == 500
    assert apply_modifiers(N(kcal=100), ["Half rice"], "x", CalcConfig())["kcal"] == pytest.approx(75)


def test_sugar_modifiers():
    f = food(ps=N(kcal=120, carbs_g=20, sugar_g=15), name="Teh tarik")
    k = compute_item(item(1, "cup", composite=True, mods=["kosong"]), f).nutrients
    assert k["sugar_g"] == pytest.approx(3) and k["kcal"] == pytest.approx(120 - 48) and k["carbs_g"] == pytest.approx(8)
    s = compute_item(item(1, "cup", composite=True, mods=["less sugar"]), f).nutrients
    assert s["sugar_g"] == pytest.approx(9)
    already = food(ps=N(kcal=5, sugar_g=0), name="Kopi O kosong")
    assert compute_item(item(1, "cup", composite=True, mods=["kosong"]), already).nutrients["kcal"] == 5
    assert apply_modifiers(N(kcal=10, carbs_g=1, sugar_g=5), ["siew dai"], "teh siew dai", CalcConfig())["sugar_g"] == 5
    assert apply_modifiers(N(kcal=1, carbs_g=0.1, sugar_g=5), ["no sugar"], "x", CalcConfig())["kcal"] == 0  # floored
    assert apply_modifiers(N(kcal=10), ["extra egg"], "x", CalcConfig()) == N(kcal=10)


def test_config_from_env(monkeypatch):
    assert config_from_env() == CalcConfig()
    monkeypatch.setenv("LESS_RICE_FACTOR", "0.25")
    assert config_from_env().less_rice_factor == 0.25
