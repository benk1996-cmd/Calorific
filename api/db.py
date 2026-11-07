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


    def insert(self, table: str, rows: list[dict]) -> list[dict]:
        r = self._client.post(f"/{table}", json=rows, headers={"Prefer": "return=representation"})
        r.raise_for_status()
        return r.json()

    def delete(self, table: str, **filters: str) -> None:
        """Delete rows matching PostgREST filters (e.g. id='eq.1'). Always include a user scope."""
        if not filters:
            raise ValueError("refusing unfiltered delete")
        r = self._client.delete(f"/{table}", params=filters)
        r.raise_for_status()

    def upsert_many(self, table: str, rows: list[dict], on_conflict: str, chunk: int = 500) -> int:
        """Bulk upsert in chunks; returns number of rows sent."""
        for i in range(0, len(rows), chunk):
            r = self._client.post(
                f"/{table}", params={"on_conflict": on_conflict}, json=rows[i : i + chunk],
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )
            r.raise_for_status()
        return len(rows)

    def rpc(self, fn: str, args: dict):
        r = self._client.post(f"/rpc/{fn}", json=args)
        r.raise_for_status()
        return r.json()

    def count(self, table: str, **filters: str) -> int:
        r = self._client.head(
            f"/{table}", params={"select": "id", **filters}, headers={"Prefer": "count=exact"}
        )
        r.raise_for_status()
        return int(r.headers["content-range"].split("/")[-1])


def get_db() -> Db:
    return Db()
