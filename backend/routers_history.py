"""GET /api/history and /api/export.csv (date ranges in the user's local dates)."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from fastapi.responses import Response

from backend.auth import User, get_current_user
from backend.db import Db, get_db
from backend.services.history import build_history, export_csv, history_stats, load_range, reset_history

router = APIRouter(prefix="/api")
MAX_HISTORY_DAYS = 90
MAX_EXPORT_DAYS = 366


def _profile(db: Db, user: User) -> dict | None:
    rows = db.select("profiles", user_id=f"eq.{user.id}")
    return rows[0] if rows else None


def _range(frm: str | None, to: str | None, profile: dict | None, max_days: int) -> tuple[date, date]:
    try:
        tz = ZoneInfo((profile or {}).get("timezone") or "Asia/Singapore")
        end = date.fromisoformat(to) if to else datetime.now(timezone.utc).astimezone(tz).date()
        start = date.fromisoformat(frm) if frm else end - timedelta(days=6)
    except ValueError:
        raise HTTPException(422, "Dates must be YYYY-MM-DD") from None
    if start > end:
        raise HTTPException(422, "'from' must not be after 'to'")
    if (end - start).days + 1 > max_days:
        raise HTTPException(422, f"Range too long (max {max_days} days)")
    return start, end


@router.get("/history")
def history(
    frm: str | None = Query(default=None, alias="from"), to: str | None = None,
    user: User = Depends(get_current_user), db: Db = Depends(get_db),
) -> dict:
    profile = _profile(db, user)
    start, end = _range(frm, to, profile, MAX_HISTORY_DAYS)
    meals, items = load_range(db, user.id, start, end)
    return build_history(meals, items, start, end, profile)


@router.get("/export.csv")
def export(
    frm: str | None = Query(default=None, alias="from"), to: str | None = None,
    user: User = Depends(get_current_user), db: Db = Depends(get_db),
) -> Response:
    start, end = _range(frm, to, _profile(db, user), MAX_EXPORT_DAYS)
    meals, items = load_range(db, user.id, start, end)
    return Response(
        export_csv(meals, items), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="calorific_{start}_{end}.csv"'},
    )


RESET_WORD = "RESET"


class ResetIn(BaseModel):
    confirm: str


@router.get("/history/stats")
def stats(user: User = Depends(get_current_user), db: Db = Depends(get_db)) -> dict:
    return history_stats(db, user.id)


@router.post("/history/reset")
def reset(body: ResetIn, user: User = Depends(get_current_user), db: Db = Depends(get_db)) -> dict:
    """Permanently delete all of the caller's meals. Requires the exact confirmation word."""
    if body.confirm != RESET_WORD:
        raise HTTPException(422, f'Type "{RESET_WORD}" to confirm')
    return reset_history(db, user.id)
