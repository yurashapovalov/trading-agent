"""Seasonality analysis (best/worst month, quarter, etc.)."""

import pandas as pd


def op_seasonality(df: pd.DataFrame, params: dict) -> dict:
    """
    Analyze seasonality patterns.

    params:
        group_by: month, quarter, week_of_year
        metric: field to analyze
        agg: aggregation (mean, sum, median)

    Example:
        params = {
            "group_by": "month",
            "metric": "change_pct",
            "agg": "mean"
        }
        → "Which month has the best average returns"

    Returns:
        {
            "data": {month: value, ...},
            "best": month,
            "worst": month,
            "best_value": X,
            "worst_value": X
        }
    """
    if df.empty:
        return {"error": "No data"}

    group_by = params.get("group_by", "month")
    metric = params.get("metric", "change_pct")
    agg = params.get("agg", "mean")

    if metric not in df.columns:
        return {"error": f"Column {metric} not found"}

    # Handle different groupings
    if group_by == "month":
        if "month" not in df.columns:
            return {"error": "month column not found, run enrich()"}
        grouped = df.groupby("month")[metric].agg(agg)
        labels = {
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
            5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
            9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
        }
    elif group_by == "quarter":
        if "quarter" not in df.columns:
            return {"error": "quarter column not found, run enrich()"}
        grouped = df.groupby("quarter")[metric].agg(agg)
        labels = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    elif group_by == "weekday":
        if "weekday" not in df.columns:
            return {"error": "weekday column not found, run enrich()"}
        grouped = df.groupby("weekday")[metric].agg(agg)
        labels = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
    elif group_by == "week_of_year":
        date_col = "date" if "date" in df.columns else "timestamp"
        df = df.copy()
        df["_week"] = pd.to_datetime(df[date_col]).dt.isocalendar().week
        grouped = df.groupby("_week")[metric].agg(agg)
        labels = {}
    else:
        return {"error": f"Unknown group_by: {group_by}"}

    if grouped.empty:
        return {"error": "No data for grouping"}

    # Round values
    data = {k: round(v, 3) if pd.notna(v) else None for k, v in grouped.items()}

    best = grouped.idxmax()
    worst = grouped.idxmin()

    result = {
        "data": data,
        "best": best,
        "worst": worst,
        "best_value": data.get(best),
        "worst_value": data.get(worst),
    }

    # Add labels if available
    if labels:
        result["labels"] = {k: labels.get(k, str(k)) for k in data.keys()}
        result["best_label"] = labels.get(best, str(best))
        result["worst_label"] = labels.get(worst, str(worst))

    return result
