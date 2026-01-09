"""Configuration management"""

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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Anthropic Claude (fallback)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

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
