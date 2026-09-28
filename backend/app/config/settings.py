import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(BACKEND_ENV_FILE, override=False)


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    values = tuple(value.strip() for value in raw_value.split(",") if value.strip())
    return values or default


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables.

    This avoids hardcoded local configuration while keeping the prototype simple.
    """

    app_name: str = os.getenv("PURPOS_APP_NAME", "PurpOS API")
    environment: str = os.getenv("PURPOS_ENV", "development")
    frontend_origins: tuple[str, ...] = _csv_env(
        "PURPOS_FRONTEND_ORIGINS",
        (
            os.getenv("PURPOS_FRONTEND_ORIGIN", "http://localhost:3000"),
            "http://127.0.0.1:3000",
        ),
    )
    ai_provider: str = os.getenv("PURPOS_AI_PROVIDER", "gemini")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    ai_timeout_seconds: float = float(os.getenv("PURPOS_AI_TIMEOUT_SECONDS", "30"))
    ai_fallback_enabled: bool = _bool_env("PURPOS_AI_FALLBACK_ENABLED", True)
    ai_retry_max_retries: int = _int_env("PURPOS_AI_RETRY_MAX_RETRIES", 1)
    ai_retry_backoff_seconds: float = _float_env(
        "PURPOS_AI_RETRY_BACKOFF_SECONDS", 0.25
    )
    ai_free_only: bool = _bool_env("PURPOS_AI_FREE_ONLY", True)
    openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")
    openrouter_model: str | None = os.getenv("OPENROUTER_MODEL")
    openrouter_fallback_models: tuple[str, ...] = _csv_env(
        "OPENROUTER_FALLBACK_MODELS", ()
    )
    openrouter_free_models: tuple[str, ...] = _csv_env(
        "OPENROUTER_FREE_MODELS", ()
    )
    openrouter_site_url: str | None = os.getenv("OPENROUTER_SITE_URL")
    openrouter_app_name: str = os.getenv("OPENROUTER_APP_NAME", "PurpOS")
    assessment_repository: str = os.getenv(
        "PURPOS_ASSESSMENT_REPOSITORY", "memory"
    )
    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_service_role_key: str | None = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY"
    )
    external_research_enabled: bool = _bool_env(
        "PURPOS_EXTERNAL_RESEARCH_ENABLED", True
    )
    research_max_pages: int = _int_env("PURPOS_RESEARCH_MAX_PAGES", 6)
    research_timeout_seconds: float = _float_env(
        "PURPOS_RESEARCH_TIMEOUT_SECONDS", 8
    )
    research_max_content_bytes: int = _int_env(
        "PURPOS_RESEARCH_MAX_CONTENT_BYTES", 500_000
    )
    research_max_text_chars: int = _int_env(
        "PURPOS_RESEARCH_MAX_TEXT_CHARS", 12_000
    )
    research_redirect_limit: int = _int_env("PURPOS_RESEARCH_REDIRECT_LIMIT", 3)

    @property
    def cors_origin_regex(self) -> str | None:
        if self.environment != "development":
            return None

        private_network_hosts = (
            r"localhost",
            r"127\.0\.0\.1",
            r"10(?:\.\d{1,3}){3}",
            r"192\.168(?:\.\d{1,3}){2}",
            r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}",
        )
        return rf"^http://(?:{'|'.join(private_network_hosts)}):30\d{{2}}$"


settings = Settings()
