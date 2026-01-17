"""
Simple statistics handler.

Handles basic statistics requests for a period.
"""

HANDLER_PROMPT = """<task>
User wants basic statistics for a period.

Key decisions:
1. **source**: Usually "daily" for daily stats
2. **period**: Extract from question or use "all"
3. **grouping**: "total" for summary, or "month"/"year"/"weekday" for breakdown
4. **metrics**: avg range, avg change, stddev (volatility), count

Return JSON with type: "data" and query_spec.
</task>

<session_rule>
Session field handling:
- User explicitly says "RTH", "ETH", "OVERNIGHT" → use that session value
- User says "session" without naming which one → session: "_default_"
- User asks about "day/день" without specifying session → DO NOT set session (leave it null/omit)

CRITICAL — Ambiguous "day" references:
When user asks about a specific DATE with words like "day", "throughout the day", "за день", "в течении дня" — this is AMBIGUOUS. DO NOT guess RTH or ETH. Simply omit session field and the system will ask for clarification with accurate times.
</session_rule>"""

EXAMPLES = """
Question: "Show NQ statistics for January 2024"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "2024-01-01",
      "period_end": "2024-02-01"
    },
    "grouping": "total",
    "metrics": [
      {"metric": "avg", "column": "range", "alias": "avg_range"},
      {"metric": "avg", "column": "change_pct", "alias": "avg_change"},
      {"metric": "stddev", "column": "change_pct", "alias": "volatility"},
      {"metric": "count", "alias": "trading_days"}
    ],
    "special_op": "none"
  }
}
```

Question: "Volatility by month for 2024"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "2024-01-01",
      "period_end": "2025-01-01"
    },
    "grouping": "month",
    "metrics": [
      {"metric": "avg", "column": "range", "alias": "avg_range"},
      {"metric": "stddev", "column": "change_pct", "alias": "volatility"},
      {"metric": "count", "alias": "trading_days"}
    ],
    "special_op": "none"
  }
}
```

Question: "Average volatility of NQ"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "all",
      "period_end": "all"
    },
    "grouping": "total",
    "metrics": [
      {"metric": "avg", "column": "range", "alias": "avg_range"},
      {"metric": "stddev", "column": "change_pct", "alias": "volatility"},
      {"metric": "count", "alias": "trading_days"}
    ],
    "special_op": "none"
  }
}
```

Question: "What happened May 16 throughout the day?" (also: "что было 16 мая в течении дня")
Note: AMBIGUOUS — user said "day" but didn't specify which session. DO NOT set session, system will clarify.
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "2024-05-16",
      "period_end": "2024-05-17"
    },
    "grouping": "none",
    "special_op": "none"
  }
}
```
"""
