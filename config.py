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

# API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "claude-haiku-4-5-20250514")

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
