"""
Test Scenarios — organized by QueryBuilder capabilities.

Structure mirrors QueryBuilder building blocks:
- Source: DAILY, MINUTES, DAILY_WITH_PREV
- Grouping: TOTAL, HOUR, WEEKDAY, MONTH, etc.
- SpecialOp: TOP_N, EVENT_TIME, FIND_EXTREMUM, COMPARE
- Filters: period, weekday, session, conditions, events

Usage:
    from agent.tests.scenarios import get_scenario, list_scenarios

    scenarios = get_scenario("follow_up")
    all_names = list_scenarios()

Run specific scenario:
    python -m agent.tests.barb_test --scenario=source_daily
    python -m agent.tests.barb_test --scenario=follow_up
"""

# Import all scenario lists
from .source import (
    SOURCE_DAILY,
    SOURCE_MINUTES,
    SOURCE_DAILY_WITH_PREV,
)
from .grouping import (
    GROUPING_TOTAL,
    GROUPING_NONE,
    GROUPING_HOUR,
    GROUPING_WEEKDAY,
    GROUPING_MONTH,
    GROUPING_YEAR,
    GROUPING_SESSION,
)
from .special_ops import (
    SPECIAL_TOP_N,
    SPECIAL_EVENT_TIME,
    SPECIAL_FIND_EXTREMUM,
    SPECIAL_COMPARE,
)
from .filters import (
    FILTER_PERIOD,
    FILTER_WEEKDAY,
    FILTER_SESSION,
    FILTER_CONDITIONS,
    FILTER_EVENTS,
    FILTER_SPECIFIC_DATE,
    FILTER_DATE_NO_YEAR,
)
from .non_data import (
    CONCEPTS,
    GREETINGS,
    NOT_SUPPORTED,
    HOLIDAYS,
)
from .follow_up import FOLLOW_UP_CHAINS
from .capabilities import FIND_CAPABILITY


# =============================================================================
# SCENARIO REGISTRY
# =============================================================================

SCENARIOS = {
    # Source scenarios
    "source_daily": SOURCE_DAILY,
    "source_minutes": SOURCE_MINUTES,
    "source_daily_with_prev": SOURCE_DAILY_WITH_PREV,

    # Grouping scenarios
    "grouping_total": GROUPING_TOTAL,
    "grouping_none": GROUPING_NONE,
    "grouping_hour": GROUPING_HOUR,
    "grouping_weekday": GROUPING_WEEKDAY,
    "grouping_month": GROUPING_MONTH,
    "grouping_year": GROUPING_YEAR,
    "grouping_session": GROUPING_SESSION,

    # SpecialOp scenarios
    "special_top_n": SPECIAL_TOP_N,
    "special_event_time": SPECIAL_EVENT_TIME,
    "special_find_extremum": SPECIAL_FIND_EXTREMUM,
    "special_compare": SPECIAL_COMPARE,

    # Filter scenarios
    "filter_period": FILTER_PERIOD,
    "filter_weekday": FILTER_WEEKDAY,
    "filter_session": FILTER_SESSION,
    "filter_conditions": FILTER_CONDITIONS,
    "filter_events": FILTER_EVENTS,
    "filter_specific_date": FILTER_SPECIFIC_DATE,
    "filter_date_no_year": FILTER_DATE_NO_YEAR,

    # Non-data scenarios
    "concepts": CONCEPTS,
    "greetings": GREETINGS,
    "not_supported": NOT_SUPPORTED,
    "holidays": HOLIDAYS,

    # Follow-up chains
    "follow_up": FOLLOW_UP_CHAINS,

    # Capability tests (atomic testing of Parser → Composer → QueryBuilder)
    "capability_find": FIND_CAPABILITY,

    # === Combined groups ===
    "all_source": SOURCE_DAILY + SOURCE_MINUTES + SOURCE_DAILY_WITH_PREV,
    "all_grouping": (
        GROUPING_TOTAL + GROUPING_NONE + GROUPING_HOUR +
        GROUPING_WEEKDAY + GROUPING_MONTH + GROUPING_YEAR + GROUPING_SESSION
    ),
    "all_special": (
        SPECIAL_TOP_N + SPECIAL_EVENT_TIME +
        SPECIAL_FIND_EXTREMUM + SPECIAL_COMPARE
    ),
    "all_filter": (
        FILTER_PERIOD + FILTER_WEEKDAY + FILTER_SESSION +
        FILTER_CONDITIONS + FILTER_EVENTS
    ),
    "all_clarification": FILTER_SPECIFIC_DATE + FILTER_DATE_NO_YEAR,
    "all_non_data": CONCEPTS + GREETINGS + NOT_SUPPORTED + HOLIDAYS,

    # Full coverage (all single questions)
    "all_single": (
        SOURCE_DAILY + SOURCE_MINUTES +
        GROUPING_TOTAL + GROUPING_HOUR + GROUPING_WEEKDAY + GROUPING_MONTH +
        SPECIAL_TOP_N + SPECIAL_EVENT_TIME + SPECIAL_COMPARE +
        FILTER_PERIOD + FILTER_WEEKDAY + FILTER_SESSION +
        FILTER_CONDITIONS + FILTER_EVENTS +
        FILTER_SPECIFIC_DATE + FILTER_DATE_NO_YEAR +
        CONCEPTS + GREETINGS + NOT_SUPPORTED
    ),
}


# =============================================================================
# PUBLIC API
# =============================================================================

def get_scenario(name: str) -> list:
    """Get scenario by name.

    Args:
        name: Scenario name (e.g., "follow_up", "source_daily")

    Returns:
        List of scenario items (dicts with "q" and "expect_*" keys,
        or chain dicts for follow_up scenarios)

    Raises:
        ValueError: If scenario name is unknown
    """
    if name not in SCENARIOS:
        available = ", ".join(sorted(SCENARIOS.keys()))
        raise ValueError(f"Unknown scenario: {name}. Available: {available}")
    return SCENARIOS[name]


def list_scenarios() -> list[str]:
    """List all available scenario names."""
    return sorted(SCENARIOS.keys())


def is_chain_scenario(scenario: list) -> bool:
    """Check if scenario contains follow-up chains (vs single questions).

    Chain scenarios have items with "chain" key containing list of steps.
    Single question scenarios have items with "q" key directly.
    """
    if not scenario:
        return False
    first = scenario[0]
    return isinstance(first, dict) and "chain" in first


def get_scenario_stats() -> dict:
    """Get statistics about all scenarios."""
    stats = {
        "total_scenarios": len(SCENARIOS),
        "by_category": {},
    }

    for name, items in SCENARIOS.items():
        if name.startswith("all_"):
            continue  # Skip combined groups

        category = name.split("_")[0]
        if category not in stats["by_category"]:
            stats["by_category"][category] = {"count": 0, "questions": 0}

        stats["by_category"][category]["count"] += 1

        if is_chain_scenario(items):
            # Count total questions in chains
            for chain in items:
                stats["by_category"][category]["questions"] += len(chain.get("chain", []))
        else:
            stats["by_category"][category]["questions"] += len(items)

    return stats
