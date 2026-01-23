"""Around — what happens before/after event days.

Uses event_filters from executor to find events when needed (e.g. consecutive).
For simple filters (comparison), events come pre-filtered in df.
"""

import pandas as pd


def op_around(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Analyze what happens around event days.

    params:
        offset: +1 (day after), -1 (day before)
        event_filters: optional list of event filters (e.g. consecutive)
    """
    if df.empty:
        return {"rows": [], "summary": {"error": "No data"}}

    offset = params.get("offset", 1)
    event_filters = params.get("event_filters", [])

    # Determine which column to use based on offset
    if offset == 1:
        col = "next_change"
    elif offset == -1:
        col = "prev_change"
    else:
        return {"rows": [], "summary": {"error": f"Offset {offset} not supported, use 1 or -1"}}

    if col not in df.columns:
        return {"rows": [], "summary": {"error": f"Column {col} not found. Run enrich() first."}}

    # If event_filters present, find events and get last day of each
    if event_filters:
        event_df = _find_event_days(df, event_filters)
        if event_df.empty:
            return {"rows": [], "summary": {"count": 0, "error": "No events found"}}
        values = event_df[col].dropna()
    else:
        # df already filtered to event days
        values = df[col].dropna()

    if len(values) == 0:
        return {"rows": [], "summary": {"count": 0}}

    positive = (values > 0).sum()
    negative = (values < 0).sum()

    summary = {
        "count": len(values),
        "avg": round(values.mean(), 3),
        "median": round(values.median(), 3),
        "positive": int(positive),
        "negative": int(negative),
        "positive_pct": round(positive / len(values) * 100, 1),
        "offset": offset,
    }

    return {"rows": [], "summary": summary}


def _find_event_days(df: pd.DataFrame, event_filters: list[dict]) -> pd.DataFrame:
    """
    Find event days from filters.

    For consecutive filter: returns LAST day of each streak (the event day).
    """
    if not event_filters:
        return df

    f = event_filters[0]
    filter_type = f.get("type")

    if filter_type == "consecutive":
        return _find_consecutive_events(df, f)

    # For other event types, return df as-is
    return df


def _find_consecutive_events(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """
    Find last day of each consecutive streak meeting criteria.

    Example: consecutive red >= 3 returns the 3rd (last) red day of each streak.
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
            result_rows.append(streak_rows.iloc[-1])  # Last row of streak

    if not result_rows:
        return pd.DataFrame()

    return pd.DataFrame(result_rows)
