"""
SQL module - fetches data at different granularities.

No LLM here. Just gets data, Analyst does the analysis.
"""

import duckdb
import numpy as np
from datetime import datetime, timedelta
from typing import Any, Literal

import config


def _convert_numpy_types(data: list[dict]) -> list[dict]:
    """Convert numpy types to Python native types for JSON serialization."""
    def convert_value(v):
        if isinstance(v, (np.integer, np.int64, np.int32)):
            return int(v)
        elif isinstance(v, (np.floating, np.float64, np.float32)):
            return float(v)
        elif isinstance(v, np.ndarray):
            return v.tolist()
        return v

    return [
        {k: convert_value(v) for k, v in row.items()}
        for row in data
    ]


# =============================================================================
# SQL Templates by Granularity
# =============================================================================

TEMPLATES = {
    # Single row for entire period (aggregated stats)
    "period": """
        SELECT
            $1 as symbol,
            MIN(timestamp)::date as period_start,
            MAX(timestamp)::date as period_end,
            COUNT(DISTINCT timestamp::date) as trading_days,
            FIRST(open ORDER BY timestamp) as open_price,
            LAST(close ORDER BY timestamp) as close_price,
            MAX(high) as max_price,
            MIN(low) as min_price,
            SUM(volume) as total_volume,
            ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
                  / FIRST(open ORDER BY timestamp) * 100, 2) as change_pct,
            ROUND(LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp), 2) as change_points
        FROM ohlcv_1min
        WHERE symbol = $1
          AND timestamp >= $2
          AND timestamp < $3
    """,

    # One row per day
    "daily": """
        SELECT
            timestamp::date as date,
            FIRST(open ORDER BY timestamp) as open,
            MAX(high) as high,
            MIN(low) as low,
            LAST(close ORDER BY timestamp) as close,
            SUM(volume) as volume,
            ROUND(MAX(high) - MIN(low), 2) as range,
            ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
                  / FIRST(open ORDER BY timestamp) * 100, 2) as change_pct
        FROM ohlcv_1min
        WHERE symbol = $1
          AND timestamp >= $2
          AND timestamp < $3
        GROUP BY date
        ORDER BY date
    """,

    # One row per hour (aggregated across all days in period)
    "hourly": """
        SELECT
            EXTRACT(HOUR FROM timestamp)::int as hour,
            COUNT(DISTINCT timestamp::date) as days_count,
            ROUND(AVG(high - low), 2) as avg_range,
            ROUND(SUM(volume) / COUNT(DISTINCT timestamp::date), 0) as avg_volume,
            ROUND(AVG(close - open), 4) as avg_move,
            ROUND(STDDEV(close - open), 4) as move_stddev
        FROM ohlcv_1min
        WHERE symbol = $1
          AND timestamp >= $2
          AND timestamp < $3
        GROUP BY hour
        ORDER BY hour
    """,

    # One row per month (time-series)
    "monthly": """
        WITH daily AS (
            SELECT
                timestamp::date as date,
                DATE_TRUNC('month', timestamp::date) as month,
                FIRST(open ORDER BY timestamp) as open,
                LAST(close ORDER BY timestamp) as close,
                MAX(high) as high,
                MIN(low) as low,
                SUM(volume) as volume
            FROM ohlcv_1min
            WHERE symbol = $1
              AND timestamp >= $2
              AND timestamp < $3
            GROUP BY date, DATE_TRUNC('month', timestamp::date)
        )
        SELECT
            STRFTIME(month, '%Y-%m') as month,
            COUNT(*) as trading_days,
            ROUND(FIRST(open ORDER BY month), 2) as open_price,
            ROUND(LAST(close ORDER BY month), 2) as close_price,
            ROUND(MAX(high), 2) as max_price,
            ROUND(MIN(low), 2) as min_price,
            ROUND(SUM(volume), 0) as total_volume,
            ROUND(AVG(high - low), 2) as avg_daily_range,
            ROUND((LAST(close ORDER BY month) - FIRST(open ORDER BY month))
                  / FIRST(open ORDER BY month) * 100, 2) as change_pct
        FROM daily
        GROUP BY month
        ORDER BY month
    """,

    # One row per day of week (aggregated across all weeks in period)
    "weekday": """
        WITH daily AS (
            SELECT
                timestamp::date as date,
                dayofweek(timestamp::date) as weekday_num,
                dayname(timestamp::date) as weekday_name,
                FIRST(open ORDER BY timestamp) as open,
                LAST(close ORDER BY timestamp) as close,
                MAX(high) as high,
                MIN(low) as low,
                SUM(volume) as volume
            FROM ohlcv_1min
            WHERE symbol = $1
              AND timestamp >= $2
              AND timestamp < $3
            GROUP BY date, dayofweek(timestamp::date), dayname(timestamp::date)
        )
        SELECT
            weekday_num,
            weekday_name,
            COUNT(*) as trading_days,
            ROUND(AVG(high - low), 2) as avg_range,
            ROUND(AVG((close - open) / open * 100), 4) as avg_change_pct,
            ROUND(AVG(volume), 0) as avg_volume,
            ROUND(STDDEV((close - open) / open * 100), 4) as volatility
        FROM daily
        WHERE weekday_num BETWEEN 1 AND 5
        GROUP BY weekday_num, weekday_name
        ORDER BY weekday_num
    """,
}


