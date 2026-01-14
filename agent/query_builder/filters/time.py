"""
Time Filter Builder — фильтрация по времени суток.

Поддерживает:
- Торговые сессии (RTH, ETH, PREMARKET, etc.)
- Кастомные временные диапазоны (time_start, time_end)
- Сессии пересекающие полночь (OVERNIGHT, ASIAN, GLOBEX)

Все времена в ET (Eastern Time).
Все значения валидируются для защиты от SQL injection.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import Filters

from agent.query_builder.sql_utils import safe_sql_time


def build_time_filter_sql(filters: "Filters") -> str:
    """
    Строит SQL условие для фильтра по времени суток.

    Все входные данные валидируются для защиты от SQL injection.

    Args:
        filters: Объект Filters с session или time_start/time_end

    Returns:
        SQL выражение (без AND в начале) или пустую строку

    Raises:
        ValidationError: Если входные данные невалидны

    Examples:
        >>> filters = Filters(..., session="RTH")
        >>> build_time_filter_sql(filters)
        "timestamp::time BETWEEN '09:30:00' AND '16:00:00'"

        >>> filters = Filters(..., session="OVERNIGHT")
        >>> build_time_filter_sql(filters)
        "(timestamp::time >= '18:00:00' OR timestamp::time < '09:30:00')"
    """
    # ETH — особый случай (NOT BETWEEN)
    if filters.session == "ETH":
        return "timestamp::time NOT BETWEEN '09:30:00' AND '16:00:00'"

    # Получаем временной диапазон из session или time_start/time_end
    time_filter = filters.get_time_filter()
    if not time_filter:
        return ""

    start_time, end_time = time_filter

    # Валидируем времена (session times из TRADING_SESSIONS уже безопасны,
    # но кастомные time_start/time_end нужно проверить)
    safe_start = safe_sql_time(start_time)
    safe_end = safe_sql_time(end_time)

    # Проверяем пересечение полночи (end < start означает что сессия идёт через полночь)
    if filters.crosses_midnight():
        # Сессия пересекает полночь: 18:00-03:00
        # SQL: (time >= '18:00:00' OR time < '03:00:00')
        return f"(timestamp::time >= {safe_start} OR timestamp::time < {safe_end})"
    else:
        # Обычная сессия в рамках одного дня: 09:30-16:00
        return f"timestamp::time BETWEEN {safe_start} AND {safe_end}"
