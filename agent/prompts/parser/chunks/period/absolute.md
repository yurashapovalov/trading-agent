# Period: Absolute (Year, Month, Date, Quarter)

Extract absolute time periods.

<rules>
YEAR (type="year"):
- 2024 → value="2024"
- in 2023 → value="2023"

MONTH (type="month"):
- January 2024 → value="2024-01"
- March 2023 → value="2023-03"
- December (no year) → unclear=["year"]

DATE (type="date"):
- May 15, 2024 → value="2024-05-15"
- January 10 (no year) → unclear=["year"]

QUARTER (type="quarter"):
- Q1 2024 → year=2024, q=1
- Q4 2023 → year=2023, q=4

RANGE (type="range"):
- Jan 1 to Jan 15, 2024 → start="2024-01-01", end="2024-01-15"
- 2020-2024 → start="2020-01-01", end="2024-12-31"
- from March to May 2024 → start="2024-03-01", end="2024-05-31"
</rules>

<examples>
Input: volatility for 2024
Output: {"period": {"type": "year", "value": "2024"}, "metric": "range"}

Input: how was January 2024
Output: {"period": {"type": "month", "value": "2024-01"}, "unclear": ["metric"]}

Input: stats for March
Output: {"period": {"type": "month"}, "unclear": ["year"], "operation": "stats"}

Input: what happened on May 15, 2024
Output: {"period": {"type": "date", "value": "2024-05-15"}}

Input: what happened on May 16, 2024
Output: {"period": {"type": "date", "value": "2024-05-16"}}

Input: Q1 2024 performance
Output: {"period": {"type": "quarter", "year": 2024, "q": 1}, "metric": "change"}

Input: compare 2023 and 2024
Output: {"operation": "compare", "compare": ["2023", "2024"]}

Input: range from January to March 2024
Output: {"period": {"type": "range", "start": "2024-01-01", "end": "2024-03-31"}, "metric": "range"}

Input: stats for Fridays 2020-2025
Output: {"operation": "stats", "weekday_filter": ["Friday"], "period": {"type": "range", "start": "2020-01-01", "end": "2025-12-31"}}

Input: how did NQ behave in December over last 3 years
Output: {"operation": "compare", "period": {"type": "relative", "value": "last_n_years", "n": 3}, "condition": "month == 12", "group_by": "year", "metric": "change"}

Input: how did NQ behave in December over the last 3 years
Output: {"operation": "compare", "period": {"type": "relative", "value": "last_n_years", "n": 3}, "condition": "month == 12", "group_by": "year", "metric": "change"}

Input: show stats for March 2024
Output: {"operation": "stats", "period": {"type": "month", "value": "2024-03"}, "unclear": ["metric"]}

Input: now compare with April
Output: {"operation": "compare", "compare": ["March", "April"], "unclear": ["year"]}

Input: which month was better for longs
Output: {"operation": "compare", "metric": "change", "unclear": ["period", "months"]}
</examples>
