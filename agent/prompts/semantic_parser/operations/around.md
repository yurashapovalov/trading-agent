# around

<description>
What happened before or after an event.
</description>

<rules>
- "after" → offset > 0
- "before" → offset < 0
- filter = the event (condition that defines the moment)
- unit = timeframe granularity
</rules>

<params>
- offset: +1 (after), -1 (before), +2 (two units after), etc.
- unit: from schema (timeframe or session)
</params>

<examples>
"what happened after red days in 2024"
{"steps": [{"id": "s1", "operation": "around", "atoms": [{"when": "2024", "what": "change", "filter": "change < 0", "timeframe": "1D"}], "params": {"offset": 1, "unit": "1D"}}]}

"what happened before big drops in 2024"
{"steps": [{"id": "s1", "operation": "around", "atoms": [{"when": "2024", "what": "change", "filter": "change < -2%", "timeframe": "1D"}], "params": {"offset": -1, "unit": "1D"}}]}

"performance one week after gap up"
{"steps": [{"id": "s1", "operation": "around", "atoms": [{"when": "2024", "what": "change", "filter": "gap > 0", "timeframe": "1D"}], "params": {"offset": 1, "unit": "1W"}}]}

"what happened 15 minutes before the high"
{"steps": [{"id": "s1", "operation": "around", "atoms": [{"when": "2024", "what": "high", "timeframe": "1m"}], "params": {"offset": -15, "unit": "1m"}}]}

"RTH session after gap down"
{"steps": [{"id": "s1", "operation": "around", "atoms": [{"when": "2024", "what": "change", "filter": "gap < 0", "timeframe": "1D"}], "params": {"offset": 1, "unit": "RTH"}}]}
</examples>
