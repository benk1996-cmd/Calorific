"""History range queries, per-day totals/averages and CSV export. Always SUM over rows."""
import csv
import io
from datetime import date, timedelta

from backend.db import Db
from backend.services.foodref import NUTRIENTS

CHUNK = 50  # meal ids per items query (keeps URLs short)


def date_range(frm: date, to: date) -> list[str]:
    return [(frm + timedelta(days=i)).isoformat() for i in range((to - frm).days + 1)]


def _items_for(db: Db, meals: list[dict], columns: str = "*") -> list[dict]:
    items: list[dict] = []
    for i in range(0, len(meals), CHUNK):
        ids = ",".join(m["id"] for m in meals[i : i + CHUNK])
        items += db.select_all("meal_items", order="id.asc", select=columns, meal_id=f"in.({ids})")
    return items


def load_range(db: Db, user_id: str, frm: date, to: date) -> tuple[list[dict], list[dict]]:
    """All of the user's meals and items between two local dates (inclusive)."""
    meals = db.select_all(
        "meals", order="local_date.asc,eaten_at_utc.asc,id.asc", user_id=f"eq.{user_id}",
        **{"and": f"(local_date.gte.{frm.isoformat()},local_date.lte.{to.isoformat()})"},
    )
    return meals, _items_for(db, meals)


def history_stats(db: Db, user_id: str) -> dict:
    """How much history the user has: used for the reset confirmation and the backup range."""
    meals = db.select_all("meals", order="local_date.asc,id.asc", select="id,local_date", user_id=f"eq.{user_id}")
    items = _items_for(db, meals, "id")
    return {
        "meals": len(meals), "items": len(items),
        "first_date": meals[0]["local_date"] if meals else None,
        "last_date": meals[-1]["local_date"] if meals else None,
    }


def reset_history(db: Db, user_id: str) -> dict:
    """Delete every meal (items cascade) belonging to the user. Profile, targets and AI usage counters are kept:
    resetting the usage counters would let anyone bypass the daily AI cap."""
    stats = history_stats(db, user_id)
    if stats["meals"]:
        db.delete("meals", user_id=f"eq.{user_id}")
    return {"deleted_meals": stats["meals"], "deleted_items": stats["items"]}


def build_history(meals: list[dict], items: list[dict], frm: date, to: date, profile: dict | None) -> dict:
    day_of = {m["id"]: m["local_date"] for m in meals}
    days = {d: {"date": d, **{k: 0.0 for k in NUTRIENTS}, "items": 0} for d in date_range(frm, to)}
    for it in items:
        d = days.get(day_of.get(it["meal_id"], ""))
        if d is None:
            continue
        d["items"] += 1
        for k in NUTRIENTS:
            d[k] += float(it.get(k) or 0)
    rows = [{**d, "logged": d["items"] > 0} for d in days.values()]
    logged = [r for r in rows if r["logged"]]
    avg = {k: (sum(r[k] for r in logged) / len(logged) if logged else 0.0) for k in NUTRIENTS}
    p = profile or {}
    targets = {"kcal": p.get("target_kcal"), "protein_g": p.get("target_protein_g"), "carbs_g": p.get("target_carbs_g"),
               "fat_g": p.get("target_fat_g"), "sugar_g": p.get("cap_sugar_g"), "sodium_mg": p.get("cap_sodium_mg")}
    return {"from": frm.isoformat(), "to": to.isoformat(), "days": rows, "averages": avg,
            "days_logged": len(logged), "targets": targets}


CSV_COLUMNS = ["date", "meal_type", "input", "food", "source", "grams", "servings", *NUTRIENTS, "confidence", "edited"]


def _safe(v: object) -> object:
    """Neutralise spreadsheet formula injection in text cells."""
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def _num(v: object) -> object:
    return "" if v is None else round(float(v), 2)


def export_csv(meals: list[dict], items: list[dict]) -> str:
    by_meal = {m["id"]: m for m in meals}
    order = {m["id"]: i for i, m in enumerate(meals)}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(CSV_COLUMNS)
    for it in sorted((i for i in items if i["meal_id"] in by_meal), key=lambda i: order[i["meal_id"]]):
        m = by_meal[it["meal_id"]]
        w.writerow([
            m["local_date"], m["meal_type"], m["input_type"], _safe(it["name"]), it["source"],
            _num(it.get("grams")), _num(it.get("servings")), *[_num(it.get(k)) for k in NUTRIENTS],
            _num(it.get("confidence")), "yes" if it.get("user_edited") else "no",
        ])
    return out.getvalue()
