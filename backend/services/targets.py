"""Daily target calculation: Mifflin-St Jeor BMR x activity factor +/- goal adjustment."""
from dataclasses import dataclass
from datetime import datetime, timezone

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}
GOAL_ADJUSTMENTS = {"lose": -500.0, "maintain": 0.0, "gain": 300.0}
MACRO_SPLIT = (0.30, 0.40, 0.30)  # protein / carbs / fat share of kcal
KCAL_PER_G = (4.0, 4.0, 9.0)
MIN_KCAL = 1200.0  # safety floor for auto-calculated targets
DEFAULT_CAP_SUGAR_G = 50.0
DEFAULT_CAP_SODIUM_MG = 2000.0


@dataclass(frozen=True)
class Targets:
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


def bmr(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    """Mifflin-St Jeor basal metabolic rate (kcal/day)."""
    if sex not in ("male", "female"):
        raise ValueError("sex must be 'male' or 'female'")
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if sex == "male" else -161)


def macros_for(kcal: float, split: tuple[float, float, float] = MACRO_SPLIT) -> Targets:
    p, c, f = (kcal * s / k for s, k in zip(split, KCAL_PER_G))
    return Targets(kcal=kcal, protein_g=p, carbs_g=c, fat_g=f)


def calculate_targets(
    sex: str,
    birth_year: int,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    goal: str,
    *,
    today_year: int | None = None,
    adjustments: dict[str, float] | None = None,
) -> Targets:
    """Return kcal and macro targets for a profile."""
    year = today_year or datetime.now(timezone.utc).year
    adj = adjustments or GOAL_ADJUSTMENTS
    tdee = bmr(sex, weight_kg, height_cm, year - birth_year) * ACTIVITY_FACTORS[activity_level]
    return macros_for(max(MIN_KCAL, tdee + adj[goal]))
