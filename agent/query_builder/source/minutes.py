"""
Minutes Source Builder — CTE для минутных данных.

Используется когда нужен анализ внутри дня:
- Время формирования high/low
- Сравнение сессий RTH vs ETH
- Распределение объёма по часам

Все значения валидируются для защиты от SQL injection.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import Filters

from agent.query_builder.types import Source
from agent.query_builder.sql_utils import safe_sql_symbol, safe_sql_date
from .base import SourceBuilder, SourceRegistry
from .common import OHLCV_TABLE


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

        Raises:
            ValidationError: Если входные данные невалидны
        """
        period_start = filters.period_start
        period_end = filters.period_end

        # Валидация входных данных
        safe_symbol = safe_sql_symbol(symbol)
        safe_start = safe_sql_date(period_start)
        safe_end = safe_sql_date(period_end)

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
    WHERE symbol = {safe_symbol}
      AND timestamp >= {safe_start}
      AND timestamp < {safe_end}
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
