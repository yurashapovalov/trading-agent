"""
Source CTE Builders — генерация WITH clause для разных источников.

Использование Registry:
    from agent.query_builder.source import SourceRegistry

    builder = SourceRegistry.get(Source.DAILY)
    cte = builder.build_cte(symbol, filters, extra_sql)

Добавление нового источника:
    1. Создать файл в source/
    2. Унаследовать от SourceBuilder
    3. Добавить декоратор @SourceRegistry.register
    4. Указать source_type = Source.YOUR_TYPE
"""

from .base import SourceBuilder, SourceRegistry

# Импортируем builders чтобы они зарегистрировались
from .minutes import MinutesSourceBuilder, build_minutes_cte
from .daily import DailySourceBuilder, build_daily_cte
from .daily_with_prev import DailyWithPrevSourceBuilder, build_daily_with_prev_cte

__all__ = [
    # Base
    "SourceBuilder",
    "SourceRegistry",
    # Builders
    "MinutesSourceBuilder",
    "DailySourceBuilder",
    "DailyWithPrevSourceBuilder",
    # Legacy functions
    "build_minutes_cte",
    "build_daily_cte",
    "build_daily_with_prev_cte",
]
