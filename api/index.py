"""FastAPI entrypoint (Vercel Python Function). Routers are added per milestone."""
from fastapi import FastAPI

from api.config import get_settings
from api.routers_analyze import router as analyze_router
from api.routers_foods import router as foods_router
from api.routers_profile import router as profile_router

app = FastAPI(title="Calorific API", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(profile_router)
app.include_router(foods_router)
app.include_router(analyze_router)


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "llm_mock": s.llm_mock,
        "vision_models": s.vision_models,
        "supabase_configured": bool(s.supabase_url),
    }
