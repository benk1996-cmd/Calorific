"""In-memory FoodRepo mimicking search_foods (pg_trgm-style similarity)."""
import re

from api.services.foodref import FoodRef


def trigrams(s: str) -> set[str]:
    out: set[str] = set()
    for w in re.findall(r"[a-z0-9]+", s.lower()):
        p = f"  {w} "
        out |= {p[i : i + 3] for i in range(len(p) - 2)}
    return out


def similarity(a: str, b: str) -> float:
    ta, tb = trigrams(a), trigrams(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


class FakeRepo:
    def __init__(self, rows: list[dict]):
        self.rows = [dict(r, id=i + 1) for i, r in enumerate(rows)]
        self.saved: list[dict] = []
        self.searches = 0

    def search(self, q, source, min_sim, limit):
        self.searches += 1
        out = []
        for r in self.rows:
            if source and r["source"] != source:
                continue
            exact = r["name"].lower() == q.lower() or q.lower() in [a.lower() for a in r.get("aliases", [])]
            score = max(similarity(r["name"], q), similarity(" ".join(r.get("aliases", [])), q))
            if exact or score >= min_sim:
                out.append(FoodRef.from_row({**r, "score": score, "is_exact": exact}))
        out.sort(key=lambda f: (not f.is_exact, -f.score, f.source))
        return out[:limit]

    def save(self, rows):
        self.saved += rows
