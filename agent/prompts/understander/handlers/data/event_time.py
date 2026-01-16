"""
Event time handler.

Handles questions about WHEN high/low USUALLY forms (distribution pattern).
"""

HANDLER_PROMPT = """<task>
User wants to know WHEN high/low typically forms — distribution over many days.

This is about PATTERNS, not specific dates:
- "когда обычно формируется high?" → distribution
- "в какое время чаще всего low?" → distribution

Key decisions:
1. **source**: Always "minutes" (need intraday data)
2. **special_op**: "event_time"
3. **event_time_spec.find**:
   - "high" — only if asks about HIGH
   - "low" — only if asks about LOW
   - "both" — if mentions both or unclear
4. **grouping**: Time bucket for distribution
   - "1min" — most precise (default)
   - "5min", "15min", "30min", "hour" — if user asks for coarser
5. **session**: If user specifies (RTH, ETH, etc.)

CRITICAL: This returns FREQUENCY DISTRIBUTION, not exact timestamps.
Result: time_bucket → how many days had high/low in that bucket.

Return JSON with type: "data" and query_spec.
</task>"""

EXAMPLES = """
Question: "Когда обычно формируется high на RTH?"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "all",
      "period_end": "all",
      "session": "RTH"
    },
    "grouping": "1min",
    "metrics": [],
    "special_op": "event_time",
    "event_time_spec": {"find": "high"}
  }
}
```

Question: "Распределение времени формирования high и low"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "all",
      "period_end": "all"
    },
    "grouping": "1min",
    "metrics": [],
    "special_op": "event_time",
    "event_time_spec": {"find": "both"}
  }
}
```

Question: "Когда формируется low по вторникам на RTH?"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "all",
      "period_end": "all",
      "session": "RTH",
      "weekdays": ["Tuesday"]
    },
    "grouping": "1min",
    "metrics": [],
    "special_op": "event_time",
    "event_time_spec": {"find": "low"}
  }
}
```

Question: "В какое время чаще формируется high? Покажи по 15-минуткам"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "all",
      "period_end": "all"
    },
    "grouping": "15min",
    "metrics": [],
    "special_op": "event_time",
    "event_time_spec": {"find": "high"}
  }
}
```
"""
