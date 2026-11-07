"""Daily summary: always a SUM over rows (no stored running totals), so edits/deletes stay consistent."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.db import Db
from backend.services.foodref import NUTRIENTS

MEAL_TYPES = ("breakfast", "lunch", "snack", "dinner")


def local_date_for(utc_dt: datetime, tz: str) -> date:
    """Midnight boundary in the user's timezone."""
    return utc_dt.astimezone(ZoneInfo(tz)).date()


def meal_type_for(utc_dt: datetime, tz: str) -> str:
    h = utc_dt.astimezone(ZoneInfo(tz)).hour
    return "breakfast" if h < 11 else "lunch" if h < 15 else "snack" if h < 18 else "dinner"


def summarize(meals: list[dict], items: list[dict], profile: dict | None) -> dict:
    profile = profile or {}
    totals = {k: 0.0 for k in NUTRIENTS}
    by_meal = {t: {"kcal": 0.0, "items": 0} for t in MEAL_TYPES}
    mtype = {m["id"]: m["meal_type"] for m in meals}
    count = 0
    for it in items:
        if it["meal_id"] not in mtype:
            continue
        count += 1
        for k in NUTRIENTS:
            totals[k] += float(it.get(k) or 0)
        b = by_meal[mtype[it["meal_id"]]]
        b["kcal"] += float(it.get("kcal") or 0)
        b["items"] += 1
    targets = {
        "kcal": profile.get("target_kcal"), "protein_g": profile.get("target_protein_g"),
        "carbs_g": profile.get("target_carbs_g"), "fat_g": profile.get("target_fat_g"),
        "sugar_g": profile.get("cap_sugar_g"), "sodium_mg": profile.get("cap_sodium_mg"),
    }
    remaining = {k: (float(v) - totals[k] if v is not None else None) for k, v in targets.items()}
    return {"totals": totals, "targets": targets, "remaining": remaining, "by_meal": by_meal, "item_count": count}


def daily_summary(db: Db, user_id: str, day: str, profile: dict | None) -> dict:
    meals = db.select("meals", user_id=f"eq.{user_id}", local_date=f"eq.{day}")
    items: list[dict] = []
    if meals:
        ids = ",".join(m["id"] for m in meals)
        items = db.select("meal_items", meal_id=f"in.({ids})")
    by_id: dict[str, list[dict]] = {}
    for it in items:
        by_id.setdefault(it["meal_id"], []).append(it)
    meals = sorted(meals, key=lambda m: m.get("eaten_at_utc") or "")
    full = [{**m, "items": by_id.get(m["id"], [])} for m in meals]
    return {"date": day, "meals": full, **summarize(meals, items, profile)}
