"""Supabase session verification. The bearer token is validated by Supabase Auth itself,
which works regardless of the project's JWT signing algorithm."""
from dataclasses import dataclass

import httpx
from fastapi import Depends, Header, HTTPException

from backend.config import Settings, get_settings


@dataclass(frozen=True)
class User:
    id: str
    email: str


def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization[7:]
    try:
        r = httpx.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": settings.supabase_anon_key},
            timeout=10,
        )
    except httpx.HTTPError:
        raise HTTPException(503, "Auth service unavailable")
    if r.status_code != 200:
        raise HTTPException(401, "Invalid or expired session")
    data = r.json()
    email = (data.get("email") or "").lower()
    if settings.allowed_emails and email not in settings.allowed_emails:
        raise HTTPException(403, "This email is not invited")
    return User(id=data["id"], email=email)
