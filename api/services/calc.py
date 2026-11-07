"""Pure nutrient calculator. Stores unrounded values; round_kcal() is for display only.

Quantity rules (food = matched reference row, may be None):
- composite dish / per-serving-only food, non-mass unit -> per_serving x portion.amount
- per_100g available -> per_100g x grams / 100 (grams = amount if mass unit, else est_grams, else serving_g x amount)
- no reference -> the model's own estimate for the stated portion (source "estimated")
Modifiers (less rice, kosong/no sugar, siew dai) adjust reference-based results unless the matched food
name already encodes the variant (e.g. an HPB "Kopi O kosong" entry)."""
import os
from dataclasses import dataclass

from api.schemas import FoodItem
from api.services.foodref import NUTRIENTS, FoodRef

MASS_UNITS = {"g", "gram", "grams", "ml", "millilitre", "milliliter", "millilitres", "milliliters"}


@dataclass(frozen=True)
class CalcConfig:
    rice_kcal_share: float = 0.5   # share of a rice dish's kcal/carbs that comes from the rice
    less_rice_factor: float = 0.5  # "less rice" keeps this fraction of the rice
    no_sugar_removal: float = 0.8  # kosong / no sugar removes this fraction of sugar
    siew_dai_removal: float = 0.4  # siew dai / less sugar removes this fraction of sugar


def config_from_env() -> CalcConfig:
    d = CalcConfig()
    f = lambda k, default: float(os.getenv(k, default))  # noqa: E731
    return CalcConfig(
        f("RICE_KCAL_SHARE", d.rice_kcal_share), f("LESS_RICE_FACTOR", d.less_rice_factor),
        f("NO_SUGAR_REMOVAL", d.no_sugar_removal), f("SIEW_DAI_REMOVAL", d.siew_dai_removal),
    )


@dataclass(frozen=True)
class Nutrition:
    nutrients: dict[str, float]
    grams: float | None
    servings: float | None
    source: str  # sgfoodid | usda | estimated


def round_kcal(kcal: float) -> int:
    """Display rounding: nearest 5 kcal."""
    return int(5 * round(kcal / 5))


def _scale(d: dict, f: float) -> dict[str, float]:
    return {k: float(d.get(k, 0) or 0) * f for k in NUTRIENTS}


def _from_serving(food: FoodRef, amount: float, est_grams: float | None) -> tuple[dict, float | None, float]:
    grams = food.serving_g * amount if food.serving_g else est_grams
    return _scale(food.per_serving, amount), grams, amount


def _from_food(item: FoodItem, food: FoodRef, amount: float, mass: bool) -> Nutrition | None:
    ps, p100, sg, est_g = food.per_serving, food.per_100g, food.serving_g, item.portion.est_grams
    if ps and not mass and (item.is_composite_dish or not p100):
        n, g, s = _from_serving(food, amount, est_g)
        return Nutrition(n, g, s, food.source)
    if p100:
        grams = amount if mass else (est_g or (sg * amount if sg else None))
        if grams is None:
            if not ps:
                return None
            n, g, s = _from_serving(food, amount, est_g)
            return Nutrition(n, g, s, food.source)
        return Nutrition(_scale(p100, grams / 100.0), grams, grams / sg if sg else None, food.source)
    if ps:  # per-serving only, mass-unit portion
        servings = amount / sg if sg else 1.0
        return Nutrition(_scale(ps, servings), amount, servings, food.source)
    return None


def _from_estimate(item: FoodItem, amount: float, mass: bool) -> Nutrition:
    n = item.est_nutrients.model_dump() if item.est_nutrients else {}
    grams = item.portion.est_grams or (amount if mass else None)
    return Nutrition(_scale(n, 1.0), grams, None if mass else amount, "estimated")


def _remove_sugar(n: dict[str, float], fraction: float) -> None:
    removed = n["sugar_g"] * fraction
    n["sugar_g"] -= removed
    n["carbs_g"] = max(0.0, n["carbs_g"] - removed)
    n["kcal"] = max(0.0, n["kcal"] - 4 * removed)


def apply_modifiers(n: dict[str, float], modifiers: list[str], matched_name: str, cfg: CalcConfig) -> dict[str, float]:
    out, name = dict(n), matched_name.lower()
    text = " | ".join(m.lower() for m in modifiers)
    if ("less rice" in text or "half rice" in text) and "less rice" not in name:
        keep = 1 - cfg.rice_kcal_share * (1 - cfg.less_rice_factor)
        for k in ("kcal", "carbs_g", "fibre_g"):
            out[k] *= keep
    if any(w in text for w in ("kosong", "no sugar", "sugar free", "sugar-free")) and not any(
        w in name for w in ("kosong", "no sugar", "unsweetened")
    ):
        _remove_sugar(out, cfg.no_sugar_removal)
    elif any(w in text for w in ("siew dai", "less sugar", "less sweet")) and "siew dai" not in name:
        _remove_sugar(out, cfg.siew_dai_removal)
    return out


def compute_item(item: FoodItem, food: FoodRef | None, cfg: CalcConfig = CalcConfig()) -> Nutrition:
    amount = item.portion.amount
    mass = item.portion.unit.strip().lower() in MASS_UNITS
    base = _from_food(item, food, amount, mass) if food else None
    if base is None:
        return _from_estimate(item, amount, mass)  # model's own estimate; modifiers already implied
    return Nutrition(apply_modifiers(base.nutrients, item.modifiers, food.name, cfg), base.grams, base.servings, base.source)
