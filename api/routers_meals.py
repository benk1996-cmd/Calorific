"""Day summary, meal/item edit & delete, and manual add (no model call). Everything is scoped to the user."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import User, get_current_user
from api.db import Db, get_db
from api.services.calc import recompute_item
from api.services.foodref import FoodRef, NUTRIENTS
from api.services.foodrepo import DbFoodRepo
from api.services.pipeline import save_meal
from api.services.tally import daily_summary

router = APIRouter(prefix="/api")
MealType = Literal["breakfast", "lunch", "snack", "dinner"]
CANT_COMPUTE = "Can't work out nutrients for that portion. Pick a food or set grams."


def _profile(db: Db, user: User) -> dict | None:
    rows = db.select("profiles", user_id=f"eq.{user.id}")
    return rows[0] if rows else None


def _own_meal(db: Db, user: User, meal_id: str) -> dict:
    rows = db.select("meals", id=f"eq.{meal_id}", user_id=f"eq.{user.id}")
    if not rows:
        raise HTTPException(404, "Meal not found")
    return rows[0]


def _own_item(db: Db, user: User, item_id: str) -> tuple[dict, dict]:
    rows = db.select("meal_items", id=f"eq.{item_id}")
    if not rows:
        raise HTTPException(404, "Item not found")
    return rows[0], _own_meal(db, user, rows[0]["meal_id"])  # 404 if the meal is not the user's


def _food(db: Db, food_id: int) -> FoodRef:
    food = DbFoodRepo(db).get(food_id)
    if food is None:
        raise HTTPException(404, "Food not found")
    return food


def _summary(db: Db, user: User, day: str) -> dict:
    return daily_summary(db, user.id, day, _profile(db, user))


def _values(computed: dict, food: FoodRef | None) -> dict:
    v = {k: computed[k] for k in (*NUTRIENTS, "grams", "servings")}
    if food:
        v.update(food_ref_id=food.id, source=food.source)
    return v


class Portion(BaseModel):
    grams: float | None = Field(default=None, gt=0, le=10000)
    servings: float | None = Field(default=None, gt=0, le=100)


class ItemPatch(Portion):
    food_ref_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)


class ItemAdd(Portion):
    food_ref_id: int


class ManualIn(ItemAdd):
    meal_type: MealType | None = None


class MealPatch(BaseModel):
    meal_type: MealType | None = None
    note: str | None = Field(default=None, max_length=200)


@router.get("/days/{day}/summary")
def day_summary(day: str, user: User = Depends(get_current_user), db: Db = Depends(get_db)) -> dict:
    try:
        day = date.fromisoformat(day).isoformat()
    except ValueError:
        raise HTTPException(422, "Date must be YYYY-MM-DD") from None
    return _summary(db, user, day)


@router.patch("/meals/{meal_id}")
def patch_meal(meal_id: str, body: MealPatch, user: User = Depends(get_current_user), db: Db = Depends(get_db)) -> dict:
    meal = _own_meal(db, user, meal_id)
    values = body.model_dump(exclude_unset=True)
    if values:
        db.update("meals", values, id=f"eq.{meal_id}", user_id=f"eq.{user.id}")
    return {"summary": _summary(db, user, meal["local_date"])}


@router.delete("/meals/{meal_id}")
def delete_meal(meal_id: str, user: User = Depends(get_current_user), db: Db = Depends(get_db)) -> dict:
    meal = _own_meal(db, user, meal_id)
    db.delete("meals", id=f"eq.{meal_id}", user_id=f"eq.{user.id}")  # items cascade
    return {"summary": _summary(db, user, meal["local_date"])}


@router.patch("/meal-items/{item_id}")
def patch_item(item_id: str, body: ItemPatch, user: User = Depends(get_current_user), db: Db = Depends(get_db)) -> dict:
    item, meal = _own_item(db, user, item_id)
    food = _food(db, body.food_ref_id) if body.food_ref_id else (
        DbFoodRepo(db).get(item["food_ref_id"]) if item.get("food_ref_id") else None)
    computed = recompute_item(item, food, body.grams, body.servings)
    if computed is None:
        raise HTTPException(422, CANT_COMPUTE)
    values = _values(computed, food if body.food_ref_id else None)
    values["user_edited"] = True
    if body.name or body.food_ref_id:
        values["name"] = body.name or food.name
    db.update("meal_items", values, id=f"eq.{item_id}")
    return {"summary": _summary(db, user, meal["local_date"])}


@router.delete("/meal-items/{item_id}")
def delete_item(item_id: str, user: User = Depends(get_current_user), db: Db = Depends(get_db)) -> dict:
    _, meal = _own_item(db, user, item_id)
    db.delete("meal_items", id=f"eq.{item_id}")
    if not db.select("meal_items", meal_id=f"eq.{meal['id']}"):
        db.delete("meals", id=f"eq.{meal['id']}", user_id=f"eq.{user.id}")  # no empty meals
    return {"summary": _summary(db, user, meal["local_date"])}


def _new_item_row(food: FoodRef, body: Portion) -> dict:
    computed = recompute_item({}, food, body.grams, body.servings)
    if computed is None:
        raise HTTPException(422, CANT_COMPUTE)
    return {"name": food.name, "confidence": None, "model_raw_json": {"manual": True}, "user_edited": True,
            **_values(computed, food)}


@router.post("/meals/{meal_id}/items")
def add_item(meal_id: str, body: ItemAdd, user: User = Depends(get_current_user), db: Db = Depends(get_db)) -> dict:
    meal = _own_meal(db, user, meal_id)
    row = _new_item_row(_food(db, body.food_ref_id), body)
    db.insert("meal_items", [{**row, "meal_id": meal_id}])
    return {"summary": _summary(db, user, meal["local_date"])}


@router.post("/meals/manual")
def manual_meal(body: ManualIn, user: User = Depends(get_current_user), db: Db = Depends(get_db)) -> dict:
    profile = _profile(db, user)
    if profile is None:
        raise HTTPException(409, "Complete your profile first")
    row = _new_item_row(_food(db, body.food_ref_id), body)
    meal = save_meal(db, user.id, profile, "text", "manual entry", [row], meal_type=body.meal_type)
    return {"meal": meal, "summary": _summary(db, user, meal["local_date"])}
