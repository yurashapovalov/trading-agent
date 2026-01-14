"""
Minutes Source Builder — CTE для минутных данных.

Используется когда нужен анализ внутри дня:
- Время формирования high/low
- Сравнение сессий RTH vs ETH
- Распределение объёма по часам
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import Filters

from agent.query_builder.types import Source
from .base import SourceBuilder, SourceRegistry
from .common import OHLCV_TABLE


@SourceRegistry.register
class MinutesSourceBuilder(SourceBuilder):
    """Builder для Source.MINUTES — сырые минутные бары."""

    source_type = Source.MINUTES

    def build_cte(
        self,
        symbol: str,
        filters: "Filters",
        extra_filters_sql: str = ""
    ) -> str:
        """Строит CTE с минутными данными."""
        period_start = filters.period_start
        period_end = filters.period_end

        return f"""WITH minutes AS (
    SELECT
        timestamp,
        timestamp::date as date,
        timestamp::time as time,
        open,
        high,
        low,
        close,
        volume,
        high - low as range
    FROM {OHLCV_TABLE}
    WHERE symbol = '{symbol}'
      AND timestamp >= '{period_start}'
      AND timestamp < '{period_end}'
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
