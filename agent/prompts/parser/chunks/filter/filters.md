# Filters

Extract filtering conditions.

<rules>
WEEKDAY filter:
- Mondays, Fridays → weekday_filter=["Monday"], ["Friday"]
- Mon/Wed/Fri → weekday_filter=["Monday", "Wednesday", "Friday"]

SESSION filter:
- RTH, regular hours → session="RTH"
- ETH, extended hours → session="ETH"
- overnight, night session → session="OVERNIGHT"
- Asian session → session="ASIAN"
- European session → session="EUROPEAN"

EVENT filter:
- OPEX, options expiration → event_filter="opex"
- FOMC days → event_filter="fomc"
- NFP, non-farm payroll → event_filter="nfp"
- CPI days → event_filter="cpi"
- quad witching → event_filter="quad_witching"

CONDITION filter:
- range > 300 → condition="range > 300"
- close > open → condition="close > open"
- change > 2% → condition="change_pct > 2"
- gap > 1% → condition="gap_pct > 1"
- volume > 1M → condition="volume > 1000000"

TIME filter (intraday):
- from 9:30 to 12:00 → time: {start: "09:30", end: "12:00"}
- first hour → time: {start: "09:30", end: "10:30"}
- last hour → time: {start: "16:00", end: "17:00"}
</rules>

<examples>
Input: volatility on Fridays in 2024
Output: {"metric": "range", "weekday_filter": ["Friday"], "period": {"type": "year", "value": "2024"}}

Input: Monday vs Friday performance
Output: {"operation": "compare", "compare": ["Monday", "Friday"], "metric": "change"}

Input: RTH volume for January 2024
Output: {"metric": "volume", "session": "RTH", "period": {"type": "month", "value": "2024-01"}}

Input: compare RTH and overnight
Output: {"operation": "compare", "compare": ["RTH", "OVERNIGHT"]}

Input: OPEX day stats for 2024
Output: {"event_filter": "opex", "operation": "stats", "period": {"type": "year", "value": "2024"}}

Input: how volatile are FOMC days
Output: {"event_filter": "fomc", "metric": "range"}

Input: days with range over 300 points
Output: {"operation": "filter", "condition": "range > 300", "unclear": ["period"]}

Input: green days with gap up
Output: {"operation": "filter", "condition": "close > open AND gap > 0", "unclear": ["period"]}

Input: first trading hour stats
Output: {"time": {"start": "09:30", "end": "10:30"}, "operation": "stats", "unclear": ["period", "metric"]}

Input: volume from 9:30 to 12:00
Output: {"metric": "volume", "time": {"start": "09:30", "end": "12:00"}, "unclear": ["period"]}

Input: stats for Fridays 2020-2025 where close - low >= 200
Output: {"operation": "stats", "weekday_filter": ["Friday"], "condition": "close - low >= 200", "period": {"type": "range", "start": "2020-01-01", "end": "2025-12-31"}}

Input: days when dropped more than 2%
Output: {"operation": "filter", "condition": "change_pct < -2", "unclear": ["period"]}

Input: days when overnight high was broken in RTH
Output: {"operation": "filter", "condition": "rth_high > overnight_high", "session": "RTH", "unclear": ["period"]}

Input: compare days when opened above prev close vs below
Output: {"operation": "compare", "compare": ["gap_up", "gap_down"]}

Input: RTH range on options expiration days vs regular Fridays
Output: {"operation": "compare", "compare": ["opex", "regular_friday"], "metric": "range", "session": "RTH"}

Input: Mondays vs Fridays - where are more gaps
Output: {"operation": "compare", "compare": ["Monday", "Friday"], "metric": "gap"}

Input: Fridays
Output: {"weekday_filter": ["Friday"], "unclear": ["period", "metric"]}

Input: RTH data
Output: {"session": "RTH", "unclear": ["period", "metric"]}

Input: ETH stats
Output: {"session": "ETH", "operation": "stats", "unclear": ["period", "metric"]}

Input: overnight
Output: {"session": "OVERNIGHT", "unclear": ["period", "metric"]}

Input: OPEX days
Output: {"event_filter": "opex", "unclear": ["period", "metric"]}

Input: FOMC
Output: {"event_filter": "fomc", "unclear": ["period", "metric"]}

Input: RTH vs ETH
Output: {"operation": "compare", "compare": ["RTH", "ETH"], "unclear": ["period", "metric"]}

Input: range over 300
Output: {"operation": "filter", "condition": "range > 300", "unclear": ["period"]}

Input: all Fridays in April 2023
Output: {"operation": "list", "weekday_filter": ["Friday"], "period": {"type": "month", "value": "2023-04"}}

Input: every Monday in 2024
Output: {"operation": "list", "weekday_filter": ["Monday"], "period": {"type": "year", "value": "2024"}}

Input: all OPEX days in 2024
Output: {"operation": "list", "event_filter": "opex", "period": {"type": "year", "value": "2024"}}

Input: each trading day last week
Output: {"operation": "list", "period": {"type": "relative", "value": "last_week"}}
</examples>
