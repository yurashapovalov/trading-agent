# Unclear Rules

When to ask for clarification.

<rules>
CRITICAL: Add to unclear[] when info is MISSING for data requests.

unclear: ["year"] when:
- Month without year: "January", "March stats"
- Date without year: "May 15", "on the 10th"
- ANY month/date reference without explicit year

unclear: ["period"] when:
- No time reference at all
- "show volatility" (volatility of when?)
- "top days by volume" (top days from when?)
- Metric mentioned but no time period

unclear: ["metric"] when:
- Vague data request: "stats for 2024"
- No specific measurement: "how was the year"
- Generic request: "show data for January"
- "summary" without what to summarize

Multiple unclear:
- "show stats" → unclear: ["metric", "period"]
- "how was January" → unclear: ["metric", "year"]
- "best day" → unclear: ["metric", "period"]
</rules>

<examples>
Input: stats for January
Output: {"period": {"type": "month"}, "operation": "stats", "unclear": ["year", "metric"]}

Input: show volatility
Output: {"metric": "range", "unclear": ["period"]}

Input: how was December
Output: {"period": {"type": "month"}, "unclear": ["year", "metric"]}

Input: top 5 days
Output: {"operation": "top_n", "top_n": 5, "unclear": ["period", "metric"]}

Input: what happened on May 15
Output: {"period": {"type": "date"}, "unclear": ["year"]}

Input: show me the data
Output: {"unclear": ["period", "metric"]}

Input: compare January and February
Output: {"operation": "compare", "compare": ["January", "February"], "unclear": ["year"]}

Input: best performing month
Output: {"operation": "top_n", "group_by": "month", "metric": "change", "unclear": ["period"]}

Input: stats
Output: {"operation": "stats", "unclear": ["metric", "period"]}

Input: show data
Output: {"operation": "list", "unclear": ["metric", "period"]}

Input: volatility
Output: {"metric": "range", "unclear": ["period"]}

Input: volume
Output: {"metric": "volume", "unclear": ["period"]}

Input: how did it go
Output: {"unclear": ["metric", "period"]}

Input: what's the average
Output: {"operation": "stats", "unclear": ["metric", "period"]}
</examples>