# =============================================================================
# Main Function
# =============================================================================

def fetch(
    symbol: str,
    period_start: str,
    period_end: str,
    granularity: Literal["period", "daily", "hourly", "weekday", "monthly"] = "daily"
) -> dict[str, Any]:
    """
    Fetch OHLCV data at specified granularity.

    Args:
        symbol: Trading symbol (NQ, ES, etc.)
        period_start: Start date ISO format (2025-01-01)
        period_end: End date ISO format (2025-02-01)
        granularity: How to group data
            - "period": single row with aggregates
            - "daily": one row per day
            - "hourly": one row per hour (aggregated across days)
            - "weekday": one row per day of week (Mon-Fri stats)
            - "monthly": one row per month (time-series)

    Returns:
        {
            "granularity": "daily",
            "symbol": "NQ",
            "period_start": "2025-01-01",
            "period_end": "2025-01-31",
            "row_count": 22,
            "rows": [{...}, {...}, ...]
        }
    """
    template = TEMPLATES.get(granularity)
    if not template:
        return {"error": f"Unknown granularity: {granularity}"}

    # Build actual SQL with params for logging
    sql_query = template.replace("$1", f"'{symbol}'").replace("$2", f"'{period_start}'").replace("$3", f"'{period_end}'")

    try:
        with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
            df = conn.execute(template, [symbol, period_start, period_end]).df()

            # Convert timestamps/dates to strings for JSON serialization
            for col in df.columns:
                if 'date' in col.lower() or 'timestamp' in col.lower() or 'period' in col.lower():
                    df[col] = df[col].astype(str).str[:10]  # Keep only date part

            rows = df.to_dict(orient='records')

            # Convert numpy types to Python native types for JSON serialization
            rows = _convert_numpy_types(rows)

            return {
                "granularity": granularity,
                "symbol": symbol,
                "period_start": period_start,
                "period_end": period_end,
                "row_count": len(rows),
                "rows": rows,
                "sql_query": sql_query.strip(),
            }

    except Exception as e:
        return {
            "error": str(e),
            "granularity": granularity,
            "symbol": symbol,
            "sql_query": sql_query.strip(),
        }


# =============================================================================
# Helper Functions
# =============================================================================

def get_data_range(symbol: str = "NQ") -> dict[str, Any] | None:
    """
    Get available data range for a symbol.

    Returns:
        {
            "symbol": "NQ",
            "start_date": "2024-01-02",
            "end_date": "2025-01-10",
            "trading_days": 252
        }
    """
    sql = """
        SELECT
            symbol,
            MIN(timestamp)::date as start_date,
            MAX(timestamp)::date as end_date,
            COUNT(DISTINCT timestamp::date) as trading_days
        FROM ohlcv_1min
        WHERE symbol = $1
        GROUP BY symbol
    """

    try:
        with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
            df = conn.execute(sql, [symbol]).df()
            if len(df) > 0:
                row = df.iloc[0].to_dict()
                # Convert to strings
                row['start_date'] = str(row['start_date'])[:10]
                row['end_date'] = str(row['end_date'])[:10]
                return row
            return None
    except Exception:
        return None


def get_available_symbols() -> list[str]:
    """Get list of symbols with data."""
    sql = "SELECT DISTINCT symbol FROM ohlcv_1min ORDER BY symbol"

    try:
        with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
            df = conn.execute(sql).df()
            return df['symbol'].tolist()
    except Exception:
        return []
