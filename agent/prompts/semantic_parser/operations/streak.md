# streak

<description>
Find consecutive series where condition is true N+ times in a row.
</description>

<rules>
- "consecutive", "in a row", "streak", "series" → streak
- filter = condition that must be true
- params.n = minimum streak length
</rules>

<params>
- n: minimum streak length (required)
</params>

<examples>
"how many times were there 3+ losing days in a row in 2024"
{"steps": [{"id": "s1", "operation": "streak", "atoms": [{"when": "2024", "what": "change", "filter": "change < 0", "timeframe": "1D"}], "params": {"n": 3}}]}

"consecutive gap up days in 2024"
{"steps": [{"id": "s1", "operation": "streak", "atoms": [{"when": "2024", "what": "gap", "filter": "gap > 0", "timeframe": "1D"}], "params": {"n": 2}}]}

"5+ days with volatility above 2% in a row"
{"steps": [{"id": "s1", "operation": "streak", "atoms": [{"when": "2024", "what": "volatility", "filter": "volatility > 2%", "timeframe": "1D"}], "params": {"n": 5}}]}

"series of high volume days in January"
{"steps": [{"id": "s1", "operation": "streak", "atoms": [{"when": "January", "what": "volume", "filter": "volume > 1000000", "timeframe": "1D"}], "params": {"n": 3}}]}
</examples>
