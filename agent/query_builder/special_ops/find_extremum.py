"""
Find Extremum Operation Builder — поиск точного времени high/low.

Отвечает на вопросы:
- "Во сколько был хай 10 января?"
- "Когда был минимум на прошлой неделе?"
- "Точное время high и low за вчера"

Отличие от EVENT_TIME:
- EVENT_TIME: распределение по bucket'ам → frequency, percentage
- FIND_EXTREMUM: точные значения → timestamp, value
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import QuerySpec

from agent.query_builder.types import SpecialOp
from agent.query_builder.source.common import OHLCV_TABLE
from .base import SpecialOpBuilder, SpecialOpRegistry


@SpecialOpRegistry.register
class FindExtremumOpBuilder(SpecialOpBuilder):
    """
    Builder для SpecialOp.FIND_EXTREMUM.

    Находит точное время и значение high/low для каждого дня в периоде.
    """

    op_type = SpecialOp.FIND_EXTREMUM

    def build_query(
        self,
        spec: "QuerySpec",
        extra_filters_sql: str = ""
    ) -> str:
        """
        Строит запрос для поиска точного времени экстремумов.

        Returns:
            SQL с колонками: date, high_time, high_value, low_time, low_value
        """
        find = spec.find_extremum_spec.find
        symbol = spec.symbol
        period_start = spec.filters.period_start
        period_end = spec.filters.period_end

        if find == "high":
            return self._build_high_query(symbol, period_start, period_end, extra_filters_sql)
        elif find == "low":
            return self._build_low_query(symbol, period_start, period_end, extra_filters_sql)
        else:  # both
            return self._build_both_query(symbol, period_start, period_end, extra_filters_sql)

    def _build_high_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска только HIGH."""
        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        timestamp::date as date,
        high
    FROM {OHLCV_TABLE}
    WHERE symbol = '{symbol}'
      AND timestamp >= '{period_start}'
      AND timestamp < '{period_end}'
      {extra_filters_sql}
),
daily_highs AS (
    SELECT
        date,
        FIRST(timestamp ORDER BY high DESC, timestamp ASC) as high_time,
        MAX(high) as high_value
    FROM filtered_data
    GROUP BY date
)
SELECT
    date,
    high_time,
    high_time::time as high_time_only,
    high_value
FROM daily_highs
ORDER BY date"""

    def _build_low_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска только LOW."""
        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        timestamp::date as date,
        low
    FROM {OHLCV_TABLE}
    WHERE symbol = '{symbol}'
      AND timestamp >= '{period_start}'
      AND timestamp < '{period_end}'
      {extra_filters_sql}
),
daily_lows AS (
    SELECT
        date,
        FIRST(timestamp ORDER BY low ASC, timestamp ASC) as low_time,
        MIN(low) as low_value
    FROM filtered_data
    GROUP BY date
)
SELECT
    date,
    low_time,
    low_time::time as low_time_only,
    low_value
FROM daily_lows
ORDER BY date"""

    def _build_both_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска HIGH и LOW."""
        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        timestamp::date as date,
        high,
        low
    FROM {OHLCV_TABLE}
    WHERE symbol = '{symbol}'
      AND timestamp >= '{period_start}'
      AND timestamp < '{period_end}'
      {extra_filters_sql}
),
daily_extremes AS (
    SELECT
        date,
        FIRST(timestamp ORDER BY high DESC, timestamp ASC) as high_time,
        MAX(high) as high_value,
        FIRST(timestamp ORDER BY low ASC, timestamp ASC) as low_time,
        MIN(low) as low_value
    FROM filtered_data
    GROUP BY date
)
SELECT
    date,
    high_time::time as high_time,
    high_value,
    low_time::time as low_time,
    low_value
FROM daily_extremes
ORDER BY date"""
