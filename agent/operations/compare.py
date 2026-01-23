"""Compare — compare metric across groups."""

import pandas as pd


def op_compare(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Compare metric across groups.

    Expects two atoms with different filters (e.g., monday vs friday).
    Or uses group parameter from atom.

    params:
        groups: list of group values to compare
        group_by: field to group by (weekday, month, year, quarter)
    """
    if df.empty:
        return {"rows": [], "summary": {"error": "No data"}}

    col = _what_to_column(what)
    if col not in df.columns:
        return {"rows": [], "summary": {"error": f"Column {col} not found"}}

    group_by = params.get("group_by", "weekday")

    if group_by not in df.columns:
        return {"rows": [], "summary": {"error": f"Group column {group_by} not found"}}

    # Group and aggregate
    grouped = df.groupby(group_by)[col].agg(["mean", "count", "std"])

    # Filter specific groups if requested
    groups = params.get("groups")
    if groups:
        grouped = grouped.loc[grouped.index.isin(groups)]

    if grouped.empty:
        return {"rows": [], "summary": {"error": "No groups found"}}

    # Labels for common groupings
    labels = _get_labels(group_by)

    # Build rows
    rows = []
    for idx, row in grouped.iterrows():
        label = labels.get(idx, str(idx))
        rows.append({
            "group": label,
            "avg": round(row["mean"], 3) if pd.notna(row["mean"]) else None,
            "count": int(row["count"]),
            "std": round(row["std"], 3) if pd.notna(row["std"]) else None,
        })

    # Find best/worst
    best_idx = grouped["mean"].idxmax()
    worst_idx = grouped["mean"].idxmin()

    summary = {
        "best": labels.get(best_idx, str(best_idx)),
        "best_avg": round(grouped.loc[best_idx, "mean"], 3),
        "worst": labels.get(worst_idx, str(worst_idx)),
        "worst_avg": round(grouped.loc[worst_idx, "mean"], 3),
        "group_by": group_by,
    }

    return {"rows": rows, "summary": summary}


def _what_to_column(what: str) -> str:
    """Map atom.what to DataFrame column."""
    if what == "volatility":
        return "range"
    return what


def _get_labels(group_by: str) -> dict:
    """Get human-readable labels for group values."""
    if group_by == "weekday":
        return {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    if group_by == "month":
        return {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
    if group_by == "quarter":
        return {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    return {}
