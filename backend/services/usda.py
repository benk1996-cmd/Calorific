"""Live USDA FoodData Central lookup (last-resort fallback). Results are cached into food_reference."""
import time
from typing import Callable

import httpx

from backend.services.foodref import FoodRef, build_food_row, usda_nutrients
from backend.services.foodrepo import FoodRepo

SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
# Branded foods are excluded on purpose: prefer Foundation / SR Legacy / Survey (FNDDS).
DATA_TYPES = "Foundation,SR Legacy,Survey (FNDDS)"


class UsdaClient:
    def __init__(
        self, api_key: str, repo: FoodRepo | None = None, *, http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep, max_retries: int = 3,
    ):
        self.api_key, self.repo, self.sleep, self.max_retries = api_key, repo, sleep, max_retries
        self.http = http or httpx.Client(timeout=15)

    def _get(self, query: str) -> dict | None:
        params = {"query": query, "dataType": DATA_TYPES, "pageSize": 5, "api_key": self.api_key}
        for attempt in range(self.max_retries + 1):
            try:
                r = self.http.get(SEARCH_URL, params=params)
            except httpx.HTTPError:
                return None
            if r.status_code == 429 and attempt < self.max_retries:
                self.sleep(2**attempt)  # exponential backoff: 1s, 2s, 4s
                continue
            return r.json() if r.status_code == 200 else None
        return None

    def lookup(self, query: str) -> FoodRef | None:
        """Best USDA match for `query` (per-100g values), cached to food_reference. None if no key/result."""
        if not self.api_key:
            return None
        data = self._get(query)
        for food in (data or {}).get("foods", []):
            per_100g = usda_nutrients((n.get("nutrientId"), n.get("value")) for n in food.get("foodNutrients", []))
            row = build_food_row("usda", str(food["fdcId"]), food.get("description", ""), per_100g=per_100g,
                                 food_group=food.get("foodCategory"))
            if row is None:
                continue
            if self.repo:
                self.repo.save([row])
            return FoodRef.from_row({**row, "id": None})
        return None
