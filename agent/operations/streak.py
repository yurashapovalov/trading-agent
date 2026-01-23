"""Streak — count/analyze consecutive days matching condition.

Uses condition_filters from executor to determine streak condition.
Receives FULL data (not pre-filtered) because requires_full_data=True.
"""

import pandas as pd

from agent.rules import get_column


def op_streak(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Analyze streaks (consecutive days matching condition).

    Receives full data (not pre-filtered). Condition comes from
    params["condition_filters"] which executor passes instead of
    applying as WHERE filter.

    params:
        n: minimum streak length (default: 2)
        condition_filters: list of filter dicts defining the condition
    """
    if df.empty:
        return {"rows": [], "summary": {"count": 0, "total_days": 0}}

    min_length = params.get("n", 2)
    condition_filters = params.get("condition_filters", [])

    # Build mask from condition_filters
    mask = _build_mask(df, condition_filters, what)

    if mask is None:
        return {"rows": [], "summary": {"error": "Could not determine condition"}}

    # Find streaks
    df = df.copy()
    df["_mask"] = mask
    df["_streak_id"] = (df["_mask"] != df["_mask"].shift()).cumsum()

    # Get streak lengths for matching values (where mask is True)
    streaks = df[df["_mask"]].groupby("_streak_id").size()

    # Filter by min_length
    valid_streaks = streaks[streaks >= min_length]

    # Build rows with streak details
    rows = []
    date_col = "date" if "date" in df.columns else "timestamp"

    for streak_id in valid_streaks.index:
        streak_rows = df[df["_streak_id"] == streak_id]
        rows.append({
            "start": str(streak_rows[date_col].iloc[0]),
            "end": str(streak_rows[date_col].iloc[-1]),
            "length": len(streak_rows),
        })

    # Sort by length descending
    rows.sort(key=lambda x: x["length"], reverse=True)

    summary = {
        "count": len(valid_streaks),
        "max_length": int(valid_streaks.max()) if len(valid_streaks) > 0 else 0,
        "avg_length": round(valid_streaks.mean(), 1) if len(valid_streaks) > 0 else 0,
        "total_days": len(df),
        "min_length": min_length,
    }

    return {"rows": rows[:20], "summary": summary}


def _build_mask(df: pd.DataFrame, condition_filters: list, what: str) -> pd.Series | None:
    """
    Build boolean mask from condition_filters.

    Supports:
    - comparison: {"type": "comparison", "metric": "change", "op": "<", "value": 0}
    - pattern: {"type": "pattern", "pattern": "red"}
    """
    if not condition_filters:
        # Default: use metric from 'what' > 0
        col = get_column(what)
        if col in df.columns:
            return df[col] > 0
        elif "change" in df.columns:
            return df["change"] > 0
        return None

    # Use first condition filter
    f = condition_filters[0]
    filter_type = f.get("type")

    if filter_type == "comparison":
        return _mask_from_comparison(df, f)

    if filter_type == "pattern":
        return _mask_from_pattern(df, f)

    # Fallback
    col = get_column(what)
    if col in df.columns:
        return df[col] > 0

    return None


def _mask_from_comparison(df: pd.DataFrame, f: dict) -> pd.Series | None:
    """Build mask from comparison filter."""
    col = f.get("metric")
    op = f.get("op")
    value = f.get("value")

    if col not in df.columns:
        return None

    series = df[col]
    ops = {
        ">": series > value,
        "<": series < value,
        ">=": series >= value,
        "<=": series <= value,
        "=": series == value,
    }

    return ops.get(op)


def _mask_from_pattern(df: pd.DataFrame, f: dict) -> pd.Series | None:
    """Build mask from pattern filter."""
    pattern = f.get("pattern")

    if pattern == "green" and "is_green" in df.columns:
        return df["is_green"]
    if pattern == "red" and "is_green" in df.columns:
        return ~df["is_green"]

    return None
