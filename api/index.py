"""Vercel Python Function entrypoint. Application code lives in backend/ (files inside api/ would each be
deployed as a separate function)."""
from backend.main import app  # noqa: F401  (Vercel serves the ASGI `app`)
