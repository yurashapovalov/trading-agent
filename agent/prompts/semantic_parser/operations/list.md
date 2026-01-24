# list

<description>
Show data matching the query. Default operation when user wants to see values.
When did pattern appear, find days with pattern, show matching days.
</description>

<rules>
- "show", "list", "what was", "find", "when did appear" → list
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

"show all engulfing patterns in 2024"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "2024", "what": "change", "filter": "bullish_engulfing", "timeframe": "1D"}]}]}

"когда появлялись inside day в 2024"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "2024", "what": "change", "filter": "inside_bar", "timeframe": "1D"}]}]}

"when did doji appear in 2024"
{"steps": [{"id": "s1", "operation": "list", "atoms": [{"when": "2024", "what": "change", "filter": "doji", "timeframe": "1D"}]}]}
</examples>
