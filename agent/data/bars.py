"""
Get OHLCV bars at any timeframe.

Aggregates minute candles to requested timeframe.
Trading day boundaries and sessions come from instrument config.
"""

import duckdb
import pandas as pd

import config
from agent.config.market.instruments import (
    get_trading_day_boundaries,
    get_session_times,
)
from agent.config.market.holidays import is_trading_day


def get_bars(
    symbol: str,
    period: str,
    timeframe: str = "1D",
) -> pd.DataFrame:
    """
    Get OHLCV bars at specified timeframe.

    Args:
        symbol: Instrument symbol
        period: Period string ("2024", "2020-2025", "all")
        timeframe: Aggregation level:
            Minutes: "1m", "5m", "15m", "30m"
            Hours: "1H", "2H", "4H"
            Days+: "1D", "1W", "1M"
            Sessions: "RTH", "ETH", "OVERNIGHT", etc. (from config)

    Returns:
        DataFrame with columns: date/timestamp, open, high, low, close, volume
    """
    start_date, end_date = _parse_period(period)

    # Minute-based timeframes
    if timeframe == "1m":
        return _get_minutes(symbol, start_date, end_date)
    if timeframe in ("5m", "15m", "30m"):
        minutes = int(timeframe.replace("m", ""))
        return _get_minute_bars(symbol, start_date, end_date, minutes)

    # Hour-based timeframes
    if timeframe in ("1H", "2H", "4H"):
        hours = int(timeframe.replace("H", ""))
        return _get_hour_bars(symbol, start_date, end_date, hours)

    # Daily — special handling for trading day
    if timeframe == "1D":
        return _get_daily(symbol, start_date, end_date)

    # Weekly
    if timeframe == "1W":
        return _get_weekly(symbol, start_date, end_date)

    # Monthly
    if timeframe == "1M":
        return _get_monthly(symbol, start_date, end_date)

    # Session (RTH, ETH, etc.)
    session_times = get_session_times(symbol, timeframe)
    if session_times:
        return _get_session(symbol, start_date, end_date, timeframe, session_times)

    raise ValueError(f"Unknown timeframe: {timeframe}")


# =============================================================================
# INTERNAL AGGREGATION FUNCTIONS
# =============================================================================


