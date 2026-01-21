"""
CONFIG — Configuration and settings.

Contains domain-specific configuration:
- market/: Trading calendar, instruments, events, holidays
- backtest/: Execution parameters, output metrics (for future use)
- patterns/: Candle and price pattern definitions
"""

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
