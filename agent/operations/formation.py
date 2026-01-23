"""Formation — when is daily high/low formed (requires minute data)."""

import pandas as pd


def op_formation(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Analyze when daily high/low is typically formed.

    Requires minute data with timestamp column.

    params:
        event: "high" or "low" (default from what)
        group_by: "hour" (default)
    """
    if df.empty:
        return {"rows": [], "summary": {"error": "No data"}}

    # Requires minute data
    if "timestamp" not in df.columns:
        return {"rows": [], "summary": {"error": "Requires minute data (timestamp column)"}}

    event = params.get("event") or what
    if event not in ("high", "low"):
        event = "high"  # Default

    group_by = params.get("group_by", "hour")

    df = df.copy()

    # Add date for daily grouping
    df["_date"] = df["timestamp"].dt.date

    # Find event bars
    if event == "high":
        daily_extreme = df.groupby("_date")["high"].transform("max")
        df["_is_event"] = df["high"] == daily_extreme
    else:  # low
        daily_extreme = df.groupby("_date")["low"].transform("min")
        df["_is_event"] = df["low"] == daily_extreme

    event_rows = df[df["_is_event"]]

    if event_rows.empty:
        return {"rows": [], "summary": {"error": "No events found"}}

    # Group by time
    event_rows = event_rows.copy()
    if group_by == "hour":
        event_rows["_group"] = event_rows["timestamp"].dt.hour
    elif group_by == "30min":
        event_rows["_group"] = event_rows["timestamp"].dt.hour + event_rows["timestamp"].dt.minute // 30 * 0.5
    else:
        event_rows["_group"] = event_rows["timestamp"].dt.hour

    # Calculate distribution
    dist = event_rows.groupby("_group").size()
    dist_pct = (dist / dist.sum() * 100).round(1)

    # Build rows
    rows = []
    for hour, pct in dist_pct.items():
        rows.append({
            "hour": int(hour) if group_by == "hour" else hour,
            "count": int(dist[hour]),
            "pct": float(pct),
        })

    # Sort by hour
    rows.sort(key=lambda x: x["hour"])

    # Find peak
    peak_hour = dist_pct.idxmax() if not dist_pct.empty else None
    peak_pct = float(dist_pct[peak_hour]) if peak_hour is not None else 0

    summary = {
        "event": event,
        "peak_hour": int(peak_hour) if peak_hour is not None else None,
        "peak_pct": peak_pct,
        "total_days": df["_date"].nunique(),
        "group_by": group_by,
    }

    return {"rows": rows, "summary": summary}
