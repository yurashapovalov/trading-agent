"""
Find Extremum Operation Builder — поиск точного времени high/low.

Отвечает на вопросы:
- "Во сколько был хай 10 января?"
- "Когда был минимум на прошлой неделе?"
- "Точное время high и low за вчера"

Отличие от EVENT_TIME:
- EVENT_TIME: распределение по bucket'ам → frequency, percentage
- FIND_EXTREMUM: точные значения → timestamp, value

Trading Day vs Calendar Day:
    For futures (NQ, ES), trading day != calendar day.
    Example: Tuesday's trading day = Monday 18:00 ET → Tuesday 17:00 ET
    When session is not specified, we use trading day boundaries.

Все значения валидируются для защиты от SQL injection.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import QuerySpec

from agent.query_builder.types import SpecialOp
from agent.query_builder.source.common import OHLCV_TABLE, build_trading_day_timestamp_filter
from agent.query_builder.sql_utils import safe_sql_symbol
from .base import SpecialOpBuilder, SpecialOpRegistry


@SpecialOpRegistry.register
class FindExtremumOpBuilder(SpecialOpBuilder):
    """
    Builder для SpecialOp.FIND_EXTREMUM.

    Находит точное время и значение high/low для каждого дня в периоде.
    Uses trading day boundaries for futures (not calendar day).
    Все входные данные валидируются для защиты от SQL injection.
    """

    op_type = SpecialOp.FIND_EXTREMUM

    def build_query(
        self,
        spec: "QuerySpec",
        extra_filters_sql: str = ""
    ) -> str:
        """
        Строит запрос для поиска точного времени событий.

        Returns:
            SQL с колонками зависящими от find:
            - high: date, high_time, high_value
            - low: date, low_time, low_value
            - open: date, open_time, open_value
            - close: date, close_time, close_value
            - max_volume: date, max_volume_time, max_volume_value
            - both: high + low
            - ohlc: open + high + low + close
            - all: open + high + low + close + max_volume

        Raises:
            ValidationError: Если входные данные невалидны
        """
        find = spec.find_extremum_spec.find
        symbol = spec.symbol
        period_start = spec.filters.period_start
        period_end = spec.filters.period_end
        session = spec.filters.session
        time_start = spec.filters.time_start

        if find == "high":
            return self._build_high_query(symbol, period_start, period_end, session, time_start, extra_filters_sql)
        elif find == "low":
            return self._build_low_query(symbol, period_start, period_end, session, time_start, extra_filters_sql)
        elif find == "open":
            return self._build_open_query(symbol, period_start, period_end, session, time_start, extra_filters_sql)
        elif find == "close":
            return self._build_close_query(symbol, period_start, period_end, session, time_start, extra_filters_sql)
        elif find == "max_volume":
            return self._build_max_volume_query(symbol, period_start, period_end, session, time_start, extra_filters_sql)
        elif find == "both":
            return self._build_both_query(symbol, period_start, period_end, session, time_start, extra_filters_sql)
        elif find == "ohlc":
            return self._build_ohlc_query(symbol, period_start, period_end, session, time_start, extra_filters_sql)
        else:  # all
            return self._build_all_query(symbol, period_start, period_end, session, time_start, extra_filters_sql)

    def _build_high_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        session: str | None,
        time_start: str | None,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска только HIGH."""
        safe_symbol = safe_sql_symbol(symbol)
        timestamp_filter, trading_date_expr = build_trading_day_timestamp_filter(
            symbol, period_start, period_end, session, time_start
        )

        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        ({trading_date_expr})::date as date,
        high
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
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
        session: str | None,
        time_start: str | None,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска только LOW."""
        safe_symbol = safe_sql_symbol(symbol)
        timestamp_filter, trading_date_expr = build_trading_day_timestamp_filter(
            symbol, period_start, period_end, session, time_start
        )

        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        ({trading_date_expr})::date as date,
        low
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
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
        session: str | None,
        time_start: str | None,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска HIGH и LOW."""
        safe_symbol = safe_sql_symbol(symbol)
        timestamp_filter, trading_date_expr = build_trading_day_timestamp_filter(
            symbol, period_start, period_end, session, time_start
        )

        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        ({trading_date_expr})::date as date,
        high,
        low
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
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

    def _build_open_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        session: str | None,
        time_start: str | None,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска времени OPEN (первая минутка)."""
        safe_symbol = safe_sql_symbol(symbol)
        timestamp_filter, trading_date_expr = build_trading_day_timestamp_filter(
            symbol, period_start, period_end, session, time_start
        )

        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        ({trading_date_expr})::date as date,
        open
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
      {extra_filters_sql}
),
daily_opens AS (
    SELECT
        date,
        FIRST(timestamp ORDER BY timestamp ASC) as open_time,
        FIRST(open ORDER BY timestamp ASC) as open_value
    FROM filtered_data
    GROUP BY date
)
SELECT
    date,
    open_time::time as open_time,
    open_value
FROM daily_opens
ORDER BY date"""

    def _build_close_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        session: str | None,
        time_start: str | None,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска времени CLOSE (последняя минутка)."""
        safe_symbol = safe_sql_symbol(symbol)
        timestamp_filter, trading_date_expr = build_trading_day_timestamp_filter(
            symbol, period_start, period_end, session, time_start
        )

        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        ({trading_date_expr})::date as date,
        close
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
      {extra_filters_sql}
),
daily_closes AS (
    SELECT
        date,
        LAST(timestamp ORDER BY timestamp ASC) as close_time,
        LAST(close ORDER BY timestamp ASC) as close_value
    FROM filtered_data
    GROUP BY date
)
SELECT
    date,
    close_time::time as close_time,
    close_value
FROM daily_closes
ORDER BY date"""

    def _build_max_volume_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        session: str | None,
        time_start: str | None,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска минуты с MAX VOLUME."""
        safe_symbol = safe_sql_symbol(symbol)
        timestamp_filter, trading_date_expr = build_trading_day_timestamp_filter(
            symbol, period_start, period_end, session, time_start
        )

        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        ({trading_date_expr})::date as date,
        volume
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
      {extra_filters_sql}
),
daily_max_volume AS (
    SELECT
        date,
        FIRST(timestamp ORDER BY volume DESC, timestamp ASC) as max_volume_time,
        MAX(volume) as max_volume_value
    FROM filtered_data
    GROUP BY date
)
SELECT
    date,
    max_volume_time::time as max_volume_time,
    max_volume_value
FROM daily_max_volume
ORDER BY date"""

    def _build_ohlc_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        session: str | None,
        time_start: str | None,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска OPEN, HIGH, LOW, CLOSE времени."""
        safe_symbol = safe_sql_symbol(symbol)
        timestamp_filter, trading_date_expr = build_trading_day_timestamp_filter(
            symbol, period_start, period_end, session, time_start
        )

        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        ({trading_date_expr})::date as date,
        open,
        high,
        low,
        close
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
      {extra_filters_sql}
),
daily_ohlc AS (
    SELECT
        date,
        FIRST(timestamp ORDER BY timestamp ASC) as open_time,
        FIRST(open ORDER BY timestamp ASC) as open_value,
        FIRST(timestamp ORDER BY high DESC, timestamp ASC) as high_time,
        MAX(high) as high_value,
        FIRST(timestamp ORDER BY low ASC, timestamp ASC) as low_time,
        MIN(low) as low_value,
        LAST(timestamp ORDER BY timestamp ASC) as close_time,
        LAST(close ORDER BY timestamp ASC) as close_value
    FROM filtered_data
    GROUP BY date
)
SELECT
    date,
    open_time::time as open_time,
    open_value,
    high_time::time as high_time,
    high_value,
    low_time::time as low_time,
    low_value,
    close_time::time as close_time,
    close_value
FROM daily_ohlc
ORDER BY date"""

    def _build_all_query(
        self,
        symbol: str,
        period_start: str,
        period_end: str,
        session: str | None,
        time_start: str | None,
        extra_filters_sql: str
    ) -> str:
        """Запрос для поиска всех событий: OPEN, HIGH, LOW, CLOSE, MAX_VOLUME."""
        safe_symbol = safe_sql_symbol(symbol)
        timestamp_filter, trading_date_expr = build_trading_day_timestamp_filter(
            symbol, period_start, period_end, session, time_start
        )

        return f"""WITH filtered_data AS (
    SELECT
        timestamp,
        ({trading_date_expr})::date as date,
        open,
        high,
        low,
        close,
        volume
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
      {extra_filters_sql}
),
daily_all AS (
    SELECT
        date,
        FIRST(timestamp ORDER BY timestamp ASC) as open_time,
        FIRST(open ORDER BY timestamp ASC) as open_value,
        FIRST(timestamp ORDER BY high DESC, timestamp ASC) as high_time,
        MAX(high) as high_value,
        FIRST(timestamp ORDER BY low ASC, timestamp ASC) as low_time,
        MIN(low) as low_value,
        LAST(timestamp ORDER BY timestamp ASC) as close_time,
        LAST(close ORDER BY timestamp ASC) as close_value,
        FIRST(timestamp ORDER BY volume DESC, timestamp ASC) as max_volume_time,
        MAX(volume) as max_volume_value
    FROM filtered_data
    GROUP BY date
)
SELECT
    date,
    open_time::time as open_time,
    open_value,
    high_time::time as high_time,
    high_value,
    low_time::time as low_time,
    low_value,
    close_time::time as close_time,
    close_value,
    max_volume_time::time as max_volume_time,
    max_volume_value
FROM daily_all
ORDER BY date"""
