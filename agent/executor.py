"""
Executor — runs ParsedQuery against data.

Simple pipeline:
    ParsedQuery → resolve_period → get_bars → enrich → filter → operation → result
"""

from datetime import date
import pandas as pd

from agent.types import ParsedQuery
from agent.date_resolver import resolve_period
from agent.data import get_bars, enrich
from agent.operations import OPERATIONS
from agent.patterns import scan_patterns


def execute(
    parsed: ParsedQuery,
    symbol: str = "NQ",
    today: date | None = None,
) -> dict:
    """
    Execute parsed query and return result.

    Args:
        parsed: ParsedQuery from Parser
        symbol: Instrument symbol
        today: Today's date (for period resolution)

    Returns:
        dict with result based on intent/operation:
        - intent=chitchat/concept → {"intent": "...", "topic": "..."}
        - intent=data → {"data": df, "result": {...}, "meta": {...}}
    """
    today = today or date.today()

    # Non-data intents
    if parsed.intent == "chitchat":
        return {"intent": "chitchat"}

    if parsed.intent == "concept":
        return {"intent": "concept", "topic": parsed.what}

    # Data intent — need clarification?
    if parsed.unclear:
        return {
            "intent": "clarification",
            "unclear": parsed.unclear,
            "parsed": parsed.model_dump(),
        }

    # Resolve period
    dates = resolve_period(parsed.period, today, symbol)
    if not dates:
        # No period specified — use all available data
        dates = ("2008-01-01", today.isoformat())

    start_date, end_date = dates

    # Determine timeframe
    timeframe = _get_timeframe(parsed)

    # Get data
    period_str = f"{start_date}:{end_date}"
    df = get_bars(symbol, period_str, timeframe)

    if df.empty:
        return {
            "intent": "no_data",
            "period": (start_date, end_date),
            "parsed": parsed.model_dump(),
        }

    # Enrich
    df = enrich(df)

    # Apply filters
    df = _apply_filters(df, parsed)

    if df.empty:
        return {
            "intent": "no_data",
            "period": (start_date, end_date),
            "filters": _get_filter_description(parsed),
            "parsed": parsed.model_dump(),
        }

    # Determine operation
    operation = parsed.operation or "stats"

    # Build operation params
    params = _build_params(parsed, operation)

    # Execute operation
    if operation in OPERATIONS:
        result = OPERATIONS[operation](df, params)
    elif operation == "list":
        result = _list_data(df, parsed)
    elif operation == "filter":
        result = _filter_data(df, parsed)
    else:
        result = OPERATIONS["stats"](df, params)

    return {
        "intent": "data",
        "operation": operation,
        "result": result,
        "row_count": len(df),
        "period": (start_date, end_date),
        "data": df,
        "parsed": parsed.model_dump(),
    }


def _get_timeframe(parsed: ParsedQuery) -> str:
    """Determine timeframe from parsed query."""
    # Session specified → use session timeframe
    if parsed.session:
        return parsed.session

    # Time range specified → hourly data
    if parsed.time:
        return "1H"

    # Group by hour → hourly data
    if parsed.group_by == "hour":
        return "1H"

    # Default to daily
    return "1D"


