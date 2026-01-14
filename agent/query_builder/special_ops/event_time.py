"""
Event Time Operation Builder — поиск времени события.

Отвечает на вопросы:
- "В какое время формируется high дня?"
- "Когда обычно бывает low?"
- "Распределение high и low по времени"
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import QuerySpec

from agent.query_builder.types import SpecialOp
from agent.query_builder.source.common import OHLCV_TABLE
from .base import SpecialOpBuilder, SpecialOpRegistry


@SpecialOpRegistry.register
class EventTimeOpBuilder(SpecialOpBuilder):
    """
    Builder для SpecialOp.EVENT_TIME.

    Находит распределение времени формирования high/low по дням.
    """

    op_type = SpecialOp.EVENT_TIME

    def build_query(
        self,
        spec: "QuerySpec",
        extra_filters_sql: str = ""
    ) -> str:
        """
        Строит запрос для поиска времени события.

        Логика:
        1. filtered_data: минутки с фильтрами
        2. daily_extremes: для каждого дня timestamp high/low
        3. distribution: группировка по time_bucket
        """
        event = spec.event_time_spec
        find_col = event.find  # "high", "low" или "both"
        interval = spec.grouping.get_interval()

        symbol = spec.symbol
        period_start = spec.filters.period_start
        period_end = spec.filters.period_end

        if find_col == "both":
            return self._build_both_query(
                symbol, period_start, period_end,
                interval, extra_filters_sql
            )
        else:
            return self._build_single_query(
                symbol, period_start, period_end,
                interval, find_col, extra_filters_sql
            )

    def _build_single_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        interval: str,
        find_col: str,
        extra_filters_sql: str
    ) -> str:
        """Запрос для одного типа экстремума (high или low)."""

        if find_col == "high":
            order_clause = "high DESC, timestamp ASC"
        else:
            order_clause = "low ASC, timestamp ASC"

        return f"""WITH filtered_data AS (
    -- Минутные данные с фильтрами
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
    -- Для каждого дня находим момент экстремума
    SELECT
        date,
        FIRST(timestamp ORDER BY {order_clause}) as event_ts
    FROM filtered_data
    GROUP BY date
),
distribution AS (
    -- Группируем по временным интервалам
    SELECT
        STRFTIME(TIME_BUCKET(INTERVAL '{interval}', event_ts), '%H:%M') as time_bucket,
        COUNT(*) as frequency
    FROM daily_extremes
    GROUP BY time_bucket
)
SELECT
    time_bucket,
    frequency,
    ROUND(frequency * 100.0 / SUM(frequency) OVER (), 2) as percentage
FROM distribution
ORDER BY time_bucket"""

    def _build_both_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        interval: str,
        extra_filters_sql: str
    ) -> str:
        """UNION запрос для high И low."""

        return f"""WITH filtered_data AS (
    -- Минутные данные с фильтрами
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
daily_highs AS (
    -- Для каждого дня находим момент HIGH
    SELECT
        date,
        FIRST(timestamp ORDER BY high DESC, timestamp ASC) as event_ts,
        'high' as event_type
    FROM filtered_data
    GROUP BY date
),
daily_lows AS (
    -- Для каждого дня находим момент LOW
    SELECT
        date,
        FIRST(timestamp ORDER BY low ASC, timestamp ASC) as event_ts,
        'low' as event_type
    FROM filtered_data
    GROUP BY date
),
all_extremes AS (
    SELECT * FROM daily_highs
    UNION ALL
    SELECT * FROM daily_lows
),
distribution AS (
    -- Группируем по временным интервалам и типу события
    SELECT
        event_type,
        STRFTIME(TIME_BUCKET(INTERVAL '{interval}', event_ts), '%H:%M') as time_bucket,
        COUNT(*) as frequency
    FROM all_extremes
    GROUP BY event_type, time_bucket
)
SELECT
    event_type,
    time_bucket,
    frequency,
    ROUND(frequency * 100.0 / SUM(frequency) OVER (PARTITION BY event_type), 2) as percentage
FROM distribution
ORDER BY event_type DESC, time_bucket"""


# Legacy wrapper
def build_event_time_query(spec: "QuerySpec", extra_filters_sql: str) -> str:
    """Legacy wrapper для EventTimeOpBuilder."""
    return EventTimeOpBuilder().build_query(spec, extra_filters_sql)
