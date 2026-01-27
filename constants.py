"""
Shared constants for Trading Agent.

Single source of truth for configuration that's used across layers.
"""

# Column display priority for data tables
# Order: time → key metrics → OHLCV → flags → time components → neighbors
COLUMN_ORDER = [
    # 1. Time — always first
    "date", "timestamp",

    # 2. Key metrics
    "change", "gap", "range",

    # 3. OHLCV
    "open", "high", "low", "close", "volume",

    # 4. Flags
    "is_green", "gap_filled",

    # 5. Time components
    "weekday", "month", "year",

    # 6. Neighbors
    "prev_change", "next_change",
]
