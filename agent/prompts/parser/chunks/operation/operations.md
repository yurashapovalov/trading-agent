# Operations

Extract the type of analysis user wants.

<rules>
- stats, average, summary, mean → operation="stats"
- compare X and Y, X vs Y → operation="compare"
- top N, best, worst, biggest, smallest → operation="top_n"
- by hour, by month, by weekday, breakdown → operation="seasonality"
- show days where, find days with, filter → operation="filter"
- streak, consecutive, in a row → operation="streak"
- show data, list days, list all → operation="list"
- all X, every X, each X (with filter) → operation="list"
</rules>

<examples>
Input: average range for 2024
Output: {"operation": "stats", "metric": "range", "period": {"type": "year", "value": "2024"}}

Input: compare January and February 2024
Output: {"operation": "compare", "compare": ["January", "February"], "period": {"type": "year", "value": "2024"}}

Input: compare RTH and ETH
Output: {"operation": "compare", "compare": ["RTH", "ETH"]}

Input: top 10 days by volume in 2024
Output: {"operation": "top_n", "top_n": 10, "sort_by": "volume", "period": {"type": "year", "value": "2024"}}

Input: worst days in January 2024
Output: {"operation": "top_n", "sort_by": "change", "sort_order": "asc", "period": {"type": "month", "value": "2024-01"}}

Input: volatility by weekday for 2024
Output: {"operation": "seasonality", "group_by": "weekday", "metric": "range", "period": {"type": "year", "value": "2024"}}

Input: hourly breakdown of volume
Output: {"operation": "seasonality", "group_by": "hour", "metric": "volume", "unclear": ["period"]}

Input: find days with range over 300
Output: {"operation": "filter", "condition": "range > 300", "unclear": ["period"]}

Input: longest green streak in 2024
Output: {"operation": "streak", "period": {"type": "year", "value": "2024"}}

Input: show all days in January 2024
Output: {"operation": "list", "period": {"type": "month", "value": "2024-01"}}

Input: top 10 volatile days in 2024
Output: {"operation": "top_n", "top_n": 10, "sort_by": "range", "sort_order": "desc", "period": {"type": "year", "value": "2024"}}

Input: compare average volatility of Mondays and Fridays in 2024
Output: {"operation": "compare", "compare": ["Monday", "Friday"], "metric": "range", "period": {"type": "year", "value": "2024"}}

Input: find top 5 days with max volume in 2024
Output: {"operation": "top_n", "top_n": 5, "sort_by": "volume", "sort_order": "desc", "period": {"type": "year", "value": "2024"}}

Input: how many times in 2024 were there 3+ red days in a row
Output: {"operation": "streak", "condition": "change < 0", "streak_length": 3, "period": {"type": "year", "value": "2024"}}

Input: which month historically has the best growth
Output: {"operation": "seasonality", "group_by": "month", "metric": "change", "sort_order": "desc"}

Input: is there seasonality in volatility by month
Output: {"operation": "seasonality", "group_by": "month", "metric": "range"}

Input: which weekday is historically most volatile
Output: {"operation": "seasonality", "group_by": "weekday", "metric": "range", "sort_order": "desc"}

Input: when is high usually formed
Output: {"operation": "seasonality", "group_by": "hour", "what": "high_formation_time"}

Input: what time of day does NQ most often reach daily high
Output: {"operation": "seasonality", "group_by": "hour", "what": "high_formation_time"}

Input: what percent of days is low formed after 14:00
Output: {"operation": "stats", "what": "low_formation_time", "condition": "low_time > 14:00"}

Input: stats for days after 3+ green days in a row
Output: {"operation": "stats", "condition": "prev_streak_green >= 3", "unclear": ["period"]}

Input: show volatility by month for 2024
Output: {"operation": "seasonality", "group_by": "month", "metric": "range", "period": {"type": "year", "value": "2024"}}

Input: volatility for 2024
Output: {"operation": "stats", "metric": "range", "period": {"type": "year", "value": "2024"}}

Input: top 5 most volatile days in 2024
Output: {"operation": "top_n", "top_n": 5, "sort_by": "range", "sort_order": "desc", "period": {"type": "year", "value": "2024"}}

Input: average volume
Output: {"operation": "stats", "metric": "volume", "unclear": ["period"]}

Input: best days
Output: {"operation": "top_n", "sort_by": "change", "sort_order": "desc", "unclear": ["period", "top_n"]}

Input: compare years
Output: {"operation": "compare", "unclear": ["compare_items"]}

Input: show all data
Output: {"operation": "list", "unclear": ["period"]}

Input: green days percentage for 2024
Output: {"operation": "stats", "metric": "green_pct", "period": {"type": "year", "value": "2024"}}

Input: volatility for all Fridays in April 2023
Output: {"operation": "list", "metric": "range", "period": {"type": "month", "value": "2023-04"}, "weekday_filter": ["Friday"]}

Input: all Mondays in 2024
Output: {"operation": "list", "period": {"type": "year", "value": "2024"}, "weekday_filter": ["Monday"]}

Input: every OPEX day in 2024
Output: {"operation": "list", "period": {"type": "year", "value": "2024"}, "event_filter": "opex"}

Input: each Friday last month
Output: {"operation": "list", "period": {"type": "relative", "value": "last_month"}, "weekday_filter": ["Friday"]}
</examples>
