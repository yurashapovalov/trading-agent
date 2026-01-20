"""Distribution of events by time (when does high/low form)."""

import pandas as pd


def op_distribution(df: pd.DataFrame, params: dict) -> dict:
    """
    Analyze when an event occurs (distribution by time).

    params:
        event: what to find
            - "high" / "daily_high": when daily high is formed
            - "low" / "daily_low": when daily low is formed
        group_by: how to group (hour, minute, etc.)
        hours_filter: optional (start, end) to limit analysis

    Example:
        params = {
            "event": "daily_high",
            "group_by": "hour",
            "hours_filter": [6, 16]
        }
        → "At what hour does the daily high usually form (6am-4pm)"

    Note: Requires minute data, not daily bars.

    Returns:
        {
            "distribution": {hour: percentage, ...},
            "peak": hour with highest %,
            "peak_pct": percentage at peak
        }
    """
    if df.empty:
        return {"error": "No data"}

    event = params.get("event")
    group_by = params.get("group_by", "hour")
    hours_filter = params.get("hours_filter")

    if not event:
        return {"error": "'event' required"}

    # Check for timestamp column (minute data)
    if "timestamp" not in df.columns:
        return {"error": "Requires minute data (timestamp column)"}

    df = df.copy()

    # Apply hours filter if specified
    if hours_filter:
        start_hour, end_hour = hours_filter
        df = df[
            (df["timestamp"].dt.hour >= start_hour) &
            (df["timestamp"].dt.hour < end_hour)
        ]

    if df.empty:
        return {"error": "No data after hours filter"}

    # Add date column for daily grouping
    df["_date"] = df["timestamp"].dt.date

    # Find event rows
    if event in ("high", "daily_high"):
        # For each day, find when high was formed
        daily_max = df.groupby("_date")["high"].transform("max")
        df["_is_event"] = df["high"] == daily_max
    elif event in ("low", "daily_low"):
        daily_min = df.groupby("_date")["low"].transform("min")
        df["_is_event"] = df["low"] == daily_min
    else:
        return {"error": f"Unknown event: {event}"}

    event_rows = df[df["_is_event"]]

    if event_rows.empty:
        return {"error": "No events found"}

    # Group by requested field
    if group_by == "hour":
        event_rows = event_rows.copy()
        event_rows["_group"] = event_rows["timestamp"].dt.hour
    elif group_by == "minute":
        event_rows = event_rows.copy()
        event_rows["_group"] = event_rows["timestamp"].dt.minute
    else:
        return {"error": f"Unknown group_by: {group_by}"}

    # Calculate distribution
    dist = event_rows.groupby("_group").size()
    dist_pct = (dist / dist.sum() * 100).round(1)

    distribution = dist_pct.to_dict()

    result = {
        "distribution": distribution,
        "total_events": len(event_rows),
        "total_days": df["_date"].nunique(),
    }

    if distribution:
        peak = max(distribution, key=distribution.get)
        result["peak"] = peak
        result["peak_pct"] = distribution[peak]

    return result
