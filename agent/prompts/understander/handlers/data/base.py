"""
Base prompt for all data handlers.

Common building blocks documentation.
"""

HANDLER_PROMPT = """<building_blocks>
## 1. SOURCE — data granularity

| Value | Use case |
|-------|----------|
| "minutes" | Intraday: time of high/low, session stats, hourly patterns |
| "daily" | Daily stats: avg range, volatility, day filtering |
| "daily_with_prev" | Gap analysis (needs previous day's close) |

## 2. FILTERS — data selection

**Period** (half-open interval [start, end)):
- period_start: first day INCLUDED
- period_end: day AFTER last wanted (NOT included)
- "all": full dataset (code resolves to actual dates)

Examples:
- "за 2024" → start: "2024-01-01", end: "2025-01-01"
- "январь 2024" → start: "2024-01-01", end: "2024-02-01"

**Calendar filters:**
- specific_dates: ["2024-01-15", "2024-03-10"]
- years: [2020, 2024]
- months: [1, 6] (1-12)
- weekdays: ["Monday", "Friday"]

**Session:** See <markers> section for "_default_" usage.

**Conditions:**
- conditions: [{"column": "change_pct", "operator": "<", "value": -2.0}]
- Columns: open, high, low, close, volume, range, change_pct, gap_pct, body

**Holidays:**
- market_holidays: "include" | "exclude" | "only"
- early_close_days: "include" | "exclude" | "only"

## 3. GROUPING — aggregation

| Value | Result |
|-------|--------|
| "none" | Individual rows |
| "total" | One summary row |
| "1min"..."hour" | By time of day |
| "day"..."year" | By calendar period |
| "weekday" | By day of week |
| "session" | By trading session |

## 4. METRICS — calculations

- {"metric": "count", "alias": "trading_days"}
- {"metric": "avg", "column": "range", "alias": "avg_range"}
- {"metric": "sum", "column": "volume"}
- {"metric": "stddev", "column": "change_pct"}
- {"metric": "min" | "max", "column": "..."}
</building_blocks>"""

EXAMPLES = ""
