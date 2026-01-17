"""
Minutes Source Builder — CTE для минутных данных.

Используется когда нужен анализ внутри дня:
- Время формирования high/low
- Сравнение сессий RTH vs ETH
- Распределение объёма по часам

Trading Day vs Calendar Day:
    For futures (NQ, ES), trading day != calendar day.
    Example: Tuesday's trading day = Monday 18:00 ET → Tuesday 17:00 ET

    When session is not specified, we use trading day boundaries
    instead of calendar day (00:00-23:59).

Все значения валидируются для защиты от SQL injection.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import Filters

from agent.query_builder.types import Source
from agent.query_builder.sql_utils import safe_sql_symbol, safe_sql_date
from agent.query_builder.instruments import get_trading_day_boundaries
from .base import SourceBuilder, SourceRegistry
from .common import OHLCV_TABLE, get_trading_date_expression


@SourceRegistry.register
class MinutesSourceBuilder(SourceBuilder):
    """
    Builder для Source.MINUTES — сырые минутные бары.

    Все входные данные валидируются для защиты от SQL injection.
    """

    source_type = Source.MINUTES

    def build_cte(
        self,
        symbol: str,
        filters: "Filters",
        extra_filters_sql: str = ""
    ) -> str:
        """
        Строит CTE с минутными данными.

        Trading Day Logic:
            When session is not specified, uses trading day boundaries.
            For futures: trading day D = (D-1) at trading_day_start → D at trading_day_end
            Example: May 16 trading day = May 15 18:00 ET → May 16 17:00 ET

        Raises:
            ValidationError: Если входные данные невалидны
        """
        period_start = filters.period_start
        period_end = filters.period_end

        # Валидация входных данных
        safe_symbol = safe_sql_symbol(symbol)
        safe_start = safe_sql_date(period_start)
        safe_end = safe_sql_date(period_end)

        # Determine timestamp filtering based on session
        # If session is specified, time filtering is handled by build_time_filter_sql
        # If session is NOT specified, use trading day boundaries (not calendar day)
        trading_bounds = get_trading_day_boundaries(symbol)

        if not filters.session and not filters.time_start and trading_bounds:
            # Use trading day boundaries
            # Trading day for date D: (D-1 day) at day_start → D at day_end
            # period_start/period_end are dates, period_end is exclusive
            day_start, day_end = trading_bounds  # e.g., ("18:00", "17:00")

            # Normalize times to HH:MM:SS
            day_start_time = day_start if len(day_start.split(":")) == 3 else f"{day_start}:00"
            day_end_time = day_end if len(day_end.split(":")) == 3 else f"{day_end}:00"

            # Trading date expression for grouping
            trading_date_expr = get_trading_date_expression(symbol)

            # DuckDB: (date - interval)::date + time::time -> timestamp
            timestamp_filter = f"""timestamp >= (({safe_start}::date - INTERVAL '1 day')::date + '{day_start_time}'::time)
      AND timestamp < (({safe_end}::date - INTERVAL '1 day')::date + '{day_end_time}'::time)"""
        else:
            # Session is specified or custom time - use calendar dates
            # Time filtering will be added by build_time_filter_sql
            trading_date_expr = "timestamp::date"
            timestamp_filter = f"""timestamp >= {safe_start}
      AND timestamp < {safe_end}"""

        return f"""WITH minutes AS (
    SELECT
        timestamp,
        ({trading_date_expr})::date as date,
        timestamp::time as time,
        open,
        high,
        low,
        close,
        volume,
        high - low as range
    FROM {OHLCV_TABLE}
    WHERE symbol = {safe_symbol}
      AND {timestamp_filter}
      {extra_filters_sql}
)
SELECT"""


# Для обратной совместимости — функция-обёртка
def build_minutes_cte(
    symbol: str,
    filters: "Filters",
    extra_filters_sql: str = ""
) -> str:
    """Legacy wrapper для MinutesSourceBuilder."""
    return MinutesSourceBuilder().build_cte(symbol, filters, extra_filters_sql)
