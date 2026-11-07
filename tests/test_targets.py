import pytest

from backend.services import targets as T


def test_bmr_known_values():
    assert T.bmr("male", 70, 175, 30) == pytest.approx(1648.75)
    assert T.bmr("female", 60, 165, 30) == pytest.approx(1320.25)


def test_bmr_bad_sex():
    with pytest.raises(ValueError):
        T.bmr("x", 70, 175, 30)


def test_maintain_target_and_macros():
    t = T.calculate_targets("male", 1996, 175, 70, "moderate", "maintain", today_year=2026)
    assert t.kcal == pytest.approx(1648.75 * 1.55)
    assert t.protein_g == pytest.approx(t.kcal * 0.30 / 4)
    assert t.carbs_g == pytest.approx(t.kcal * 0.40 / 4)
    assert t.fat_g == pytest.approx(t.kcal * 0.30 / 9)


@pytest.mark.parametrize("goal,delta", [("lose", -500), ("gain", 300)])
def test_goal_adjustments(goal, delta):
    base = T.calculate_targets("male", 1996, 175, 70, "moderate", "maintain", today_year=2026)
    t = T.calculate_targets("male", 1996, 175, 70, "moderate", goal, today_year=2026)
    assert t.kcal == pytest.approx(base.kcal + delta)


def test_floor_applies():
    t = T.calculate_targets("female", 1996, 150, 40, "sedentary", "lose", today_year=2026)
    assert t.kcal == T.MIN_KCAL


def test_custom_adjustments():
    t = T.calculate_targets("male", 1996, 175, 70, "sedentary", "lose", today_year=2026,
                            adjustments={"lose": -100, "maintain": 0, "gain": 0})
    assert t.kcal == pytest.approx(1648.75 * 1.2 - 100)
