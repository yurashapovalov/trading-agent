"""
Query Builder Types — все типы данных для построения SQL запросов.

Этот модуль определяет "кубики" из которых собираются запросы:
- Source: откуда берём данные (минутки, дневки)
- Filters: как фильтруем (период, время, условия)
- Grouping: как группируем результат
- Metrics: какие метрики считаем
- SpecialOp: особые операции (EVENT_TIME, TOP_N, COMPARE)

Understander возвращает QuerySpec, QueryBuilder превращает его в SQL.
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

# Все временные интервалы в ET (Eastern Time)
TRADING_SESSIONS = {
    # Основные сессии
    "RTH": ("09:30:00", "16:00:00"),       # Regular Trading Hours (основная)
    "ETH": None,                            # Extended = всё кроме RTH (NOT BETWEEN)
    "OVERNIGHT": ("18:00:00", "09:30:00"),  # Ночная сессия (crosses midnight)
    "GLOBEX": ("18:00:00", "17:00:00"),     # Полная сессия CME Globex (почти 24ч)

    # Региональные сессии
    "ASIAN": ("18:00:00", "03:00:00"),      # Азиатская сессия
    "EUROPEAN": ("03:00:00", "09:30:00"),   # Европейская/Лондон сессия
    "US": ("09:30:00", "16:00:00"),         # US сессия (= RTH)

    # Части дня
    "PREMARKET": ("04:00:00", "09:30:00"),  # Пре-маркет
    "POSTMARKET": ("16:00:00", "20:00:00"), # Пост-маркет / after-hours
    "MORNING": ("09:30:00", "12:00:00"),    # Утренняя сессия RTH
    "AFTERNOON": ("12:00:00", "16:00:00"),  # Дневная сессия RTH
    "LUNCH": ("12:00:00", "14:00:00"),      # Обеденное время (низкая активность)

    # Открытия рынков (первый час)
    "LONDON_OPEN": ("03:00:00", "04:00:00"),  # Открытие Лондона
    "NY_OPEN": ("09:30:00", "10:30:00"),      # Открытие Нью-Йорка (первый час)
    "NY_CLOSE": ("15:00:00", "16:00:00"),     # Закрытие Нью-Йорка (последний час)
}

# Type для session field
SessionType = Literal[
    "RTH", "ETH", "OVERNIGHT", "GLOBEX",
    "ASIAN", "EUROPEAN", "US",
    "PREMARKET", "POSTMARKET", "MORNING", "AFTERNOON", "LUNCH",
    "LONDON_OPEN", "NY_OPEN", "NY_CLOSE",
]


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

    Example:
        # Январь 2024, только RTH сессия, дни с падением > 1%
        Filters(
            period_start="2024-01-01",
            period_end="2024-02-01",
            session="RTH",
            conditions=[Condition("change_pct", "<", -1.0)]
        )

        # Вторники и пятницы за 2020, 2022, 2024 годы
        Filters(
            period_start="2020-01-01",
            period_end="2025-01-01",
            years=[2020, 2022, 2024],
            weekdays=["Tuesday", "Friday"]
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

    def get_time_filter(self) -> tuple[str, str] | None:
        """
        Возвращает временной фильтр (start, end) или None.

        Приоритет: session > time_start/time_end

        Note: Для сессий пересекающих полночь (OVERNIGHT, ASIAN, GLOBEX)
              end_time < start_time — QueryBuilder должен обрабатывать это
              через OR условие.
        """
        if self.session:
            return TRADING_SESSIONS.get(self.session)

        if self.time_start and self.time_end:
            return (self.time_start, self.time_end)

        return None

    def crosses_midnight(self) -> bool:
        """Проверяет, пересекает ли сессия полночь."""
        time_filter = self.get_time_filter()
        if not time_filter:
            return False
        start, end = time_filter
        return end < start  # 18:00 - 03:00 → True


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

    Attributes:
        find: Что ищем внутри каждого дня.
              "high" — момент максимальной цены
              "low" — момент минимальной цены
              "both" — и high и low (возвращает обе колонки)
    """

    find: Literal["high", "low", "both"]


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

    Находит точное время и значение high/low для конкретных дней.

    Attributes:
        find: Что ищем.
              "high" — время и значение максимума
              "low" — время и значение минимума
              "both" — и high и low

    Example output:
        {"date": "2025-01-10", "high_time": "06:12:00", "high_value": 21543.25,
         "low_time": "10:15:00", "low_value": 21234.50}
    """

    find: Literal["high", "low", "both"]


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
