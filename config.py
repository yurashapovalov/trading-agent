"""Application configuration loaded from environment variables.

All settings are loaded from .env file or environment. Provides configuration
for LLM providers (Gemini, Claude), database paths, Supabase, CORS, and trading symbols.

Example:
    import config
    print(config.GEMINI_MODEL)  # "gemini-3-flash-preview"
    print(config.DATABASE_PATH)  # "data/trading.duckdb"
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/trading.duckdb")

# LLM Provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # "gemini" or "claude"

# Google Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
GEMINI_LITE_MODEL = os.getenv("GEMINI_LITE_MODEL", "gemini-2.5-flash-lite-preview-09-2025")

# Anthropic Claude (fallback)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")  # From Supabase Dashboard > Settings > API

# CORS - allowed origins for frontend
_default_origins = "https://askbar.ai,https://www.askbar.ai,http://localhost:3000"
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", _default_origins).split(",")

# Chat settings
CHAT_HISTORY_LIMIT = 20  # Max recent messages to include in LLM context (Gemini handles 1M tokens)

# Feature flags
USE_BARB = os.getenv("USE_BARB", "true").lower() == "true"  # Parser+Composer flow (default)
ANALYST_FAST_MODE = os.getenv("ANALYST_FAST_MODE", "false").lower() == "true"  # Skip JSON/stats, plain text

# Trading symbols config
SYMBOLS = {
    "CL": {
        "name": "Crude Oil",
        "tick_size": 0.01,
        "tick_value": 10.0,
        "exchange": "NYMEX",
        "trading_hours": "18:00-17:00"
    },
    "NQ": {
        "name": "Nasdaq 100 E-mini",
        "tick_size": 0.25,
        "tick_value": 5.0,
        "exchange": "CME",
        "trading_hours": "18:00-17:00"
    },
    "ES": {
        "name": "S&P 500 E-mini",
        "tick_size": 0.25,
        "tick_value": 12.50,
        "exchange": "CME",
        "trading_hours": "18:00-17:00"
    }
}
# Auto-deploy configured
