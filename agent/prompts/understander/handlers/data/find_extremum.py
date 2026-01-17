"""
Find extremum handler.

Handles questions about EXACT time of events (open, high, low, close, max_volume)
on SPECIFIC date(s).
"""

HANDLER_PROMPT = """<task>
User wants to know EXACT time when an event occurred on specific date(s).

This is about SPECIFIC EVENTS, not patterns:
- "what time was high yesterday?" → exact timestamp
- "when did session open?" → open time
- "time of high/low on Jan 10" → exact timestamps

Key decisions:
1. **source**: Always "minutes" (need intraday data)
2. **special_op**: "find_extremum"
3. **find_extremum_spec.find** — choose based on what user asks:
   - "open" — when session/day started (first bar time + price)
   - "close" — when session/day ended (last bar time + price)
   - "high" — when maximum price occurred
   - "low" — when minimum price occurred
   - "max_volume" — when highest volume occurred
   - "both" — high and low
   - "ohlc" — open + high + low + close
   - "all" — open + high + low + close + max_volume
4. **filters**: Use period or specific_dates to select day(s)
   - Single date: period_start = date, period_end = date + 1 day
   - Multiple dates: use specific_dates

CRITICAL for follow-up questions:
- If user asks "when did it start" / "what time did it open" after discussing a date → find: "open"
- If user asks "when did it end" → find: "close"

CRITICAL: This returns EXACT TIMESTAMPS (e.g., "09:47:00"), not distributions.
Result: date → event_time, event_value (depends on find type)

Return JSON with type: "data" and query_spec.
</task>

<session_rule>
Session field handling:
- User explicitly says "RTH", "ETH", "OVERNIGHT" → use that session value
- User says "session" without naming which one → session: "_default_"
- User asks about "day/день" without specifying session → DO NOT set session (leave it null/omit)

CRITICAL — Ambiguous "day" references:
When user asks about a specific DATE with words like "day", "throughout the day", "за день", "в течении дня" — this is AMBIGUOUS. DO NOT guess RTH or ETH. Simply omit session field and the system will ask for clarification with accurate times (including early close days).
</session_rule>"""

EXAMPLES = """
Question: "What time was high and low on NQ Jan 10 2025?"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "2025-01-10",
      "period_end": "2025-01-11"
    },
    "grouping": "none",
    "metrics": [],
    "special_op": "find_extremum",
    "find_extremum_spec": {"find": "both"}
  }
}
```

Question: "What time did session open on Nov 20?"
Note: User says "session" but doesn't specify WHICH session (RTH/ETH/etc) → use "_default_" marker
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "2025-11-20",
      "period_end": "2025-11-21",
      "session": "_default_"
    },
    "grouping": "none",
    "metrics": [],
    "special_op": "find_extremum",
    "find_extremum_spec": {"find": "open"}
  }
}
```

Question: "session open on Nov 20"
Note: Same case — "session" mentioned but not specified → "_default_"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "2025-11-20",
      "period_end": "2025-11-21",
      "session": "_default_"
    },
    "grouping": "none",
    "metrics": [],
    "special_op": "find_extremum",
    "find_extremum_spec": {"find": "open"}
  }
}
```

Question: "When did RTH session end yesterday?"
Note: User explicitly says "RTH" → use "RTH" directly
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "2025-01-16",
      "period_end": "2025-01-17",
      "session": "RTH"
    },
    "grouping": "none",
    "metrics": [],
    "special_op": "find_extremum",
    "find_extremum_spec": {"find": "close"}
  }
}
```

Question: "Time of high on RTH for last week"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "2025-01-09",
      "period_end": "2025-01-16",
      "session": "RTH"
    },
    "grouping": "none",
    "metrics": [],
    "special_op": "find_extremum",
    "find_extremum_spec": {"find": "high"}
  }
}
```

Question: "Show OHLC with times for Jan 10"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "2025-01-10",
      "period_end": "2025-01-11"
    },
    "grouping": "none",
    "metrics": [],
    "special_op": "find_extremum",
    "find_extremum_spec": {"find": "ohlc"}
  }
}
```

Question: "What happened on May 16 throughout the day?" (also: "что было 16 мая в течении дня")
Note: AMBIGUOUS — user said "day" but didn't specify which session. DO NOT set session, system will clarify.
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "2024-05-16",
      "period_end": "2024-05-17"
    },
    "grouping": "none",
    "special_op": "find_extremum",
    "find_extremum_spec": {"find": "ohlc"}
  }
}
```

Question: "Show data for trading day May 16"
Note: User explicitly said "trading day" → no session filter, use trading day boundaries
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "2023-05-16",
      "period_end": "2023-05-17"
    },
    "grouping": "none",
    "metrics": [],
    "special_op": "find_extremum",
    "find_extremum_spec": {"find": "all"}
  }
}
```
"""
