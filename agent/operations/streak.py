"""Detect consecutive days matching a condition (streaks)."""

import pandas as pd


def op_streak(df: pd.DataFrame, params: dict) -> dict:
    """
    Count/analyze consecutive days matching a condition.

    params:
        condition: "red", "green", or expression like "change_pct < 0"
        min_length: minimum streak length to count (default: 1)
        agg: what to return
            - "count": number of streaks
            - "max": longest streak length
            - "list": all streak lengths
            - "details": detailed info about each streak

    Example:
        params = {
            "condition": "red",
            "min_length": 3,
            "agg": "count"
        }
        → "How many times were there 3+ red days in a row"

    Returns:
        {
            "count": N,
            "max_length": N,
            "streaks": [...]
        }
    """
    if df.empty:
        return {"error": "No data"}

    condition = params.get("condition")
    min_length = params.get("min_length", 1)
    agg = params.get("agg", "count")

    if not condition:
        return {"error": "'condition' required"}

    # Build mask based on condition
    if condition == "red":
        if "is_red" not in df.columns:
            return {"error": "is_red column not found, run enrich()"}
        mask = df["is_red"]
    elif condition == "green":
        if "is_green" not in df.columns:
            return {"error": "is_green column not found, run enrich()"}
        mask = df["is_green"]
    else:
        # Custom expression
        try:
            mask = df.eval(condition)
        except Exception as e:
            return {"error": f"Invalid condition: {e}"}

    # Find streaks using group-by on changes
    df = df.copy()
    df["_mask"] = mask
    df["_streak_id"] = (df["_mask"] != df["_mask"].shift()).cumsum()

    # Get streak lengths for True values
    streaks = df[df["_mask"]].groupby("_streak_id").size()

    # Filter by min_length
    valid_streaks = streaks[streaks >= min_length]

    result = {
        "count": len(valid_streaks),
        "max_length": int(valid_streaks.max()) if len(valid_streaks) > 0 else 0,
        "total_streaks": len(streaks),  # All streaks regardless of length
    }

    if agg == "list" or agg == "details":
        result["streaks"] = valid_streaks.tolist()

    if agg == "details" and len(valid_streaks) > 0:
        # Get date ranges for each streak
        details = []
        for streak_id in valid_streaks.index:
            streak_rows = df[df["_streak_id"] == streak_id]
            date_col = "date" if "date" in df.columns else "timestamp"
            details.append({
                "length": len(streak_rows),
                "start": str(streak_rows[date_col].iloc[0]),
                "end": str(streak_rows[date_col].iloc[-1]),
            })
        result["details"] = details

    return result
