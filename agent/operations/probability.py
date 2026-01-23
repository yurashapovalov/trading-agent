"""Probability — conditional probability P(outcome | condition).

Uses event_filters from executor when needed (e.g. consecutive filter).
For event-based probability, looks at the NEXT day after event.
"""

import pandas as pd


def op_probability(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Calculate probability of outcome given condition.

    For simple conditions: df is pre-filtered, calculate outcome on those rows.
    For event conditions (consecutive): find events, look at NEXT day's outcome.

    params:
        outcome: condition for success, e.g. "> 0", "< 0", "> 1%"
        event_filters: optional list of event filters (e.g. consecutive)
    """
    if df.empty:
        return {"rows": [], "summary": {"probability": 0, "count": 0, "matches": 0}}

    outcome = params.get("outcome", "> 0")
    event_filters = params.get("event_filters", [])

    col = _what_to_column(what)

    # If event_filters present, find events and look at NEXT day
    if event_filters:
        return _probability_after_event(df, event_filters, outcome, col)

    # Standard case: df is pre-filtered to condition
    if col not in df.columns:
        return {"rows": [], "summary": {"error": f"Column {col} not found"}}

    try:
        matches = _eval_outcome(df[col], outcome)
    except Exception as e:
        return {"rows": [], "summary": {"error": f"Invalid outcome: {e}"}}

    match_count = matches.sum()
    total = len(df)
    prob = match_count / total * 100 if total > 0 else 0

    summary = {
        "probability": round(prob, 1),
        "matches": int(match_count),
        "total": total,
        "outcome": outcome,
        "metric": col,
    }

    return {"rows": [], "summary": summary}


def _probability_after_event(
    df: pd.DataFrame,
    event_filters: list[dict],
    outcome: str,
    col: str
) -> dict:
    """
    Calculate probability of outcome in the day AFTER event.

    Example: P(green | after 2+ red days) looks at day after streak ends.
    """
    if "next_change" not in df.columns:
        return {"rows": [], "summary": {"error": "next_change not found. Run enrich() first."}}

    # Find event days (last day of each qualifying streak)
    event_df = _find_event_days(df, event_filters)

    if event_df.empty:
        return {"rows": [], "summary": {"probability": 0, "count": 0, "matches": 0, "error": "No events found"}}

    # Use next_change as the "next day's" performance
    # (for outcome like "> 0" meaning green next day)
    next_values = event_df["next_change"].dropna()

    if len(next_values) == 0:
        return {"rows": [], "summary": {"probability": 0, "count": 0, "matches": 0}}

    try:
        matches = _eval_outcome(next_values, outcome)
    except Exception as e:
        return {"rows": [], "summary": {"error": f"Invalid outcome: {e}"}}

    match_count = matches.sum()
    total = len(next_values)
    prob = match_count / total * 100 if total > 0 else 0

    summary = {
        "probability": round(prob, 1),
        "matches": int(match_count),
        "total": total,
        "outcome": outcome,
        "metric": "next_change",
        "event_type": "consecutive",
    }

    return {"rows": [], "summary": summary}


def _find_event_days(df: pd.DataFrame, event_filters: list[dict]) -> pd.DataFrame:
    """
    Find event days from filters.

    For consecutive filter: returns LAST day of each streak.
    """
    if not event_filters:
        return df

    f = event_filters[0]
    filter_type = f.get("type")

    if filter_type == "consecutive":
        return _find_consecutive_events(df, f)

    return df


def _find_consecutive_events(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    """
    Find last day of each consecutive streak meeting criteria.
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

    # Filter to valid streaks
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


def _eval_outcome(series: pd.Series, outcome: str) -> pd.Series:
    """Evaluate outcome condition on series."""
    outcome = outcome.strip()

    # Handle percentage
    if outcome.endswith("%"):
        outcome = outcome[:-1].strip()

    # Parse operator and value
    for op in [">=", "<=", ">", "<", "="]:
        if outcome.startswith(op):
            value = float(outcome[len(op):].strip())
            if op == ">":
                return series > value
            elif op == "<":
                return series < value
            elif op == ">=":
                return series >= value
            elif op == "<=":
                return series <= value
            elif op == "=":
                return series == value

    # Default: positive
    return series > 0


def _what_to_column(what: str) -> str:
    """Map atom.what to DataFrame column."""
    if what == "volatility":
        return "range"
    return what
