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

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# PARSED QUERY — Parser → Composer contract
# =============================================================================

class ParsedPeriod(BaseModel):
    """Period extracted from user question."""

    raw: str | None = None
    start: str | None = None  # YYYY-MM-DD, inclusive
    end: str | None = None    # YYYY-MM-DD, inclusive
    dates: list[str] | None = None  # specific dates


class ParsedFilters(BaseModel):
    """Filters extracted from user question."""

    weekdays: list[str] | None = None
    months: list[int] | None = None
    session: str | None = None
    time_start: str | None = None  # HH:MM for calendar day
    time_end: str | None = None    # HH:MM for calendar day
    conditions: list[str] | None = None  # raw strings like "close - low >= 200"
    event_filter: str | None = None  # "opex", "nfp", "quad_witching", "fomc", etc.


class ParsedModifiers(BaseModel):
    """Query modifiers: grouping, top_n, compare."""

    group_by: str | None = None
    top_n: int | None = None
    compare: list[str] | None = None


class ParsedQuery(BaseModel):
    """
    Parser output — structured extraction from user question.

    This is the contract between Parser (LLM) and Composer (code).
    Parser fills this, Composer validates and converts to QuerySpec.
    """

    what: str  # "statistics", "day data", "range comparison", "explain gap", "greeting"
    period: ParsedPeriod | None = None
    filters: ParsedFilters | None = None
    modifiers: ParsedModifiers | None = None
    unclear: list[str] = Field(default_factory=list)  # fields needing clarification
    summary: str = ""  # human-readable summary

    def merge_with(self, new: "ParsedQuery") -> "ParsedQuery":
        """Merge new parsed data with this (base) data.

        Used in clarification flow: base contains previously resolved data,
        new contains freshly parsed data. New values take priority,
        base provides fallback for missing fields.
        """
        merged_period = None
        if new.period or self.period:
            new_p = new.period or ParsedPeriod()
            base_p = self.period or ParsedPeriod()
            merged_period = ParsedPeriod(
                raw=new_p.raw or base_p.raw,
                start=new_p.start or base_p.start,
                end=new_p.end or base_p.end,
                dates=new_p.dates or base_p.dates,
            )

        merged_filters = None
        if new.filters or self.filters:
            new_f = new.filters or ParsedFilters()
            base_f = self.filters or ParsedFilters()
            merged_filters = ParsedFilters(
                weekdays=new_f.weekdays or base_f.weekdays,
                months=new_f.months or base_f.months,
                session=new_f.session or base_f.session,
                time_start=new_f.time_start or base_f.time_start,
                time_end=new_f.time_end or base_f.time_end,
                conditions=new_f.conditions or base_f.conditions,
                event_filter=new_f.event_filter or base_f.event_filter,
            )

        merged_modifiers = None
        if new.modifiers or self.modifiers:
            new_m = new.modifiers or ParsedModifiers()
            base_m = self.modifiers or ParsedModifiers()
            merged_modifiers = ParsedModifiers(
                group_by=new_m.group_by or base_m.group_by,
                top_n=new_m.top_n or base_m.top_n,
                compare=new_m.compare or base_m.compare,
            )

        return ParsedQuery(
            what=new.what or self.what,
            period=merged_period,
            filters=merged_filters,
            modifiers=merged_modifiers,
            unclear=new.unclear,
            summary=new.summary,
        )


class ClarificationState(BaseModel):
    """Holds resolved data between clarification rounds.

    Instead of relying on LLM to extract context from chat history,
    we preserve parsed data across rounds deterministically.

    Usage:
        r1 = barb.ask("what was jan 10")  # returns state
        r2 = barb.ask("2024", state=r1.state)  # merges with previous
    """

    original_question: str
    resolved: ParsedQuery | None = None


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

class Condition(BaseModel):
    """Filter condition: column operator value (e.g. change_pct < -2.0)."""

    column: str
    operator: Literal[">", "<", ">=", "<=", "==", "!="]
    value: float

    def to_sql(self) -> str:
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
#   from agent.market.instruments import get_session_times
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


class PeriodFilter(BaseModel):
    """Period boundaries for the query."""

    start: str  # YYYY-MM-DD, inclusive
    end: str    # YYYY-MM-DD, exclusive for MINUTES source
    specific_dates: list[str] | None = None  # Overrides start/end if set


class CalendarFilter(BaseModel):
    """Calendar-based filters: years, months, weekdays."""

    years: list[int] | None = None
    months: list[int] | None = None
    weekdays: list[str] | None = None


class TimeFilter(BaseModel):
    """Intraday time filters: session or explicit time range."""

    session: SessionType | None = None  # RTH, ETH, OVERNIGHT
    start: str | None = None  # HH:MM
    end: str | None = None    # HH:MM


class HolidaysConfig(BaseModel):
    """Holiday filtering configuration."""

    market_holidays: HolidayFilter = HolidayFilter.INCLUDE
    early_close_days: HolidayFilter = HolidayFilter.INCLUDE


