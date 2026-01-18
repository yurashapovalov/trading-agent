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
from agent.query_builder.sql_utils import safe_sql_symbol
from .base import SourceBuilder, SourceRegistry
from .common import OHLCV_TABLE, build_trading_day_timestamp_filter


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
        safe_symbol = safe_sql_symbol(symbol)

        # Use centralized helper for trading day boundaries
        timestamp_filter, trading_date_expr = build_trading_day_timestamp_filter(
            symbol,
            filters.period_start,
            filters.period_end,
            session=filters.session,
            time_start=filters.time_start,
        )

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
        high - low as range,
        ROUND((close - open) / NULLIF(open, 0) * 100, 4) as change_pct
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
