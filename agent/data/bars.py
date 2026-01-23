"""
Get OHLCV bars at specified timeframe.

Supported timeframes:
  - 1m, 5m, 15m, 30m (minute bars)
  - 1H, 4H (hour bars)
  - 1D (daily bars)

Weekly/monthly aggregation is done via 'group' parameter in operations, not here.
"""

import duckdb
import pandas as pd

import config
from agent.config.market.instruments import get_trading_day_boundaries
from agent.config.market.holidays import is_trading_day


def get_bars(
    symbol: str,
    period: str,
    timeframe: str = "1D",
) -> pd.DataFrame:
    """
    Get OHLCV bars at specified timeframe.

    Args:
        symbol: Instrument symbol (e.g., "NQ")
        period: Period string ("2024", "2020-2025", "all")
        timeframe: "1m", "5m", "15m", "30m", "1H", "4H", "1D"

    Returns:
        DataFrame with: date/timestamp, open, high, low, close, volume
    """
    start_date, end_date = _parse_period(period)

    if timeframe == "1m":
        return _get_minute_bars(symbol, start_date, end_date, 1)

    if timeframe in ("5m", "15m", "30m"):
        minutes = int(timeframe.replace("m", ""))
        return _get_minute_bars(symbol, start_date, end_date, minutes)

    if timeframe in ("1H", "4H"):
        hours = int(timeframe.replace("H", ""))
        return _get_hour_bars(symbol, start_date, end_date, hours)

    if timeframe == "1D":
        return _get_daily_bars(symbol, start_date, end_date)

    raise ValueError(f"Unknown timeframe: {timeframe}. Use: 1m, 5m, 15m, 30m, 1H, 4H, 1D")


# =============================================================================
# Internal functions
# =============================================================================

def _get_minute_bars(symbol: str, start: str, end: str, minutes: int) -> pd.DataFrame:
    """Get minute bars (1m, 5m, 15m, 30m)."""
    if minutes == 1:
        sql = """
            SELECT timestamp, open, high, low, close, volume
            FROM ohlcv_1min
            WHERE symbol = ?
              AND timestamp >= ?
              AND timestamp < ?
            ORDER BY timestamp
        """
    else:
        sql = f"""
            SELECT
                TIME_BUCKET(INTERVAL '{minutes} minutes', timestamp) AS timestamp,
                FIRST(open ORDER BY timestamp) AS open,
                MAX(high) AS high,
                MIN(low) AS low,
                LAST(close ORDER BY timestamp) AS close,
                SUM(volume) AS volume
            FROM ohlcv_1min
            WHERE symbol = ?
              AND timestamp >= ?
              AND timestamp < ?
            GROUP BY 1
            ORDER BY 1
        """
    return _query(sql, [symbol, start, end])


def _get_hour_bars(symbol: str, start: str, end: str, hours: int) -> pd.DataFrame:
    """Get hour bars (1H, 4H)."""
    sql = f"""
        SELECT
            TIME_BUCKET(INTERVAL '{hours} hours', timestamp) AS timestamp,
            FIRST(open ORDER BY timestamp) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            LAST(close ORDER BY timestamp) AS close,
            SUM(volume) AS volume
        FROM ohlcv_1min
        WHERE symbol = ?
          AND timestamp >= ?
          AND timestamp < ?
        GROUP BY 1
        ORDER BY 1
    """
    return _query(sql, [symbol, start, end])


def _get_daily_bars(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Get daily bars with trading day boundaries."""
    boundaries = get_trading_day_boundaries(symbol)

    if boundaries:
        # Futures: trading day starts previous evening (e.g., 18:00)
        start_hour = int(boundaries[0].split(":")[0])
        sql = f"""
            SELECT
                CASE
                    WHEN EXTRACT(HOUR FROM timestamp) >= {start_hour}
                    THEN CAST(timestamp AS DATE) + INTERVAL '1 day'
                    ELSE CAST(timestamp AS DATE)
                END AS date,
                FIRST(open ORDER BY timestamp) AS open,
                MAX(high) AS high,
                MIN(low) AS low,
                LAST(close ORDER BY timestamp) AS close,
                SUM(volume) AS volume
            FROM ohlcv_1min
            WHERE symbol = ?
              AND timestamp >= ?
              AND timestamp < ?
            GROUP BY 1
            ORDER BY 1
        """
    else:
        # Stocks: simple calendar day
        sql = """
            SELECT
                CAST(timestamp AS DATE) AS date,
                FIRST(open ORDER BY timestamp) AS open,
                MAX(high) AS high,
                MIN(low) AS low,
                LAST(close ORDER BY timestamp) AS close,
                SUM(volume) AS volume
            FROM ohlcv_1min
            WHERE symbol = ?
              AND timestamp >= ?
              AND timestamp < ?
            GROUP BY 1
            ORDER BY 1
        """

    df = _query(sql, [symbol, start, end])
    if df.empty:
        return df

    # Filter out holidays/weekends
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[df["date"].apply(lambda d: is_trading_day(symbol, d))]
    return df.reset_index(drop=True)


def _query(sql: str, params: list | None = None) -> pd.DataFrame:
    """Execute SQL query with optional parameters."""
    con = duckdb.connect(config.DATABASE_PATH, read_only=True)
    if params:
        df = con.execute(sql, params).fetchdf()
    else:
        df = con.execute(sql).fetchdf()
    con.close()
    return df


def _parse_period(period: str) -> tuple[str, str]:
    """Parse period to (start_date, end_date)."""
    from datetime import date, timedelta

    period = period.strip().lower()
    today = date.today()

    if period == "all":
        return "2000-01-01", "2100-01-01"

    if period == "today":
        return str(today), str(today + timedelta(days=1))

    if period == "yesterday":
        return str(today - timedelta(days=1)), str(today)

    # Exact date range: "2024-01-01:2024-12-31"
    if ":" in period:
        parts = period.split(":")
        return parts[0], parts[1]

    # Year: "2024"
    if period.isdigit() and len(period) == 4:
        year = int(period)
        return f"{year}-01-01", f"{year + 1}-01-01"

    # Year range: "2020-2025"
    if "-" in period and len(period) == 9:
        parts = period.split("-")
        return f"{parts[0]}-01-01", f"{int(parts[1]) + 1}-01-01"

    raise ValueError(f"Unknown period: {period}")
