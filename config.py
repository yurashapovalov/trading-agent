"""Application configuration with Pydantic validation.

All settings are loaded from .env file or environment variables.
Validation happens at import time - app fails fast with clear errors.

Usage:
    import config
    print(config.GEMINI_MODEL)  # "gemini-3-flash-preview"
    print(config.DATABASE_PATH)  # "data/trading.duckdb"
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars
    )

    # Google Gemini (required for core functionality)
    google_api_key: str = Field(description="Google API key for Gemini")
    gemini_model: str = Field(default="gemini-3-flash-preview")
    gemini_lite_model: str = Field(default="gemini-flash-lite-latest")

    # Anthropic Claude (optional fallback)
    anthropic_api_key: str | None = Field(default=None)
    claude_model: str = Field(default="claude-haiku-4-5-20251001")

    # LLM Provider selection
    llm_provider: str = Field(default="gemini")

    # Database
    database_path: str = Field(default="data/trading.duckdb")

    # Supabase (optional - for logging and persistence)
    supabase_url: str | None = Field(default=None)
    supabase_service_key: str | None = Field(default=None)
    supabase_jwt_secret: str | None = Field(default=None)

    # CORS
    allowed_origins: str = Field(
        default="https://askbar.ai,https://www.askbar.ai,http://localhost:3000"
    )

    @field_validator("google_api_key")
    @classmethod
    def validate_google_api_key(cls, v: str) -> str:
        if not v or len(v) < 10:
            raise ValueError(
                "GOOGLE_API_KEY is required. "
                "Get your key at https://aistudio.google.com/apikey"
            )
        return v

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        if v not in ("gemini", "claude"):
            raise ValueError("LLM_PROVIDER must be 'gemini' or 'claude'")
        return v


# Validate at import time - fail fast with clear errors
settings = Settings()

# =============================================================================
# Backward compatible exports (all existing code continues to work)
# =============================================================================

# Paths
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
DATABASE_PATH = settings.database_path

# LLM Provider
LLM_PROVIDER = settings.llm_provider

# Google Gemini
GOOGLE_API_KEY = settings.google_api_key
GEMINI_MODEL = settings.gemini_model
GEMINI_LITE_MODEL = settings.gemini_lite_model

# Anthropic Claude
ANTHROPIC_API_KEY = settings.anthropic_api_key
CLAUDE_MODEL = settings.claude_model

# Supabase
SUPABASE_URL = settings.supabase_url
SUPABASE_SERVICE_KEY = settings.supabase_service_key
SUPABASE_JWT_SECRET = settings.supabase_jwt_secret

# CORS
ALLOWED_ORIGINS = settings.allowed_origins.split(",")

# Chat settings
CHAT_HISTORY_LIMIT = 20
