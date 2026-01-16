"""
Event time handler.

Handles questions about WHEN events (open, high, low, close, max_volume)
USUALLY occur (distribution pattern).
"""

HANDLER_PROMPT = """<task>
User wants to know WHEN events typically occur — distribution over many days.

This is about PATTERNS, not specific dates:
- "когда обычно формируется high?" → distribution
- "в какое время чаще всего low?" → distribution
- "когда обычно открывается рынок?" → distribution of open times

Key decisions:
1. **source**: Always "minutes" (need intraday data)
2. **special_op**: "event_time"
3. **event_time_spec.find** — choose based on what user asks:
   - "open" — when session/day typically starts
   - "close" — when session/day typically ends
   - "high" — when maximum price typically forms
   - "low" — when minimum price typically forms
   - "max_volume" — when highest volume typically occurs
   - "both" — high and low
   - "all" — open + high + low + close + max_volume
4. **grouping**: Time bucket for distribution
   - "1min" — most precise (default)
   - "5min", "15min", "30min", "hour" — if user asks for coarser
5. **session**: If user specifies (RTH, ETH, etc.)

CRITICAL: This returns FREQUENCY DISTRIBUTION, not exact timestamps.
Result: time_bucket → how many days had event in that bucket.

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
