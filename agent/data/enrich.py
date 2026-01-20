"""
Add computed fields to OHLCV data.

All fields that can be derived from base OHLCV are computed here:
- change_pct: (close - open) / open * 100
- range: high - low (absolute)
- range_pct: range / low * 100
- weekday, month, quarter, year
- is_red, is_green
- gap_pct: (open - prev_close) / prev_close * 100
- prev_change: previous day's change_pct
"""

import pandas as pd


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add computed fields to OHLCV DataFrame.

    Works with both daily and minute data.
    For minute data, some fields (weekday, gap_pct) may not make sense.

    Args:
        df: DataFrame with columns: date/timestamp, open, high, low, close, volume

    Returns:
        Same DataFrame with added columns
    """
    # Price change (intraday)
    df["change_pct"] = (df["close"] - df["open"]) / df["open"] * 100

    # Range (volatility measure)
    df["range"] = df["high"] - df["low"]
    df["range_pct"] = df["range"] / df["low"] * 100

    # Color
    df["is_red"] = df["close"] < df["open"]
    df["is_green"] = df["close"] > df["open"]

    # Date components (for daily data)
    date_col = "date" if "date" in df.columns else "timestamp"
    if date_col in df.columns:
        dates = pd.to_datetime(df[date_col])
        df["weekday"] = dates.dt.dayofweek  # 0=Monday, 6=Sunday
        df["month"] = dates.dt.month
        df["quarter"] = dates.dt.quarter
        df["year"] = dates.dt.year

    # Gap (from previous close to current open)
    # Only meaningful for daily data
    if "date" in df.columns:
        df["gap_pct"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1) * 100
        df["prev_change"] = df["change_pct"].shift(1)
        df["prev_close"] = df["close"].shift(1)

    return df
