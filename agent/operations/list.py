"""List — top N records sorted by metric."""

import logging

import pandas as pd

from agent.rules import get_column
from agent.operations._utils import df_to_rows

logger = logging.getLogger(__name__)


def op_list(df: pd.DataFrame, what: str, params: dict) -> dict:
    """
    Return top N records sorted by metric.

    params:
        n: number of records (default: 10)
        sort: "asc" or "desc" (default: "desc")
    """
    logger.debug(f"op_list: what={what}, params={params}, rows={len(df)}")

    if df.empty:
        logger.warning("op_list: empty dataframe")
        return {"rows": [], "summary": {"count": 0}}

    n = params.get("n")  # None = all records
    sort = params.get("sort", "desc")
    ascending = sort == "asc"

    col = get_column(what)
    if col not in df.columns:
        logger.warning(f"op_list: column {col} not found")
        return {"rows": [], "summary": {"error": f"Column {col} not found"}}

    # Sort and optionally limit
    df_sorted = df.sort_values(col, ascending=ascending)
    if n is not None:
        df_sorted = df_sorted.head(n)

    return {
        "rows": df_to_rows(df_sorted),
        "summary": {
            "count": len(df_sorted),
            "total": len(df),
            "by": col,
            "sort": sort,
        }
    }
