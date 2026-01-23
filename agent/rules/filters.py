"""
Filter types — conditions for data selection.

Each filter type has:
- description: what it does
- pattern: regex for parsing from string
- examples: for prompt generation
- always_where: if True, always acts as WHERE regardless of operation
- always_event: if True, always acts as EVENT regardless of operation

If neither always_where nor always_event, semantics depends on operation.
See semantics.py for operation-specific rules.
"""

from typing import TypedDict
import re


class FilterTypeDef(TypedDict, total=False):
    description: str
    pattern: str  # regex for parsing
    examples: list[str]
    always_where: bool
    always_event: bool


FILTER_TYPES: dict[str, FilterTypeDef] = {

    "categorical": {
        "description": "Weekday, session, or calendar event",
        "pattern": r"^(monday|tuesday|wednesday|thursday|friday|session\s*=\s*\w+|event\s*=\s*\w+)$",
        "examples": [
            "monday",
            "friday",
            "session = RTH",
            "session = OVERNIGHT",
            "event = fomc",
            "event = opex",
        ],
        "always_where": True,
    },

    "comparison": {
        "description": "Metric comparison (>, <, >=, <=, =)",
        "pattern": r"^(change|gap|range|volume|open|high|low|close)\s*(>=|<=|>|<|=)\s*-?\d+\.?\d*%?$",
        "examples": [
            "change > 0",
            "change < -2%",
            "gap > 0",
            "gap < -1%",
            "range > 300",
            "volume > 1000000",
        ],
        # НЕ always_where — зависит от операции
    },

    "consecutive": {
        "description": "Consecutive red/green days",
        "pattern": r"^consecutive\s+(red|green)\s*(>=|>|=)\s*\d+$",
        "examples": [
            "consecutive red >= 2",
            "consecutive green >= 3",
            "consecutive red > 1",
        ],
        "always_event": True,  # Всегда EVENT — не имеет смысла как WHERE
    },

    "time": {
        "description": "Time of day filter (requires intraday data)",
        "pattern": r"^time\s*(>=|<=|>|<)\s*\d{1,2}:\d{2}$",
        "examples": [
            "time >= 09:30",
            "time < 12:00",
            "time >= 14:00",
        ],
        "always_where": True,
    },

    "pattern": {
        "description": "Price patterns",
        "pattern": r"^(inside_day|outside_day|doji|gap_fill|gap_filled|higher_high|lower_low|green|red)$",
        "examples": [
            "inside_day",
            "outside_day",
            "doji",
            "gap_fill",
            "gap_filled",
            "green",
            "red",
        ],
        # НЕ always_where — зависит от операции
    },

}


# =============================================================================
# Parsing
# =============================================================================

def detect_filter_type(filter_str: str) -> str | None:
    """Detect filter type from string."""
    filter_str = filter_str.strip().lower()

    for type_name, type_def in FILTER_TYPES.items():
        pattern = type_def.get("pattern")
        if pattern and re.match(pattern, filter_str, re.IGNORECASE):
            return type_name

    return None


def parse_filter(filter_str: str) -> dict | None:
    """
    Parse filter string to structured dict.

    Returns:
        {"type": "comparison", "metric": "change", "op": ">", "value": 0}
        {"type": "categorical", "weekday": "monday"}
        {"type": "consecutive", "color": "red", "op": ">=", "length": 2}
        etc.
    """
    filter_str = filter_str.strip().lower()

    # Weekday
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    if filter_str in weekdays:
        return {"type": "categorical", "weekday": filter_str}

    # Session
    if m := re.match(r"session\s*=\s*(\w+)", filter_str):
        return {"type": "categorical", "session": m.group(1).upper()}

    # Event
    if m := re.match(r"event\s*=\s*(\w+)", filter_str):
        return {"type": "categorical", "event": m.group(1).lower()}

    # Comparison
    if m := re.match(r"(change|gap|range|volume|open|high|low|close)\s*(>=|<=|>|<|=)\s*(-?\d+\.?\d*)%?", filter_str):
        return {
            "type": "comparison",
            "metric": m.group(1),
            "op": m.group(2),
            "value": float(m.group(3))
        }

    # Consecutive
    if m := re.match(r"consecutive\s+(red|green)\s*(>=|>|=)\s*(\d+)", filter_str):
        return {
            "type": "consecutive",
            "color": m.group(1),
            "op": m.group(2),
            "length": int(m.group(3))
        }

    # Time
    if m := re.match(r"time\s*(>=|<=|>|<)\s*(\d{1,2}:\d{2})", filter_str):
        time_val = m.group(2)
        if len(time_val.split(":")[0]) == 1:
            time_val = "0" + time_val
        return {"type": "time", "op": m.group(1), "value": time_val}

    # Pattern
    patterns = ["inside_day", "outside_day", "doji", "gap_fill", "gap_filled", "higher_high", "lower_low", "green", "red"]
    if filter_str in patterns:
        return {"type": "pattern", "pattern": filter_str}

    return None


def parse_filters(filter_str: str) -> list[dict]:
    """
    Parse comma-separated filters.

    "monday, change > 0" → [{"type": "categorical", ...}, {"type": "comparison", ...}]
    """
    if not filter_str:
        return []

    filters = []
    for part in filter_str.split(","):
        part = part.strip()
        if not part:
            continue
        parsed = parse_filter(part)
        if parsed:
            filters.append(parsed)

    return filters


# =============================================================================
# Helpers
# =============================================================================

def get_filter_type(name: str) -> FilterTypeDef | None:
    """Get filter type definition."""
    return FILTER_TYPES.get(name)


def get_all_filter_types() -> list[str]:
    """Get list of all filter type names."""
    return list(FILTER_TYPES.keys())


def is_always_where(filter_type: str) -> bool:
    """Check if filter type is always WHERE."""
    ft = FILTER_TYPES.get(filter_type)
    return ft.get("always_where", False) if ft else False


def is_always_event(filter_type: str) -> bool:
    """Check if filter type is always EVENT."""
    ft = FILTER_TYPES.get(filter_type)
    return ft.get("always_event", False) if ft else False


def get_examples_for_prompt(filter_type: str | None = None) -> list[str]:
    """Get examples for prompt generation."""
    if filter_type:
        ft = FILTER_TYPES.get(filter_type)
        return ft.get("examples", []) if ft else []

    # All examples
    examples = []
    for ft in FILTER_TYPES.values():
        examples.extend(ft.get("examples", []))
    return examples
