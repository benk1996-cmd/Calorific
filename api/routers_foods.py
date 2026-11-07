"""GET /api/foods/search?q= — food search used when editing meals and for manual add (no model call)."""
from fastapi import APIRouter, Depends, Query

from api.auth import User, get_current_user
from api.db import Db, get_db
from api.services.foodrepo import DbFoodRepo

router = APIRouter(prefix="/api")
SEARCH_MIN_SIM = 0.15


@router.get("/foods/search")
def search_foods(
    q: str = Query(min_length=2, max_length=100), limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user), db: Db = Depends(get_db),
) -> dict:
    foods = DbFoodRepo(db).search(q, None, SEARCH_MIN_SIM, limit)
    return {"results": [
        {"id": f.id, "source": f.source, "name": f.name, "serving_desc": f.serving_desc,
         "serving_g": f.serving_g, "per_serving": f.per_serving, "per_100g": f.per_100g}
        for f in foods
    ]}
