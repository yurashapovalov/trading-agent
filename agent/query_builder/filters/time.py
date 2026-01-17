"""
Time Filter Builder — фильтрация по времени суток.

Поддерживает:
- Торговые сессии (RTH, ETH, OVERNIGHT, etc.)
- Кастомные временные диапазоны (time_start, time_end)
- Сессии пересекающие полночь (OVERNIGHT, ASIAN, etc.)

Session times are loaded from instrument config (instruments.py) — Single Source of Truth.
All times in data timezone (ET for NQ/ES).
All values validated for SQL injection protection.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import Filters

from agent.query_builder.sql_utils import safe_sql_time
from agent.query_builder.instruments import get_session_times


def build_time_filter_sql(filters: "Filters", symbol: str = "NQ") -> str:
    """
    Строит SQL условие для фильтра по времени суток.

    Session times are loaded from instrument config based on symbol.

    Args:
        filters: Объект Filters с session или time_start/time_end
        symbol: Instrument symbol (NQ, ES, CL) for session lookup

    Returns:
        SQL выражение (без AND в начале) или пустую строку

    Raises:
        ValidationError: Если входные данные невалидны

    Examples:
        >>> filters = Filters(..., session="RTH")
        >>> build_time_filter_sql(filters, "NQ")
        "timestamp::time BETWEEN '09:30:00' AND '17:00:00'"

        >>> filters = Filters(..., session="OVERNIGHT")
        >>> build_time_filter_sql(filters, "NQ")
        "(timestamp::time >= '18:00:00' OR timestamp::time < '09:30:00')"
    """
    # Get time filter from session or custom time_start/time_end
    if filters.session:
        # Load session times from instrument config
        session_times = get_session_times(symbol, filters.session)
        if not session_times:
            # Fallback: unknown session, return empty
            return ""
        start_time, end_time = session_times
    elif filters.time_start and filters.time_end:
        # Custom time range
        start_time = filters.time_start
        end_time = filters.time_end
    else:
        return ""

    # Normalize to HH:MM:SS format
    start_time = _normalize_time(start_time)
    end_time = _normalize_time(end_time)

    # Validate times for SQL injection protection
    safe_start = safe_sql_time(start_time)
    safe_end = safe_sql_time(end_time)

    # Check if session crosses midnight (end < start)
    if end_time < start_time:
        # Session crosses midnight: 18:00-03:00
        # SQL: (time >= '18:00:00' OR time < '03:00:00')
        return f"(timestamp::time >= {safe_start} OR timestamp::time < {safe_end})"
    else:
        # Regular session within same day: 09:30-17:00
        return f"timestamp::time BETWEEN {safe_start} AND {safe_end}"


def _normalize_time(time_str: str) -> str:
    """Normalize time to HH:MM:SS format."""
    parts = time_str.split(":")
    if len(parts) == 2:
        return f"{parts[0]}:{parts[1]}:00"
    return time_str
