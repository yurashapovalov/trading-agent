"""
Calendar Filter Builder — фильтрация по календарным периодам.

Поддерживает:
- specific_dates: конкретные даты ["2005-05-16", "2003-04-12"]
- years: конкретные годы [2020, 2022, 2024]
- months: месяцы (1-12) [1, 6] для января и июня
- weekdays: дни недели ["Monday", "Friday"]

Все фильтры комбинируются через AND.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import Filters


def build_calendar_filters_sql(
    filters: "Filters",
    date_col: str = "timestamp::date"
) -> str:
    """
    Строит SQL условия для календарных фильтров.

    Args:
        filters: Объект Filters с календарными фильтрами
        date_col: Имя колонки с датой.
                  Для minutes: "timestamp::date"
                  Для daily: "date"

    Returns:
        SQL выражение (без AND в начале) или пустую строку

    Examples:
        >>> filters = Filters(..., years=[2020, 2024], weekdays=["Friday"])
        >>> build_calendar_filters_sql(filters, "date")
        "YEAR(date) IN (2020, 2024) AND DAYNAME(date) IN ('Friday')"
    """
    parts = []

    # specific_dates: конкретные даты
    if filters.specific_dates:
        dates_str = ", ".join(f"'{d}'" for d in filters.specific_dates)
        parts.append(f"{date_col} IN ({dates_str})")

    # years: конкретные годы
    if filters.years:
        years_str = ", ".join(str(y) for y in filters.years)
        parts.append(f"YEAR({date_col}) IN ({years_str})")

    # months: конкретные месяцы (1-12)
    if filters.months:
        months_str = ", ".join(str(m) for m in filters.months)
        parts.append(f"MONTH({date_col}) IN ({months_str})")

    # weekdays: дни недели (Monday, Tuesday, ...)
    if filters.weekdays:
        days_str = ", ".join(f"'{d}'" for d in filters.weekdays)
        parts.append(f"DAYNAME({date_col}) IN ({days_str})")

    return " AND ".join(parts) if parts else ""
