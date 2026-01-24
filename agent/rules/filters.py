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
        "description": "Candle and price patterns",
        # Pattern regex built dynamically from config — see _build_pattern_regex()
        "pattern": None,  # Set below
        "examples": [
            "inside_day",
            "doji",
            "hammer",
            "green",
            "red",
        ],
        # НЕ always_where — зависит от операции
    },

}


# =============================================================================
# Dynamic pattern list from config (single source of truth)
# =============================================================================

def _get_all_pattern_names() -> set[str]:
    """Get all pattern names from config + legacy aliases."""
    from agent.config.patterns import list_all_patterns
    patterns = set(list_all_patterns())
    patterns.update({"green", "red", "gap_fill", "gap_filled"})  # legacy
    patterns.update(PATTERN_ALIASES.keys())  # accept aliases too
    return patterns


# =============================================================================
# Pattern aliases (user-friendly → config name)
# =============================================================================

PATTERN_ALIASES: dict[str, str] = {
    "inside_day": "inside_bar",
    "outside_day": "outside_bar",
}


def normalize_pattern_filter(filter_str: str) -> str:
    """Normalize pattern aliases in filter string to canonical names."""
    if not filter_str:
        return filter_str

    result = filter_str
    for alias, canonical in PATTERN_ALIASES.items():
        # Case-insensitive replacement
        import re
        result = re.sub(rf'\b{alias}\b', canonical, result, flags=re.IGNORECASE)

    return result


def _build_pattern_regex() -> str:
    """Build regex for pattern filter from config."""
    patterns = _get_all_pattern_names()
    escaped = [re.escape(p) for p in sorted(patterns)]
    return r"^(" + "|".join(escaped) + r")$"


# Set pattern regex from config
FILTER_TYPES["pattern"]["pattern"] = _build_pattern_regex()


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

    # Pattern (from config)
    if filter_str in _get_all_pattern_names():
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


# =============================================================================
# Pattern timeframe validation
# =============================================================================

# Timeframe order for comparison (smallest to largest)
_TF_ORDER = ["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W"]


def get_min_timeframe_for_pattern_filter(filter_str: str) -> str | None:
    """
    Get minimum required timeframe if filter contains patterns.

    Returns:
        Minimum timeframe string (e.g., "1H", "1D") or None if no pattern filter.
    """
    if not filter_str:
        return None

    from agent.config.patterns import get_pattern_min_timeframe, get_pattern_type

    parsed = parse_filters(filter_str)
    min_tf = None

    for f in parsed:
        if f.get("type") != "pattern":
            continue

        pattern_name = f.get("pattern")
        if not pattern_name:
            continue

        # Legacy patterns (green, red, gap_fill) work on any timeframe
        if pattern_name in ("green", "red", "gap_fill", "gap_filled"):
            continue

        # Get min timeframe from config
        pattern_type = get_pattern_type(pattern_name)
        if not pattern_type:
            continue

        pattern_min = get_pattern_min_timeframe(pattern_name)

        # Track highest minimum
        if min_tf is None:
            min_tf = pattern_min
        elif _TF_ORDER.index(pattern_min) > _TF_ORDER.index(min_tf):
            min_tf = pattern_min

    return min_tf


def is_timeframe_valid_for_filter(timeframe: str, filter_str: str) -> bool:
    """Check if timeframe is valid for pattern filters."""
    min_tf = get_min_timeframe_for_pattern_filter(filter_str)
    if min_tf is None:
        return True

    if timeframe not in _TF_ORDER or min_tf not in _TF_ORDER:
        return True

    return _TF_ORDER.index(timeframe) >= _TF_ORDER.index(min_tf)
