"""
Query completeness rules — when to default vs clarify.

Defines for each query type:
- REQUIRED fields: must be present, otherwise unclear
- OPTIONAL fields: apply default if missing
- DERIVED fields: computed from context

Used by Parser to decide:
1. Query is complete → execute
2. Missing optional → apply default
3. Missing required → ask for clarification

Logic:
    unclear = check_completeness(query_type, parsed_fields)
    if unclear:
        return ClarificationResponse(unclear)
    else:
        apply_defaults(query_type, parsed_fields)
        return execute(query)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FieldRequirement(str, Enum):
    """Field requirement level."""
    REQUIRED = "required"    # Must be present, unclear if missing
    OPTIONAL = "optional"    # Apply default if missing
    DERIVED = "derived"      # Computed from other fields/context


@dataclass
class FieldRule:
    """Rule for a single field."""
    requirement: FieldRequirement
    default: Any = None           # Default value if optional
    unclear_key: str | None = None  # Key to add to unclear[] if required & missing
    description: str = ""         # Human-readable description


# =============================================================================
# ANALYTICS (grouped statistics)
# =============================================================================

ANALYTICS_RULES = {
    "group": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=["day"],  # Default = daily aggregation (trading days)
        description="Grouping dimension (hour, weekday, month). Default = day.",
    ),
    "metrics": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default="STANDARD",  # Sentinel for DEFAULT_STATISTICS_METRICS
        description="Metrics to compute. Default = standard stats.",
    ),
    "period": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,  # None = all available data
        description="Date range. Default = all data.",
    ),
    "filter": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Filter conditions (weekday, session, etc.).",
    ),
    "sort": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Sort order for results.",
    ),
    "limit": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Max rows to return.",
    ),
}


# =============================================================================
# DATA (raw bars listing)
# =============================================================================

DATA_RULES = {
    "period": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default="RECENT",  # Sentinel for last N days
        description="Date range. Default = recent 30 days.",
    ),
    "filter": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Filter conditions.",
    ),
    "sort": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default="DATE_DESC",  # Sentinel for date descending
        description="Sort order. Default = date descending.",
    ),
    "limit": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=50,
        description="Max rows. Default = 50.",
    ),
}


# =============================================================================
# EVENT_TIME (when does X form?)
# =============================================================================

EVENT_TIME_RULES = {
    "event": FieldRule(
        requirement=FieldRequirement.REQUIRED,
        unclear_key="event_type",
        description="Event to analyze: high, low, open, close, max_volume.",
    ),
    "group_by": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default="hour",
        description="Time granularity. Default = hour.",
    ),
    "period": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Date range. Default = all data.",
    ),
}


# =============================================================================
# COMPARE (A vs B)
# =============================================================================

COMPARE_RULES = {
    "a": FieldRule(
        requirement=FieldRequirement.REQUIRED,
        unclear_key="compare_first",
        description="First slice to compare (e.g., RTH, Monday).",
    ),
    "b": FieldRule(
        requirement=FieldRequirement.REQUIRED,
        unclear_key="compare_second",
        description="Second slice to compare (e.g., ETH, Friday).",
    ),
    "metrics": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default="STANDARD",
        description="Metrics to compare. Default = range, volume, count.",
    ),
    "period": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Date range. Default = all data.",
    ),
}


# =============================================================================
# PATTERN (find candle/price patterns)
# =============================================================================

PATTERN_RULES = {
    "candle": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Candle patterns to find (doji, hammer, etc.).",
    ),
    "price": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Price patterns to find (inside_bar, breakout, etc.).",
    ),
    # At least one of candle/price must be specified
    # This is a cross-field validation handled separately
    "period": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Date range. Default = all data.",
    ),
}


# =============================================================================
# CROSS (cross-symbol operations)
# =============================================================================

CROSS_RULES = {
    "type": FieldRule(
        requirement=FieldRequirement.REQUIRED,
        unclear_key="cross_operation",
        description="Operation: correlation, spread, ratio, beta.",
    ),
    "symbols": FieldRule(
        requirement=FieldRequirement.REQUIRED,
        unclear_key="cross_symbols",
        description="Symbols to compare (e.g., ['NQ', 'ES']).",
    ),
    "field": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default="close",
        description="Field to use. Default = close.",
    ),
    "period": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Date range. Default = all data.",
    ),
}


# =============================================================================
# GRANULARITY (time aggregation)
# =============================================================================

GRANULARITY_RULES = {
    "level": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default="day",
        description="Aggregation level: hour, day, week, month.",
    ),
}


# =============================================================================
# STRATEGY (indicators + entry/exit)
# =============================================================================

STRATEGY_RULES = {
    "indicators": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Technical indicators to compute.",
    ),
    "entry": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Entry conditions.",
    ),
    "exit": FieldRule(
        requirement=FieldRequirement.OPTIONAL,
        default=None,
        description="Exit rules.",
    ),
}


# =============================================================================
# REGISTRY
# =============================================================================

COMPLETENESS_RULES = {
    "analytics": ANALYTICS_RULES,
    "data": DATA_RULES,
    "event_time": EVENT_TIME_RULES,
    "compare": COMPARE_RULES,
    "pattern": PATTERN_RULES,
    "cross": CROSS_RULES,
    "granularity": GRANULARITY_RULES,
    "strategy": STRATEGY_RULES,
}


# =============================================================================
# CROSS-FIELD VALIDATIONS
# =============================================================================

def validate_pattern(fields: dict) -> list[str]:
    """Pattern needs at least one of candle or price."""
    if not fields.get("candle") and not fields.get("price"):
        return ["pattern_type"]
    return []


CROSS_FIELD_VALIDATIONS = {
    "pattern": validate_pattern,
}


# =============================================================================
# PUBLIC API
# =============================================================================

def check_completeness(query_type: str, fields: dict) -> list[str]:
    """Check if query has all required fields.

    Args:
        query_type: Type of query (analytics, data, event_time, etc.)
        fields: Parsed fields from Parser

    Returns:
        List of unclear keys (empty if complete)
    """
    if query_type not in COMPLETENESS_RULES:
        return []

    rules = COMPLETENESS_RULES[query_type]
    unclear = []

    for field_name, rule in rules.items():
        if rule.requirement == FieldRequirement.REQUIRED:
            if field_name not in fields or fields[field_name] is None:
                if rule.unclear_key:
                    unclear.append(rule.unclear_key)

    # Cross-field validations
    if query_type in CROSS_FIELD_VALIDATIONS:
        unclear.extend(CROSS_FIELD_VALIDATIONS[query_type](fields))

    return unclear


def get_defaults(query_type: str) -> dict[str, Any]:
    """Get all default values for a query type.

    Args:
        query_type: Type of query

    Returns:
        Dict of field_name -> default_value (only for optional fields)
    """
    if query_type not in COMPLETENESS_RULES:
        return {}

    rules = COMPLETENESS_RULES[query_type]
    defaults = {}

    for field_name, rule in rules.items():
        if rule.requirement == FieldRequirement.OPTIONAL and rule.default is not None:
            defaults[field_name] = rule.default

    return defaults


def get_field_description(query_type: str, field_name: str) -> str:
    """Get human-readable description for a field.

    Used by ClarificationResponder to explain what's needed.
    """
    if query_type not in COMPLETENESS_RULES:
        return ""

    rules = COMPLETENESS_RULES[query_type]
    if field_name not in rules:
        return ""

    return rules[field_name].description


# =============================================================================
# UNCLEAR KEY DESCRIPTIONS (for ClarificationResponder)
# =============================================================================

UNCLEAR_DESCRIPTIONS = {
    "event_type": "What event to analyze? (high, low, open, close, max_volume)",
    "compare_first": "What to compare? (e.g., RTH, Monday, 2023)",
    "compare_second": "Compare against what? (e.g., ETH, Friday, 2024)",
    "cross_operation": "What operation? (correlation, spread, ratio, beta)",
    "cross_symbols": "Which symbols to compare? (e.g., NQ vs ES)",
    "pattern_type": "What pattern to find? (doji, hammer, engulfing, inside_bar, etc.)",
    "year": "Which year?",
    "session": "Which session? (RTH, ETH, or full day)",
}


def get_unclear_description(unclear_key: str) -> str:
    """Get human-readable question for unclear field."""
    return UNCLEAR_DESCRIPTIONS.get(unclear_key, f"Please specify: {unclear_key}")
