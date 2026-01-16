"""
Base prompt for all data handlers.

Common building blocks (source, filters, grouping, metrics) documentation.
"""

HANDLER_PROMPT = """<building_blocks>
## Query Building Blocks

### 1. SOURCE — where data comes from

| Value | When to use |
|-------|-------------|
| "minutes" | Intraday analysis: time of high/low, session stats, hourly data |
| "daily" | Daily statistics: avg range, volatility, day filtering |
| "daily_with_prev" | Gap analysis (needs previous day's close) |

### 2. FILTERS — what data to include

**Period** — half-open interval [start, end):
- period_start: first day INCLUDED
- period_end: first day NOT included (the day AFTER the last day user wants)
- Use "all" for full dataset when user doesn't specify period

Rule: period_end = first day of NEXT period
- "за 2024" → end = "2025-01-01" (first day of 2025)
- "2020-2025" → end = "2026-01-01" (first day of 2026)
- "январь 2024" → end = "2024-02-01" (first day of February)

**Calendar filters (optional):**
- specific_dates: ["2024-01-15", "2024-03-10"] - exact dates
- years: [2020, 2024] - specific years
- months: [1, 6] - months (1-12)
- weekdays: ["Monday", "Friday"] - day names in English

**Time of day:**
- session: "RTH", "ETH", "OVERNIGHT", "ASIAN", "EUROPEAN", etc.
- time_start / time_end: "HH:MM:SS" for custom time range

Use session when user mentions session name. Use time_start/end for custom ranges.

**Conditions:**
- conditions: [{"column": "change_pct", "operator": "<", "value": -2.0}]
- Available columns for filtering:
  - Basic: open, high, low, close, volume
  - Computed: range, change_pct, gap_pct (only with daily_with_prev)
  - Close to extremes: close_to_low (close - low), close_to_high (high - close)
  - Open to extremes: open_to_high (high - open), open_to_low (open - low)
  - Candle structure: body (|close - open|), upper_wick, lower_wick

**Holidays (optional):**
- market_holidays: "include" (default) | "exclude" | "only"
- early_close_days: "include" (default) | "exclude" | "only"

Modes:
- "include": Include these days in the results (default behavior)
- "exclude": Remove these days from results (for "clean" statistics)
- "only": Show ONLY these days (for holiday trading analysis)

When to ASK (return clarification):
- Volatility/range analysis for periods > 1 month — holidays can skew stats
- Comparing time periods that may have different holiday counts
- User asks for "clean" or "accurate" statistics

When NOT to ask (just include by default):
- Simple lookups ("what was the high on Jan 5?")
- Short periods (< 2 weeks)
- User explicitly mentions dates

Examples:
- "average range excluding holidays" → market_holidays: "exclude"
- "show me early close days" → early_close_days: "only"
- "how does market behave on shortened days?" → early_close_days: "only"

### 3. GROUPING — how to aggregate

| Value | Result |
|-------|--------|
| "none" | Individual rows (for filtering, top_n) |
| "total" | One summary row |
| "1min", "5min", "15min", "30min", "hour" | By time of day |
| "day", "week", "month", "quarter", "year" | By calendar period |
| "weekday" | By day of week (Monday-Friday) |
| "session" | By trading session |

### 4. METRICS — what to calculate

For grouping != "none":
- {"metric": "count", "alias": "trading_days"}
- {"metric": "avg", "column": "range", "alias": "avg_range"}
- {"metric": "sum", "column": "volume", "alias": "total_volume"}
- {"metric": "stddev", "column": "change_pct", "alias": "volatility"}
- {"metric": "min", "column": "low", "alias": "min_low"}
- {"metric": "max", "column": "high", "alias": "max_high"}

For grouping == "none":
- {"metric": "open"}, {"metric": "close"}, {"metric": "range"}, etc.
</building_blocks>"""

EXAMPLES = ""
