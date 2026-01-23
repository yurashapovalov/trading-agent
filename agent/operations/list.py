"""List — top N records sorted by metric."""

import logging

import pandas as pd

from agent.rules import get_column

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

    n = params.get("n", 10)
    sort = params.get("sort", "desc")
    ascending = sort == "asc"

    col = get_column(what)
    if col not in df.columns:
        logger.warning(f"op_list: column {col} not found")
        return {"rows": [], "summary": {"error": f"Column {col} not found"}}

    # Sort and limit
    df_sorted = df.sort_values(col, ascending=ascending).head(n)

    # Build rows
    rows = _df_to_rows(df_sorted)

    return {
        "rows": rows,
        "summary": {
            "count": len(rows),
            "total": len(df),
            "by": col,
            "sort": sort,
        }
    }


def _df_to_rows(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to list of dicts."""
    rows = []
    for _, row in df.iterrows():
        record = {}
        for col, val in row.items():
            if pd.isna(val):
                continue
            elif hasattr(val, "isoformat"):
                record[col] = val.isoformat()
            elif isinstance(val, float):
                record[col] = round(val, 3)
            elif hasattr(val, "item"):
                record[col] = val.item()
            else:
                record[col] = val
        rows.append(record)
    return rows
