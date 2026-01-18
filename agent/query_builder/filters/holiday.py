"""
Holiday Filter Builder — фильтрация по праздникам.

Поддерживает три режима:
- INCLUDE: включить праздники в выборку (по умолчанию)
- EXCLUDE: исключить праздники из выборки
- ONLY: показать ТОЛЬКО праздничные дни

Праздники определяются динамически для каждого года на основе правил
из agent/query_builder/holidays.py.

Usage:
    from agent.query_builder.filters.holiday import build_holiday_filter_sql

    # Исключить праздники
    sql = build_holiday_filter_sql("NQ", filters)
    # → "date NOT IN ('2024-12-25', '2024-12-24', ...)"

    # Только укороченные дни
    sql = build_holiday_filter_sql("NQ", filters)  # early_close_days=ONLY
    # → "date IN ('2024-12-24', '2024-11-29', ...)"
"""

from __future__ import annotations
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import Filters

from agent.query_builder.types import HolidayFilter
from agent.market.holidays import get_holidays_for_year


def build_holiday_filter_sql(
    symbol: str,
    filters: "Filters",
    date_column: str = "date"
) -> str:
    """
    Строит SQL условие для фильтрации праздников.

    Args:
        symbol: Торговый инструмент (NQ, ES, CL)
        filters: Объект Filters с market_holidays / early_close_days
        date_column: Название колонки с датой (default: "date")

    Returns:
        SQL выражение (без AND в начале) или пустую строку

    Examples:
        >>> filters = Filters(..., market_holidays=HolidayFilter.EXCLUDE)
        >>> build_holiday_filter_sql("NQ", filters)
        "date NOT IN ('2024-01-01', '2024-12-25', ...)"

        >>> filters = Filters(..., early_close_days=HolidayFilter.ONLY)
        >>> build_holiday_filter_sql("NQ", filters)
        "date IN ('2024-12-24', '2024-11-29', ...)"
    """
    # Собираем даты для каждого режима
    exclude_dates: list[date] = []
    only_dates: list[date] = []

    # Извлекаем годы из периода
    years = _get_years_in_range(filters.period_start, filters.period_end)
    if not years:
        return ""

    for year in years:
        holidays = get_holidays_for_year(symbol, year)

        # Market holidays (full close)
        if filters.market_holidays == HolidayFilter.EXCLUDE:
            exclude_dates.extend(holidays.get("full_close", []))
        elif filters.market_holidays == HolidayFilter.ONLY:
            only_dates.extend(holidays.get("full_close", []))

        # Early close days
        if filters.early_close_days == HolidayFilter.EXCLUDE:
            exclude_dates.extend(holidays.get("early_close", []))
        elif filters.early_close_days == HolidayFilter.ONLY:
            only_dates.extend(holidays.get("early_close", []))

    # Приоритет: ONLY важнее EXCLUDE
    # Если есть ONLY — возвращаем IN, иначе NOT IN
    if only_dates:
        unique_dates = sorted(set(only_dates))
        formatted_dates = ", ".join(f"'{d.isoformat()}'" for d in unique_dates)
        return f"{date_column} IN ({formatted_dates})"

    if exclude_dates:
        unique_dates = sorted(set(exclude_dates))
        formatted_dates = ", ".join(f"'{d.isoformat()}'" for d in unique_dates)
        return f"{date_column} NOT IN ({formatted_dates})"

    return ""


def _get_years_in_range(period_start: str, period_end: str) -> list[int]:
    """
    Извлекает список годов из диапазона дат.

    Args:
        period_start: Начало периода (YYYY-MM-DD или "all")
        period_end: Конец периода (YYYY-MM-DD или "all")

    Returns:
        Список годов [2020, 2021, 2022, ...]
    """
    # Обработка "all" — используем разумный диапазон
    if period_start == "all" or not period_start:
        start_year = 2008  # Начало данных
    else:
        try:
            start_year = int(period_start[:4])
        except (ValueError, IndexError):
            start_year = 2008

    if period_end == "all" or not period_end:
        end_year = date.today().year + 1
    else:
        try:
            end_year = int(period_end[:4])
        except (ValueError, IndexError):
            end_year = date.today().year + 1

    # Генерируем список годов
    return list(range(start_year, end_year + 1))


def get_holiday_dates_for_period(
    symbol: str,
    period_start: str,
    period_end: str,
    include_holidays: bool = True,
    include_early_close: bool = True
) -> list[date]:
    """
    Возвращает список дат праздников для периода.

    Полезно для отладки и тестирования.

    Args:
        symbol: Торговый инструмент
        period_start: Начало периода
        period_end: Конец периода
        include_holidays: Включить дни полного закрытия
        include_early_close: Включить дни раннего закрытия

    Returns:
        Отсортированный список дат
    """
    years = _get_years_in_range(period_start, period_end)
    dates: list[date] = []

    for year in years:
        holidays = get_holidays_for_year(symbol, year)

        if include_holidays:
            dates.extend(holidays.get("full_close", []))

        if include_early_close:
            dates.extend(holidays.get("early_close", []))

    return sorted(set(dates))
