# probability

<description>
Conditional probability P(outcome | condition). What is the probability of outcome given condition is true.
</description>

<rules>
- filter = condition (when this is true)
- params.outcome = what we measure (probability of this)
</rules>

<params>
- outcome: what to measure (e.g., "> 0", "< 0", "> 1%")
</params>

<examples>
"probability of green day after gap up"
{"steps": [{"id": "s1", "operation": "probability", "atoms": [{"when": "all", "what": "change", "filter": "gap > 0", "timeframe": "1D"}], "params": {"outcome": "> 0"}}]}

"probability of growth after gap up in 2024"
{"steps": [{"id": "s1", "operation": "probability", "atoms": [{"when": "2024", "what": "change", "filter": "gap > 0", "timeframe": "1D"}], "params": {"outcome": "> 0"}}]}

"chance of decline on mondays in 2024"
{"steps": [{"id": "s1", "operation": "probability", "atoms": [{"when": "2024", "what": "change", "filter": "monday", "timeframe": "1D"}], "params": {"outcome": "< 0"}}]}

"probability of gap fill after gap down"
{"steps": [{"id": "s1", "operation": "probability", "atoms": [{"when": "2024", "what": "change", "filter": "gap < 0", "timeframe": "1D"}], "params": {"outcome": "> 0"}}]}

"what percent of high volume days close positive"
{"steps": [{"id": "s1", "operation": "probability", "atoms": [{"when": "2024", "what": "change", "filter": "volume > 1000000", "timeframe": "1D"}], "params": {"outcome": "> 0"}}]}
</examples>
