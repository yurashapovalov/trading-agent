"""Distribution — distribution of metric values."""

import pandas as pd
import numpy as np


def op_distribution(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Analyze distribution of metric values.

    params:
        bins: number of bins (default: 10)
        percentiles: list of percentiles to calculate
    """
    if df.empty:
        return {"rows": [], "summary": {"error": "No data"}}

    col = _what_to_column(what)
    if col not in df.columns:
        return {"rows": [], "summary": {"error": f"Column {col} not found"}}

    values = df[col].dropna()
    if len(values) == 0:
        return {"rows": [], "summary": {"error": "No valid values"}}

    bins = params.get("bins", 10)

    # Calculate histogram
    counts, edges = np.histogram(values, bins=bins)

    # Build rows
    rows = []
    for i in range(len(counts)):
        rows.append({
            "range": f"{edges[i]:.1f} to {edges[i+1]:.1f}",
            "from": round(edges[i], 2),
            "to": round(edges[i+1], 2),
            "count": int(counts[i]),
            "pct": round(counts[i] / len(values) * 100, 1),
        })

    # Percentiles
    percentiles = params.get("percentiles", [5, 25, 50, 75, 95])
    pct_values = {}
    for p in percentiles:
        pct_values[f"p{p}"] = round(np.percentile(values, p), 3)

    summary = {
        "count": len(values),
        "mean": round(values.mean(), 3),
        "std": round(values.std(), 3),
        "min": round(values.min(), 3),
        "max": round(values.max(), 3),
        "metric": col,
        **pct_values,
    }

    return {"rows": rows, "summary": summary}


def _what_to_column(what: str) -> str:
    """Map atom.what to DataFrame column."""
    if what == "volatility":
        return "range"
    return what
