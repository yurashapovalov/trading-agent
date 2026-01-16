"""
Find extremum handler.

Handles questions about EXACT time of events (open, high, low, close, max_volume)
on SPECIFIC date(s).
"""

HANDLER_PROMPT = """<task>
User wants to know EXACT time when an event occurred on specific date(s).

This is about SPECIFIC EVENTS, not patterns:
- "во сколько был high вчера?" → exact timestamp
- "когда открылась сессия?" → open time
- "время high/low 10 января" → exact timestamps

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
5. **session**: If user specifies (RTH, ETH, etc.)

CRITICAL for follow-up questions:
- If user asks "когда она началась" / "во сколько открылась" after discussing a date → find: "open"
- If user asks "когда закончилась" → find: "close"

CRITICAL: This returns EXACT TIMESTAMPS (e.g., "09:47:00"), not distributions.
Result: date → event_time, event_value (depends on find type)

Return JSON with type: "data" and query_spec.
</task>"""

EXAMPLES = """
Question: "Во сколько был high и low на NQ 10 января 2025?"
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

Question: "Во сколько открылась сессия 20 ноября?"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "2025-11-20",
      "period_end": "2025-11-21"
    },
    "grouping": "none",
    "metrics": [],
    "special_op": "find_extremum",
    "find_extremum_spec": {"find": "open"}
  }
}
```

Question: "Когда закончилась RTH сессия вчера?"
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

Question: "Время high на RTH за последнюю неделю"
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

Question: "Покажи OHLC с временем за 10 января"
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
"""
