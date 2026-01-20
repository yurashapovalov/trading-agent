"""Correlation between fields."""

import pandas as pd


def op_correlation(df: pd.DataFrame, params: dict) -> dict:
    """
    Calculate correlation between two fields.

    params:
        field1: first field
        field2: second field
        method: correlation method (pearson, spearman, kendall)

    Example:
        params = {
            "field1": "volume",
            "field2": "change_pct"
        }
        → "Correlation between volume and price change"

    Returns:
        {
            "correlation": X,
            "interpretation": "strong positive" / "weak negative" / etc.
        }
    """
    if df.empty:
        return {"error": "No data"}

    field1 = params.get("field1")
    field2 = params.get("field2")
    method = params.get("method", "pearson")

    if not field1 or not field2:
        return {"error": "'field1' and 'field2' required"}

    if field1 not in df.columns:
        return {"error": f"Column {field1} not found"}

    if field2 not in df.columns:
        return {"error": f"Column {field2} not found"}

    # Calculate correlation
    corr = df[field1].corr(df[field2], method=method)

    if pd.isna(corr):
        return {"error": "Could not calculate correlation (insufficient data)"}

    corr = round(corr, 3)

    # Interpret
    abs_corr = abs(corr)
    if abs_corr >= 0.7:
        strength = "strong"
    elif abs_corr >= 0.4:
        strength = "moderate"
    elif abs_corr >= 0.2:
        strength = "weak"
    else:
        strength = "very weak"

    direction = "positive" if corr > 0 else "negative" if corr < 0 else "no"

    if abs_corr < 0.1:
        interpretation = "no correlation"
    else:
        interpretation = f"{strength} {direction}"

    return {
        "correlation": corr,
        "interpretation": interpretation,
        "n": len(df[[field1, field2]].dropna()),
    }
