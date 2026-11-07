"""POST /api/analyze/photo|text (auto-saves the meal), GET /api/usage, DELETE /api/meals/{id}."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from starlette.formparsers import MultiPartParser

from api.auth import User, get_current_user
from api.config import Settings, get_settings
from api.db import Db, get_db
from api.services import tally
from api.services.analyzer import Analyzer, AnalysisError, QuotaExceeded, ServiceBusy
from api.services.calc import config_from_env
from api.services.foodrepo import DbFoodRepo
from api.services.llm import LLMProvider, MockProvider, OpenRouterProvider
from api.services.pipeline import build_item_rows, save_meal
from api.services.quota import get_usage, make_consumer
from api.services.resolver import Resolver
from api.services.usda import UsdaClient

# Keep uploads in memory: Starlette spools parts above 1 MB to disk by default; photos must never be stored.
MultiPartParser.spool_max_size = 2 * 1024 * 1024

router = APIRouter(prefix="/api")
MAX_IMAGE_BYTES = 1_500_000
QUOTA_MSG = "Daily AI limit reached. Use search to add food manually."


def get_provider(settings: Settings = Depends(get_settings)) -> LLMProvider:
    if settings.llm_mock:
        return MockProvider()
    if not settings.openrouter_api_key:
        raise HTTPException(503, "AI provider is not configured")
    return OpenRouterProvider(settings.openrouter_api_key, settings.app_url)


def get_resolver(db: Db = Depends(get_db), settings: Settings = Depends(get_settings)) -> Resolver:
    repo = DbFoodRepo(db)
    usda = UsdaClient(settings.usda_api_key, repo) if settings.usda_api_key else None
    return Resolver(repo, usda, threshold=settings.resolver_threshold)


def sniff_image(data: bytes) -> str | None:
    """Detect the real image type from magic bytes (the client-supplied content type is not trusted)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _profile(db: Db, user: User) -> dict:
    rows = db.select("profiles", user_id=f"eq.{user.id}")
    if not rows:
        raise HTTPException(409, "Complete your profile first")
    return rows[0]


def _finish(db: Db, user: User, settings: Settings, profile: dict, result, input_type: str, note, resolver, now=None) -> dict:
    usage = get_usage(db, user.id, settings, now)
    if result.not_food:
        return {"not_food": True, "meal": None, "usage": usage,
                "summary": tally.daily_summary(db, user.id, tally.local_date_for(now or _utcnow(), profile["timezone"]).isoformat(), profile)}
    rows = build_item_rows(result, resolver, config_from_env())
    meal = save_meal(db, user.id, profile, input_type, note, rows, now)
    return {"not_food": False, "meal": meal, "usage": usage,
            "summary": tally.daily_summary(db, user.id, meal["local_date"], profile)}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _run(fn):
    try:
        return fn()
    except QuotaExceeded:
        raise HTTPException(429, QUOTA_MSG) from None
    except ServiceBusy:
        raise HTTPException(503, "The AI service is busy right now. Please try again in a minute.") from None
    except AnalysisError as e:
        raise HTTPException(502, str(e)) from None


@router.post("/analyze/photo")
async def analyze_photo(
    image: UploadFile = File(...), note: str | None = Form(default=None, max_length=200),
    user: User = Depends(get_current_user), db: Db = Depends(get_db), settings: Settings = Depends(get_settings),
    provider: LLMProvider = Depends(get_provider), resolver: Resolver = Depends(get_resolver),
) -> dict:
    profile = _profile(db, user)
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image is too large (max 1.5 MB)")
    mime = sniff_image(data)
    if mime is None:
        raise HTTPException(415, "Please upload a JPEG, PNG or WebP image")
    analyzer = Analyzer(provider, make_consumer(db, user.id, settings), timeout=settings.llm_timeout_s)
    result = _run(lambda: analyzer.analyze_photo(data, mime, note, settings.vision_models))
    del data  # bytes are never stored or logged
    return _finish(db, user, settings, profile, result, "photo", note, resolver)


class TextIn(BaseModel):
    text: str = Field(min_length=2, max_length=300)


@router.post("/analyze/text")
def analyze_text(
    body: TextIn, user: User = Depends(get_current_user), db: Db = Depends(get_db),
    settings: Settings = Depends(get_settings), provider: LLMProvider = Depends(get_provider),
    resolver: Resolver = Depends(get_resolver),
) -> dict:
    profile = _profile(db, user)
    analyzer = Analyzer(provider, make_consumer(db, user.id, settings), timeout=settings.llm_timeout_s)
    result = _run(lambda: analyzer.analyze_text(body.text, settings.text_models))
    return _finish(db, user, settings, profile, result, "text", body.text, resolver)


@router.get("/usage")
def usage(user: User = Depends(get_current_user), db: Db = Depends(get_db),
          settings: Settings = Depends(get_settings)) -> dict:
    return get_usage(db, user.id, settings)
