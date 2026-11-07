"""In-memory FoodRepo mimicking search_foods (pg_trgm-style similarity)."""
import re

from api.db import Db
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


_PARAMS = {"limit", "offset", "order", "select"}


def _match(row: dict, filters: dict) -> bool:
    for k, v in filters.items():
        if k in _PARAMS:
            continue
        if k == "and":  # "(col.op.val,col.op.val)"
            for cond in v.strip("()").split(","):
                col, op, val = cond.split(".", 2)
                if not _match(row, {col: f"{op}.{val}"}):
                    return False
            continue
        op, _, val = v.partition(".")
        if op == "gte" and not str(row.get(k)) >= val:
            return False
        if op == "lte" and not str(row.get(k)) <= val:
            return False
        if op == "eq" and str(row.get(k)) != val:
            return False
        if op == "in" and str(row.get(k)) not in val.strip("()").split(","):
            return False
    return True


class FakeDb:
    """In-memory PostgREST stand-in (eq./in. filters, insert, delete, rpc) for endpoint tests."""

    def __init__(self, foods: list[dict] | None = None):
        self.repo = FakeRepo(foods or [])
        self.t: dict[str, list[dict]] = {"profiles": [], "meals": [], "meal_items": [], "usage_counters": [],
                                         "food_reference": [dict(r) for r in self.repo.rows]}
        self._n = 0
        self.rpc_calls: list[str] = []

    def select(self, table, **filters):
        rows = [dict(r) for r in self.t[table] if _match(r, filters)]
        for col in reversed([c.split(".")[0] for c in filters.get("order", "").split(",") if c]):
            rows.sort(key=lambda r: str(r.get(col)))
        off, lim = int(filters.get("offset", 0)), filters.get("limit")
        return rows[off : off + int(lim)] if lim else rows[off:]

    select_all = Db.select_all  # reuse the real pagination loop on top of the fake select

    def insert(self, table, rows):
        out = []
        for r in rows:
            self._n += 1
            row = {"id": f"{table[:1]}{self._n}", **r}
            self.t[table].append(row)
            out.append(dict(row))
        return out

    def upsert(self, table, row, on_conflict):
        self.t[table] = [r for r in self.t[table] if r.get(on_conflict) != row.get(on_conflict)] + [row]
        return row

    def update(self, table, values, **filters):
        rows = [r for r in self.t[table] if _match(r, filters)]
        for r in rows:
            r.update(values)
        return [dict(r) for r in rows]

    def delete(self, table, **filters):
        gone = [r for r in self.t[table] if _match(r, filters)]
        self.t[table] = [r for r in self.t[table] if r not in gone]
        if table == "meals":  # cascade
            ids = {g["id"] for g in gone}
            self.t["meal_items"] = [i for i in self.t["meal_items"] if i["meal_id"] not in ids]

    def rpc(self, fn, args):
        self.rpc_calls.append(fn)
        if fn == "search_foods":
            return [
                {**vars(f), "id": f.id} for f in self.repo.search(args["p_q"], args["p_source"], args["p_min"], args["p_limit"])
            ]
        if fn == "try_consume_analyze":
            rows = [r for r in self.t["usage_counters"] if r["local_date"] == args["p_date"]]
            mine = next((r for r in rows if r["user_id"] == args["p_user"]), None)
            if sum(r["analyze_count"] for r in rows) >= args["p_global_cap"] or (mine and mine["analyze_count"] >= args["p_user_cap"]):
                return False
            if mine:
                mine["analyze_count"] += 1
            else:
                self.t["usage_counters"].append(
                    {"user_id": args["p_user"], "local_date": args["p_date"], "analyze_count": 1})
            return True
        raise KeyError(fn)
