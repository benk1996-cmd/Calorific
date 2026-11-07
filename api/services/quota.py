"""Free-tier quota guard. Counted in Postgres (try_consume_analyze), reset at midnight SGT."""
from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from api.config import Settings
from api.db import Db

SGT = ZoneInfo("Asia/Singapore")


def quota_date(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(SGT).date().isoformat()


def make_consumer(db: Db, user_id: str, settings: Settings, now: datetime | None = None) -> Callable[[], bool]:
    """Returns consume(): atomically counts one model call, False if a cap would be exceeded."""
    d = quota_date(now)

    def consume() -> bool:
        return bool(db.rpc("try_consume_analyze", {
            "p_user": user_id, "p_date": d,
            "p_user_cap": settings.limit_per_user, "p_global_cap": settings.limit_global,
        }))

    return consume


def get_usage(db: Db, user_id: str, settings: Settings, now: datetime | None = None) -> dict:
    d = quota_date(now)
    rows = db.select("usage_counters", local_date=f"eq.{d}")
    total = sum(int(r["analyze_count"]) for r in rows)
    mine = sum(int(r["analyze_count"]) for r in rows if r["user_id"] == user_id)
    remaining = max(0, min(settings.limit_per_user - mine, settings.limit_global - total))
    return {"date": d, "used": mine, "user_limit": settings.limit_per_user, "remaining": remaining}
