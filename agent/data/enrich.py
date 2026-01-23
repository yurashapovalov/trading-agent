"""
Enrich OHLCV data with computed columns.

Input:  Raw OHLCV (date/timestamp, open, high, low, close, volume)
Output: Same + computed columns for filtering and operations
"""

import pandas as pd


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add computed columns to OHLCV DataFrame.

    Columns added:
        change      - intraday return %
        gap         - overnight gap %
        range       - high - low (points)
        is_green    - True if change > 0
        weekday     - 0-4 (Mon-Fri)
        month       - 1-12
        year        - 2024, 2025, ...
        time        - "09:30" (minute data only)
        prev_change - previous day's change
        next_change - next day's change
    """
    if df.empty:
        return df

    df = df.copy()

    # Change: intraday return
    df["change"] = (df["close"] - df["open"]) / df["open"] * 100

    # Range: intraday range in points
    df["range"] = df["high"] - df["low"]

    # Gap: overnight gap (needs previous close)
    df["gap"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1) * 100

    # Color
    df["is_green"] = df["change"] > 0

    # Gap filled: price returned to prev_close during the day
    prev_close = df["close"].shift(1)
    gap_up_filled = (df["gap"] > 0) & (df["low"] <= prev_close)
    gap_down_filled = (df["gap"] < 0) & (df["high"] >= prev_close)
    df["gap_filled"] = gap_up_filled | gap_down_filled

    # For around operation
    df["prev_change"] = df["change"].shift(1)
    df["next_change"] = df["change"].shift(-1)

    # Date components
    date_col = _get_date_column(df)
    if date_col:
        dates = pd.to_datetime(df[date_col])
        df["weekday"] = dates.dt.dayofweek
        df["month"] = dates.dt.month
        df["year"] = dates.dt.year

        # Time (for minute data)
        if date_col == "timestamp":
            df["time"] = dates.dt.strftime("%H:%M")

    return df


def _get_date_column(df: pd.DataFrame) -> str | None:
    """Find date/timestamp column."""
    if "timestamp" in df.columns:
        return "timestamp"
    if "date" in df.columns:
        return "date"
    return None
