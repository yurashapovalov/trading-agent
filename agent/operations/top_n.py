"""Top N records with optional aggregation."""

import pandas as pd


def op_top_n(df: pd.DataFrame, params: dict) -> dict:
    """
    Get top N records by a field, optionally aggregate another metric.

    params:
        n: number of records (default: 5)
        by: field to sort by
        ascending: sort direction (default: False = largest first)
        then: optional aggregation on the top N
            {"metric": "change_pct", "agg": "mean"}

    Example:
        params = {
            "n": 5,
            "by": "volume",
            "then": {"metric": "change_pct", "agg": "mean"}
        }
        → "Top 5 days by volume, average change_pct for them"

    Returns:
        {
            "rows": [...],
            "agg_result": X  # if 'then' specified
        }
    """
    if df.empty:
        return {"error": "No data"}

    n = params.get("n", 5)
    by = params.get("by", "range")  # default: top by volatility
    ascending = params.get("ascending", False)
    then = params.get("then")

    if by not in df.columns:
        return {"error": f"Column {by} not found"}

    # Get top N
    if ascending:
        top = df.nsmallest(n, by)
    else:
        top = df.nlargest(n, by)

    # Convert to records, handling date columns
    records = []
    for _, row in top.iterrows():
        record = {}
        for col, val in row.items():
            if pd.isna(val):
                record[col] = None
            elif hasattr(val, "isoformat"):
                record[col] = val.isoformat()
            elif isinstance(val, (int, float)):
                record[col] = round(val, 3) if isinstance(val, float) else val
            else:
                record[col] = val
        records.append(record)

    result = {"rows": records}

    # Optional aggregation on top N
    if then:
        metric = then.get("metric")
        agg = then.get("agg", "mean")

        if metric and metric in top.columns:
            agg_value = top[metric].agg(agg)
            result["agg_result"] = round(agg_value, 3) if pd.notna(agg_value) else None
            result["agg_label"] = f"{agg}_{metric}"

    return result
