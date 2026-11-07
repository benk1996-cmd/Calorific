"""Turns an AnalysisResult into saved meal + items (resolve -> calculate -> save)."""
from datetime import datetime, timezone

from api.db import Db
from api.schemas import AnalysisResult
from api.services.calc import CalcConfig, compute_item
from api.services.resolver import Resolver
from api.services.tally import local_date_for, meal_type_for


def build_item_rows(result: AnalysisResult, resolver: Resolver, cfg: CalcConfig) -> list[dict]:
    rows = []
    for item in result.items:
        res = resolver.resolve(item.name, item.aliases)
        n = compute_item(item, res.food, cfg)
        rows.append({
            "name": item.name,
            "food_ref_id": res.food.id if res.food else None,
            "source": n.source, "grams": n.grams, "servings": n.servings, **n.nutrients,
            "confidence": item.confidence,
            "model_raw_json": {**item.model_dump(), "matched": res.food.name if res.food else None, "method": res.method},
            "user_edited": False,
        })
    return rows


def save_meal(db: Db, user_id: str, profile: dict, input_type: str, note: str | None,
              item_rows: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    tz = profile["timezone"]
    meal = db.insert("meals", [{
        "user_id": user_id, "eaten_at_utc": now.isoformat(), "local_date": local_date_for(now, tz).isoformat(),
        "meal_type": meal_type_for(now, tz), "input_type": input_type, "note": note,
    }])[0]
    try:
        items = db.insert("meal_items", [{**r, "meal_id": meal["id"]} for r in item_rows])
    except Exception:
        db.delete("meals", id=f"eq.{meal['id']}", user_id=f"eq.{user_id}")  # no half-saved meals
        raise
    return {**meal, "items": items}
