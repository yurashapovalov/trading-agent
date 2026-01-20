"""Basic statistics for a period."""

import pandas as pd


def op_stats(df: pd.DataFrame, params: dict) -> dict:
    """
    Calculate basic statistics.

    params:
        metrics: list of metrics to calculate (default: all)

    Returns:
        {
            "count": N,
            "avg_change_pct": X,
            "avg_range": X,
            "green_days": N,
            "red_days": N,
            "green_pct": X,
            ...
        }
    """
    if df.empty:
        return {"error": "No data"}

    result = {
        "count": len(df),
    }

    # Change stats
    if "change_pct" in df.columns:
        result["avg_change_pct"] = round(df["change_pct"].mean(), 3)
        result["median_change_pct"] = round(df["change_pct"].median(), 3)
        result["std_change_pct"] = round(df["change_pct"].std(), 3)
        result["max_change_pct"] = round(df["change_pct"].max(), 3)
        result["min_change_pct"] = round(df["change_pct"].min(), 3)

    # Range/volatility stats
    if "range" in df.columns:
        result["avg_range"] = round(df["range"].mean(), 2)
        result["max_range"] = round(df["range"].max(), 2)

    if "range_pct" in df.columns:
        result["avg_range_pct"] = round(df["range_pct"].mean(), 3)

    # Color stats
    if "is_green" in df.columns:
        green_count = df["is_green"].sum()
        result["green_days"] = int(green_count)
        result["red_days"] = int(len(df) - green_count)
        result["green_pct"] = round(green_count / len(df) * 100, 1)

    # Volume stats
    if "volume" in df.columns:
        result["avg_volume"] = int(df["volume"].mean())
        result["total_volume"] = int(df["volume"].sum())

    # Gap stats
    if "gap_pct" in df.columns:
        gaps = df["gap_pct"].dropna()
        if len(gaps) > 0:
            result["avg_gap_pct"] = round(gaps.mean(), 3)
            result["gap_up_count"] = int((gaps > 0).sum())
            result["gap_down_count"] = int((gaps < 0).sum())

    return result
