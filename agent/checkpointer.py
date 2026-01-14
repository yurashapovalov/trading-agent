"""LangGraph checkpointer configuration for state persistence.

Provides checkpointer implementations for storing conversation state:
- SQLite: Default, persistent storage in data/checkpoints.db
- PostgreSQL: Production option with Supabase
- Memory: Development/testing only (not persistent)

The checkpointer enables interrupt/resume functionality in LangGraph.
"""

import os
from pathlib import Path
from typing import Optional, Iterator
from contextlib import contextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

import config


def get_memory_checkpointer() -> BaseCheckpointSaver:
    """Get in-memory checkpointer (for development/testing)."""
    return MemorySaver()


@contextmanager
def get_sqlite_checkpointer() -> Iterator[BaseCheckpointSaver]:
    """Get SQLite checkpointer as context manager."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = Path(config.ROOT_DIR) / "data" / "checkpoints.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        yield saver


def get_checkpointer() -> BaseCheckpointSaver:
    """
    Get appropriate checkpointer based on environment.

    Always use SQLite for persistence (required for interrupt/resume).
    MemorySaver doesn't work across requests.

    Returns:
        Checkpointer instance
    """
    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = Path(config.ROOT_DIR) / "data" / "checkpoints.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # SqliteSaver.from_conn_string returns a context manager, but we need
    # a persistent saver. Use direct connection.
    import sqlite3
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


def get_postgres_checkpointer() -> Optional[BaseCheckpointSaver]:
    """
    Get PostgreSQL checkpointer for production.

    Requires DATABASE_URL environment variable with Supabase connection string.
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("WARNING: DATABASE_URL not set, falling back to SQLite")
        return get_sqlite_checkpointer()

    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        saver = PostgresSaver.from_conn_string(database_url)
        saver.setup()  # Create checkpoint tables if not exist
        return saver
    except Exception as e:
        print(f"WARNING: Failed to create Postgres checkpointer: {e}")
        print("Falling back to SQLite")
        return get_sqlite_checkpointer()


async def get_async_postgres_checkpointer() -> Optional[BaseCheckpointSaver]:
    """
    Get async PostgreSQL checkpointer for production.

    Use this in async contexts for better performance.
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("WARNING: DATABASE_URL not set, falling back to SQLite")
        return get_sqlite_checkpointer()

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        return AsyncPostgresSaver.from_conn_string(database_url)
    except Exception as e:
        print(f"WARNING: Failed to create async Postgres checkpointer: {e}")
        return None
