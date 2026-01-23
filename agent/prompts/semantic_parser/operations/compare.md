# compare

<description>
Compare multiple data sets.
</description>

<rules>
- "compare", "vs", "versus" → compare
- need 2+ atoms
</rules>

<params>
None
</params>

<examples>
"compare mondays and fridays in 2024"
{"steps": [{"id": "s1", "operation": "compare", "atoms": [{"when": "2024", "what": "change", "filter": "monday", "timeframe": "1D"}, {"when": "2024", "what": "change", "filter": "friday", "timeframe": "1D"}]}]}

"compare January and February volume"
{"steps": [{"id": "s1", "operation": "compare", "atoms": [{"when": "January", "what": "volume", "timeframe": "1D"}, {"when": "February", "what": "volume", "timeframe": "1D"}]}]}

"compare 2023 and 2024 volatility"
{"steps": [{"id": "s1", "operation": "compare", "atoms": [{"when": "2023", "what": "volatility", "timeframe": "1D"}, {"when": "2024", "what": "volatility", "timeframe": "1D"}]}]}

"compare Q1, Q2, Q3, Q4 change in 2024"
{"steps": [{"id": "s1", "operation": "compare", "atoms": [{"when": "Q1 2024", "what": "change", "timeframe": "1D"}, {"when": "Q2 2024", "what": "change", "timeframe": "1D"}, {"when": "Q3 2024", "what": "change", "timeframe": "1D"}, {"when": "Q4 2024", "what": "change", "timeframe": "1D"}]}]}

"compare morning vs afternoon range"
{"steps": [{"id": "s1", "operation": "compare", "atoms": [{"when": "all", "what": "range", "filter": "session = MORNING", "timeframe": "1D"}, {"when": "all", "what": "range", "filter": "session = AFTERNOON", "timeframe": "1D"}]}]}

"compare RTH and overnight volatility"
{"steps": [{"id": "s1", "operation": "compare", "atoms": [{"when": "all", "what": "volatility", "filter": "session = RTH", "timeframe": "1D"}, {"when": "all", "what": "volatility", "filter": "session = OVERNIGHT", "timeframe": "1D"}]}]}
</examples>
