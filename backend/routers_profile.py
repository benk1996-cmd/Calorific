"""GET/PUT /api/profile. PUT recalculates targets unless a manual override is set."""
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth import User, get_current_user
from backend.db import Db, get_db
from backend.services import targets as T

router = APIRouter(prefix="/api")


class ProfileIn(BaseModel):
    display_name: str | None = None
    sex: Literal["male", "female"]
    birth_year: int = Field(ge=1900, le=2100)
    height_cm: float = Field(ge=80, le=250)
    weight_kg: float = Field(ge=20, le=400)
    activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"]
    goal: Literal["lose", "maintain", "gain"]
    timezone: str = "Asia/Singapore"
    target_override: bool = False
    target_kcal: float | None = Field(default=None, ge=500, le=10000)
    cap_sugar_g: float = T.DEFAULT_CAP_SUGAR_G
    cap_sodium_mg: float = T.DEFAULT_CAP_SODIUM_MG


def build_profile_row(user_id: str, p: ProfileIn, now_year: int | None = None) -> dict:
    """Validate and compute the stored row (targets calculated unless overridden)."""
    try:
        ZoneInfo(p.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, f"Unknown timezone: {p.timezone}")
    year = now_year or datetime.now(timezone.utc).year
    if p.birth_year >= year:
        raise HTTPException(422, "birth_year must be in the past")
    if p.target_override:
        if p.target_kcal is None:
            raise HTTPException(422, "target_kcal required when target_override is true")
        t = T.macros_for(p.target_kcal)
    else:
        t = T.calculate_targets(
            p.sex, p.birth_year, p.height_cm, p.weight_kg, p.activity_level, p.goal, today_year=year
        )
    return {
        **p.model_dump(exclude={"target_kcal"}),
        "user_id": user_id,
        "target_kcal": round(t.kcal),
        "target_protein_g": round(t.protein_g),
        "target_carbs_g": round(t.carbs_g),
        "target_fat_g": round(t.fat_g),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/profile")
def get_profile(user: User = Depends(get_current_user), db: Db = Depends(get_db)) -> dict:
    rows = db.select("profiles", user_id=f"eq.{user.id}")
    return {"email": user.email, "profile": rows[0] if rows else None}


@router.put("/profile")
def put_profile(
    body: ProfileIn, user: User = Depends(get_current_user), db: Db = Depends(get_db)
) -> dict:
    row = build_profile_row(user.id, body)
    return {"email": user.email, "profile": db.upsert("profiles", row, "user_id")}
