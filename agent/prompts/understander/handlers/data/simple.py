"""
Simple statistics handler.

Handles basic statistics requests for a period.
"""

HANDLER_PROMPT = """<task>
User wants basic statistics for a period.

Key decisions:
1. **source**: "daily" for aggregated stats, "minutes" when session filter is used
2. **period**: Extract from question or use "all"
3. **grouping**: "total" for summary, or "month"/"year"/"weekday" for breakdown
4. **metrics**: avg range, avg change, stddev (volatility), count

Return JSON with type: "data" and query_spec.
</task>

<source_rule>
CRITICAL — Source selection based on session:
- If session is specified (RTH, ETH, etc.) → source MUST be "minutes"
  (because filtering by time requires minute-level data)
- If no session filter → source can be "daily" for aggregated daily stats

This is a technical constraint: daily source doesn't have timestamp column,
so time-based session filters cannot be applied to it.
</source_rule>

<grouping_rule>
Grouping selection for session queries:
- Single day + session (no explicit breakdown request) → grouping: "total"
  (aggregates all session minutes into one summary row: open, high, low, close, range)
- User explicitly asks "по часам" / "hourly" / "breakdown" → grouping: "hour"
  (returns hourly bars within the session)

Why: Raw minutes for a session = 400+ rows, not useful for "what happened" questions.
Default to "total" for session summary, "hour" only when explicitly requested.
</grouping_rule>

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

Question: "RTH" (follow-up after clarification asking about May 16)
Note: source="minutes" for session filter, grouping="total" to aggregate into session summary.
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "session": "RTH",
      "period_start": "2024-05-16",
      "period_end": "2024-05-17"
    },
    "grouping": "total",
    "metrics": [
      {"metric": "first", "column": "open", "alias": "open"},
      {"metric": "max", "column": "high", "alias": "high"},
      {"metric": "min", "column": "low", "alias": "low"},
      {"metric": "last", "column": "close", "alias": "close"},
      {"metric": "sum", "column": "volume", "alias": "volume"},
      {"metric": "raw", "column": "max(high) - min(low)", "alias": "range"}
    ],
    "special_op": "none"
  }
}
```

Question: "ETH" (follow-up after clarification asking about Nov 29, 2024)
Note: source="minutes" for session filter, grouping="total" for session summary.
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "session": "ETH",
      "period_start": "2024-11-29",
      "period_end": "2024-11-30"
    },
    "grouping": "total",
    "metrics": [
      {"metric": "first", "column": "open", "alias": "open"},
      {"metric": "max", "column": "high", "alias": "high"},
      {"metric": "min", "column": "low", "alias": "low"},
      {"metric": "last", "column": "close", "alias": "close"},
      {"metric": "sum", "column": "volume", "alias": "volume"},
      {"metric": "raw", "column": "max(high) - min(low)", "alias": "range"}
    ],
    "special_op": "none"
  }
}
```

Question: "Show RTH hourly breakdown for May 16" (also: "покажи RTH по часам за 16 мая")
Note: User explicitly asks for hourly → grouping="hour".
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "session": "RTH",
      "period_start": "2024-05-16",
      "period_end": "2024-05-17"
    },
    "grouping": "hour",
    "metrics": [
      {"metric": "first", "column": "open", "alias": "open"},
      {"metric": "max", "column": "high", "alias": "high"},
      {"metric": "min", "column": "low", "alias": "low"},
      {"metric": "last", "column": "close", "alias": "close"},
      {"metric": "sum", "column": "volume", "alias": "volume"}
    ],
    "special_op": "none"
  }
}
```
"""
