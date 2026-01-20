"""Detect patterns: after X happened, what was Y."""

import pandas as pd


def op_sequence(df: pd.DataFrame, params: dict) -> dict:
    """
    Find days where previous day was X and current day is Y.

    params:
        prev: condition for previous day (expression)
        curr: condition for current day (expression)

    Example:
        params = {
            "prev": "change_pct > 1",
            "curr": "change_pct < -2"
        }
        → "Days when fell >2% after rising >1% the day before"

    Returns:
        {
            "count": N,
            "rows": [...],
            "probability": X%
        }
    """
    if df.empty:
        return {"error": "No data"}

    prev_cond = params.get("prev")
    curr_cond = params.get("curr")

    if not prev_cond or not curr_cond:
        return {"error": "'prev' and 'curr' conditions required"}

    df = df.copy()

    # Evaluate previous day condition
    try:
        prev_mask = df.eval(prev_cond)
    except Exception as e:
        return {"error": f"Invalid prev condition: {e}"}

    # Shift to align with current day
    prev_matches = prev_mask.shift(1)
    prev_matches = prev_matches.fillna(False).infer_objects(copy=False)

    # Evaluate current day condition
    try:
        curr_mask = df.eval(curr_cond)
    except Exception as e:
        return {"error": f"Invalid curr condition: {e}"}

    # Days where both conditions match
    matches = df[prev_matches & curr_mask]

    # Count days where prev condition was true (for probability)
    prev_true_count = prev_matches.sum()

    result = {
        "count": len(matches),
        "prev_count": int(prev_true_count),
    }

    if prev_true_count > 0:
        result["probability"] = round(len(matches) / prev_true_count * 100, 1)

    # Return sample of matching rows
    if len(matches) > 0:
        sample = matches.head(10)
        records = []
        date_col = "date" if "date" in df.columns else "timestamp"
        for _, row in sample.iterrows():
            records.append({
                "date": str(row[date_col]),
                "change_pct": round(row["change_pct"], 2) if "change_pct" in row else None,
                "prev_change": round(row["prev_change"], 2) if "prev_change" in row else None,
            })
        result["sample"] = records

    return result
