"""Data loading utilities"""

import duckdb
import pandas as pd
from pathlib import Path
from typing import Optional

from .database import init_database, get_connection


def load_csv(
    file_path: str,
    symbol: str,
    db_path: str = "data/trading.duckdb",
    replace: bool = False
) -> int:
    """
    Load CSV file into database.

    Args:
        file_path: Path to CSV file
        symbol: Symbol name (e.g. 'CL')
        db_path: Path to database
        replace: If True, replace existing data for this symbol

    Returns:
        Number of rows loaded

    Expected CSV format:
        timestamp,open,high,low,close,volume
        2025-11-30 18:00:00,58.96,59.3,58.83,59.21,2181
    """
    # Initialize database if needed
    init_database(db_path)

    # Read CSV
    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['symbol'] = symbol

    # Reorder columns
    df = df[['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']]

    with get_connection(db_path) as conn:
        if replace:
            conn.execute(
                "DELETE FROM ohlcv_1min WHERE symbol = ?",
                [symbol]
            )

        # Insert data
        conn.execute("""
            INSERT OR REPLACE INTO ohlcv_1min
            SELECT * FROM df
        """)

        # Get count
        result = conn.execute(
            "SELECT COUNT(*) FROM ohlcv_1min WHERE symbol = ?",
            [symbol]
        ).fetchone()

    return result[0]


def get_data_info(db_path: str = "data/trading.duckdb") -> pd.DataFrame:
    """Get summary of loaded data."""

    with get_connection(db_path, read_only=True) as conn:
        return conn.execute("""
            SELECT
                symbol,
                COUNT(*) as bars,
                MIN(timestamp) as start_date,
                MAX(timestamp) as end_date,
                COUNT(DISTINCT DATE(timestamp)) as trading_days
            FROM ohlcv_1min
            GROUP BY symbol
            ORDER BY symbol
        """).df()