def _apply_filters(df: pd.DataFrame, parsed: ParsedQuery) -> pd.DataFrame:
    """Apply filters to DataFrame."""
    # Weekday filter
    if parsed.weekday_filter:
        weekday_map = {
            "monday": 0, "mon": 0,
            "tuesday": 1, "tue": 1,
            "wednesday": 2, "wed": 2,
            "thursday": 3, "thu": 3,
            "friday": 4, "fri": 4,
            "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6,
        }
        weekdays = []
        for day in parsed.weekday_filter:
            day_lower = day.lower()
            if day_lower in weekday_map:
                weekdays.append(weekday_map[day_lower])
        if weekdays and "weekday" in df.columns:
            df = df[df["weekday"].isin(weekdays)]

    # Time range filter (for intraday data)
    if parsed.time and "timestamp" in df.columns:
        df = df.copy()
        df["_hour"] = pd.to_datetime(df["timestamp"]).dt.strftime("%H:%M")
        start_time = parsed.time.start
        end_time = parsed.time.end
        df = df[(df["_hour"] >= start_time) & (df["_hour"] < end_time)]
        df = df.drop(columns=["_hour"])

    # Condition filter
    if parsed.condition:
        try:
            df = df.query(parsed.condition)
        except Exception:
            # If query fails, try with enriched column names
            condition = _normalize_condition(parsed.condition)
            try:
                df = df.query(condition)
            except Exception:
                pass  # Ignore invalid conditions

    return df.reset_index(drop=True)


def _normalize_condition(condition: str) -> str:
    """Normalize condition string for pandas query."""
    # Common aliases
    replacements = {
        "gap": "gap_pct",
        "change": "change_pct",
        "volatility": "range_pct",
    }
    result = condition
    for old, new in replacements.items():
        if old in result and new not in result:
            result = result.replace(old, new)
    return result


def _build_params(parsed: ParsedQuery, operation: str) -> dict:
    """Build operation params from parsed query."""
    params = {}

    # Top N
    if parsed.top_n:
        params["n"] = parsed.top_n

    # Sort
    if parsed.sort_by:
        params["by"] = parsed.sort_by
        params["ascending"] = parsed.sort_order == "asc"

    # Group by (for seasonality, compare)
    if parsed.group_by:
        params["group_by"] = parsed.group_by
        params["metric"] = parsed.sort_by or "change_pct"

    # Compare
    if parsed.compare:
        params["groups"] = parsed.compare

    # Streak condition
    if operation == "streak" and parsed.condition:
        params["condition"] = parsed.condition

    # Default metric for operations that need it
    if operation in ("seasonality", "compare") and "metric" not in params:
        params["metric"] = "change_pct"

    return params


MAX_LIST_ROWS = 100


def _list_data(df: pd.DataFrame, parsed: ParsedQuery) -> dict:
    """Return data as list of records."""
    total = len(df)

    # Sort if requested
    if parsed.sort_by:
        ascending = parsed.sort_order == "asc"
        df = df.sort_values(parsed.sort_by, ascending=ascending)

    # Apply limit
    limit = parsed.top_n or MAX_LIST_ROWS
    truncated = total > limit
    df = df.head(limit)

    # Convert to records
    records = []
    for _, row in df.iterrows():
        record = {}
        for col, val in row.items():
            if pd.isna(val):
                record[col] = None
            elif hasattr(val, "isoformat"):
                record[col] = val.isoformat()
            elif isinstance(val, float):
                record[col] = round(val, 3)
            else:
                record[col] = val
        records.append(record)

    # Scan for candle patterns if OHLC data present
    if records:
        cols = set(records[0].keys())
        if {"open", "high", "low", "close"}.issubset(cols):
            records = scan_patterns(records)

    result = {"rows": records, "total": total}
    if truncated:
        result["truncated"] = True
        result["shown"] = limit

    return result


def _filter_data(df: pd.DataFrame, parsed: ParsedQuery) -> dict:
    """Filter and return matching records."""
    # Condition already applied in _apply_filters
    return _list_data(df, parsed)


def _get_filter_description(parsed: ParsedQuery) -> str:
    """Get human-readable filter description."""
    parts = []
    if parsed.weekday_filter:
        parts.append(f"weekdays: {parsed.weekday_filter}")
    if parsed.event_filter:
        parts.append(f"event: {parsed.event_filter}")
    if parsed.condition:
        parts.append(f"condition: {parsed.condition}")
    if parsed.time:
        parts.append(f"time: {parsed.time.start}-{parsed.time.end}")
    return ", ".join(parts) if parts else "none"
