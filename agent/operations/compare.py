"""Compare groups (weekdays, months, sessions, etc.)."""

import pandas as pd


def op_compare(df: pd.DataFrame, params: dict) -> dict:
    """
    Compare metric across groups.

    params:
        group_by: field to group by (weekday, month, hour, etc.)
        metric: field to compare (change_pct, range, volume, etc.)
        agg: aggregation function (mean, median, sum, count, std)
        groups: optional list of specific groups to compare

    Example:
        params = {
            "group_by": "weekday",
            "metric": "range_pct",
            "agg": "mean",
            "groups": [0, 4]  # Monday vs Friday
        }

    Returns:
        {
            "data": {0: 1.23, 4: 1.45},
            "best": 4,
            "worst": 0
        }
    """
    if df.empty:
        return {"error": "No data"}

    group_by = params.get("group_by", "year")  # default: compare by year
    metric = params.get("metric", "change_pct")  # default: compare returns
    agg = params.get("agg", "mean")
    groups = params.get("groups")

    if group_by not in df.columns:
        return {"error": f"Column {group_by} not found"}

    if metric not in df.columns:
        return {"error": f"Column {metric} not found"}

    # Group and aggregate
    grouped = df.groupby(group_by)[metric].agg(agg)

    # Filter to specific groups if requested
    if groups:
        grouped = grouped.loc[grouped.index.isin(groups)]

    if grouped.empty:
        return {"error": "No data for specified groups"}

    # Convert to dict and round
    data = {k: round(v, 3) if pd.notna(v) else None for k, v in grouped.items()}

    result = {
        "data": data,
        "best": grouped.idxmax() if not grouped.empty else None,
        "worst": grouped.idxmin() if not grouped.empty else None,
    }

    # Add readable labels for common groupings
    if group_by == "weekday":
        weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        result["labels"] = {k: weekday_names[k] for k in data.keys() if k < 7}
    elif group_by == "month":
        month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        result["labels"] = {k: month_names[k] for k in data.keys() if 1 <= k <= 12}

    return result
