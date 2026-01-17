"""
Concept handler.

Handles questions about trading concepts and terminology.
"""

HANDLER_PROMPT = """<task>
User is asking what a trading concept means.

Identify the concept and return it. The system will provide the explanation.

Known concepts:
- gap: overnight price jump between sessions
- range: intraday price movement (high - low)
- rth: Regular Trading Hours
- eth: Electronic Trading Hours (extended)
- overnight: trading session before RTH
- session: trading time window
- ohlcv: Open, High, Low, Close, Volume data

Return JSON:
{
  "type": "concept",
  "concept": "<concept_name>"
}
</task>"""

EXAMPLES = """
Question: "What is a gap?"
```json
{
  "type": "concept",
  "concept": "gap"
}
```

Question: "What does RTH mean?"
```json
{
  "type": "concept",
  "concept": "rth"
}
```

Question: "What is range?"
```json
{
  "type": "concept",
  "concept": "range"
}
```
"""
