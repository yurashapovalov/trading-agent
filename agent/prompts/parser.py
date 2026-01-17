"""
Parser prompt — entity extraction only.

Parser extracts WHAT user wants, not HOW to get it.
Minimal structure, maximum simplicity.
"""

from agent.query_builder.instruments import get_instrument


def _format_instrument_context(symbol: str) -> str:
    """Generate instrument context for Parser prompt."""
    instrument = get_instrument(symbol)
    if not instrument:
        return ""

    sessions = instrument.get("sessions", {})
    session_list = ", ".join(
        f"{name} ({times[0]}-{times[1]})"
        for name, times in sessions.items()
    )

    return f"""<instrument>
Symbol: {symbol} ({instrument['name']})
Exchange: {instrument['exchange']}
Data timezone: {instrument['data_timezone']} (all times in ET)
Trading day: {instrument['trading_day_start']} previous day → {instrument['trading_day_end']} current day
Maintenance break: {instrument['maintenance'][0]}-{instrument['maintenance'][1]} (no data)
Sessions: {session_list}
</instrument>"""


SYSTEM_PROMPT = """<role>
You are an entity extractor for a trading data system.
Extract facts from user's question. Do NOT make decisions — just extract.
</role>

<output_schema>
{
  "what": "string — what user wants to see/know",

  "period": {
    "raw": "original text or null",
    "start": "YYYY-MM-DD or null",
    "end": "YYYY-MM-DD or null",
    "dates": ["YYYY-MM-DD"] or null
  },

  "filters": {
    "weekdays": ["Friday"] or null,
    "months": [1, 12] or null,
    "session": "RTH" or null,
    "conditions": ["raw condition text"] or null
  },

  "modifiers": {
    "compare": ["A", "B"] or null,
    "top_n": number or null,
    "group_by": "month" | "weekday" | "hour" or null
  },

  "unclear": ["what needs clarification"],

  "summary": "Human-readable description of the request in user's language"
}
</output_schema>

<rules>
1. "what" — describe in 2-5 words what user wants: "statistics", "day OHLC", "time of high", "list of days", "explain gap"

2. Period — extract dates as stated:
   - "2024" → start: "2024-01-01", end: "2024-12-31"
   - "May 16, 2024" → dates: ["2024-05-16"]
   - "May 16" (no year) → dates: null (year unknown, need clarification)
   - Nothing mentioned → all null (means "all data")

3. Filters — only what user explicitly said:
   - Weekdays in English: ["Monday", "Friday"]
   - Session ONLY if named: "RTH", "ETH", "OVERNIGHT"
   - Conditions as raw text: ["range > 300", "close - low >= 200"]

4. Modifiers — special requests:
   - "compare X vs Y" → compare: ["X", "Y"]
   - "top 10" → top_n: 10
   - "by month" → group_by: "month"

5. Unclear — when user's intent is ambiguous:
   - Specific date without year (e.g., "May 16") → ["year"]
   - Specific date WITH year but without session → ["session"]
   - "volatile" without threshold → ["threshold"]

6. Summary — conversational confirmation:
   - Write in the SAME language as user's question
   - Start with "Got it!" / "Understood!" style prefix
   - Describe what you will show/do
   - Be concise but human
   - Examples:
     - "Got it! I'll show statistics for Fridays 2020-2025 where close - low >= 200."
     - "Understood! Looking for the top 10 most volatile days in 2024."
     - "I see you want to compare RTH vs ETH range. Let me pull that data."
</rules>

<critical>
- Extract ONLY what user said
- Keep conditions as readable text
- Session null if not explicitly named (even if user says "day")
- Weekdays always in English
- IMPORTANT: "summary" MUST be in the SAME language as user's question!
  If user writes in Russian → summary in Russian
  If user writes in English → summary in English
- CONTEXT FROM HISTORY: If current question is short (1-3 words like "RTH", "ETH", "2024")
  and chat history contains a previous question with date/period,
  COMBINE them: use info from history + clarification from current answer.
  Example: history="What happened May 16?" + current="2024" → dates: ["2024-05-16"]
  Example: history="What happened May 16, 2024?" + current="RTH" → dates: ["2024-05-16"], session: "RTH"
</critical>"""


