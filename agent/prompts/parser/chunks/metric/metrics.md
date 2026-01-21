# Metrics

Extract what user wants to measure.

<rules>
SPECIFIC metric → extract:
- volatility, range, daily range → metric="range"
- return, change, performance, move → metric="change"
- volume, trading volume → metric="volume"
- win rate, green days, positive days → metric="green_pct"
- gap, opening gap → metric="gap"

VAGUE request (no specific metric) → unclear: ["metric"]:
- "stats for 2024" → unclear=["metric"]
- "how was the year" → unclear=["metric"]
- "show data" → unclear=["metric"]
</rules>

<examples>
Input: what was the volatility in 2024
Output: {"metric": "range", "period": {"type": "year", "value": "2024"}}

Input: average daily range for January 2024
Output: {"metric": "range", "period": {"type": "month", "value": "2024-01"}, "operation": "stats"}

Input: total volume last week
Output: {"metric": "volume", "period": {"type": "relative", "value": "last_week"}}

Input: return for 2024
Output: {"metric": "change", "period": {"type": "year", "value": "2024"}}

Input: how many green days in 2024
Output: {"metric": "green_pct", "period": {"type": "year", "value": "2024"}}

Input: biggest gaps in January 2024
Output: {"metric": "gap", "period": {"type": "month", "value": "2024-01"}, "sort_by": "gap", "sort_order": "desc"}

Input: show me stats for 2024
Output: {"period": {"type": "year", "value": "2024"}, "operation": "stats", "unclear": ["metric"]}

Input: how was last month
Output: {"period": {"type": "relative", "value": "last_month"}, "unclear": ["metric"]}

Input: what was the max intraday range in percent for 2024
Output: {"metric": "range_pct", "operation": "top_n", "top_n": 1, "sort_order": "desc", "period": {"type": "year", "value": "2024"}}

Input: average pullback from high to close on trend days
Output: {"metric": "high_to_close", "operation": "stats", "condition": "change_pct > 1", "unclear": ["period"]}

Input: correlation between gap size and daily range
Output: {"operation": "correlation", "compare": ["gap", "range"], "unclear": ["period"]}

Input: correlation between volume and price change
Output: {"operation": "correlation", "compare": ["volume", "change"], "unclear": ["period"]}

Input: win rate for strategy: enter at open if gap down > 0.5%, exit at close
Output: {"operation": "backtest", "what": "win_rate", "condition": "gap_pct < -0.5", "entry": "open", "exit": "close", "unclear": ["period"]}

Input: compare volatility and volume
Output: {"operation": "compare", "compare": ["range", "volume"], "unclear": ["period"]}

Input: range for 2024
Output: {"metric": "range", "period": {"type": "year", "value": "2024"}}

Input: daily range
Output: {"metric": "range", "unclear": ["period"]}

Input: trading volume
Output: {"metric": "volume", "unclear": ["period"]}

Input: win rate
Output: {"metric": "green_pct", "unclear": ["period"]}

Input: returns
Output: {"metric": "change", "unclear": ["period"]}

Input: gaps
Output: {"metric": "gap", "unclear": ["period"]}

Input: performance
Output: {"metric": "change", "unclear": ["period"]}
</examples>
