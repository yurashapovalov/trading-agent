"""Checkpointer configuration for LangGraph persistence."""

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

    - Development: MemorySaver (simple, in-memory)
    - Production: PostgreSQL (Supabase)

    Returns:
        Checkpointer instance
    """
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production" and os.getenv("DATABASE_URL"):
        return get_postgres_checkpointer()
    else:
        # Use MemorySaver for development (simpler than SQLite context manager)
        return get_memory_checkpointer()


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
