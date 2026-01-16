"""
Find extremum handler.

Handles questions about EXACT time of high/low on SPECIFIC date(s).
"""

HANDLER_PROMPT = """<task>
User wants to know EXACT time when high/low occurred on specific date(s).

This is about SPECIFIC EVENTS, not patterns:
- "во сколько был high вчера?" → exact timestamp
- "время high/low 10 января" → exact timestamps

Key decisions:
1. **source**: Always "minutes" (need intraday data)
2. **special_op**: "find_extremum"
3. **find_extremum_spec.find**:
   - "high" — only if asks about HIGH
   - "low" — only if asks about LOW
   - "both" — if mentions both or unclear
4. **filters**: Use period or specific_dates to select day(s)
   - Single date: period_start = date, period_end = date + 1 day
   - Multiple dates: use specific_dates
5. **session**: If user specifies

CRITICAL: This returns EXACT TIMESTAMPS (e.g., "09:47:00"), not distributions.
Result: date → high_time, high_value, low_time, low_value

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

Question: "Когда был low в эти дни: 15 марта и 20 марта 2024?"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "all",
      "period_end": "all",
      "specific_dates": ["2024-03-15", "2024-03-20"]
    },
    "grouping": "none",
    "metrics": [],
    "special_op": "find_extremum",
    "find_extremum_spec": {"find": "low"}
  }
}
```
"""
