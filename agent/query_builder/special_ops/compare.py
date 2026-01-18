"""
Compare Operation Builder — сравнение метрик между группами.

Отвечает на вопросы:
- "Compare Monday and Friday volatility"
- "RTH vs ETH range"
- "2023 vs 2024 performance"

Типы сравнения:
1. Weekday — GROUP BY DAYNAME(date)
2. Session — отдельные CTE для каждой сессии
3. Year — GROUP BY YEAR(date)
4. Month — GROUP BY MONTHNAME(date)
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import QuerySpec

from agent.query_builder.types import SpecialOp
from agent.query_builder.source.common import OHLCV_TABLE, build_trading_day_timestamp_filter
from agent.query_builder.sql_utils import safe_sql_symbol
from agent.market.instruments import get_session_times
from .base import SpecialOpBuilder, SpecialOpRegistry


# Known values for dimension detection
WEEKDAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
SESSIONS = {"RTH", "ETH", "OVERNIGHT", "GLOBEX"}
MONTHS = {
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
}


@SpecialOpRegistry.register
class CompareOpBuilder(SpecialOpBuilder):
    """
    Builder для SpecialOp.COMPARE.

    Сравнивает метрики между группами (weekdays, sessions, years, months).
    """

    op_type = SpecialOp.COMPARE

    def build_query(
        self,
        spec: "QuerySpec",
        extra_filters_sql: str = ""
    ) -> str:
        """
        Строит запрос для сравнения групп.

        Логика:
        1. Определить dimension (weekday, session, year, month)
        2. Построить соответствующий SQL
        """
        compare_spec = spec.compare_spec
        items = compare_spec.items

        dimension = self._detect_dimension(items)

        if dimension == "weekday":
            return self._build_weekday_compare(spec, items, extra_filters_sql)
        elif dimension == "session":
            return self._build_session_compare(spec, items, extra_filters_sql)
        elif dimension == "year":
            return self._build_year_compare(spec, items, extra_filters_sql)
        elif dimension == "month":
            return self._build_month_compare(spec, items, extra_filters_sql)
        else:
            # Fallback to weekday
            return self._build_weekday_compare(spec, items, extra_filters_sql)

    def _detect_dimension(self, items: list[str]) -> str:
        """Определяет тип сравнения по items."""
        # Check weekdays
        if all(item in WEEKDAYS for item in items):
            return "weekday"

        # Check sessions
        if all(item.upper() in SESSIONS for item in items):
            return "session"

        # Check years (4 digits)
        if all(item.isdigit() and len(item) == 4 for item in items):
            return "year"

        # Check months
        if all(item.capitalize() in MONTHS for item in items):
            return "month"

        return "unknown"

    def _get_base_filter(self, spec: "QuerySpec") -> tuple[str, str, str]:
        """Get base filters for query using centralized helper."""
        symbol = spec.symbol
        safe_symbol = safe_sql_symbol(symbol)

        timestamp_filter, trading_date_expr = build_trading_day_timestamp_filter(
            symbol,
            spec.filters.period_start,
            spec.filters.period_end,
        )

        return safe_symbol, timestamp_filter, trading_date_expr

    def _build_weekday_compare(
        self,
        spec: "QuerySpec",
        items: list[str],
        extra_filters_sql: str
    ) -> str:
        """Compare by weekday (Monday vs Friday)."""
        safe_symbol, timestamp_filter, trading_date_expr = self._get_base_filter(spec)

        # Build IN clause
        items_sql = ", ".join(f"'{item}'" for item in items)

        return f"""WITH daily_raw AS (
    SELECT
        ({trading_date_expr})::date as date,
        FIRST(open ORDER BY timestamp) as open,
        MAX(high) as high,
        MIN(low) as low,
        LAST(close ORDER BY timestamp) as close,
        SUM(volume) as volume,
        ROUND(MAX(high) - MIN(low), 2) as range,
        ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
              / NULLIF(FIRST(open ORDER BY timestamp), 0) * 100, 2) as change_pct
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
      {extra_filters_sql}
    GROUP BY ({trading_date_expr})::date
)
SELECT
    DAYNAME(date) as group_name,
    ROUND(AVG(range), 2) as avg_range,
    ROUND(AVG(change_pct), 2) as avg_change,
    ROUND(STDDEV(change_pct), 2) as volatility,
    COUNT(*) as count
FROM daily_raw
WHERE DAYNAME(date) IN ({items_sql})
GROUP BY DAYNAME(date)
ORDER BY CASE DAYNAME(date)
    WHEN 'Monday' THEN 1
    WHEN 'Tuesday' THEN 2
    WHEN 'Wednesday' THEN 3
    WHEN 'Thursday' THEN 4
    WHEN 'Friday' THEN 5
    WHEN 'Saturday' THEN 6
    WHEN 'Sunday' THEN 7
