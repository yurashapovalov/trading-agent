"""Correlation — correlation between two metrics."""

import logging

import pandas as pd

from agent.rules import get_column

logger = logging.getLogger(__name__)


def op_correlation(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Calculate correlation between two metrics.

    Expects two atoms with different 'what' values.
    Or params.metrics = ["gap", "change"]

    params:
        metrics: list of two metrics to correlate
    """
    logger.debug(f"op_correlation: what={what}, params={params}, rows={len(df)}")

    if df.empty:
        logger.warning("op_correlation: empty dataframe")
        return {"rows": [], "summary": {"error": "No data"}}

    metrics = params.get("metrics", [])

    # If no explicit metrics, try to infer from what
    if len(metrics) < 2:
        # Default: correlate what with change
        col1 = get_column(what)
        col2 = "change" if what != "change" else "gap"
        metrics = [col1, col2]
    else:
        metrics = [get_column(m) for m in metrics]

    col1, col2 = metrics[0], metrics[1]

    if col1 not in df.columns:
        return {"rows": [], "summary": {"error": f"Column {col1} not found"}}
    if col2 not in df.columns:
        return {"rows": [], "summary": {"error": f"Column {col2} not found"}}

    # Calculate correlation
    valid = df[[col1, col2]].dropna()
    if len(valid) < 3:
        return {"rows": [], "summary": {"error": "Not enough data for correlation"}}

    corr = valid[col1].corr(valid[col2])

    # Interpretation
    if abs(corr) < 0.2:
        strength = "none"
    elif abs(corr) < 0.4:
        strength = "weak"
    elif abs(corr) < 0.6:
        strength = "moderate"
    elif abs(corr) < 0.8:
        strength = "strong"
    else:
        strength = "very strong"

    direction = "positive" if corr > 0 else "negative"

    summary = {
        "correlation": round(corr, 3),
        "strength": strength,
        "direction": direction,
        "metric1": col1,
        "metric2": col2,
        "n": len(valid),
    }

    return {"rows": [], "summary": summary}
