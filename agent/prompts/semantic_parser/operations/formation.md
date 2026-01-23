# formation

<description>
When does an event typically occur (time of day analysis).
</description>

<rules>
- "when", "what time", "at what hour" → formation
- what = event to track (high, low, gap_fill, range_50, prev_close)
- group by time period (hour, session)
</rules>

<params>
None
</params>

<examples>
"when is daily high usually formed"
{"steps": [{"id": "s1", "operation": "formation", "atoms": [{"when": "2024", "what": "high", "group": "by hour", "timeframe": "1m"}]}]}

"what time does gap usually fill"
{"steps": [{"id": "s1", "operation": "formation", "atoms": [{"when": "2024", "what": "gap_fill", "group": "by hour", "timeframe": "1m"}]}]}

"when does price reach 50% of daily range"
{"steps": [{"id": "s1", "operation": "formation", "atoms": [{"when": "2024", "what": "range_50", "group": "by hour", "timeframe": "1m"}]}]}

"what session does the low form in"
{"steps": [{"id": "s1", "operation": "formation", "atoms": [{"when": "2024", "what": "low", "group": "by session", "timeframe": "1m"}]}]}
</examples>
