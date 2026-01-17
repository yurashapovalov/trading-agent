"""QueryBuilder types - Single Source of Truth for all query building blocks.

Defines the "kubiks" (building blocks) that queries are assembled from:
- Source: Where to get data (minutes, daily)
- Filters: How to filter (period, time, conditions)
- Grouping: How to group results
- Metrics: What metrics to calculate
- SpecialOp: Special operations (EVENT_TIME, FIND_EXTREMUM, TOP_N)

Understander returns QuerySpec, QueryBuilder converts it to SQL.

JSON Schema for LLM is auto-generated from these types in schema.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


# =============================================================================
# SOURCE — откуда берём данные
# =============================================================================

class Source(Enum):
    """
    Источник данных для запроса.

    Определяет какой базовый CTE будет использоваться:
    - MINUTES: сырые минутные бары (ohlcv_1min)
    - DAILY: агрегированные дневные бары
    - DAILY_WITH_PREV: дневные + LAG данные (для gap анализа)
    """

    MINUTES = "minutes"
    """
    Сырые минутные бары из таблицы ohlcv_1min.

    Используется когда нужен анализ внутри дня:
    - Время формирования high/low
    - Сравнение сессий RTH vs ETH
    - Распределение объёма по часам
    """

    DAILY = "daily"
    """
    Агрегированные дневные бары.

    Создаётся из минуток через:
    - open = FIRST(open ORDER BY timestamp)
    - high = MAX(high)
    - low = MIN(low)
    - close = LAST(close ORDER BY timestamp)
    - volume = SUM(volume)

    Используется для большинства дневных запросов.
    """

    DAILY_WITH_PREV = "daily_with_prev"
    """
    Дневные бары + данные предыдущего дня через LAG.

    Добавляет колонки:
    - prev_close: закрытие предыдущего дня
    - prev_change_pct: изменение предыдущего дня
    - gap_pct: гэп открытия ((open - prev_close) / prev_close * 100)

    Используется для анализа гэпов и паттернов "следующий день".
    """


# =============================================================================
# FILTERS — фильтрация данных
# =============================================================================

@dataclass
class Condition:
    """
    Условие фильтрации по значению колонки.

    Примеры:
        Condition("change_pct", "<", -2.0)   → change_pct < -2
        Condition("volume", ">", 1000000)    → volume > 1000000
        Condition("gap_pct", ">=", 1.0)      → gap_pct >= 1

    Attributes:
        column: Имя колонки для фильтрации.
                Доступные: open, high, low, close, volume,
                          range, change_pct, gap_pct
        operator: Оператор сравнения: >, <, >=, <=, ==, !=
        value: Значение для сравнения (число)
    """

    column: str
    operator: Literal[">", "<", ">=", "<=", "==", "!="]
    value: float

    def to_sql(self) -> str:
        """Преобразует условие в SQL выражение."""
        # Маппинг операторов Python → SQL
        op_map = {"==": "=", "!=": "<>"}
        sql_op = op_map.get(self.operator, self.operator)
        return f"{self.column} {sql_op} {self.value}"


# =============================================================================
# TRADING SESSIONS — торговые сессии
# =============================================================================

# Session times are defined per-instrument in instruments.py (Single Source of Truth)
# This file only defines the type alias for type checking.
#
# To get session times, use:
#   from agent.query_builder.instruments import get_session_times
#   times = get_session_times("NQ", "RTH")  # → ("09:30", "17:00")

# Type alias - actual valid sessions are defined in instruments.py per symbol
SessionType = str  # Session name like "RTH", "ETH", "OVERNIGHT"


class HolidayFilter(Enum):
    """
    Режим фильтрации праздничных дней.

    Используется для:
    - market_holidays: дни полного закрытия (Christmas, New Year, etc.)
    - early_close_days: дни раннего закрытия (Christmas Eve, Black Friday, etc.)
    """

    INCLUDE = "include"
    """Включить эти дни в выборку (по умолчанию)."""

    EXCLUDE = "exclude"
    """Исключить эти дни из выборки."""

    ONLY = "only"
    """Показать ТОЛЬКО эти дни (для анализа праздничной торговли)."""


@dataclass
class Filters:
    """
    Фильтры для ограничения выборки данных.

    Attributes:
        # === Календарные фильтры ===
        period_start: Начало периода в ISO формате (YYYY-MM-DD). Включительно.
        period_end: Конец периода в ISO формате (YYYY-MM-DD). Не включительно.
        specific_dates: Конкретные даты ["2005-05-16", "2003-04-12"]
        years: Конкретные годы [2020, 2022, 2024]
        months: Месяцы (1-12) [1, 6] для января и июня
        weekdays: Дни недели ["Monday", "Friday"]

        # === Время суток ===
        session: Торговая сессия (RTH, ETH, PREMARKET, etc.)
        time_start: Начало кастомного времени (HH:MM:SS)
        time_end: Конец кастомного времени (HH:MM:SS)

        # === Условия по значениям ===
        conditions: Список условий фильтрации [{column, operator, value}]

        # === Праздники ===
        market_holidays: Режим для дней полного закрытия (include/exclude/only)
        early_close_days: Режим для дней раннего закрытия (include/exclude/only)

    Example:
        # Январь 2024, только RTH сессия, дни с падением > 1%
        Filters(
            period_start="2024-01-01",
            period_end="2024-02-01",
            session="RTH",
            conditions=[Condition("change_pct", "<", -1.0)]
        )

        # Статистика без праздников
        Filters(
            period_start="2024-01-01",
            period_end="2025-01-01",
            market_holidays=HolidayFilter.EXCLUDE,
            early_close_days=HolidayFilter.EXCLUDE
        )

        # Только укороченные дни
        Filters(
            period_start="2020-01-01",
            period_end="2025-01-01",
            early_close_days=HolidayFilter.ONLY
        )
    """

    # Календарные фильтры
    period_start: str
    period_end: str
    specific_dates: list[str] | None = None
    years: list[int] | None = None
    months: list[int] | None = None
    weekdays: list[str] | None = None

    # Время суток
    session: SessionType | None = None
    time_start: str | None = None
    time_end: str | None = None

    # Условия по значениям
    conditions: list[Condition] = field(default_factory=list)

    # Праздники
    market_holidays: HolidayFilter = HolidayFilter.INCLUDE
    """Режим для дней полного закрытия рынка (Christmas, New Year, etc.)"""

    early_close_days: HolidayFilter = HolidayFilter.INCLUDE
    """Режим для дней раннего закрытия (Christmas Eve, Black Friday, etc.)"""

    # Note: Session time resolution is done in query_builder/filters/time.py
    # using instruments.py as the single source of truth for session times.


# =============================================================================
# GROUPING — как группируем результат
# =============================================================================

class Grouping(Enum):
    """
    Способ группировки результатов.

    Understander выбирает ОДНО значение из этого enum.
    QueryBuilder генерирует соответствующий GROUP BY.
    """

    # === Нет группировки ===

    NONE = "none"
    """
    Вернуть отдельные строки без агрегации.

    Используется для:
    - Фильтрации: "найди дни когда упало > 2%"
    - TOP_N: "10 самых волатильных дней"

    Результат: каждая строка = один день/бар.
    """

    TOTAL = "total"
    """
    Агрегировать весь период в одну строку.

    Используется для:
    - Общей статистики: "средняя волатильность за 2024"
    - Итогов: "суммарный объём за период"

    Результат: одна строка с агрегированными значениями.
    """

    # === По времени суток (анализ внутри дня) ===

    MINUTE_1 = "1min"
    """Группировка по 1-минутным интервалам (максимальная детализация)."""

    MINUTE_5 = "5min"
    """Группировка по 5-минутным интервалам: 09:30, 09:35, 09:40..."""

    MINUTE_10 = "10min"
    """Группировка по 10-минутным интервалам: 09:30, 09:40, 09:50..."""

    MINUTE_15 = "15min"
    """Группировка по 15-минутным интервалам: 09:30, 09:45, 10:00..."""

    MINUTE_30 = "30min"
    """Группировка по 30-минутным интервалам: 09:30, 10:00, 10:30..."""

    HOUR = "hour"
    """Группировка по часам: 09:00, 10:00, 11:00..."""

    # === По календарным периодам ===

    DAY = "day"
    """Группировка по дням. Результат: 2024-01-15, 2024-01-16..."""

    WEEK = "week"
    """Группировка по неделям. Результат: 2024-W01, 2024-W02..."""

    MONTH = "month"
    """Группировка по месяцам. Результат: 2024-01, 2024-02..."""

    QUARTER = "quarter"
    """Группировка по кварталам. Результат: 2024-Q1, 2024-Q2..."""

    YEAR = "year"
    """Группировка по годам. Результат: 2023, 2024..."""

    # === По категориям ===

    WEEKDAY = "weekday"
    """
    Группировка по дням недели.

    Результат: Monday, Tuesday, Wednesday, Thursday, Friday
    Используется для: "волатильность по дням недели"
    """

    SESSION = "session"
    """
    Группировка по торговым сессиям.

    Результат: RTH, ETH
    Используется для: "сравни объём RTH vs ETH"
    """

    def is_time_based(self) -> bool:
        """Проверяет, является ли группировка по времени суток."""
        return self in (
            Grouping.MINUTE_1,
            Grouping.MINUTE_5,
            Grouping.MINUTE_10,
            Grouping.MINUTE_15,
            Grouping.MINUTE_30,
            Grouping.HOUR,
        )

    def is_calendar_based(self) -> bool:
        """Проверяет, является ли группировка по календарным периодам."""
        return self in (
            Grouping.DAY,
            Grouping.WEEK,
            Grouping.MONTH,
            Grouping.QUARTER,
            Grouping.YEAR,
        )

    def get_interval(self) -> str | None:
        """Возвращает SQL INTERVAL для time_bucket или None."""
        intervals = {
            Grouping.MINUTE_1: "1 minute",
            Grouping.MINUTE_5: "5 minutes",
            Grouping.MINUTE_10: "10 minutes",
            Grouping.MINUTE_15: "15 minutes",
            Grouping.MINUTE_30: "30 minutes",
            Grouping.HOUR: "1 hour",
        }
        return intervals.get(self)


# =============================================================================
# METRICS — какие метрики считаем
# =============================================================================

class Metric(Enum):
    """
    Доступные метрики для расчёта.

    Делятся на три категории:
    1. Базовые OHLCV — значения из данных
    2. Производные — вычисляются из базовых
    3. Агрегатные — функции агрегации
    """

    # === Базовые OHLCV ===
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    VOLUME = "volume"

    # === Производные (вычисляются) ===
    RANGE = "range"
    """Диапазон дня: high - low"""

    CHANGE_PCT = "change_pct"
    """Изменение в процентах: (close - open) / open * 100"""

    GAP_PCT = "gap_pct"
    """Гэп в процентах: (open - prev_close) / prev_close * 100"""

    # === Computed columns (расстояния) ===
    CLOSE_TO_LOW = "close_to_low"
    """Расстояние от close до low: close - low"""

    CLOSE_TO_HIGH = "close_to_high"
    """Расстояние от close до high: high - close"""

    OPEN_TO_HIGH = "open_to_high"
    """Расстояние от open до high: high - open"""

    OPEN_TO_LOW = "open_to_low"
    """Расстояние от open до low: open - low"""

    BODY = "body"
    """Тело свечи: |close - open|"""

    # === Агрегатные функции ===
    COUNT = "count"
    """Количество записей"""

    AVG = "avg"
    """Среднее значение"""

    SUM = "sum"
    """Сумма"""

    MIN = "min"
    """Минимум"""

    MAX = "max"
    """Максимум"""

    STDDEV = "stddev"
    """Стандартное отклонение"""

    MEDIAN = "median"
    """Медиана"""

    def is_aggregate(self) -> bool:
        """Проверяет, является ли метрика агрегатной функцией."""
        return self in (
            Metric.COUNT,
            Metric.AVG,
            Metric.SUM,
            Metric.MIN,
            Metric.MAX,
            Metric.STDDEV,
            Metric.MEDIAN,
        )


@dataclass
class MetricSpec:
    """
    Спецификация метрики для расчёта.

    Attributes:
        metric: Какую метрику/функцию использовать
        column: Для агрегатов — к какой колонке применять.
                Например: AVG("range"), SUM("volume")
        alias: Название колонки в результате.
               Если не указано, генерируется автоматически.

    Examples:
        # Средний диапазон
        MetricSpec(Metric.AVG, "range", "avg_range")

        # Количество записей
        MetricSpec(Metric.COUNT, alias="trading_days")

        # Просто колонка close
        MetricSpec(Metric.CLOSE)
    """

    metric: Metric
    column: str | None = None
    alias: str | None = None

    def to_sql(self) -> str:
        """Генерирует SQL выражение для метрики."""
        m = self.metric
        col = self.column

        # Агрегатные функции
        if m == Metric.COUNT:
            expr = "COUNT(*)"
        elif m == Metric.AVG:
            expr = f"ROUND(AVG({col}), 2)" if col else "AVG(*)"
        elif m == Metric.SUM:
            expr = f"SUM({col})" if col else "SUM(*)"
        elif m == Metric.MIN:
            expr = f"MIN({col})" if col else "MIN(*)"
        elif m == Metric.MAX:
            expr = f"MAX({col})" if col else "MAX(*)"
        elif m == Metric.STDDEV:
            expr = f"ROUND(STDDEV({col}), 4)" if col else "STDDEV(*)"
        elif m == Metric.MEDIAN:
            expr = f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {col})" if col else "NULL"
        # Простые колонки
        else:
            expr = m.value

        # Добавляем alias если есть
        if self.alias:
            return f"{expr} as {self.alias}"
        return expr


# =============================================================================
# SPECIAL_OP — особые операции
# =============================================================================

class SpecialOp(Enum):
    """
    Специальные операции для сложных запросов.

    Обычные запросы: filter → group → aggregate
    Специальные требуют особой SQL логики.
    """

    NONE = "none"
    """Обычный запрос без специальной логики."""

    EVENT_TIME = "event_time"
    """
    Найти КОГДА событие произошло внутри группы.

    Пример: "в какое время формируется high дня"

    Логика:
    1. Для каждого дня найти минуту с MAX(high)
    2. Сгруппировать эти минуты в time buckets
    3. Посчитать частоту для каждого bucket

    Требует: EventTimeSpec с параметром find (high/low)
    """

    TOP_N = "top_n"
    """
    Вернуть топ N записей по метрике.

    Пример: "10 самых волатильных дней"

    Логика: ORDER BY metric DESC LIMIT N

    Требует: TopNSpec с параметрами n, order_by, direction
    """

    COMPARE = "compare"
    """
    Сравнить две или более категории.

    Пример: "сравни понедельник и пятницу"

    Логика: WHERE weekday IN (...) GROUP BY weekday

    Требует: CompareSpec со списком items для сравнения
    """

    FIND_EXTREMUM = "find_extremum"
    """
    Найти точное время и значение high/low.

    Пример: "во сколько был хай 10 января?"

    Логика:
    1. Для каждого дня найти минуту с MAX(high) или MIN(low)
    2. Вернуть timestamp + value (не распределение!)

    Отличие от EVENT_TIME:
    - EVENT_TIME: распределение по bucket'ам → frequency, percentage
    - FIND_EXTREMUM: точные значения → timestamp, value

    Требует: FindExtremumSpec с параметром find (high/low/both)
    """


@dataclass
class EventTimeSpec:
    """
    Параметры для операции EVENT_TIME.

    Находит распределение времени события по дням (когда ОБЫЧНО происходит).

    Attributes:
        find: Что ищем внутри каждого дня.
              "high" — момент максимальной цены
              "low" — момент минимальной цены
              "open" — момент открытия (первая минутка)
              "close" — момент закрытия (последняя минутка)
              "max_volume" — минута с максимальным объёмом
              "both" — high и low
              "all" — open + high + low + close + max_volume
    """

    find: Literal["high", "low", "open", "close", "max_volume", "both", "all"]


@dataclass
class TopNSpec:
    """
    Параметры для операции TOP_N.

    Attributes:
        n: Количество записей для возврата (топ N)
        order_by: По какой колонке сортировать
        direction: Направление сортировки (DESC = от большего)
    """

    n: int
    order_by: str
    direction: Literal["DESC", "ASC"] = "DESC"


@dataclass
class CompareSpec:
    """
    Параметры для операции COMPARE.

    Attributes:
        items: Список элементов для сравнения.
               Например: ["Monday", "Friday"] или ["RTH", "ETH"]
    """

    items: list[str]


@dataclass
class FindExtremumSpec:
    """
    Параметры для операции FIND_EXTREMUM.

    Находит точное время и значение события для конкретных дней.

    Attributes:
        find: Что ищем.
              "high" — время и значение максимума
              "low" — время и значение минимума
              "open" — время и цена открытия (первая минутка)
              "close" — время и цена закрытия (последняя минутка)
              "max_volume" — минута с максимальным объёмом
              "both" — high и low
              "ohlc" — open + high + low + close
              "all" — open + high + low + close + max_volume

    Example output:
        {"date": "2025-01-10", "high_time": "06:12:00", "high_value": 21543.25,
         "low_time": "10:15:00", "low_value": 21234.50}
    """

    find: Literal["high", "low", "open", "close", "max_volume", "both", "ohlc", "all"]


# =============================================================================
# QUERY SPEC — полная спецификация запроса
# =============================================================================

@dataclass
class QuerySpec:
    """
    Полная спецификация запроса от Understander.

    QueryBuilder использует эту структуру для генерации SQL.
    Все поля типизированы — невозможно передать невалидные данные.

    Attributes:
        symbol: Торговый инструмент (NQ, ES, CL)
        source: Откуда данные (minutes, daily, daily_with_prev)
        filters: Фильтры (период, время, условия)
        grouping: Способ группировки результатов
        metrics: Список метрик для расчёта
        special_op: Специальная операция (если нужна)
        event_time_spec: Параметры для EVENT_TIME
        top_n_spec: Параметры для TOP_N
        compare_spec: Параметры для COMPARE
        order_by: Колонка для сортировки
        order_direction: Направление сортировки
        limit: Ограничение количества строк

    Example:
        # "Найди дни когда NQ упал больше 2%"
        QuerySpec(
            symbol="NQ",
            source=Source.DAILY,
            filters=Filters(
                period_start="2020-01-01",
                period_end="2025-01-01",
                conditions=[Condition("change_pct", "<", -2.0)],
            ),
            grouping=Grouping.NONE,
            metrics=[
                MetricSpec(Metric.OPEN),
                MetricSpec(Metric.CLOSE),
                MetricSpec(Metric.CHANGE_PCT),
            ],
            order_by="date",
        )
    """

    # === Обязательные поля ===
    symbol: str
    source: Source
    filters: Filters

    # === Группировка и метрики ===
    grouping: Grouping = Grouping.NONE
    metrics: list[MetricSpec] = field(default_factory=list)

    # === Специальные операции ===
    special_op: SpecialOp = SpecialOp.NONE
    event_time_spec: EventTimeSpec | None = None
    top_n_spec: TopNSpec | None = None
    compare_spec: CompareSpec | None = None
    find_extremum_spec: FindExtremumSpec | None = None

    # === Сортировка и лимит ===
    order_by: str | None = None
    order_direction: Literal["ASC", "DESC"] = "ASC"
    limit: int | None = None

    def validate(self) -> list[str]:
        """
        Проверяет корректность спецификации.

        Returns:
            Список ошибок (пустой если всё ок)
        """
        errors = []

        # Проверка специальных операций
        if self.special_op == SpecialOp.EVENT_TIME and not self.event_time_spec:
            errors.append("EVENT_TIME требует event_time_spec")

        if self.special_op == SpecialOp.TOP_N and not self.top_n_spec:
            errors.append("TOP_N требует top_n_spec")

        if self.special_op == SpecialOp.COMPARE and not self.compare_spec:
            errors.append("COMPARE требует compare_spec")

        if self.special_op == SpecialOp.FIND_EXTREMUM and not self.find_extremum_spec:
            errors.append("FIND_EXTREMUM требует find_extremum_spec")

        # EVENT_TIME требует группировку по времени
        if self.special_op == SpecialOp.EVENT_TIME:
            if not self.grouping.is_time_based():
                errors.append(
                    "EVENT_TIME требует группировку по времени "
                    "(MINUTE_5, MINUTE_15, HOUR и т.д.)"
                )

        # EVENT_TIME требует Source.MINUTES
        if self.special_op == SpecialOp.EVENT_TIME:
            if self.source != Source.MINUTES:
                errors.append("EVENT_TIME требует source=MINUTES")

        # FIND_EXTREMUM требует Source.MINUTES
        if self.special_op == SpecialOp.FIND_EXTREMUM:
            if self.source != Source.MINUTES:
                errors.append("FIND_EXTREMUM требует source=MINUTES")

        return errors
