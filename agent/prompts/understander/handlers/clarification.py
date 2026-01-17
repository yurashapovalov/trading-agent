"""
Clarification handler.

Handles ambiguous or unclear requests.
"""

HANDLER_PROMPT = """<task>
User's request is unclear or ambiguous. Ask for clarification.

When to clarify:
1. ACTION unclear - "show data" (what to do with data?)
2. AMBIGUOUS - could mean multiple different things
3. CUSTOM TIME RANGE - user specified non-standard time like "from 6 to 16"
   (need to clarify timezone and whether they mean a session)

Provide helpful suggestions showing what's possible.

Return JSON:
{
  "type": "clarification",
  "clarification_question": "Your question to user",
  "suggestions": ["Option 1", "Option 2", "Option 3", "Option 4"]
}
</task>

<important>
Do NOT ask for clarification when:
- Period not specified → just use "all" (full dataset)
- Symbol not specified → just use NQ
- User explicitly uses session names (RTH, ETH)
</important>"""

EXAMPLES = """
Question: "Show high low"
```json
{
  "type": "clarification",
  "clarification_question": "What exactly interests you about high/low?",
  "suggestions": [
    "Show daily high/low for the last month",
    "Find days with maximum range (high-low)",
    "Find out when the daily high/low typically forms",
    "Compare high/low by day of week"
  ]
}
```

Question: "Statistics from 6am to 4pm"
```json
{
  "type": "clarification",
  "clarification_question": "Please clarify the time range. Times should be in ET (Eastern Time):",
  "suggestions": [
    "RTH session (09:30-16:00 ET) - main trading session",
    "Premarket + RTH (04:00-16:00 ET)",
    "Custom time 06:00-16:00 ET",
    "Full trading day ETH"
  ]
}
```
"""
