# distribution

<description>
Statistical distribution of metric values (histogram).
</description>

<rules>
- "distribution", "spread", "histogram" → distribution
- single atom, single metric
</rules>

<params>
None
</params>

<examples>
"how is volatility distributed in 2024"
{"steps": [{"id": "s1", "operation": "distribution", "atoms": [{"when": "2024", "what": "volatility", "timeframe": "1D"}]}]}

"distribution of daily changes in 2024"
{"steps": [{"id": "s1", "operation": "distribution", "atoms": [{"when": "2024", "what": "change", "timeframe": "1D"}]}]}

"gap distribution for Q1 2024"
{"steps": [{"id": "s1", "operation": "distribution", "atoms": [{"when": "Q1 2024", "what": "gap", "timeframe": "1D"}]}]}

"volume distribution on mondays"
{"steps": [{"id": "s1", "operation": "distribution", "atoms": [{"when": "2024", "what": "volume", "filter": "monday", "timeframe": "1D"}]}]}
</examples>
