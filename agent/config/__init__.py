"""
CONFIG — Configuration and settings.

Contains domain-specific configuration that doesn't expand to atoms:
- defaults.py: Smart defaults (single source of truth)
- completeness.py: Query completeness rules
- market/: Trading calendar, instruments, events
- backtest/: Execution parameters, output metrics
- patterns/: Candle and price pattern definitions

This is NOT molecules (molecules expand to atoms).
Config is parameters passed to engines as-is.
"""

# Smart defaults and completeness rules
from agent.config.defaults import (
    DEFAULT_ANALYTICS_GROUP,
    DEFAULT_STATISTICS_METRICS,
    DEFAULT_SYMBOL,
    DEFAULT_DATA_SORT,
    DEFAULT_DATA_LIMIT,
    DEFAULT_RECENT_DAYS,
    DEFAULT_EVENT_TIME_GROUP,
    DEFAULT_BREAKOUT_LOOKBACK,
    DEFAULT_COMPARE_METRICS,
)

from agent.config.completeness import (
    FieldRequirement,
    FieldRule,
    COMPLETENESS_RULES,
    check_completeness,
    get_defaults,
    get_field_description,
    get_unclear_description,
)

# Re-export for convenience
from agent.config.backtest import (
    PositionSizing,
    Position,
    Execution,
    BacktestMetric,
    BacktestMetrics,
    TradeDetailLevel,
    BacktestOutput,
)

from agent.config.patterns import (
    CANDLE_PATTERNS,
    get_candle_pattern,
    list_candle_patterns,
    get_candle_patterns_by_signal,
    get_candle_patterns_by_category,
    PRICE_PATTERNS,
    get_price_pattern,
    list_price_patterns,
)

__all__ = [
    # Backtest execution
    "PositionSizing",
    "Position",
    "Execution",
    # Backtest output
    "BacktestMetric",
    "BacktestMetrics",
    "TradeDetailLevel",
    "BacktestOutput",
    # Patterns
    "CANDLE_PATTERNS",
    "get_candle_pattern",
    "list_candle_patterns",
    "get_candle_patterns_by_signal",
    "get_candle_patterns_by_category",
    "PRICE_PATTERNS",
    "get_price_pattern",
    "list_price_patterns",
]
