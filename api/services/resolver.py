"""Nutrition resolver. Order:
SG FoodID exact/alias -> SG FoodID trigram >= threshold -> local USDA trigram -> live USDA API -> estimated.
`food is None` with method "estimated" means the caller should use the model's own estimate.
The optional LLM pick-from-top-5 step (RESOLVER_LLM_PICK) is a hook only; it is off by default so
resolving never spends model calls."""
from dataclasses import dataclass
from typing import Callable, Sequence

from api.services.foodref import FoodRef
from api.services.foodrepo import FoodRepo
from api.services.usda import UsdaClient

TOP_K = 5


@dataclass(frozen=True)
class Resolution:
    food: FoodRef | None
    method: str  # sg_exact | sg_fuzzy | usda_local | usda_api | estimated


class Resolver:
    def __init__(
        self, repo: FoodRepo, usda: UsdaClient | None = None, *, threshold: float = 0.45,
        llm_pick: Callable[[str, Sequence[FoodRef]], FoodRef | None] | None = None,
    ):
        self.repo, self.usda, self.threshold, self.llm_pick = repo, usda, threshold, llm_pick

    def _best(self, queries: list[str], source: str, min_sim: float) -> tuple[list[FoodRef], FoodRef | None]:
        cands: list[FoodRef] = []
        for q in queries:
            cands += self.repo.search(q, source, min_sim, TOP_K)
        cands.sort(key=lambda f: (not f.is_exact, -f.score))
        return cands, (cands[0] if cands else None)

    def resolve(self, name: str, aliases: Sequence[str] = ()) -> Resolution:
        queries = list(dict.fromkeys(q.strip() for q in [name, *aliases] if q and q.strip()))
        if not queries:
            return Resolution(None, "estimated")

        cands, best = self._best(queries, "sgfoodid", self.threshold)
        if best:
            if best.is_exact:
                return Resolution(best, "sg_exact")
            if self.llm_pick and len(cands) > 1:
                picked = self.llm_pick(name, cands)
                if picked:
                    return Resolution(picked, "sg_fuzzy")
            return Resolution(best, "sg_fuzzy")

        _, best = self._best(queries, "usda", self.threshold)
        if best:
            return Resolution(best, "usda_local")

        if self.usda:
            for q in queries:
                food = self.usda.lookup(q)
                if food:
                    return Resolution(food, "usda_api")
        return Resolution(None, "estimated")
