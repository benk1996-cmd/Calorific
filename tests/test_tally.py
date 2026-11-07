from datetime import datetime, timezone

import pytest

from api.config import Settings
from api.services import quota, tally
from tests.fakes import FakeDb

U = lambda *a: datetime(*a, tzinfo=timezone.utc)  # noqa: E731


def test_midnight_sgt_boundary():
    # 23:59 SGT (UTC+8) on 7 Nov = 15:59 UTC; 00:01 SGT on 8 Nov = 16:01 UTC
    assert str(tally.local_date_for(U(2026, 11, 7, 15, 59), "Asia/Singapore")) == "2026-11-07"
    assert str(tally.local_date_for(U(2026, 11, 7, 16, 1), "Asia/Singapore")) == "2026-11-08"
    assert str(tally.local_date_for(U(2026, 11, 7, 16, 1), "America/New_York")) == "2026-11-07"


@pytest.mark.parametrize("h,exp", [(6, "breakfast"), (10, "breakfast"), (11, "lunch"), (14, "lunch"),
                                   (15, "snack"), (17, "snack"), (18, "dinner"), (23, "dinner")])
def test_meal_type_by_local_hour(h, exp):
    assert tally.meal_type_for(U(2026, 11, 7, (h - 8) % 24), "Asia/Singapore") == exp


PROFILE = {"target_kcal": 2000, "target_protein_g": 150, "target_carbs_g": 200, "target_fat_g": 67,
           "cap_sugar_g": 50, "cap_sodium_mg": 2000}


def test_summarize_edits_and_deletes_stay_consistent():
    meals = [{"id": "m1", "meal_type": "lunch"}, {"id": "m2", "meal_type": "dinner"}]
    items = [{"meal_id": "m1", "kcal": 600, "sugar_g": 5, "sodium_mg": 1200},
             {"meal_id": "m2", "kcal": 400, "sugar_g": 10}, {"meal_id": "gone", "kcal": 999}]
    s = tally.summarize(meals, items, PROFILE)
    assert s["totals"]["kcal"] == 1000 and s["remaining"]["kcal"] == 1000 and s["item_count"] == 2
    assert s["remaining"]["sodium_mg"] == 800 and s["by_meal"]["lunch"] == {"kcal": 600.0, "items": 1}
    items[0]["kcal"] = 100  # edit
    assert tally.summarize(meals, items, PROFILE)["totals"]["kcal"] == 500
    assert tally.summarize(meals[1:], items, PROFILE)["totals"]["kcal"] == 400  # delete meal m1
    empty = tally.summarize([], [], None)
    assert empty["totals"]["kcal"] == 0 and empty["remaining"]["kcal"] is None


def test_daily_summary_scoped_by_user_and_date():
    db = FakeDb()
    db.insert("meals", [{"user_id": "A", "local_date": "2026-11-07", "meal_type": "lunch"},
                        {"user_id": "B", "local_date": "2026-11-07", "meal_type": "lunch"},
                        {"user_id": "A", "local_date": "2026-11-08", "meal_type": "lunch"}])
    for m in db.t["meals"]:
        db.insert("meal_items", [{"meal_id": m["id"], "kcal": 100}])
    assert tally.daily_summary(db, "A", "2026-11-07", PROFILE)["totals"]["kcal"] == 100
    assert tally.daily_summary(db, "C", "2026-11-07", PROFILE)["item_count"] == 0


def test_quota_resets_at_midnight_sgt_and_caps():
    s = Settings(limit_per_user=2, limit_global=3)
    db = FakeDb()
    before, after = U(2026, 11, 7, 15, 59), U(2026, 11, 7, 16, 1)
    assert quota.quota_date(before) == "2026-11-07" and quota.quota_date(after) == "2026-11-08"
    a, b = quota.make_consumer(db, "A", s, before), quota.make_consumer(db, "B", s, before)
    assert a() and a() and not a()                      # per-user cap
    assert b() and not b()                              # global cap (3) reached
    assert quota.get_usage(db, "A", s, before) == {"date": "2026-11-07", "used": 2, "user_limit": 2, "remaining": 0}
    assert quota.get_usage(db, "B", s, before)["remaining"] == 0
    assert quota.make_consumer(db, "A", s, after)()     # new SGT day, fresh quota
    assert quota.get_usage(db, "A", s, after)["remaining"] == 1
