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
Question: "Что такое гэп?"
```json
{
  "type": "concept",
  "concept": "gap"
}
```

Question: "Что означает RTH?"
```json
{
  "type": "concept",
  "concept": "rth"
}
```

Question: "Что такое range?"
```json
{
  "type": "concept",
  "concept": "range"
}
```
"""
