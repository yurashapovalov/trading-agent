"""Database management"""

import duckdb
from pathlib import Path


def init_database(db_path: str = "data/trading.duckdb") -> None:
    """Initialize database with required tables."""

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect(db_path) as conn:
        # OHLCV table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_1min (
                timestamp TIMESTAMP NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                open DOUBLE NOT NULL,
                high DOUBLE NOT NULL,
                low DOUBLE NOT NULL,
                close DOUBLE NOT NULL,
                volume INTEGER NOT NULL,
                PRIMARY KEY (timestamp, symbol)
            )
        """)

        # Symbols reference table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                symbol VARCHAR(10) PRIMARY KEY,
                name VARCHAR(100),
                tick_size DOUBLE,
                tick_value DOUBLE,
                exchange VARCHAR(20),
                trading_hours VARCHAR(50)
            )
        """)

        # Create index for fast queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time
            ON ohlcv_1min(symbol, timestamp)
        """)


def get_connection(db_path: str = "data/trading.duckdb", read_only: bool = False):
    """Get database connection."""
    return duckdb.connect(db_path, read_only=read_only)