class Filters(BaseModel):
    """Query filters: period, calendar, time, conditions, holidays.

    Structured into logical groups for scalability:
    - period: date range boundaries
    - calendar: year/month/weekday filters
    - time: session or explicit time range
    - conditions: price/volume conditions
    - holidays: holiday handling config
    """

    period: PeriodFilter
    calendar: CalendarFilter | None = None
    time: TimeFilter | None = None
    conditions: list[Condition] = Field(default_factory=list)
    holidays: HolidaysConfig = Field(default_factory=HolidaysConfig)

    # === Backward compatibility properties ===
    # TODO: Remove after all usages migrated to new structure

    @property
    def period_start(self) -> str:
        return self.period.start

    @property
    def period_end(self) -> str:
        return self.period.end

    @property
    def specific_dates(self) -> list[str] | None:
        return self.period.specific_dates

    @property
    def years(self) -> list[int] | None:
        return self.calendar.years if self.calendar else None

    @property
    def months(self) -> list[int] | None:
        return self.calendar.months if self.calendar else None

    @property
    def weekdays(self) -> list[str] | None:
        return self.calendar.weekdays if self.calendar else None

    @property
    def session(self) -> SessionType | None:
        return self.time.session if self.time else None

    @property
    def time_start(self) -> str | None:
        return self.time.start if self.time else None

    @property
    def time_end(self) -> str | None:
        return self.time.end if self.time else None

    @property
    def market_holidays(self) -> HolidayFilter:
        return self.holidays.market_holidays

    @property
    def early_close_days(self) -> HolidayFilter:
        return self.holidays.early_close_days


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


class MetricSpec(BaseModel):
    """Metric specification: what to calculate and how to name it."""

    metric: Metric
    column: str | None = None
    alias: str | None = None

    def to_sql(self) -> str:
        m = self.metric
        col = self.column

        aggregate_map = {
            Metric.COUNT: "COUNT(*)",
            Metric.AVG: f"ROUND(AVG({col}), 2)" if col else "AVG(*)",
            Metric.SUM: f"SUM({col})" if col else "SUM(*)",
            Metric.MIN: f"MIN({col})" if col else "MIN(*)",
            Metric.MAX: f"MAX({col})" if col else "MAX(*)",
            Metric.STDDEV: f"ROUND(STDDEV({col}), 4)" if col else "STDDEV(*)",
            Metric.MEDIAN: f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {col})" if col else "NULL",
        }

        expr = aggregate_map.get(m, m.value)
        return f"{expr} as {self.alias}" if self.alias else expr


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


class EventTimeSpec(BaseModel):
    """When does event usually occur? Finds time distribution across days."""

    find: Literal["high", "low", "open", "close", "max_volume", "both", "all"]


class TopNSpec(BaseModel):
    """Top N records by metric."""

    n: int
    order_by: str
    direction: Literal["DESC", "ASC"] = "DESC"


class CompareSpec(BaseModel):
    """Compare categories (e.g. Monday vs Friday, RTH vs ETH)."""

    items: list[str]


class FindExtremumSpec(BaseModel):
    """Find exact time and value of high/low for specific days."""

    find: Literal["high", "low", "open", "close", "max_volume", "both", "ohlc", "all"]


# =============================================================================
# QUERY SPEC — полная спецификация запроса
# =============================================================================

class QuerySpec(BaseModel):
    """Full query specification: source, filters, grouping, metrics, special ops."""

    symbol: str
    source: Source
    filters: Filters

    grouping: Grouping = Grouping.NONE
    metrics: list[MetricSpec] = Field(default_factory=list)

    special_op: SpecialOp = SpecialOp.NONE
    event_time_spec: EventTimeSpec | None = None
    top_n_spec: TopNSpec | None = None
    compare_spec: CompareSpec | None = None
    find_extremum_spec: FindExtremumSpec | None = None

    order_by: str | None = None
    order_direction: Literal["ASC", "DESC"] = "ASC"
    limit: int | None = None

    def validate(self) -> list[str]:
        """Check spec consistency. Returns list of errors (empty if valid)."""
        errors = []

        spec_requirements = {
            SpecialOp.EVENT_TIME: ("event_time_spec", self.event_time_spec),
            SpecialOp.TOP_N: ("top_n_spec", self.top_n_spec),
            SpecialOp.COMPARE: ("compare_spec", self.compare_spec),
            SpecialOp.FIND_EXTREMUM: ("find_extremum_spec", self.find_extremum_spec),
        }

        if self.special_op in spec_requirements:
            spec_name, spec_value = spec_requirements[self.special_op]
            if not spec_value:
                errors.append(f"{self.special_op.name} requires {spec_name}")

        if self.special_op == SpecialOp.EVENT_TIME:
            if not self.grouping.is_time_based():
                errors.append("EVENT_TIME requires time-based grouping (HOUR, MINUTE_5, etc.)")
            if self.source != Source.MINUTES:
                errors.append("EVENT_TIME requires source=MINUTES")

        if self.special_op == SpecialOp.FIND_EXTREMUM and self.source != Source.MINUTES:
            errors.append("FIND_EXTREMUM requires source=MINUTES")

        # Time-based grouping requires minute data with timestamp column
        if self.grouping.is_time_based() and self.source != Source.MINUTES:
            errors.append(f"Time-based grouping ({self.grouping.value}) requires source=MINUTES")

        return errors