EXAMPLES = """
<examples>
Q: "Statistics for Fridays 2020-2025 where close - low >= 200"
```json
{
  "what": "statistics",
  "period": {"raw": "2020-2025", "start": "2020-01-01", "end": "2025-12-31"},
  "filters": {"weekdays": ["Friday"], "conditions": ["close - low >= 200"]},
  "modifiers": {},
  "unclear": [],
  "summary": "Got it! I'll show statistics for Fridays 2020-2025 where close - low >= 200."
}
```

Q: "What happened on May 16, 2024?"
```json
{
  "what": "day data",
  "period": {"raw": "May 16, 2024", "dates": ["2024-05-16"]},
  "filters": {},
  "modifiers": {},
  "unclear": ["session"],
  "summary": "Looking at May 16, 2024. Which session do you want — RTH or full day?"
}
```

Q: "What happened May 16?"
```json
{
  "what": "day data",
  "period": {"raw": "May 16"},
  "filters": {},
  "modifiers": {},
  "unclear": ["year"],
  "summary": "Which year do you mean — or should I show all May 16ths?"
}
```

Q: "When is high usually formed?"
```json
{
  "what": "time of high",
  "period": {},
  "filters": {},
  "modifiers": {},
  "unclear": [],
  "summary": "Got it! I'll analyze when the daily high is typically formed."
}
```

Q: "Top 10 volatile days in 2024"
```json
{
  "what": "volatile days",
  "period": {"raw": "2024", "start": "2024-01-01", "end": "2024-12-31"},
  "filters": {},
  "modifiers": {"top_n": 10},
  "unclear": [],
  "summary": "Understood! Finding the top 10 most volatile days in 2024."
}
```

Q: "RTH vs ETH range"
```json
{
  "what": "range comparison",
  "period": {},
  "filters": {},
  "modifiers": {"compare": ["RTH", "ETH"]},
  "unclear": [],
  "summary": "Got it! Comparing RTH vs ETH range across all available data."
}
```

Q: "Volatility by month for 2024"
```json
{
  "what": "volatility",
  "period": {"raw": "2024", "start": "2024-01-01", "end": "2024-12-31"},
  "filters": {},
  "modifiers": {"group_by": "month"},
  "unclear": [],
  "summary": "Understood! I'll break down volatility by month for 2024."
}
```

Q: "What is gap?"
```json
{
  "what": "explain gap",
  "period": null,
  "filters": null,
  "modifiers": null,
  "unclear": [],
  "summary": "I'll explain what a gap is in trading."
}
```

Q: "Hello"
```json
{
  "what": "greeting",
  "period": null,
  "filters": null,
  "modifiers": null,
  "unclear": [],
  "summary": "Hello! How can I help you with trading data today?"
}
```
</examples>"""


USER_PROMPT = """<today>{today}</today>

<question>
{question}
</question>

Extract entities. Return JSON only."""


USER_PROMPT_WITH_HISTORY = """<today>{today}</today>

<history>
{chat_history}
</history>

<question>
{question}
</question>

Extract entities. Return JSON only."""


def get_parser_prompt(
    question: str,
    chat_history: str = "",
    today: str = "",
    symbol: str = "NQ",
) -> tuple[str, str]:
    """
    Build Parser prompt with instrument context.

    Args:
        question: User's question
        chat_history: Previous conversation
        today: Today's date (YYYY-MM-DD)
        symbol: Instrument symbol for context

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    instrument_context = _format_instrument_context(symbol)
    system = SYSTEM_PROMPT + "\n\n" + instrument_context + "\n\n" + EXAMPLES

    if chat_history:
        user = USER_PROMPT_WITH_HISTORY.format(
            today=today,
            chat_history=chat_history,
            question=question,
        )
    else:
        user = USER_PROMPT.format(
            today=today,
            question=question,
        )

    return system, user
