"""
Query Builder — главный класс для построения SQL из QuerySpec.

Принимает структурированную спецификацию запроса (QuerySpec)
и генерирует валидный SQL для DuckDB.

Архитектура:
    QuerySpec → QueryBuilder.build() → SQL string

Принципы:
    1. Детерминированность: один QuerySpec = один SQL
    2. Валидность: сгенерированный SQL всегда синтаксически корректен
    3. Модульность: каждый "кубик" собирается отдельным методом
"""

from __future__ import annotations

from .types import (
    QuerySpec,
    Source,
    Filters,
    Grouping,
    SpecialOp,
)


class QueryBuilder:
    """
    Строит SQL запросы из QuerySpec.

    Использование:
        spec = QuerySpec(...)
        builder = QueryBuilder()
        sql = builder.build(spec)

    QueryBuilder не хранит состояние между вызовами —
    можно использовать один инстанс для многих запросов.
    """

    def build(self, spec: QuerySpec) -> str:
        """
        Главный метод — строит SQL из спецификации.

        Args:
            spec: Полная спецификация запроса

        Returns:
            SQL строка (без точки с запятой в конце)

        Raises:
            ValueError: Если спецификация невалидна
        """
        # Валидация
        errors = spec.validate()
        if errors:
            raise ValueError(f"Invalid QuerySpec: {', '.join(errors)}")

        # Выбираем стратегию построения в зависимости от special_op
        if spec.special_op == SpecialOp.EVENT_TIME:
            return self._build_event_time_query(spec)
        elif spec.special_op == SpecialOp.TOP_N:
            return self._build_top_n_query(spec)
        elif spec.special_op == SpecialOp.COMPARE:
            return self._build_compare_query(spec)
        else:
            return self._build_standard_query(spec)

    # =========================================================================
    # Стандартный запрос (без специальных операций)
    # =========================================================================

    def _build_standard_query(self, spec: QuerySpec) -> str:
        """
        Строит стандартный запрос: CTE → SELECT → WHERE → GROUP BY.

        Используется когда special_op == NONE.
        """
        parts = []

        # 1. CTE (Common Table Expression) — базовые данные
        cte = self._build_source_cte(spec)
        parts.append(cte)

        # 2. SELECT с метриками
        select = self._build_select(spec)
        parts.append(select)

        # 3. FROM
        parts.append(self._get_cte_name(spec.source))

        # 4. WHERE (условия из filters)
        where = self._build_where_conditions(spec)
        if where:
            parts.append(f"WHERE {where}")

        # 5. GROUP BY (если есть группировка)
        group_by = self._build_group_by(spec)
        if group_by:
            parts.append(f"GROUP BY {group_by}")

        # 6. ORDER BY
        order_by = self._build_order_by(spec)
        if order_by:
            parts.append(f"ORDER BY {order_by}")

        # 7. LIMIT
        if spec.limit:
            parts.append(f"LIMIT {spec.limit}")

        return self._join_parts(parts)

    # =========================================================================
    # EVENT_TIME запрос (когда формируется high/low)
    # =========================================================================

    def _build_event_time_query(self, spec: QuerySpec) -> str:
        """
        Строит запрос для поиска времени события.

        Логика:
        1. filtered_data: минутки с фильтрами по периоду и времени
        2. daily_extremes: для каждого дня находим timestamp high/low
        3. distribution: группируем по time_bucket, считаем частоту
        """
        event = spec.event_time_spec
        find_col = event.find  # "high" или "low"
        interval = spec.grouping.get_interval()

        # Определяем ORDER BY для поиска экстремума
        if find_col == "high":
            order_clause = "high DESC, timestamp ASC"
        else:  # low
            order_clause = "low ASC, timestamp ASC"

        # Строим CTE для filtered_data
        time_filter = self._build_time_filter_sql(spec.filters)
        time_where = f"AND {time_filter}" if time_filter else ""

        sql = f"""WITH filtered_data AS (
    -- Минутные данные с фильтрами
    SELECT
        timestamp,
        timestamp::date as date,
        high,
        low
    FROM ohlcv_1min
    WHERE symbol = '{spec.symbol}'
      AND timestamp >= '{spec.filters.period_start}'
      AND timestamp < '{spec.filters.period_end}'
      {time_where}
),
daily_extremes AS (
    -- Для каждого дня находим момент экстремума
    SELECT
        date,
        FIRST(timestamp ORDER BY {order_clause}) as event_ts
    FROM filtered_data
    GROUP BY date
),
distribution AS (
    -- Группируем по временным интервалам
    SELECT
        STRFTIME(TIME_BUCKET(INTERVAL '{interval}', event_ts), '%H:%M') as time_bucket,
        COUNT(*) as frequency
    FROM daily_extremes
    GROUP BY time_bucket
)
SELECT
    time_bucket,
    frequency,
    ROUND(frequency * 100.0 / SUM(frequency) OVER (), 2) as percentage
FROM distribution
ORDER BY time_bucket"""

        return sql

    # =========================================================================
    # TOP_N запрос (топ N записей)
    # =========================================================================

    def _build_top_n_query(self, spec: QuerySpec) -> str:
        """
        Строит запрос для получения топ N записей.

        По сути стандартный запрос с ORDER BY и LIMIT.
        """
        top_n = spec.top_n_spec

        # Создаём модифицированную спецификацию
        # с нужными order_by и limit
        modified_spec = QuerySpec(
            symbol=spec.symbol,
            source=spec.source,
            filters=spec.filters,
            grouping=spec.grouping,
            metrics=spec.metrics,
            special_op=SpecialOp.NONE,  # Убираем special_op
            order_by=top_n.order_by,
            order_direction=top_n.direction,
            limit=top_n.n,
        )

        return self._build_standard_query(modified_spec)

    # =========================================================================
    # COMPARE запрос (сравнение категорий)
    # =========================================================================

    def _build_compare_query(self, spec: QuerySpec) -> str:
        """
        Строит запрос для сравнения категорий.

        Добавляет фильтр по категориям из compare_spec.
        """
        # TODO: Реализовать COMPARE
        # Пока делегируем к стандартному запросу
        return self._build_standard_query(spec)

    # =========================================================================
    # Вспомогательные методы: CTE
    # =========================================================================

    def _build_source_cte(self, spec: QuerySpec) -> str:
        """
        Строит CTE для источника данных.

        Возвращает WITH ... AS (...) часть запроса.
        """
        source = spec.source
        symbol = spec.symbol
        period_start = spec.filters.period_start
        period_end = spec.filters.period_end

        if source == Source.MINUTES:
            # Для минуток — простой SELECT из ohlcv_1min
            time_filter = self._build_time_filter_sql(spec.filters)
            time_where = f"AND {time_filter}" if time_filter else ""

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
    FROM ohlcv_1min
    WHERE symbol = '{symbol}'
      AND timestamp >= '{period_start}'
      AND timestamp < '{period_end}'
      {time_where}
)
SELECT"""

        elif source == Source.DAILY:
            return f"""WITH daily AS (
    SELECT
        timestamp::date as date,
        FIRST(open ORDER BY timestamp) as open,
        MAX(high) as high,
        MIN(low) as low,
        LAST(close ORDER BY timestamp) as close,
        SUM(volume) as volume,
        ROUND(MAX(high) - MIN(low), 2) as range,
        ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
              / FIRST(open ORDER BY timestamp) * 100, 2) as change_pct
    FROM ohlcv_1min
    WHERE symbol = '{symbol}'
      AND timestamp >= '{period_start}'
      AND timestamp < '{period_end}'
    GROUP BY timestamp::date
)
SELECT"""

        elif source == Source.DAILY_WITH_PREV:
            return f"""WITH daily AS (
    SELECT
        timestamp::date as date,
        FIRST(open ORDER BY timestamp) as open,
        MAX(high) as high,
        MIN(low) as low,
        LAST(close ORDER BY timestamp) as close,
        SUM(volume) as volume,
        ROUND(MAX(high) - MIN(low), 2) as range,
        ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
              / FIRST(open ORDER BY timestamp) * 100, 2) as change_pct
    FROM ohlcv_1min
    WHERE symbol = '{symbol}'
      AND timestamp >= '{period_start}'
      AND timestamp < '{period_end}'
    GROUP BY timestamp::date
),
daily_with_prev AS (
    SELECT
        *,
        LAG(close) OVER (ORDER BY date) as prev_close,
        LAG(change_pct) OVER (ORDER BY date) as prev_change_pct,
        ROUND((open - LAG(close) OVER (ORDER BY date))
              / LAG(close) OVER (ORDER BY date) * 100, 2) as gap_pct
    FROM daily
)
SELECT"""

        raise ValueError(f"Unknown source: {source}")

    def _get_cte_name(self, source: Source) -> str:
        """Возвращает имя CTE для источника."""
        names = {
            Source.MINUTES: "minutes",
            Source.DAILY: "daily",
            Source.DAILY_WITH_PREV: "daily_with_prev",
        }
        return f"FROM {names[source]}"

    # =========================================================================
    # Вспомогательные методы: SELECT, WHERE, GROUP BY, ORDER BY
    # =========================================================================

    def _build_select(self, spec: QuerySpec) -> str:
        """Строит SELECT часть запроса."""
        columns = []

        # Добавляем группирующую колонку
        group_col = self._get_grouping_column(spec.grouping)
        if group_col:
            columns.append(group_col)

        # Если нет метрик и нет группировки — выбираем все колонки
        if not spec.metrics and spec.grouping == Grouping.NONE:
            return "*"

        # Если нет метрик но есть группировка — ошибка
        if not spec.metrics and spec.grouping != Grouping.NONE:
            columns.append("COUNT(*) as count")
        else:
            # Добавляем метрики
            for m in spec.metrics:
                columns.append(m.to_sql())

        return ",\n    ".join(columns)

    def _build_where_conditions(self, spec: QuerySpec) -> str:
        """Строит WHERE часть из conditions в filters."""
        conditions = []

        for cond in spec.filters.conditions:
            conditions.append(cond.to_sql())

        return " AND ".join(conditions) if conditions else ""

    def _build_group_by(self, spec: QuerySpec) -> str:
        """Строит GROUP BY часть запроса."""
        grouping = spec.grouping

        if grouping in (Grouping.NONE, Grouping.TOTAL):
            return ""

        return self._get_grouping_expression(grouping)

    def _build_order_by(self, spec: QuerySpec) -> str:
        """Строит ORDER BY часть запроса."""
        if spec.order_by:
            return f"{spec.order_by} {spec.order_direction}"

        # Дефолтная сортировка по группирующей колонке
        grouping = spec.grouping
        if grouping == Grouping.NONE:
            return "date" if spec.source != Source.MINUTES else "timestamp"

        return self._get_grouping_expression(grouping)

    # =========================================================================
    # Вспомогательные методы: Grouping
    # =========================================================================

    def _get_grouping_column(self, grouping: Grouping) -> str:
        """Возвращает колонку для SELECT при группировке."""
        if grouping == Grouping.NONE:
            return "date"
        elif grouping == Grouping.TOTAL:
            return ""
        elif grouping == Grouping.DAY:
            return "date"
        elif grouping == Grouping.WEEK:
            return "STRFTIME(date, '%Y-W%W') as week"
        elif grouping == Grouping.MONTH:
            return "STRFTIME(date, '%Y-%m') as month"
        elif grouping == Grouping.QUARTER:
            return "CONCAT(YEAR(date), '-Q', QUARTER(date)) as quarter"
        elif grouping == Grouping.YEAR:
            return "YEAR(date) as year"
        elif grouping == Grouping.WEEKDAY:
            return "DAYNAME(date) as weekday, DAYOFWEEK(date) as day_num"
        elif grouping == Grouping.SESSION:
            return """CASE
        WHEN time BETWEEN '09:30:00' AND '16:00:00' THEN 'RTH'
        ELSE 'ETH'
    END as session"""
        elif grouping.is_time_based():
            interval = grouping.get_interval()
            return f"TIME_BUCKET(INTERVAL '{interval}', timestamp)::time as time_bucket"

        return ""

    def _get_grouping_expression(self, grouping: Grouping) -> str:
        """Возвращает выражение для GROUP BY."""
        if grouping == Grouping.DAY:
            return "date"
        elif grouping == Grouping.WEEK:
            return "STRFTIME(date, '%Y-W%W')"
        elif grouping == Grouping.MONTH:
            return "STRFTIME(date, '%Y-%m')"
        elif grouping == Grouping.QUARTER:
            return "YEAR(date), QUARTER(date)"
        elif grouping == Grouping.YEAR:
            return "YEAR(date)"
        elif grouping == Grouping.WEEKDAY:
            return "DAYOFWEEK(date), DAYNAME(date)"
        elif grouping == Grouping.SESSION:
            return "session"
        elif grouping.is_time_based():
            interval = grouping.get_interval()
            return f"TIME_BUCKET(INTERVAL '{interval}', timestamp)"

        return ""

    # =========================================================================
    # Вспомогательные методы: Time Filters
    # =========================================================================

    def _build_time_filter_sql(self, filters: Filters) -> str:
        """
        Строит SQL для фильтра по времени суток.

        Использует TRADING_SESSIONS из types.py.
        Корректно обрабатывает сессии пересекающие полночь через OR.

        Returns:
            SQL выражение или пустую строку
        """
        from agent.query_builder.types import TRADING_SESSIONS

        # ETH — особый случай (NOT BETWEEN)
        if filters.session == "ETH":
            return "timestamp::time NOT BETWEEN '09:30:00' AND '16:00:00'"

        # Получаем временной диапазон из session или time_start/time_end
        time_filter = filters.get_time_filter()
        if not time_filter:
            return ""

        start_time, end_time = time_filter

        # Проверяем пересечение полночи (end < start)
        if filters.crosses_midnight():
            # Сессия пересекает полночь: 18:00-03:00
            # → (time >= '18:00:00' OR time < '03:00:00')
            return f"(timestamp::time >= '{start_time}' OR timestamp::time < '{end_time}')"
        else:
            # Обычная сессия: 09:30-16:00
            return f"timestamp::time BETWEEN '{start_time}' AND '{end_time}'"

    # =========================================================================
    # Утилиты
    # =========================================================================

    def _join_parts(self, parts: list[str]) -> str:
        """Соединяет части SQL в один запрос."""
        # Убираем пустые части
        parts = [p for p in parts if p]

        # Соединяем CTE и SELECT особым образом
        result = []
        for part in parts:
            if part.startswith("WITH"):
                result.append(part)
            elif part.startswith("FROM"):
                result.append(part)
            elif part.startswith("WHERE"):
                result.append(part)
            elif part.startswith("GROUP BY"):
                result.append(part)
            elif part.startswith("ORDER BY"):
                result.append(part)
            elif part.startswith("LIMIT"):
                result.append(part)
            else:
                # SELECT часть — добавляем с отступом
                result.append(f"    {part}")

        return "\n".join(result)
