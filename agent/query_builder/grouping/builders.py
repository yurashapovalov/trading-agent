"""
Grouping Builders — функции для генерации GROUP BY логики.

Каждый тип группировки (Grouping enum) требует:
1. SELECT колонку — что показывать в результате
2. GROUP BY выражение — как группировать
3. ORDER BY выражение — как сортировать (обычно совпадает с GROUP BY)
"""

from __future__ import annotations

from agent.query_builder.types import Grouping
from agent.market.instruments import get_session_times, list_sessions


def _build_session_case(symbol: str) -> str:
    """Build dynamic CASE expression for session classification.

    Uses session times from instruments.py (single source of truth).
    """
    sessions = list_sessions(symbol)
    if not sessions:
        # Fallback if no instrument config
        return """CASE
        WHEN time BETWEEN '09:30:00' AND '17:00:00' THEN 'RTH'
        ELSE 'ETH'
    END as session"""

    # Build CASE with actual session times
    # Priority: RTH first (most specific), then others
    cases = []

    # RTH is the main session
    rth_times = get_session_times(symbol, "RTH")
    if rth_times:
        start, end = rth_times
        start = start if len(start.split(":")) == 3 else f"{start}:00"
        end = end if len(end.split(":")) == 3 else f"{end}:00"
        cases.append(f"WHEN time BETWEEN '{start}' AND '{end}' THEN 'RTH'")

    # Default to ETH for everything else
    cases.append("ELSE 'ETH'")

    case_body = "\n        ".join(cases)
    return f"""CASE
        {case_body}
    END as session"""


def get_grouping_column(grouping: Grouping, symbol: str = "NQ") -> str:
    """
    Возвращает SELECT колонку для группировки.

    Args:
        grouping: Тип группировки
        symbol: Инструмент (для SESSION — берёт времена из instruments.py)

    Returns:
        SQL выражение для SELECT или пустую строку
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
        return _build_session_case(symbol)

    elif grouping.is_time_based():
        # Группировка по времени суток (5min, 15min, hour, etc.)
        interval = grouping.get_interval()
        return f"TIME_BUCKET(INTERVAL '{interval}', timestamp)::time as time_bucket"

    # Явная ошибка для неизвестных значений
    raise ValueError(f"Unknown grouping type: {grouping}")


def get_grouping_expression(grouping: Grouping, symbol: str = "NQ") -> str:
    """
    Возвращает выражение для GROUP BY.

    Args:
        grouping: Тип группировки
        symbol: Инструмент (для консистентности API, не используется)

    Returns:
        SQL выражение для GROUP BY или пустую строку
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
        # Cast to time to group by time-of-day across all days
        # Without ::time, it groups by full timestamp (each day separately)
        interval = grouping.get_interval()
        return f"TIME_BUCKET(INTERVAL '{interval}', timestamp)::time"

    # Явная ошибка для неизвестных значений
    # (NONE и TOTAL обрабатываются в builder.py до вызова этой функции)
    raise ValueError(f"Unknown grouping type: {grouping}")
