"""Food lookup repository: Postgres-backed (via the search_foods SQL function)."""
from typing import Protocol

from api.db import Db
from api.services.foodref import FoodRef


class FoodRepo(Protocol):
    def search(self, q: str, source: str | None, min_sim: float, limit: int) -> list[FoodRef]: ...
    def save(self, rows: list[dict]) -> None: ...


class DbFoodRepo:
    def __init__(self, db: Db):
        self._db = db

    def search(self, q: str, source: str | None, min_sim: float, limit: int) -> list[FoodRef]:
        rows = self._db.rpc(
            "search_foods", {"p_q": q, "p_source": source, "p_min": min_sim, "p_limit": limit}
        )
        return [FoodRef.from_row(r) for r in rows]

    def save(self, rows: list[dict]) -> None:
        self._db.upsert_many("food_reference", rows, "source,source_id")

    def get(self, food_id: int) -> FoodRef | None:
        rows = self._db.select("food_reference", id=f"eq.{food_id}")
        return FoodRef.from_row(rows[0]) if rows else None
