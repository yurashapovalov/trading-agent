"""Around — what happens before/after event days.

Uses event_filters from executor to find events when needed (e.g. consecutive).
For simple filters (comparison), events come pre-filtered in df.
"""

import logging

import pandas as pd

from agent.operations._utils import find_days_in_streak, df_to_rows

logger = logging.getLogger(__name__)


def op_around(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Analyze what happens around event days.

    params:
        offset: +1 (day after), -1 (day before)
        event_filters: optional list of event filters (e.g. consecutive)
    """
    logger.debug(f"op_around: what={what}, params={params}, rows={len(df)}")

    if df.empty:
        logger.warning("op_around: empty dataframe")
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
        result_df = event_df
        values = event_df[col].dropna()
    else:
        # df already filtered to event days
        result_df = df
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

    return {"rows": df_to_rows(result_df), "summary": summary}


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

    # For other event types, return df as-is
    return df
