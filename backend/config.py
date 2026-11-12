"""Environment-driven settings. All secrets come from env vars, never code."""
import os
from dataclasses import dataclass, field


def _list(name: str, default: str = "") -> list[str]:
    return [s.strip() for s in os.getenv(name, default).split(",") if s.strip()]


# Single default: it is the model that answered photos reliably when the Gemma models were rate-limited upstream.
# Add more (comma-separated, best first) in VISION_MODELS / TEXT_MODELS if you want a fallback.
DEFAULT_MODELS = "nvidia/nemotron-3.5-super-vl:free"


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str = ""
    vision_models: list[str] = field(default_factory=list)
    text_models: list[str] = field(default_factory=list)
    usda_api_key: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    allowed_emails: list[str] = field(default_factory=list)
    limit_global: int = 45
    limit_per_user: int = 10
    resolver_threshold: float = 0.45
    resolver_llm_pick: bool = False
    llm_mock: bool = True
    llm_timeout_s: float = 25.0
    app_url: str = "http://localhost:5173"


def get_settings() -> Settings:
    vision = _list("VISION_MODELS", DEFAULT_MODELS)
    return Settings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        vision_models=vision,
        text_models=_list("TEXT_MODELS") or vision,
        usda_api_key=os.getenv("USDA_API_KEY", ""),
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        allowed_emails=[e.lower() for e in _list("ALLOWED_EMAILS")],
        limit_global=int(os.getenv("ANALYZE_DAILY_LIMIT_GLOBAL", "45")),
        limit_per_user=int(os.getenv("ANALYZE_DAILY_LIMIT_PER_USER", "10")),
        resolver_threshold=float(os.getenv("RESOLVER_THRESHOLD", "0.45")),
        resolver_llm_pick=os.getenv("RESOLVER_LLM_PICK", "false").lower() == "true",
        llm_mock=os.getenv("LLM_MOCK", "true").lower() == "true",
        llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "25")),
        app_url=os.getenv("APP_URL", "http://localhost:5173"),
    )
