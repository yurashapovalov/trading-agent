# count

<description>
Count items and calculate aggregate stats (count, avg, min, max).
</description>

<rules>
- "how many", "count", "average", "mean", "what is the avg" → count
- Returns: count, avg, min, max of the metric
- filter = condition to count
</rules>

<params>
None
</params>

<examples>
"how many gap ups historically"
{"steps": [{"id": "s1", "operation": "count", "atoms": [{"when": "all", "what": "gap", "filter": "gap > 0", "timeframe": "1D"}]}]}

"how many red days in 2024"
{"steps": [{"id": "s1", "operation": "count", "atoms": [{"when": "2024", "what": "change", "filter": "change < 0", "timeframe": "1D"}]}]}

"how many days with gap > 1% in 2024"
{"steps": [{"id": "s1", "operation": "count", "atoms": [{"when": "2024", "what": "gap", "filter": "gap > 1%", "timeframe": "1D"}]}]}

"how many green fridays in 2024"
{"steps": [{"id": "s1", "operation": "count", "atoms": [{"when": "2024", "what": "change", "filter": "change > 0, friday", "timeframe": "1D"}]}]}

"top 10 drops in 2024, how many were on monday"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "2024", "what": "change", "timeframe": "1D"}], "params": {"n": 10, "sort": "asc"}}, {"id": "s2", "operation": "count", "atoms": [{"when": "2024", "what": "change", "filter": "monday", "timeframe": "1D"}], "from": "s1"}]}

"average range in 2024"
{"steps": [{"id": "s1", "operation": "count", "atoms": [{"when": "2024", "what": "range", "timeframe": "1D"}]}]}

"what is the average gap on mondays"
{"steps": [{"id": "s1", "operation": "count", "atoms": [{"when": "all", "what": "gap", "filter": "monday", "timeframe": "1D"}]}]}

"average morning session range in 2024"
{"steps": [{"id": "s1", "operation": "count", "atoms": [{"when": "2024", "what": "range", "filter": "session = MORNING", "timeframe": "1D"}]}]}

"how many morning star patterns in 2024"
{"steps": [{"id": "s1", "operation": "count", "atoms": [{"when": "2024", "what": "change", "filter": "morning_star", "timeframe": "1D"}]}]}
</examples>
