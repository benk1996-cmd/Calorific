"""Turns an AnalysisResult into saved meal + items (resolve -> calculate -> save)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from backend.db import Db
from backend.schemas import AnalysisResult
from backend.services.calc import CalcConfig, compute_item
from backend.services.resolver import Resolver
from backend.services.tally import local_date_for, meal_type_for

MAX_RESOLVE_WORKERS = 4


def build_item_rows(result: AnalysisResult, resolver: Resolver, cfg: CalcConfig) -> list[dict]:
    items = result.items
    if len(items) > 1:  # database lookups are network-bound: resolve the items side by side
        with ThreadPoolExecutor(max_workers=min(len(items), MAX_RESOLVE_WORKERS)) as pool:
            resolutions = list(pool.map(lambda i: resolver.resolve(i.name, i.aliases), items))
    else:
        resolutions = [resolver.resolve(i.name, i.aliases) for i in items]
    rows = []
    for item, res in zip(items, resolutions):
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
              item_rows: list[dict], now: datetime | None = None, meal_type: str | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    tz = profile["timezone"]
    meal = db.insert("meals", [{
        "user_id": user_id, "eaten_at_utc": now.isoformat(), "local_date": local_date_for(now, tz).isoformat(),
        "meal_type": meal_type or meal_type_for(now, tz), "input_type": input_type, "note": note,
    }])[0]
    try:
        items = db.insert("meal_items", [{**r, "meal_id": meal["id"]} for r in item_rows])
    except Exception:
        db.delete("meals", id=f"eq.{meal['id']}", user_id=f"eq.{user_id}")  # no half-saved meals
        raise
    return {**meal, "items": items}
