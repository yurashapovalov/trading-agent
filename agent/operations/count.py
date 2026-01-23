"""Count — count matching records."""

import pandas as pd


def op_count(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Count records matching filter.

    Returns count and basic stats.
    """
    count = len(df)

    summary = {"count": count}

    # Add basic stats if we have the metric
    col = _what_to_column(what)
    if col in df.columns and count > 0:
        values = df[col].dropna()
        if len(values) > 0:
            summary["avg"] = round(values.mean(), 3)
            summary["min"] = round(values.min(), 3)
            summary["max"] = round(values.max(), 3)

    return {
        "rows": [],
        "summary": summary,
    }


def _what_to_column(what: str) -> str:
    """Map atom.what to DataFrame column."""
    if what == "volatility":
        return "range"
    return what
