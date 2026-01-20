"""
Pattern definitions — candle and price patterns.

Static knowledge about patterns:
- Detection parameters (for Expander → Computed)
- Descriptions (for Responder context)
- Categories, signals, relationships

Used by:
- Parser: understands pattern names and categories
- Expander: converts pattern → Computed atom
- Responder: explains what patterns mean
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
]
