"""
Event Time Operation Builder — поиск времени события.

Отвечает на вопросы:
- "В какое время формируется high дня?"
- "Когда обычно бывает low?"
- "Распределение high и low по времени"

Все значения валидируются для защиты от SQL injection.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import QuerySpec

from agent.query_builder.types import SpecialOp
from agent.query_builder.source.common import OHLCV_TABLE
from agent.query_builder.sql_utils import safe_sql_symbol, safe_sql_date
from .base import SpecialOpBuilder, SpecialOpRegistry


@SpecialOpRegistry.register
class EventTimeOpBuilder(SpecialOpBuilder):
    """
    Builder для SpecialOp.EVENT_TIME.

    Находит распределение времени формирования high/low по дням.
    Все входные данные валидируются для защиты от SQL injection.
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

        Raises:
            ValidationError: Если входные данные невалидны
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
        elif find_col == "all":
            return self._build_all_query(
                symbol, period_start, period_end,
                interval, extra_filters_sql
            )
        else:
            # high, low, open, close, max_volume
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
        """Запрос для одного типа события (high, low, open, close, max_volume)."""
        # Валидация входных данных
        safe_symbol = safe_sql_symbol(symbol)
        safe_start = safe_sql_date(period_start)
        safe_end = safe_sql_date(period_end)

        # Определяем ORDER BY и нужные колонки для поиска события
        event_configs = {
            "high": {"order": "high DESC, timestamp ASC", "columns": "high"},
            "low": {"order": "low ASC, timestamp ASC", "columns": "low"},
            "open": {"order": "timestamp ASC", "columns": "open"},
            "close": {"order": "timestamp DESC", "columns": "close"},
            "max_volume": {"order": "volume DESC, timestamp ASC", "columns": "volume"},
        }
        config = event_configs.get(find_col, {"order": "timestamp ASC", "columns": "open"})
        order_clause = config["order"]
        select_columns = config["columns"]

        return f"""WITH filtered_data AS (
    -- Минутные данные с фильтрами
    SELECT
        timestamp,
        timestamp::date as date,
        {select_columns}
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND timestamp >= {safe_start}
      AND timestamp < {safe_end}
      {extra_filters_sql}
),
daily_events AS (
    -- Для каждого дня находим момент события
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
    FROM daily_events
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
        # Валидация входных данных
        safe_symbol = safe_sql_symbol(symbol)
        safe_start = safe_sql_date(period_start)
        safe_end = safe_sql_date(period_end)

        return f"""WITH filtered_data AS (
    -- Минутные данные с фильтрами
    SELECT
        timestamp,
        timestamp::date as date,
        high,
        low
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND timestamp >= {safe_start}
      AND timestamp < {safe_end}
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

    def _build_all_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        interval: str,
        extra_filters_sql: str
    ) -> str:
        """UNION запрос для всех событий: open, high, low, close, max_volume."""
        safe_symbol = safe_sql_symbol(symbol)
        safe_start = safe_sql_date(period_start)
        safe_end = safe_sql_date(period_end)

        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        timestamp::date as date,
        open,
        high,
        low,
        close,
        volume
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND timestamp >= {safe_start}
      AND timestamp < {safe_end}
      {extra_filters_sql}
),
daily_opens AS (
    SELECT date, FIRST(timestamp ORDER BY timestamp ASC) as event_ts, 'open' as event_type
    FROM filtered_data GROUP BY date
),
daily_highs AS (
    SELECT date, FIRST(timestamp ORDER BY high DESC, timestamp ASC) as event_ts, 'high' as event_type
    FROM filtered_data GROUP BY date
),
daily_lows AS (
    SELECT date, FIRST(timestamp ORDER BY low ASC, timestamp ASC) as event_ts, 'low' as event_type
    FROM filtered_data GROUP BY date
),
daily_closes AS (
    SELECT date, LAST(timestamp ORDER BY timestamp ASC) as event_ts, 'close' as event_type
    FROM filtered_data GROUP BY date
),
daily_max_volumes AS (
    SELECT date, FIRST(timestamp ORDER BY volume DESC, timestamp ASC) as event_ts, 'max_volume' as event_type
    FROM filtered_data GROUP BY date
),
all_events AS (
    SELECT * FROM daily_opens
    UNION ALL SELECT * FROM daily_highs
    UNION ALL SELECT * FROM daily_lows
    UNION ALL SELECT * FROM daily_closes
    UNION ALL SELECT * FROM daily_max_volumes
),
distribution AS (
    SELECT
        event_type,
        STRFTIME(TIME_BUCKET(INTERVAL '{interval}', event_ts), '%H:%M') as time_bucket,
        COUNT(*) as frequency
    FROM all_events
    GROUP BY event_type, time_bucket
)
SELECT
    event_type,
    time_bucket,
    frequency,
    ROUND(frequency * 100.0 / SUM(frequency) OVER (PARTITION BY event_type), 2) as percentage
FROM distribution
ORDER BY event_type, time_bucket"""


# Legacy wrapper
def build_event_time_query(spec: "QuerySpec", extra_filters_sql: str) -> str:
    """Legacy wrapper для EventTimeOpBuilder."""
    return EventTimeOpBuilder().build_query(spec, extra_filters_sql)
