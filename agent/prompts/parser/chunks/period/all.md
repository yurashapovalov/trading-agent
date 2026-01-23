# Period: All Time (Historical)

Extract when user asks about ALL available data.

<rules>
ALL (type="all"):
- historically → value="all"
- all time → value="all"
- all data → value="all"
- entire history → value="all"
- over the years → value="all"
- across all years → value="all"

Use type="all" when user wants analysis across ALL available data, not a specific period.
Common with seasonality questions (best month, best weekday, patterns).
</rules>

<examples>
Input: which month historically performs best
Output: {"period": {"type": "all", "value": "all"}, "operation": "seasonality", "group_by": "month", "metric": "change"}

Input: what is the best day of week historically
Output: {"period": {"type": "all", "value": "all"}, "operation": "seasonality", "group_by": "weekday", "metric": "change"}

Input: NQ average return by month all time
Output: {"period": {"type": "all", "value": "all"}, "operation": "seasonality", "group_by": "month", "metric": "change"}

Input: historically which quarter is most volatile
Output: {"period": {"type": "all", "value": "all"}, "operation": "seasonality", "group_by": "quarter", "metric": "range"}

Input: what month has the highest win rate over the years
Output: {"period": {"type": "all", "value": "all"}, "operation": "seasonality", "group_by": "month", "metric": "green_pct"}

Input: seasonal patterns in NQ
Output: {"period": {"type": "all", "value": "all"}, "operation": "seasonality", "group_by": "month"}

Input: best performing month across all years
Output: {"period": {"type": "all", "value": "all"}, "operation": "seasonality", "group_by": "month", "metric": "change"}
</examples>
