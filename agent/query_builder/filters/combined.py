"""
Combined Filter Builder — объединение всех фильтров.

Комбинирует:
- Time filters (сессии, кастомное время)
- Calendar filters (годы, месяцы, дни недели, даты)
- Holiday filters (исключение праздников)

Возвращает готовое SQL выражение для WHERE или AND clause.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import Filters

from .time import build_time_filter_sql
from .calendar import build_calendar_filters_sql
from .holiday import build_holiday_filter_sql


def build_all_filters_sql(
    filters: "Filters",
    date_col: str = "timestamp::date",
    prefix_and: bool = True,
    symbol: str = "NQ"
) -> str:
    """
    Строит все дополнительные фильтры (время + календарь + праздники).

    Args:
        filters: Объект Filters со всеми фильтрами
        date_col: Имя колонки с датой для календарных фильтров
        prefix_and: Добавлять "AND " в начало результата
        symbol: Instrument symbol for session time lookup and holidays

    Returns:
        SQL выражение с "AND " в начале (если prefix_and=True),
        или пустую строку если фильтров нет

    Example:
        >>> filters = Filters(..., session="RTH", weekdays=["Tuesday"])
        >>> build_all_filters_sql(filters, symbol="NQ")
        "AND timestamp::time BETWEEN '09:30:00' AND '17:00:00' AND DAYNAME(timestamp::date) IN ('Tuesday')"

        >>> filters = Filters(..., exclude_holidays=True)
        >>> build_all_filters_sql(filters, symbol="NQ")
        "AND date NOT IN ('2024-12-25', '2025-01-01', ...)"
    """
    parts = []

    # Время суток (сессии, кастомное время)
    time_filter = build_time_filter_sql(filters, symbol)
    if time_filter:
        parts.append(time_filter)

    # Календарные фильтры (годы, месяцы, дни недели, даты)
    calendar_filter = build_calendar_filters_sql(filters, date_col)
    if calendar_filter:
        parts.append(calendar_filter)

    # Праздники (исключение closed и early close дней)
    # Используем "date" колонку для daily sources, date_col для minutes
    holiday_date_col = "date" if date_col == "timestamp::date" else date_col
    holiday_filter = build_holiday_filter_sql(symbol, filters, holiday_date_col)
    if holiday_filter:
        parts.append(holiday_filter)

    if not parts:
        return ""

    result = " AND ".join(parts)
    return f"AND {result}" if prefix_and else result
