"""Count — count matching records."""

import logging

import pandas as pd

from agent.rules import get_column

logger = logging.getLogger(__name__)


def op_count(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Count records matching filter.

    Returns count and basic stats.
    """
    logger.debug(f"op_count: what={what}, params={params}, rows={len(df)}")
    count = len(df)

    summary = {"count": count}

    # Add basic stats if we have the metric
    col = get_column(what)
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
