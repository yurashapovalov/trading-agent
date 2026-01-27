"""
Operations — what user can do with data.

Each operation has:
- description: what it does
- atoms: how many atoms required
- params: operation-specific parameters
- requires_full_data: if True, don't apply filters as WHERE before operation
- examples: for prompt generation
"""

from typing import TypedDict, Literal


class ParamDef(TypedDict, total=False):
    type: str
    default: any
    required: bool
    description: str


class OperationDef(TypedDict, total=False):
    description: str
    atoms: dict[str, int]  # {"min": 1, "max": 2}
    params: dict[str, ParamDef]
    requires_full_data: bool  # streak needs all data, not pre-filtered
    requires_timeframe: str | None  # "1m" for formation
    examples: list[dict]  # {"q": "question", "output": {...}}


OPERATIONS: dict[str, OperationDef] = {

    # =========================================================================
    # Group A: filter = WHERE (standard filtering)
    # =========================================================================

    "list": {
        "description": "Show top N records sorted by metric",
        "atoms": {"min": 1, "max": 1},
        "params": {
            "n": {"type": "int", "description": "Number of records (omit for all)"},
            "sort": {"type": "asc|desc", "default": "desc", "description": "Sort order"},
        },
        "requires_full_data": False,
        "examples": [
            {
                "q": "top 10 biggest drops in 2024",
                "output": {"operation": "list", "atoms": [{"when": "2024", "what": "change"}], "params": {"n": 10, "sort": "asc"}}
            },
            {
                "q": "show red mondays in 2024",
                "output": {"operation": "list", "atoms": [{"when": "2024", "what": "change", "filter": "monday, change < 0"}]}
            },
        ],
    },

    "count": {
        "description": "Count records matching filter, with basic stats",
        "atoms": {"min": 1, "max": 1},
        "params": {},
        "requires_full_data": False,
        "examples": [
            {
                "q": "how many red days in 2024",
                "output": {"operation": "count", "atoms": [{"when": "2024", "what": "change", "filter": "change < 0"}]}
            },
            {
                "q": "how many gap ups in January",
                "output": {"operation": "count", "atoms": [{"when": "January", "what": "gap", "filter": "gap > 0"}]}
            },
        ],
    },

    "distribution": {
        "description": "Show distribution/histogram of metric values",
        "atoms": {"min": 1, "max": 1},
        "params": {
            "bins": {"type": "int", "default": 10, "description": "Number of bins"},
        },
        "requires_full_data": False,
        "examples": [
            {
                "q": "distribution of daily changes in 2024",
                "output": {"operation": "distribution", "atoms": [{"when": "2024", "what": "change"}]}
            },
        ],
    },

    "correlation": {
        "description": "Calculate correlation between two metrics",
        "atoms": {"min": 2, "max": 2},
        "params": {},
        "requires_full_data": False,
        "examples": [
            {
                "q": "correlation between volume and volatility",
                "output": {"operation": "correlation", "atoms": [
                    {"when": "all", "what": "volume"},
                    {"when": "all", "what": "range"}
                ]}
            },
        ],
    },

    "compare": {
        "description": "Compare metric across groups (periods, weekdays, etc.)",
        "atoms": {"min": 2, "max": 10},
        "params": {
            "group_by": {"type": "str", "description": "Field to group by: weekday, month, year"},
        },
        "requires_full_data": False,
        "examples": [
            {
                "q": "compare monday vs friday in 2024",
                "output": {"operation": "compare", "atoms": [
                    {"when": "2024", "what": "change", "filter": "monday"},
                    {"when": "2024", "what": "change", "filter": "friday"}
                ]}
            },
        ],
    },

    "formation": {
        "description": "When is daily high/low typically formed (requires minute data)",
        "atoms": {"min": 1, "max": 1},
        "params": {
            "event": {"type": "high|low", "description": "What to find"},
            "group_by": {"type": "str", "default": "hour", "description": "Grouping"},
        },
        "requires_full_data": False,
        "requires_timeframe": "1m",  # formation needs minute data
        "examples": [
            {
                "q": "when is daily high usually formed",
                "output": {"operation": "formation", "atoms": [{"when": "all", "what": "high", "timeframe": "1m"}]}
            },
        ],
    },

    # =========================================================================
    # Group B: filter = EVENT/CONDITION (special handling)
    # =========================================================================

    "streak": {
        "description": "Find consecutive series where condition is true N+ times",
        "atoms": {"min": 1, "max": 1},
        "params": {
            "n": {"type": "int", "required": True, "description": "Minimum streak length"},
        },
        "requires_full_data": True,  # ВАЖНО: нужны ВСЕ данные для поиска серий
        "examples": [
            {
                "q": "how many times were there 3+ red days in a row in 2024",
                "output": {"operation": "streak", "atoms": [{"when": "2024", "what": "change", "filter": "change < 0"}], "params": {"n": 3}}
            },
            {
                "q": "longest winning streak in 2024",
                "output": {"operation": "streak", "atoms": [{"when": "2024", "what": "change", "filter": "change > 0"}], "params": {"n": 2, "sort": "desc"}}
            },
        ],
    },

    "around": {
        "description": "What happens before/after event days",
        "atoms": {"min": 1, "max": 1},
        "params": {
            "offset": {"type": "int", "default": 1, "description": "+1 = day after, -1 = day before"},
        },
        "requires_full_data": False,  # around использует prev/next_change из enrich
        "examples": [
            {
                "q": "what happens after big drops (> 2%)",
                "output": {"operation": "around", "atoms": [{"when": "all", "what": "change", "filter": "change < -2"}], "params": {"offset": 1}}
            },
            {
                "q": "performance after 3 red days in a row",
                "output": {"operation": "around", "atoms": [{"when": "all", "what": "change", "filter": "consecutive red >= 3"}], "params": {"offset": 1}}
            },
        ],
    },

    "probability": {
        "description": "Probability of outcome given condition: P(outcome | condition)",
        "atoms": {"min": 1, "max": 1},
        "params": {
            "outcome": {"type": "str", "default": "> 0", "description": "Condition for success"},
        },
        "requires_full_data": False,
        "examples": [
            {
                "q": "probability of green day after gap up",
                "output": {"operation": "probability", "atoms": [{"when": "all", "what": "change", "filter": "gap > 0"}], "params": {"outcome": "> 0"}}
            },
            {
                "q": "chance of green after 2+ red days",
                "output": {"operation": "probability", "atoms": [{"when": "all", "what": "change", "filter": "consecutive red >= 2"}], "params": {"outcome": "> 0"}}
            },
        ],
    },
}


