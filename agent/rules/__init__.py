"""
Rules — single source of truth for parser system.

This module defines ALL rules for the system:
- Operations: what user can do with data
- Filters: how to select data
- Metrics: what to measure
- Semantics: how filters behave with operations

Used by:
- Parser prompts (examples generated from rules)
- Pydantic validators (check combinations)
- Executor (decides how to apply filters)
- Documentation (auto-generated)

Structure:
- operations.py: 9 operations with params, examples
- filters.py: 5 filter types with parsing
- metrics.py: metrics with column mapping
- semantics.py: operation × filter → where/condition/event

Quick reference:
    from agent.rules import (
        # Operations
        OPERATIONS,
        get_operation,
        requires_full_data,

        # Filters
        FILTER_TYPES,
        parse_filter,
        parse_filters,

        # Metrics
        METRICS,
        get_column,

        # Semantics
        get_semantic,
        split_filters_by_semantic,
        validate_combination,
    )
"""

# Operations
from agent.rules.operations import (
    OPERATIONS,
    get_operation,
    get_all_operations,
    requires_full_data,
    get_required_timeframe,
    get_atoms_range,
    get_default_params,
    get_examples_for_prompt as get_operation_examples,
)

# Filters
from agent.rules.filters import (
    FILTER_TYPES,
    get_filter_type,
    get_all_filter_types,
    detect_filter_type,
    parse_filter,
    parse_filters,
    is_always_where,
    is_always_event,
    get_examples_for_prompt as get_filter_examples,
)

# Metrics
from agent.rules.metrics import (
    METRICS,
    get_metric,
    get_column,
    get_all_metrics,
    get_computed_metrics,
    get_raw_metrics,
    requires_daily,
    requires_intraday,
)

# Semantics
from agent.rules.semantics import (
    SEMANTICS,
    Semantic,
    get_semantic,
    validate_combination,
    split_filters_by_semantic,
    describe_semantic,
    get_matrix_as_table,
)


__all__ = [
    # Operations
    "OPERATIONS",
    "get_operation",
    "get_all_operations",
    "requires_full_data",
    "get_required_timeframe",
    "get_atoms_range",
    "get_default_params",
    "get_operation_examples",

    # Filters
    "FILTER_TYPES",
    "get_filter_type",
    "get_all_filter_types",
    "detect_filter_type",
    "parse_filter",
    "parse_filters",
    "is_always_where",
    "is_always_event",
    "get_filter_examples",

    # Metrics
    "METRICS",
    "get_metric",
    "get_column",
    "get_all_metrics",
    "get_computed_metrics",
    "get_raw_metrics",
    "requires_daily",
    "requires_intraday",

    # Semantics
    "SEMANTICS",
    "Semantic",
    "get_semantic",
    "validate_combination",
    "split_filters_by_semantic",
    "describe_semantic",
    "get_matrix_as_table",
]
