"""QueryBuilder - deterministically converts QuerySpec to SQL.

Uses Registry pattern for extensibility:
- SourceRegistry: Builders for different data sources (daily, minutes)
- SpecialOpRegistry: Builders for special operations (event_time, find_extremum)

Adding new building blocks:
    1. Create class in appropriate directory
    2. Inherit from base class
    3. Add @Registry.register decorator
    4. Done - builder finds it automatically

Architecture:
    QuerySpec → QueryBuilder.build() → SQL string

Example:
    builder = QueryBuilder()
    sql = builder.build(spec)  # Always valid SQL, deterministic
"""

from __future__ import annotations

from .types import (
    QuerySpec,
    Source,
    Grouping,
    SpecialOp,
)

# Registries
from .source import SourceRegistry
from .special_ops import SpecialOpRegistry
from .special_ops.top_n import TopNOpBuilder

# Filters
from .filters import (
    build_all_filters_sql,
    build_calendar_filters_sql,
)

# Grouping
from .grouping import (
    get_grouping_column,
    get_grouping_expression,
)


class QueryBuilder:
    """Builds SQL queries from QuerySpec deterministically.

    Stateless - single instance can be reused for multiple queries.
    Uses Registry pattern to find appropriate builders for sources and special ops.

    Example:
        builder = QueryBuilder()
        sql = builder.build(spec)
    """

    def build(self, spec: QuerySpec) -> str:
        """Build SQL from QuerySpec.

        Args:
            spec: Complete query specification with source, filters, metrics.

        Returns:
            Valid DuckDB SQL string.

        Raises:
            ValueError: If spec validation fails.
        """
        # Валидация
        errors = spec.validate()
        if errors:
            raise ValueError(f"Invalid QuerySpec: {', '.join(errors)}")

        # Проверяем special_op через registry
        if spec.special_op == SpecialOp.TOP_N:
            # TOP_N — особый случай: трансформирует spec, использует стандартный builder
            modified_spec = TopNOpBuilder.transform_spec(spec)
            return self._build_standard_query(modified_spec)

        if spec.special_op != SpecialOp.NONE:
            special_builder = SpecialOpRegistry.get(spec.special_op)
            if special_builder:
                extra_filters = build_all_filters_sql(
                    spec.filters, "timestamp::date", symbol=spec.symbol
                )
                return special_builder.build_query(spec, extra_filters)

        # Стандартный запрос
        return self._build_standard_query(spec)

    # =========================================================================
    # Standard Query Building
    # =========================================================================

    def _build_standard_query(self, spec: QuerySpec) -> str:
        """Build standard query: CTE → SELECT → WHERE → GROUP BY."""
        parts = []

        # 1. CTE через registry
        cte = self._build_source_cte(spec)
        parts.append(cte)

        # 2. SELECT с метриками
        select = self._build_select(spec)
        parts.append(select)

        # 3. FROM
        source_builder = SourceRegistry.get_or_raise(spec.source)
        parts.append(f"FROM {source_builder.cte_name}")

        # 4. WHERE
        where = self._build_where_conditions(spec)
        if where:
            parts.append(f"WHERE {where}")

        # 5. GROUP BY
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
    # CTE Building via Registry
    # =========================================================================

    def _build_source_cte(self, spec: QuerySpec) -> str:
        """Build CTE using SourceRegistry."""
        source_builder = SourceRegistry.get_or_raise(spec.source)

        # Определяем какие фильтры передавать
        if spec.source == Source.MINUTES:
            extra_sql = build_all_filters_sql(
                spec.filters, "timestamp::date", symbol=spec.symbol
            )
        else:
            # Для daily/daily_with_prev — календарные + holiday фильтры
            extra_sql = build_all_filters_sql(
                spec.filters, "date", prefix_and=False, symbol=spec.symbol
            )

        return source_builder.build_cte(spec.symbol, spec.filters, extra_sql)

    # =========================================================================
    # SELECT, WHERE, GROUP BY, ORDER BY
    # =========================================================================

    def _build_select(self, spec: QuerySpec) -> str:
        """Build SELECT clause with metrics and grouping columns."""
        columns = []

        group_col = get_grouping_column(spec.grouping)
        if group_col:
            columns.append(group_col)

        if not spec.metrics and spec.grouping == Grouping.NONE:
            return "*"

        if not spec.metrics and spec.grouping != Grouping.NONE:
            columns.append("COUNT(*) as count")
        else:
            for m in spec.metrics:
                columns.append(m.to_sql())

        return ",\n    ".join(columns)

    def _build_where_conditions(self, spec: QuerySpec) -> str:
        """Build WHERE clause from filter conditions."""
        conditions = []
        for cond in spec.filters.conditions:
            conditions.append(cond.to_sql())
        return " AND ".join(conditions) if conditions else ""

    def _build_group_by(self, spec: QuerySpec) -> str:
        """Build GROUP BY clause based on grouping type."""
        if spec.grouping in (Grouping.NONE, Grouping.TOTAL):
            return ""
        return get_grouping_expression(spec.grouping)

    def _build_order_by(self, spec: QuerySpec) -> str:
        """Build ORDER BY clause based on grouping or explicit order."""
        if spec.order_by:
            return f"{spec.order_by} {spec.order_direction}"

        grouping = spec.grouping
        if grouping == Grouping.NONE:
            return "date" if spec.source != Source.MINUTES else "timestamp"

        # TOTAL — одна строка, ORDER BY не нужен
        if grouping == Grouping.TOTAL:
            return ""

        return get_grouping_expression(grouping)

    # =========================================================================
    # Utilities
    # =========================================================================

    def _join_parts(self, parts: list[str]) -> str:
        """Join SQL parts into final query with proper formatting."""
        parts = [p for p in parts if p]

        result = []
        for part in parts:
            if part.startswith(("WITH", "FROM", "WHERE", "GROUP BY", "ORDER BY", "LIMIT")):
                result.append(part)
            else:
                result.append(f"    {part}")

        return "\n".join(result)
