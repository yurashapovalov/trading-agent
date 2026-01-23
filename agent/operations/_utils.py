"""Shared utilities for operations."""

import pandas as pd


def find_consecutive_events(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """
    Find last day of each consecutive streak meeting criteria.

    Example: consecutive red >= 3 returns the 3rd (last) red day of each streak.

    Args:
        df: DataFrame with is_green column
        f: Filter dict with color, op, length

    Returns:
        DataFrame with last day of each matching streak
    """
    if "is_green" not in df.columns:
        return pd.DataFrame()

    color = f.get("color")
    op = f.get("op", ">=")
    length = f.get("length", 1)

    mask = df["is_green"] if color == "green" else ~df["is_green"]

    df = df.copy()
    df["_streak_id"] = (mask != mask.shift()).cumsum()

    # Get streak lengths
    streak_lengths = df.groupby("_streak_id").size()

    # Filter to valid streaks (meeting length requirement)
    if op == ">=":
        valid_streaks = streak_lengths[streak_lengths >= length].index
    elif op == ">":
        valid_streaks = streak_lengths[streak_lengths > length].index
    elif op == "=":
        valid_streaks = streak_lengths[streak_lengths == length].index
    else:
        valid_streaks = streak_lengths[streak_lengths >= length].index

    # Get last day of each valid streak
    result_rows = []
    for streak_id in valid_streaks:
        streak_rows = df[(df["_streak_id"] == streak_id) & mask]
        if not streak_rows.empty:
            result_rows.append(streak_rows.iloc[-1])

    if not result_rows:
        return pd.DataFrame()

    return pd.DataFrame(result_rows)
