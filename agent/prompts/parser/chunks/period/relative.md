# Period: Relative

Extract relative time periods.

<rules>
RELATIVE (type="relative"):
- today → value="today"
- yesterday → value="yesterday"
- day before yesterday → value="day_before_yesterday"
- last N days → value="last_n_days", n=N
- last week → value="last_week"
- last N weeks → value="last_n_weeks", n=N
- last month → value="last_month"
- year to date / YTD → value="ytd"
- month to date / MTD → value="mtd"
</rules>

<examples>
Input: what was the range yesterday
Output: {"period": {"type": "relative", "value": "yesterday"}, "metric": "range"}

Input: volatility last week
Output: {"period": {"type": "relative", "value": "last_week"}, "metric": "range"}

Input: stats for last 30 days
Output: {"period": {"type": "relative", "value": "last_n_days", "n": 30}, "operation": "stats"}

Input: YTD performance
Output: {"period": {"type": "relative", "value": "ytd"}, "metric": "change"}

Input: show me MTD volume
Output: {"period": {"type": "relative", "value": "mtd"}, "metric": "volume"}

Input: how was last month
Output: {"period": {"type": "relative", "value": "last_month"}, "unclear": ["metric"]}

Input: volume for last month
Output: {"period": {"type": "relative", "value": "last_month"}, "metric": "volume"}

Input: last 3 years
Output: {"period": {"type": "relative", "value": "last_n_years", "n": 3}}

Input: today's range
Output: {"period": {"type": "relative", "value": "today"}, "metric": "range"}
</examples>
