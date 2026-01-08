"""SQL query tool for OHLCV data"""

import duckdb
import pandas as pd
from typing import Optional


def query_ohlcv(sql: str, db_path: str = None) -> pd.DataFrame:
    """
    Execute SQL query against OHLCV data.

    Available tables:
    - ohlcv_1min: timestamp, symbol, open, high, low, close, volume
    - symbols: symbol, name, tick_size, tick_value

    Args:
        sql: SQL query to execute
        db_path: Path to DuckDB database

    Returns:
        DataFrame with query results

    Example:
        SELECT * FROM ohlcv_1min
        WHERE symbol = 'CL'
        AND timestamp >= '2025-01-01'
        LIMIT 100
    """
    import config
    if db_path is None:
        db_path = config.DATABASE_PATH
    with duckdb.connect(db_path, read_only=True) as conn:
        return conn.execute(sql).df()