def _get_minutes(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Raw minute bars."""
    sql = f"""
        SELECT timestamp, open, high, low, close, volume
        FROM ohlcv_1min
        WHERE symbol = '{symbol}'
          AND timestamp >= '{start_date}'
          AND timestamp < '{end_date}'
        ORDER BY timestamp
    """
    return _execute(sql)


def _get_minute_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    minutes: int,
) -> pd.DataFrame:
    """Aggregate to N-minute bars (5m, 15m, 30m)."""
    sql = f"""
        SELECT
            TIME_BUCKET(INTERVAL '{minutes} minutes', timestamp) AS timestamp,
            FIRST(open ORDER BY timestamp) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            LAST(close ORDER BY timestamp) AS close,
            SUM(volume) AS volume
        FROM ohlcv_1min
        WHERE symbol = '{symbol}'
          AND timestamp >= '{start_date}'
          AND timestamp < '{end_date}'
        GROUP BY 1
        ORDER BY 1
    """
    return _execute(sql)


def _get_hour_bars(
    symbol: str,
    start_date: str,
    end_date: str,
    hours: int,
) -> pd.DataFrame:
    """Aggregate to N-hour bars (1H, 2H, 4H)."""
    sql = f"""
        SELECT
            TIME_BUCKET(INTERVAL '{hours} hours', timestamp) AS timestamp,
            FIRST(open ORDER BY timestamp) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            LAST(close ORDER BY timestamp) AS close,
            SUM(volume) AS volume
        FROM ohlcv_1min
        WHERE symbol = '{symbol}'
          AND timestamp >= '{start_date}'
          AND timestamp < '{end_date}'
        GROUP BY 1
        ORDER BY 1
    """
    return _execute(sql)


def _get_daily(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Daily bars with trading day logic from config."""
    boundaries = get_trading_day_boundaries(symbol)

    if boundaries:
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
            WHERE symbol = '{symbol}'
              AND timestamp >= '{start_date}'
              AND timestamp < '{end_date}'
            GROUP BY 1
            ORDER BY 1
        """
    else:
        sql = f"""
            SELECT
                CAST(timestamp AS DATE) AS date,
                FIRST(open ORDER BY timestamp) AS open,
                MAX(high) AS high,
                MIN(low) AS low,
                LAST(close ORDER BY timestamp) AS close,
                SUM(volume) AS volume
            FROM ohlcv_1min
            WHERE symbol = '{symbol}'
              AND timestamp >= '{start_date}'
              AND timestamp < '{end_date}'
            GROUP BY 1
            ORDER BY 1
        """

    df = _execute(sql)
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[df["date"].apply(lambda d: is_trading_day(symbol, d))]
    return df.reset_index(drop=True)


def _get_hourly(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Hourly bars."""
    sql = f"""
        SELECT
            DATE_TRUNC('hour', timestamp) AS timestamp,
            FIRST(open ORDER BY timestamp) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            LAST(close ORDER BY timestamp) AS close,
            SUM(volume) AS volume
        FROM ohlcv_1min
        WHERE symbol = '{symbol}'
          AND timestamp >= '{start_date}'
          AND timestamp < '{end_date}'
        GROUP BY 1
        ORDER BY 1
    """
    return _execute(sql)


def _get_weekly(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Weekly bars (Monday start)."""
    # First get daily, then aggregate to weekly in pandas
    df = _get_daily(symbol, start_date, end_date)
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.to_period("W-SUN").dt.start_time

    weekly = df.groupby("week").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()

    weekly = weekly.rename(columns={"week": "date"})
    weekly["date"] = weekly["date"].dt.date
    return weekly


def _get_monthly(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Monthly bars."""
    df = _get_daily(symbol, start_date, end_date)
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").dt.start_time

    monthly = df.groupby("month").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()

    monthly = monthly.rename(columns={"month": "date"})
    monthly["date"] = monthly["date"].dt.date
    return monthly


def _get_session(
    symbol: str,
    start_date: str,
    end_date: str,
    session: str,
    session_times: tuple[str, str],
) -> pd.DataFrame:
    """Session bars (RTH, ETH, etc.)."""
    start_time, end_time = session_times
    start_hour = int(start_time.split(":")[0])
    end_hour = int(end_time.split(":")[0])

    # Handle sessions that cross midnight
    if start_hour > end_hour:
        hour_filter = f"(EXTRACT(HOUR FROM timestamp) >= {start_hour} OR EXTRACT(HOUR FROM timestamp) < {end_hour})"
    else:
        hour_filter = f"(EXTRACT(HOUR FROM timestamp) >= {start_hour} AND EXTRACT(HOUR FROM timestamp) < {end_hour})"

    # Get trading day boundaries for date assignment
    boundaries = get_trading_day_boundaries(symbol)
    if boundaries:
        day_start_hour = int(boundaries[0].split(":")[0])
        date_expr = f"""
            CASE
                WHEN EXTRACT(HOUR FROM timestamp) >= {day_start_hour}
                THEN CAST(timestamp AS DATE) + INTERVAL '1 day'
                ELSE CAST(timestamp AS DATE)
            END
        """
    else:
        date_expr = "CAST(timestamp AS DATE)"

    sql = f"""
        SELECT
            {date_expr} AS date,
            FIRST(open ORDER BY timestamp) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            LAST(close ORDER BY timestamp) AS close,
            SUM(volume) AS volume
        FROM ohlcv_1min
        WHERE symbol = '{symbol}'
          AND timestamp >= '{start_date}'
          AND timestamp < '{end_date}'
          AND {hour_filter}
        GROUP BY 1
        ORDER BY 1
    """

    df = _execute(sql)
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[df["date"].apply(lambda d: is_trading_day(symbol, d))]
    return df.reset_index(drop=True)


# =============================================================================
# HELPERS
# =============================================================================


def _execute(sql: str) -> pd.DataFrame:
    """Execute SQL and return DataFrame."""
    con = duckdb.connect(config.DATABASE_PATH, read_only=True)
    df = con.execute(sql).fetchdf()
    con.close()
    return df


def _parse_period(period: str) -> tuple[str, str]:
    """
    Parse period string to (start_date, end_date).

    Supports:
        "2024" → year
        "2020-2025" → year range
        "2024-01-15:2024-01-20" → exact date range
        "all" → all data
        "last_week" → last 7 calendar days
        "last_month" → last 30 calendar days
        "last_N_days" → last N calendar days
        "yesterday" → yesterday
        "today" → today
        "ytd" → year to date
        "mtd" → month to date
    """
    from datetime import date, timedelta

    period = period.strip().lower()
    today = date.today()

    # All data
    if period == "all":
        return "2000-01-01", "2100-01-01"

    # Exact date range: "2024-01-15:2024-01-20"
    if ":" in period:
        parts = period.split(":")
        return parts[0], parts[1]

    # Relative periods
    if period == "today":
        return str(today), str(today + timedelta(days=1))

    if period == "yesterday":
        yesterday = today - timedelta(days=1)
        return str(yesterday), str(today)

    if period == "last_week":
        start = today - timedelta(days=7)
        return str(start), str(today)

    if period == "last_month":
        start = today - timedelta(days=30)
        return str(start), str(today)

    if period.startswith("last_") and period.endswith("_days"):
        # last_N_days
        n = int(period.replace("last_", "").replace("_days", ""))
        start = today - timedelta(days=n)
        return str(start), str(today)

    if period == "ytd":
        start = date(today.year, 1, 1)
        return str(start), str(today + timedelta(days=1))

    if period == "mtd":
        start = date(today.year, today.month, 1)
        return str(start), str(today + timedelta(days=1))

    # Year range: "2020-2025"
    if "-" in period and len(period) == 9 and period[4] == "-":
        parts = period.split("-")
        start_year = int(parts[0])
        end_year = int(parts[1])
        return f"{start_year}-01-01", f"{end_year + 1}-01-01"

    # Single year: "2024"
    if period.isdigit() and len(period) == 4:
        year = int(period)
        return f"{year}-01-01", f"{year + 1}-01-01"

    # Fallback: try to parse as year
    try:
        year = int(period)
        return f"{year}-01-01", f"{year + 1}-01-01"
    except ValueError:
        raise ValueError(f"Unknown period format: {period}")