# =============================================================================
# Helpers
# =============================================================================

def get_operation(name: str) -> OperationDef | None:
    """Get operation definition by name."""
    return OPERATIONS.get(name)


def get_all_operations() -> list[str]:
    """Get list of all operation names."""
    return list(OPERATIONS.keys())


def requires_full_data(operation: str) -> bool:
    """Check if operation needs full data (no pre-filtering)."""
    op = OPERATIONS.get(operation)
    return op.get("requires_full_data", False) if op else False


def get_examples_for_prompt(operation: str | None = None) -> list[dict]:
    """Get examples for prompt generation."""
    if operation:
        op = OPERATIONS.get(operation)
        return op.get("examples", []) if op else []

    # All examples
    examples = []
    for op in OPERATIONS.values():
        examples.extend(op.get("examples", []))
    return examples


def get_required_timeframe(operation: str) -> str | None:
    """Get required timeframe for operation (e.g. '1m' for formation)."""
    op = OPERATIONS.get(operation)
    return op.get("requires_timeframe") if op else None


def get_atoms_range(operation: str) -> tuple[int, int]:
    """Get (min, max) atoms for operation."""
    op = OPERATIONS.get(operation)
    if not op:
        return (1, 10)  # default
    atoms = op.get("atoms", {})
    return (atoms.get("min", 1), atoms.get("max", 10))


def get_default_params(operation: str) -> dict:
    """Get default params for operation."""
    op = OPERATIONS.get(operation)
    if not op:
        return {}

    defaults = {}
    for param_name, param_def in op.get("params", {}).items():
        if "default" in param_def:
            defaults[param_name] = param_def["default"]
    return defaults
