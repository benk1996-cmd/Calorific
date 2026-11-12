"""Food lookup repository: Postgres-backed (via the search_foods SQL function)."""
import time
from typing import Protocol

from backend.db import Db
from backend.services.foodref import FoodRef


class FoodRepo(Protocol):
    def search(self, q: str, source: str | None, min_sim: float, limit: int) -> list[FoodRef]: ...
    def save(self, rows: list[dict]) -> None: ...


_HAS_SOURCE_TTL_S = 300
_has_source_cache: dict[str, tuple[float, bool]] = {}  # per server process; avoids a query on every lookup


class DbFoodRepo:
    def __init__(self, db: Db):
        self._db = db

    def has_source(self, source: str) -> bool:
        """True if any food of this source is loaded (cached for a few minutes).
        Lets the resolver skip searching an empty table (e.g. SG FoodID before HPB data is ingested)."""
        now = time.monotonic()
        hit = _has_source_cache.get(source)
        if hit and now - hit[0] < _HAS_SOURCE_TTL_S:
            return hit[1]
        found = bool(self._db.select("food_reference", select="id", source=f"eq.{source}", limit="1"))
        _has_source_cache[source] = (now, found)
        return found

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
