"""Probability — conditional probability P(outcome | condition).

Uses event_filters from executor when needed (e.g. consecutive filter).
For event-based probability, looks at the NEXT day after event.
"""

import logging

import pandas as pd

from agent.rules import get_column
from agent.operations._utils import find_days_in_streak, df_to_rows

logger = logging.getLogger(__name__)


def op_probability(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Calculate probability of outcome given condition.

    For simple conditions: df is pre-filtered, calculate outcome on those rows.
    For event conditions (consecutive): find events, look at NEXT day's outcome.

    params:
        outcome: condition for success, e.g. "> 0", "< 0", "> 1%"
        event_filters: optional list of event filters (e.g. consecutive)
    """
    logger.debug(f"op_probability: what={what}, params={params}, rows={len(df)}")

    if df.empty:
        logger.warning("op_probability: empty dataframe")
        return {"rows": [], "summary": {"probability": 0, "count": 0, "matches": 0}}

    outcome = params.get("outcome", "> 0")
    event_filters = params.get("event_filters", [])

    col = get_column(what)

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

    return {"rows": df_to_rows(df), "summary": summary}


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

    return {"rows": df_to_rows(event_df), "summary": summary}


def _find_event_days(df: pd.DataFrame, event_filters: list[dict]) -> pd.DataFrame:
    """
    Find event days from filters.

    For consecutive filter: returns ALL days in matching streaks.
    """
    if not event_filters:
        return df

    f = event_filters[0]
    filter_type = f.get("type")

    if filter_type == "consecutive":
        return find_days_in_streak(df, f)

    return df


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
