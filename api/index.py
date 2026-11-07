"""FastAPI entrypoint (Vercel Python Function). Routers are added per milestone."""
from fastapi import FastAPI

from api.config import get_settings

app = FastAPI(title="Calorific API", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "llm_mock": s.llm_mock,
        "vision_models": s.vision_models,
        "supabase_configured": bool(s.supabase_url),
    }
