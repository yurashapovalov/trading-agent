# list

<description>
Show data matching the query. Default operation when user wants to see values.
</description>

<rules>
- "show", "list", "what was" → list
- "top N", "best", "worst" → add params n + sort
- sort=desc for largest, sort=asc for smallest
</rules>

<params>
- n: limit to N items (optional)
- sort: "asc" (smallest first) or "desc" (largest first) (optional)
</params>

<examples>
"show all days with gap > 1%"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "all", "what": "gap", "filter": "gap > 1%", "timeframe": "1D"}]}]}

"show volatility for 2024"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "2024", "what": "volatility", "timeframe": "1D"}]}]}

"show green days in January"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "January", "what": "change", "filter": "change > 0", "timeframe": "1D"}]}]}

"show volume by month for 2024"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "2024", "what": "volume", "group": "by month", "timeframe": "1D"}]}]}

"what was the gap yesterday"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "yesterday", "what": "gap", "timeframe": "1D"}]}]}

"top 10 by volume in 2024"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "2024", "what": "volume", "timeframe": "1D"}], "params": {"n": 10, "sort": "desc"}}]}

"top 5 biggest drops in 2024"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "2024", "what": "change", "timeframe": "1D"}], "params": {"n": 5, "sort": "asc"}}]}

"top 10 drops in 2024, show volume for those days"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "2024", "what": "change", "timeframe": "1D"}], "params": {"n": 10, "sort": "asc"}}, {"id": "s2", "operation": "list", "atoms": [{"when": "2024", "what": "volume", "timeframe": "1D"}], "from": "s1"}]}
</examples>
