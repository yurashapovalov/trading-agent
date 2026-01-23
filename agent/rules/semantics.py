"""
Semantics — how filters behave with different operations.

Three semantics:
- WHERE: filter rows before operation (SQL WHERE)
- CONDITION: defines condition for streak/probability analysis
- EVENT: defines event for around analysis (what triggers the event)

Rules:
1. always_where filters (categorical, time) → always WHERE
2. always_event filters (consecutive) → always EVENT
3. Other filters → depends on operation (see SEMANTICS matrix)
"""

from typing import Literal

from agent.rules.filters import FILTER_TYPES, is_always_where, is_always_event


Semantic = Literal["where", "condition", "event", "invalid"]


# =============================================================================
# Semantics Matrix: operation × filter_type → semantic
# =============================================================================
#
# Rows: operations
# Columns: filter types
# Values: "where" | "condition" | "event" | "invalid"
#

SEMANTICS: dict[str, dict[str, Semantic]] = {

    # =========================================================================
    # Group A: Standard operations (filter = WHERE)
    # =========================================================================

    "list": {
        "categorical": "where",
        "comparison": "where",
        "consecutive": "where",   # filter to days inside streaks
        "time": "where",
        "pattern": "where",
    },

    "count": {
        "categorical": "where",
        "comparison": "where",
        "consecutive": "where",
        "time": "where",
        "pattern": "where",
    },

    "distribution": {
        "categorical": "where",
        "comparison": "where",
        "consecutive": "where",
        "time": "where",
        "pattern": "where",
    },

    "correlation": {
        "categorical": "where",
        "comparison": "where",
        "consecutive": "where",
        "time": "where",
        "pattern": "where",
    },

    "compare": {
        "categorical": "where",   # compare mondays vs fridays
        "comparison": "where",
        "consecutive": "where",
        "time": "where",
        "pattern": "where",
    },

    "formation": {
        "categorical": "where",
        "comparison": "where",
        "consecutive": "where",
        "time": "where",
        "pattern": "where",
    },

    # =========================================================================
    # Group B: Event-based operations (filter = CONDITION/EVENT)
    # =========================================================================

    "streak": {
        "categorical": "where",      # streak of red mondays
        "comparison": "condition",   # THIS IS THE KEY: condition for streak
        "consecutive": "invalid",    # can't use consecutive with streak
        "time": "where",
        "pattern": "condition",      # streak of inside_days
    },

    "around": {
        "categorical": "where",      # around mondays
        "comparison": "event",       # THIS IS THE KEY: defines the event
        "consecutive": "event",      # what happens after 3 red days
        "time": "where",
        "pattern": "event",          # what happens after inside_day
    },

    "probability": {
        "categorical": "where",      # probability on mondays
        "comparison": "condition",   # P(outcome | comparison condition)
        "consecutive": "event",      # P(green | after consecutive red) - needs special handling
        "time": "where",
        "pattern": "condition",      # P(outcome | pattern)
    },
}


# =============================================================================
# API
# =============================================================================

def get_semantic(operation: str, filter_type: str) -> Semantic:
    """
    Get semantic for operation + filter_type combination.

    Returns: "where" | "condition" | "event" | "invalid"
    """
    # Always-where filters override matrix
    if is_always_where(filter_type):
        return "where"

    # Always-event filters override matrix
    if is_always_event(filter_type):
        # But some operations don't support events
        op_semantics = SEMANTICS.get(operation, {})
        if op_semantics.get(filter_type) == "invalid":
            return "invalid"
        return "event"

    # Look up in matrix
    op_semantics = SEMANTICS.get(operation, {})
    return op_semantics.get(filter_type, "where")


def validate_combination(operation: str, filter_type: str) -> tuple[bool, str]:
    """
    Validate operation + filter combination.

    Returns: (is_valid, error_message)
    """
    semantic = get_semantic(operation, filter_type)

    if semantic == "invalid":
        return False, f"'{filter_type}' filter cannot be used with '{operation}' operation"

    return True, ""


def split_filters_by_semantic(
    filters: list[dict],
    operation: str
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Split filters by semantic for given operation.

    Args:
        filters: list of parsed filter dicts (from filters.parse_filters)
        operation: operation name

    Returns:
        (where_filters, condition_filters, event_filters)
    """
    where_filters = []
    condition_filters = []
    event_filters = []

    for f in filters:
        filter_type = f.get("type")
        if not filter_type:
            continue

        semantic = get_semantic(operation, filter_type)

        if semantic == "where":
            where_filters.append(f)
        elif semantic == "condition":
            condition_filters.append(f)
        elif semantic == "event":
            event_filters.append(f)
        # invalid filters are skipped

    return where_filters, condition_filters, event_filters


def describe_semantic(semantic: Semantic) -> str:
    """Human-readable description of semantic."""
    descriptions = {
        "where": "Filter rows before operation (SQL WHERE clause)",
        "condition": "Defines condition for analysis (streak condition, probability condition)",
        "event": "Defines event that triggers analysis (around event)",
        "invalid": "Invalid combination",
    }
    return descriptions.get(semantic, "Unknown")


# =============================================================================
# Introspection (for docs/debugging)
# =============================================================================

def get_matrix_as_table() -> str:
    """Return semantics matrix as markdown table."""
    operations = list(SEMANTICS.keys())
    filter_types = list(FILTER_TYPES.keys())

    # Header
    lines = ["| Operation | " + " | ".join(filter_types) + " |"]
    lines.append("|-----------|" + "|".join(["--------"] * len(filter_types)) + "|")

    # Rows
    for op in operations:
        row = [op]
        for ft in filter_types:
            sem = get_semantic(op, ft)
            row.append(sem)
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)
