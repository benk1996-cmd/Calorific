"""Shared helpers for food_reference rows: number parsing, nutrient dicts, serving<->100g derivation."""
from dataclasses import dataclass
from typing import Any, Iterable

NUTRIENTS = ("kcal", "protein_g", "carbs_g", "fat_g", "sugar_g", "sodium_mg", "fibre_g")

# USDA FoodData Central nutrient ids -> our keys. Energy has several ids; earlier = preferred.
USDA_ENERGY_IDS = (1008, 2047, 2048)
USDA_NUTRIENT_IDS = {
    1003: "protein_g", 1004: "fat_g", 1005: "carbs_g", 1079: "fibre_g", 2000: "sugar_g", 1093: "sodium_mg",
}

_TRACE = {"tr", "trace"}
_MISSING = {"", "-", "--", "na", "n/a", "nd", "nan", "none", "null"}


def parse_number(v: Any) -> float | None:
    """Parse '1,234', '<1' (-> 1), 'tr' (-> 0). Returns None when missing/unparseable."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if v != v else float(v)
    s = str(v).strip().lower().replace(",", "")
    if s in _MISSING:
        return None
    if s in _TRACE:
        return 0.0
    s = s.lstrip("<>~≈ ")
    try:
        return float(s)
    except ValueError:
        return None


def nutrient_dict(raw: dict[str, Any], scale: dict[str, float] | None = None) -> dict[str, float] | None:
    """Build a full 7-nutrient dict (missing -> 0). Returns None if kcal is unknown."""
    scale = scale or {}
    vals = {k: parse_number(raw.get(k)) for k in NUTRIENTS}
    if vals["kcal"] is None:
        return None
    return {k: (v if v is not None else 0.0) * scale.get(k, 1.0) for k, v in vals.items()}


def scaled(d: dict[str, float], factor: float) -> dict[str, float]:
    return {k: v * factor for k, v in d.items()}


def derive_missing(
    per_serving: dict | None, per_100g: dict | None, serving_g: float | None
) -> tuple[dict | None, dict | None]:
    """Fill per_100g from per_serving (and vice versa) when serving_g is known."""
    if serving_g and serving_g > 0:
        if per_100g is None and per_serving is not None:
            per_100g = scaled(per_serving, 100.0 / serving_g)
        elif per_serving is None and per_100g is not None:
            per_serving = scaled(per_100g, serving_g / 100.0)
    return per_serving, per_100g


def build_food_row(
    source: str, source_id: str, name: str, *, aliases: Iterable[str] = (), food_group: str | None = None,
    serving_desc: str | None = None, serving_g: float | None = None,
    per_serving: dict | None = None, per_100g: dict | None = None,
) -> dict | None:
    """Normalised food_reference row, or None if unusable (no name / no kcal anywhere)."""
    name = (name or "").strip()
    if not name or (per_serving is None and per_100g is None):
        return None
    per_serving, per_100g = derive_missing(per_serving, per_100g, serving_g)
    seen, alias_list = {name.lower()}, []
    for a in aliases:
        a = (a or "").strip()
        if a and a.lower() not in seen:
            seen.add(a.lower())
            alias_list.append(a)
    return {
        "source": source, "source_id": source_id, "name": name, "aliases": alias_list,
        "food_group": food_group, "serving_desc": serving_desc, "serving_g": serving_g,
        "per_serving": per_serving, "per_100g": per_100g,
    }


def usda_nutrients(pairs: Iterable[tuple[int, Any]]) -> dict[str, float] | None:
    """Map (nutrient_id, amount) pairs from USDA data to our per-100g nutrient dict."""
    raw: dict[str, Any] = {}
    energy: dict[int, Any] = {}
    for nid, amount in pairs:
        if nid in USDA_ENERGY_IDS:
            energy[nid] = amount
        elif nid in USDA_NUTRIENT_IDS:
            raw[USDA_NUTRIENT_IDS[nid]] = amount
    for nid in USDA_ENERGY_IDS:
        if parse_number(energy.get(nid)) is not None:
            raw["kcal"] = energy[nid]
            break
    return nutrient_dict(raw)


@dataclass(frozen=True)
class FoodRef:
    id: int | None
    source: str
    source_id: str | None
    name: str
    serving_desc: str | None = None
    serving_g: float | None = None
    per_serving: dict | None = None
    per_100g: dict | None = None
    score: float = 0.0
    is_exact: bool = False

    @classmethod
    def from_row(cls, r: dict) -> "FoodRef":
        return cls(
            id=r.get("id"), source=r["source"], source_id=r.get("source_id"), name=r["name"],
            serving_desc=r.get("serving_desc"),
            serving_g=float(r["serving_g"]) if r.get("serving_g") is not None else None,
            per_serving=r.get("per_serving"), per_100g=r.get("per_100g"),
            score=float(r.get("score") or 0.0), is_exact=bool(r.get("is_exact")),
        )
