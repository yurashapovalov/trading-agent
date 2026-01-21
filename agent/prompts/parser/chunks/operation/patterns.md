# Complex Patterns

Extract patterns involving previous day conditions, sequences, and multi-day analysis.

<rules>
PREVIOUS DAY conditions:
- after gap up → condition involves prev day gap
- day after X → sequence analysis
- following day → next day stats

STREAK patterns:
- N days in a row → streak analysis
- consecutive green/red → streak detection
- after N+ days of X → post-streak analysis

SEQUENCE patterns:
- what happens after X → conditional next-day stats
- if X then Y → correlation/causation analysis
</rules>

<examples>
Input: find days when NQ dropped more than 2% after rising more than 1% previous day
Output: {"operation": "filter", "condition": "change_pct < -2 AND prev_change_pct > 1", "unclear": ["period"]}

Input: what happens the next day after gap up more than 1%
Output: {"operation": "stats", "what": "next_day", "condition": "gap_pct > 1", "unclear": ["period"]}

Input: average range on Monday after Friday with range > 400
Output: {"operation": "stats", "metric": "range", "weekday_filter": ["Monday"], "condition": "prev_friday_range > 400", "unclear": ["period"]}

Input: how often is high formed in first RTH hour
Output: {"operation": "stats", "what": "high_in_first_hour", "session": "RTH", "unclear": ["period"]}

Input: how many times did price close above previous day high in 2024
Output: {"operation": "filter", "condition": "close > prev_high", "period": {"type": "year", "value": "2024"}}

Input: at what time is low most often formed if day closed green
Output: {"operation": "seasonality", "group_by": "hour", "what": "low_formation", "condition": "change > 0", "unclear": ["period"]}

Input: days when first hour range was more than 50% of daily range
Output: {"operation": "filter", "condition": "first_hour_range > daily_range * 0.5", "unclear": ["period"]}

Input: how did NQ behave in December over last 3 years
Output: {"operation": "stats", "period": {"type": "month", "value": "12"}, "compare": ["2022", "2023", "2024"]}

Input: if Q1 was red, what is usually Q2
Output: {"operation": "stats", "what": "Q2", "condition": "Q1_change < 0"}

Input: does January volatility correlate with yearly return
Output: {"operation": "correlation", "compare": ["january_range", "yearly_change"]}
</examples>
