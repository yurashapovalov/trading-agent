"""
Grouping Builders — функции для генерации GROUP BY логики.

Каждый тип группировки (Grouping enum) требует:
1. SELECT колонку — что показывать в результате
2. GROUP BY выражение — как группировать
3. ORDER BY выражение — как сортировать (обычно совпадает с GROUP BY)
"""

from __future__ import annotations

from agent.query_builder.types import Grouping


def get_grouping_column(grouping: Grouping) -> str:
    """
    Возвращает SELECT колонку для группировки.

    Args:
        grouping: Тип группировки

    Returns:
        SQL выражение для SELECT или пустую строку

    Examples:
        >>> get_grouping_column(Grouping.YEAR)
        "YEAR(date) as year"

        >>> get_grouping_column(Grouping.WEEKDAY)
        "DAYNAME(date) as weekday, DAYOFWEEK(date) as day_num"
    """
    if grouping == Grouping.NONE:
        return "date"

    elif grouping == Grouping.TOTAL:
        # Нет группирующей колонки — агрегация всего периода
        return ""

    elif grouping == Grouping.DAY:
        return "date"

    elif grouping == Grouping.WEEK:
        return "STRFTIME(date, '%Y-W%W') as week"

    elif grouping == Grouping.MONTH:
        return "STRFTIME(date, '%Y-%m') as month"

    elif grouping == Grouping.QUARTER:
        return "CONCAT(YEAR(date), '-Q', QUARTER(date)) as quarter"

    elif grouping == Grouping.YEAR:
        return "YEAR(date) as year"

    elif grouping == Grouping.WEEKDAY:
        # Две колонки: название для отображения, номер для сортировки
        return "DAYNAME(date) as weekday, DAYOFWEEK(date) as day_num"

    elif grouping == Grouping.SESSION:
        return """CASE
        WHEN time BETWEEN '09:30:00' AND '16:00:00' THEN 'RTH'
        ELSE 'ETH'
    END as session"""

    elif grouping.is_time_based():
        # Группировка по времени суток (5min, 15min, hour, etc.)
        interval = grouping.get_interval()
        return f"TIME_BUCKET(INTERVAL '{interval}', timestamp)::time as time_bucket"

    # Явная ошибка для неизвестных значений
    raise ValueError(f"Unknown grouping type: {grouping}")


def get_grouping_expression(grouping: Grouping) -> str:
    """
    Возвращает выражение для GROUP BY.

    Args:
        grouping: Тип группировки

    Returns:
        SQL выражение для GROUP BY или пустую строку

    Note:
        GROUP BY выражение может отличаться от SELECT колонки.
        Например, для WEEKDAY в SELECT два поля, но GROUP BY по обоим.
    """
    if grouping == Grouping.DAY:
        return "date"

    elif grouping == Grouping.WEEK:
        return "STRFTIME(date, '%Y-W%W')"

    elif grouping == Grouping.MONTH:
        return "STRFTIME(date, '%Y-%m')"

    elif grouping == Grouping.QUARTER:
        # GROUP BY по году и кварталу отдельно
        return "YEAR(date), QUARTER(date)"

    elif grouping == Grouping.YEAR:
        return "YEAR(date)"

    elif grouping == Grouping.WEEKDAY:
        # Сортировка по номеру дня, группировка по обоим
        return "DAYOFWEEK(date), DAYNAME(date)"

    elif grouping == Grouping.SESSION:
        return "session"

    elif grouping.is_time_based():
        interval = grouping.get_interval()
        return f"TIME_BUCKET(INTERVAL '{interval}', timestamp)"

    # Явная ошибка для неизвестных значений
    # (NONE и TOTAL обрабатываются в builder.py до вызова этой функции)
    raise ValueError(f"Unknown grouping type: {grouping}")
