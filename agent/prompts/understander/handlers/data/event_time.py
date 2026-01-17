"""
Event time handler.

Handles questions about WHEN events (open, high, low, close, max_volume)
USUALLY occur (distribution pattern).
"""

HANDLER_PROMPT = """<task>
User wants to know WHEN events typically occur — distribution over many days.

This is about PATTERNS, not specific dates:
- "when does high usually form?" → distribution
- "what time is low most often?" → distribution
- "when does market usually open?" → distribution of open times

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

CRITICAL: This returns FREQUENCY DISTRIBUTION, not exact timestamps.
Result: time_bucket → how many days had event in that bucket.

Return JSON with type: "data" and query_spec.
</task>

<session_rule>
IMPORTANT — Session field handling (see <markers> for details):
- User explicitly says "RTH", "ETH", "OVERNIGHT" → session: "RTH" (or that name)
- User says "session" without naming which one → session: "_default_"
- User doesn't mention session at all → session: null

DO NOT invent session names! Only use: RTH, ETH, OVERNIGHT, ASIAN, EUROPEAN, MORNING, AFTERNOON, or "_default_".
</session_rule>"""

EXAMPLES = """
Question: "When does high usually form on RTH?"
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

Question: "Distribution of high and low formation times"
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

Question: "When does low form on Tuesdays during RTH?"
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

Question: "What time does high usually form? Show in 15-min buckets"
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
