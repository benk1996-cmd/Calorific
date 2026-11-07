"""FastAPI application (served by api/index.py on Vercel)."""
import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.routers_analyze import router as analyze_router
from backend.routers_foods import router as foods_router
from backend.routers_history import router as history_router
from backend.routers_meals import router as meals_router
from backend.routers_profile import router as profile_router

log = logging.getLogger("calorific")
MAX_PHOTO_REQUEST_BYTES = 2_000_000  # photos are <=1.5 MB; Vercel's hard limit is 4.5 MB

app = FastAPI(title="Calorific API", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(profile_router)
app.include_router(foods_router)
app.include_router(analyze_router)
app.include_router(meals_router)
app.include_router(history_router)


@app.middleware("http")
async def limit_photo_upload(request: Request, call_next):
    """Reject oversized photo uploads from the header alone, before any of the body is read."""
    if request.method == "POST" and request.url.path == "/api/analyze/photo":
        length = request.headers.get("content-length", "")
        if not length.isdigit():
            return JSONResponse({"detail": "Content-Length is required"}, status_code=411)
        if int(length) > MAX_PHOTO_REQUEST_BYTES:
            return JSONResponse({"detail": "Image is too large (max 1.5 MB)"}, status_code=413)
    return await call_next(request)


@app.exception_handler(httpx.HTTPError)
async def upstream_error(request: Request, exc: httpx.HTTPError) -> JSONResponse:
    """Database/auth/AI upstream failed. Log only the type and status, never request or response bodies."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    log.error("Upstream %s (status=%s) on %s %s", type(exc).__name__, status, request.method, request.url.path)
    return JSONResponse({"detail": "A data service is unavailable. Please try again in a moment."}, status_code=502)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.error("Unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
    return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "llm_mock": s.llm_mock,
        "vision_models": s.vision_models,
        "supabase_configured": bool(s.supabase_url),
    }
