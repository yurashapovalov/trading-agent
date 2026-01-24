"""
Pattern definitions — candle and price patterns.

Static knowledge about patterns:
- Detection parameters
- Descriptions for Presenter context
- Categories, signals, relationships

Used by:
- Parser: understands pattern names and categories
- Presenter: explains what patterns mean
- Scanner: detects patterns in data
"""

from agent.config.patterns.candle import (
    CANDLE_PATTERNS,
    get_candle_pattern,
    list_candle_patterns,
    get_candle_patterns_by_signal,
    get_candle_patterns_by_category,
)

from agent.config.patterns.price import (
    PRICE_PATTERNS,
    get_price_pattern,
    list_price_patterns,
)


# =============================================================================
# UNIFIED PATTERN ACCESS (DRY)
# =============================================================================

def get_pattern(name: str) -> dict | None:
    """Get any pattern by name (candle or price)."""
    name = name.lower()
    return CANDLE_PATTERNS.get(name) or PRICE_PATTERNS.get(name)


def list_all_patterns() -> list[str]:
    """List all pattern names (candle + price)."""
    return list(CANDLE_PATTERNS.keys()) + list(PRICE_PATTERNS.keys())


def get_pattern_type(name: str) -> str | None:
    """Get pattern type: 'candle', 'price', or None."""
    name = name.lower()
    if name in CANDLE_PATTERNS:
        return "candle"
    if name in PRICE_PATTERNS:
        return "price"
    return None


# =============================================================================
# TIMEFRAME SUPPORT (unified)
# =============================================================================

# Timeframe order for comparison
_TF_ORDER = ["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W", "1M"]

# Default timeframes by candle count (for candle patterns)
_CANDLE_TF_DEFAULTS = {
    1: ["1H", "4H", "1D", "1W"],      # Single candle: hourly+
    2: ["4H", "1D", "1W"],             # Two candle: 4-hour+
    3: ["1D", "1W"],                   # Three candle: daily+
}

# Price patterns work on any timeframe (structural)
_PRICE_TF_DEFAULT = ["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W"]


def get_pattern_timeframes(name: str) -> list[str]:
    """
    Get valid timeframes for pattern.

    - Checks explicit 'timeframes' field in config first
    - Falls back to sensible defaults based on pattern type
    """
    pattern = get_pattern(name)
    if not pattern:
        return ["1D"]  # Safe default

    # Explicit timeframes in config take priority
    if "timeframes" in pattern:
        return pattern["timeframes"]

    # Determine defaults based on pattern type
    pattern_type = get_pattern_type(name)

    if pattern_type == "candle":
        candles = pattern.get("candles", 1)
        return _CANDLE_TF_DEFAULTS.get(candles, ["1D"])

    if pattern_type == "price":
        return _PRICE_TF_DEFAULT

    return ["1D"]


def get_pattern_min_timeframe(name: str) -> str:
    """Get minimum recommended timeframe for pattern."""
    timeframes = get_pattern_timeframes(name)
    for tf in _TF_ORDER:
        if tf in timeframes:
            return tf
    return "1D"


def is_pattern_valid_for_timeframe(name: str, timeframe: str) -> bool:
    """Check if pattern is valid for given timeframe."""
    return timeframe in get_pattern_timeframes(name)


__all__ = [
    # Candle patterns
    "CANDLE_PATTERNS",
    "get_candle_pattern",
    "list_candle_patterns",
    "get_candle_patterns_by_signal",
    "get_candle_patterns_by_category",
    # Price patterns
    "PRICE_PATTERNS",
    "get_price_pattern",
    "list_price_patterns",
    # Unified access
    "get_pattern",
    "list_all_patterns",
    "get_pattern_type",
    # Timeframe support
    "get_pattern_timeframes",
    "get_pattern_min_timeframe",
    "is_pattern_valid_for_timeframe",
]
