# correlation

<description>
Calculate correlation between two metrics.
</description>

<rules>
- "correlation", "relationship between" → correlation
- exactly 2 atoms required
</rules>

<params>
None
</params>

<examples>
"correlation between volume and change in 2024"
{"steps": [{"id": "s1", "operation": "correlation", "atoms": [{"when": "2024", "what": "volume", "timeframe": "1D"}, {"when": "2024", "what": "change", "timeframe": "1D"}]}]}

"correlation of volatility and gap in 2024"
{"steps": [{"id": "s1", "operation": "correlation", "atoms": [{"when": "2024", "what": "volatility", "timeframe": "1D"}, {"when": "2024", "what": "gap", "timeframe": "1D"}]}]}

"correlation between volume and range in January"
{"steps": [{"id": "s1", "operation": "correlation", "atoms": [{"when": "January", "what": "volume", "timeframe": "1D"}, {"when": "January", "what": "range", "timeframe": "1D"}]}]}
</examples>
