import pytest

from backend.services.foodref import FoodRef, build_food_row, derive_missing, nutrient_dict, parse_number, usda_nutrients


@pytest.mark.parametrize("v,exp", [
    ("1,234.5", 1234.5), ("<1", 1.0), ("tr", 0.0), ("-", None), ("", None), (None, None),
    (12, 12.0), ("abc", None), (float("nan"), None), (True, None), ("N/A", None),
])
def test_parse_number(v, exp):
    assert parse_number(v) == exp


def test_nutrient_dict_requires_kcal_and_fills_zero():
    assert nutrient_dict({"protein_g": 5}) is None
    d = nutrient_dict({"kcal": "100", "sodium_mg": "0.5"}, scale={"sodium_mg": 1000})
    assert d["kcal"] == 100 and d["sodium_mg"] == 500 and d["fibre_g"] == 0


def test_derive_both_directions():
    ps = {"kcal": 600.0}
    assert derive_missing(ps, None, 300)[1] == {"kcal": 200.0}
    assert derive_missing(None, {"kcal": 200.0}, 300)[0] == {"kcal": 600.0}
    assert derive_missing(ps, None, None) == (ps, None)


def test_build_food_row_aliases_and_rejects():
    assert build_food_row("sgfoodid", "1", "  ") is None
    assert build_food_row("sgfoodid", "1", "X") is None
    r = build_food_row("sgfoodid", "1", "Nasi Lemak", aliases=["nasi lemak", "Coconut rice", ""],
                       serving_g=300, per_serving={"kcal": 600.0})
    assert r["aliases"] == ["Coconut rice"] and r["per_100g"]["kcal"] == 200.0


def test_usda_nutrients_energy_priority_and_missing():
    pairs = [(2047, "50"), (1008, "70"), (1003, "3"), (1093, "10"), (9999, "1")]
    d = usda_nutrients(pairs)
    assert d["kcal"] == 70 and d["protein_g"] == 3 and d["sodium_mg"] == 10
    assert usda_nutrients([(2048, "42")])["kcal"] == 42
    assert usda_nutrients([(1003, "3")]) is None


def test_foodref_from_row():
    f = FoodRef.from_row({"id": 1, "source": "usda", "name": "x", "serving_g": "100", "score": 0.5})
    assert f.serving_g == 100.0 and f.score == 0.5 and not f.is_exact


def test_usda_nutrients_fndds_number_scheme():
    d = usda_nutrients([(208, "300"), (203, "20"), (204, "10"), (205, "40"), (291, "3"), (269, "5"), (307, "600")])
    assert d == {"kcal": 300, "protein_g": 20, "fat_g": 10, "carbs_g": 40, "sugar_g": 5, "sodium_mg": 600, "fibre_g": 3}