END"""

    def _build_session_compare(
        self,
        spec: "QuerySpec",
        items: list[str],
        extra_filters_sql: str
    ) -> str:
        """Compare by session (RTH vs ETH)."""
        safe_symbol, timestamp_filter, trading_date_expr = self._get_base_filter(spec)
        symbol = spec.symbol

        # Build CTE for each session
        session_ctes = []
        session_selects = []

        for session in items:
            session_upper = session.upper()
            session_times = get_session_times(symbol, session_upper)

            if session_times:
                time_start, time_end = session_times
                time_start = time_start if len(time_start.split(":")) == 3 else f"{time_start}:00"
                time_end = time_end if len(time_end.split(":")) == 3 else f"{time_end}:00"

                # Check if session crosses midnight
                if time_start > time_end:
                    # Session spans overnight (e.g., ETH 18:00-17:00)
                    time_filter = ""  # No filter = full trading day
                else:
                    time_filter = f"AND timestamp::time BETWEEN '{time_start}' AND '{time_end}'"
            else:
                time_filter = ""

            cte_name = f"daily_{session_upper.lower()}"
            session_ctes.append(f"""{cte_name} AS (
    SELECT
        ({trading_date_expr})::date as date,
        FIRST(open ORDER BY timestamp) as open,
        MAX(high) as high,
        MIN(low) as low,
        LAST(close ORDER BY timestamp) as close,
        SUM(volume) as volume,
        ROUND(MAX(high) - MIN(low), 2) as range,
        ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
              / NULLIF(FIRST(open ORDER BY timestamp), 0) * 100, 2) as change_pct
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
      {time_filter}
      {extra_filters_sql}
    GROUP BY ({trading_date_expr})::date
)""")

            session_selects.append(f"""SELECT
    '{session_upper}' as group_name,
    ROUND(AVG(range), 2) as avg_range,
    ROUND(AVG(change_pct), 2) as avg_change,
    ROUND(STDDEV(change_pct), 2) as volatility,
    COUNT(*) as count
FROM {cte_name}""")

        ctes_sql = ",\n".join(session_ctes)
        union_sql = "\nUNION ALL\n".join(session_selects)

        return f"""WITH {ctes_sql}
{union_sql}"""

    def _build_year_compare(
        self,
        spec: "QuerySpec",
        items: list[str],
        extra_filters_sql: str
    ) -> str:
        """Compare by year (2023 vs 2024)."""
        safe_symbol, timestamp_filter, trading_date_expr = self._get_base_filter(spec)

        # Build IN clause
        items_sql = ", ".join(items)

        return f"""WITH daily_raw AS (
    SELECT
        ({trading_date_expr})::date as date,
        FIRST(open ORDER BY timestamp) as open,
        MAX(high) as high,
        MIN(low) as low,
        LAST(close ORDER BY timestamp) as close,
        SUM(volume) as volume,
        ROUND(MAX(high) - MIN(low), 2) as range,
        ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
              / NULLIF(FIRST(open ORDER BY timestamp), 0) * 100, 2) as change_pct
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
      {extra_filters_sql}
    GROUP BY ({trading_date_expr})::date
)
SELECT
    CAST(YEAR(date) AS VARCHAR) as group_name,
    ROUND(AVG(range), 2) as avg_range,
    ROUND(AVG(change_pct), 2) as avg_change,
    ROUND(STDDEV(change_pct), 2) as volatility,
    COUNT(*) as count
FROM daily_raw
WHERE YEAR(date) IN ({items_sql})
GROUP BY YEAR(date)
ORDER BY YEAR(date)"""

    def _build_month_compare(
        self,
        spec: "QuerySpec",
        items: list[str],
        extra_filters_sql: str
    ) -> str:
        """Compare by month (January vs December)."""
        safe_symbol, timestamp_filter, trading_date_expr = self._get_base_filter(spec)

        # Build IN clause
        items_sql = ", ".join(f"'{item.capitalize()}'" for item in items)

        return f"""WITH daily_raw AS (
    SELECT
        ({trading_date_expr})::date as date,
        FIRST(open ORDER BY timestamp) as open,
        MAX(high) as high,
        MIN(low) as low,
        LAST(close ORDER BY timestamp) as close,
        SUM(volume) as volume,
        ROUND(MAX(high) - MIN(low), 2) as range,
        ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
              / NULLIF(FIRST(open ORDER BY timestamp), 0) * 100, 2) as change_pct
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
      {extra_filters_sql}
    GROUP BY ({trading_date_expr})::date
)
SELECT
    MONTHNAME(date) as group_name,
    ROUND(AVG(range), 2) as avg_range,
    ROUND(AVG(change_pct), 2) as avg_change,
    ROUND(STDDEV(change_pct), 2) as volatility,
    COUNT(*) as count
FROM daily_raw
WHERE MONTHNAME(date) IN ({items_sql})
GROUP BY MONTHNAME(date)
ORDER BY CASE MONTHNAME(date)
    WHEN 'January' THEN 1
    WHEN 'February' THEN 2
    WHEN 'March' THEN 3
    WHEN 'April' THEN 4
    WHEN 'May' THEN 5
    WHEN 'June' THEN 6
    WHEN 'July' THEN 7
    WHEN 'August' THEN 8
    WHEN 'September' THEN 9
    WHEN 'October' THEN 10
    WHEN 'November' THEN 11
    WHEN 'December' THEN 12
END"""
