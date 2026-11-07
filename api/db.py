"""Minimal PostgREST client using the service-role key. Callers MUST scope by user_id."""
import httpx

from api.config import Settings, get_settings


class Db:
    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self._client = httpx.Client(
            base_url=f"{s.supabase_url}/rest/v1",
            headers={
                "apikey": s.supabase_service_role_key,
                "Authorization": f"Bearer {s.supabase_service_role_key}",
            },
            timeout=20,
        )

    def select(self, table: str, **filters: str) -> list[dict]:
        r = self._client.get(f"/{table}", params={"select": "*", **filters})
        r.raise_for_status()
        return r.json()

    def upsert(self, table: str, row: dict, on_conflict: str) -> dict:
        r = self._client.post(
            f"/{table}",
            params={"on_conflict": on_conflict},
            json=row,
            headers={"Prefer": "resolution=merge-duplicates,return=representation"},
        )
        r.raise_for_status()
        return r.json()[0]


def get_db() -> Db:
    return Db()
