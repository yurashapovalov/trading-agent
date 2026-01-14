"""
Query Builder — построение SQL запросов из структурированных спецификаций.

Этот модуль заменяет SQL Agent (LLM-генерацию SQL) на детерминированное
построение SQL из типизированных "кубиков".

Использование:
    from agent.query_builder import QueryBuilder, QuerySpec, Source, Filters

    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2024-01-01",
            period_end="2024-02-01",
        ),
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

Публичные классы:
    - QueryBuilder: Главный класс для построения SQL
    - QuerySpec: Полная спецификация запроса
    - Source: Источник данных (MINUTES, DAILY, DAILY_WITH_PREV)
    - Filters: Фильтры (период, время, условия)
    - Condition: Условие фильтрации
    - Grouping: Способ группировки
    - Metric: Доступные метрики
    - MetricSpec: Спецификация метрики
    - SpecialOp: Специальные операции
    - EventTimeSpec, TopNSpec, CompareSpec: Параметры спец. операций
"""

from .types import (
    # Основные типы
    QuerySpec,
    Source,
    Filters,
    Condition,
    Grouping,
    Metric,
    MetricSpec,
    # Специальные операции
    SpecialOp,
    EventTimeSpec,
    TopNSpec,
    CompareSpec,
    FindExtremumSpec,
)

from .builder import QueryBuilder

__all__ = [
    # Builder
    "QueryBuilder",
    # Основные типы
    "QuerySpec",
    "Source",
    "Filters",
    "Condition",
    "Grouping",
    "Metric",
    "MetricSpec",
    # Специальные операции
    "SpecialOp",
    "EventTimeSpec",
    "TopNSpec",
    "CompareSpec",
    "FindExtremumSpec",
]
