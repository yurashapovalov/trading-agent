"""
Daily Source Builder — CTE для дневных данных.

Агрегирует минутные данные в дневные бары.
Используется для большинства дневных запросов.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.query_builder.types import Filters

from agent.query_builder.types import Source
from .base import SourceBuilder, SourceRegistry
from .common import build_daily_aggregation_sql


@SourceRegistry.register
class DailySourceBuilder(SourceBuilder):
    """Builder для Source.DAILY — агрегированные дневные бары."""

    source_type = Source.DAILY

    def build_cte(
        self,
        symbol: str,
        filters: "Filters",
        extra_filters_sql: str = ""
    ) -> str:
        """
        Строит CTE для дневных данных.

        Note:
            extra_filters_sql здесь это calendar_filter (years, months, weekdays).
            Применяется как WHERE к daily CTE, не к сырым минуткам.
        """
        daily_raw = build_daily_aggregation_sql(
            symbol, filters.period_start, filters.period_end
        )

        # extra_filters_sql содержит календарные фильтры
        calendar_where = f"WHERE {extra_filters_sql}" if extra_filters_sql else ""

        return f"""WITH {daily_raw},
daily AS (
    SELECT * FROM daily_raw
    {calendar_where}
)
SELECT"""


# Для обратной совместимости
def build_daily_cte(
    symbol: str,
    filters: "Filters",
    calendar_filter_sql: str = ""
) -> str:
    """Legacy wrapper для DailySourceBuilder."""
    return DailySourceBuilder().build_cte(symbol, filters, calendar_filter_sql)
