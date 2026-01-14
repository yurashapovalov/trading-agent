"""
Daily With Prev Source Builder — дневные данные с LAG функциями.

Добавляет колонки для анализа относительно предыдущего дня:
- prev_close: закрытие предыдущего дня
- prev_change_pct: изменение предыдущего дня
- gap_pct: гэп открытия

Используется для анализа гэпов и паттернов "следующий день".
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import Filters

from agent.query_builder.types import Source
from .base import SourceBuilder, SourceRegistry
from .common import build_daily_aggregation_sql


@SourceRegistry.register
class DailyWithPrevSourceBuilder(SourceBuilder):
    """Builder для Source.DAILY_WITH_PREV — дневки + LAG колонки."""

    source_type = Source.DAILY_WITH_PREV

    def build_cte(
        self,
        symbol: str,
        filters: "Filters",
        extra_filters_sql: str = ""
    ) -> str:
        """
        Строит CTE для дневных данных с данными предыдущего дня.

        Трёхступенчатая структура:
        1. daily_raw: агрегация минуток
        2. daily: календарные фильтры
        3. daily_with_prev: LAG колонки
        """
        daily_raw = build_daily_aggregation_sql(
            symbol, filters.period_start, filters.period_end
        )

        calendar_where = f"WHERE {extra_filters_sql}" if extra_filters_sql else ""

        return f"""WITH {daily_raw},
daily AS (
    SELECT * FROM daily_raw
    {calendar_where}
),
daily_with_prev AS (
    SELECT
        *,
        LAG(close) OVER (ORDER BY date) as prev_close,
        LAG(change_pct) OVER (ORDER BY date) as prev_change_pct,
        ROUND((open - LAG(close) OVER (ORDER BY date))
              / NULLIF(LAG(close) OVER (ORDER BY date), 0) * 100, 2) as gap_pct
    FROM daily
)
SELECT"""


# Для обратной совместимости
def build_daily_with_prev_cte(
    symbol: str,
    filters: "Filters",
    calendar_filter_sql: str = ""
) -> str:
    """Legacy wrapper для DailyWithPrevSourceBuilder."""
    return DailyWithPrevSourceBuilder().build_cte(symbol, filters, calendar_filter_sql)
