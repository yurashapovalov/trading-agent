"""
Smart defaults — single source of truth.

All implicit behaviors documented here.
When defaults accumulate, patterns emerge for optimization.

Used by:
- Parser: keyword detection, default values
- Expander: fill missing fields
- DataBuilder: query limits
"""

from __future__ import annotations


# =============================================================================
# ANALYTICS DEFAULTS
# =============================================================================

# Default granularity for analytics/statistics
# Day is the natural unit for trading — "statistics" means "daily statistics"
DEFAULT_GRANULARITY = "day"

# Default grouping when analytics without explicit dimension
# ["day"] = aggregate to daily level (trading days)
DEFAULT_ANALYTICS_GROUP: list[str] = ["day"]

# Default metrics for "statistics" queries when no specific metric requested
DEFAULT_STATISTICS_METRICS = [
    {"func": "count", "field": "*", "alias": "days"},
    {"func": "avg", "field": "range", "alias": "avg_range"},
    {"func": "avg", "field": "volume", "alias": "avg_volume"},
    {"func": "stddev", "field": "range", "alias": "volatility"},
    {"func": "min", "field": "range", "alias": "min_range"},
    {"func": "max", "field": "range", "alias": "max_range"},
]


# =============================================================================
# DATA DEFAULTS
# =============================================================================

# Default symbol when not specified
DEFAULT_SYMBOL = "NQ"

# Default sort for raw data queries
DEFAULT_DATA_SORT = [{"field": "date", "dir": "desc"}]

# Default limit for raw data (prevent huge result sets)
DEFAULT_DATA_LIMIT = 50

# Recent period when no dates specified for data queries
DEFAULT_RECENT_DAYS = 30


# =============================================================================
# EVENT_TIME DEFAULTS
# =============================================================================

# Default time grouping for "when does X form?"
DEFAULT_EVENT_TIME_GROUP = "hour"


# =============================================================================
# PATTERN DEFAULTS
# =============================================================================

# Lookback period for breakout patterns
DEFAULT_BREAKOUT_LOOKBACK = 20

# Period for narrow range patterns (NR4 = 4, NR7 = 7)
DEFAULT_NARROW_RANGE_PERIOD = 4


# =============================================================================
# COMPARE DEFAULTS
# =============================================================================

# Default metrics for comparison queries
DEFAULT_COMPARE_METRICS = [
    {"func": "avg", "field": "range"},
    {"func": "avg", "field": "volume"},
    {"func": "count", "field": "*"},
]


# =============================================================================
# INDICATOR DEFAULTS
# =============================================================================

DEFAULT_RSI_PERIOD = 14
DEFAULT_SMA_PERIOD = 20
DEFAULT_EMA_PERIOD = 20
DEFAULT_ATR_PERIOD = 14
DEFAULT_MACD_FAST = 12
DEFAULT_MACD_SLOW = 26
DEFAULT_MACD_SIGNAL = 9
DEFAULT_BOLLINGER_PERIOD = 20
DEFAULT_BOLLINGER_STD = 2.0
