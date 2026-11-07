"""Pydantic models for LLM output (vision + text parse share this schema)."""
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _num(v: Any) -> Any:
    """Tolerate '350g', '12.5 g', '1,200' from weaker models; leave non-numeric for validation to reject."""
    if isinstance(v, str):
        m = _NUM.search(v.replace(",", ""))
        return float(m.group()) if m else None
    return v


class Portion(BaseModel):
    amount: float = 1.0
    unit: str = "serving"
    est_grams: float | None = None

    @field_validator("amount", "est_grams", mode="before")
    @classmethod
    def _n(cls, v):
        return _num(v)

    @field_validator("amount")
    @classmethod
    def _positive(cls, v: float) -> float:
        return v if v and v > 0 else 1.0

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v):
        return str(v) if v else "serving"


class EstNutrients(BaseModel):
    kcal: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    sugar_g: float = 0
    sodium_mg: float = 0
    fibre_g: float = 0

    @field_validator("*", mode="before")
    @classmethod
    def _n(cls, v):
        n = _num(v)
        return 0 if n is None else n


class FoodItem(BaseModel):
    name: str = Field(min_length=1)
    aliases: list[str] = []
    cuisine: str | None = None
    is_composite_dish: bool = False
    components: list[str] = []
    modifiers: list[str] = []  # e.g. "less rice", "no sugar", "extra egg"
    portion: Portion = Portion()
    est_nutrients: EstNutrients | None = None
    confidence: float = 0.5

    @field_validator("aliases", "components", "modifiers", mode="before")
    @classmethod
    def _names(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(x.get("name", x)) if isinstance(x, dict) else str(x) for x in v]

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        n = _num(v)
        return 0.5 if n is None else min(1.0, max(0.0, n))


class AnalysisResult(BaseModel):
    not_food: bool = False
    items: list[FoodItem] = []
