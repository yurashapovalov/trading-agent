"""
Parser prompt — entity extraction only.

Parser extracts WHAT user wants, not HOW to get it.
Minimal structure, maximum simplicity.
"""

from agent.market.instruments import get_instrument


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

    data_start = instrument.get("data_start", "unknown")
    data_end = instrument.get("data_end", "unknown")

    return f"""<instrument>
Symbol: {symbol} ({instrument['name']})
Exchange: {instrument['exchange']}
Available data: {data_start} to {data_end}
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
    "conditions": ["raw condition text"] or null,
    "event_filter": "opex" | "nfp" | "quad_witching" | "vix_exp" | "fomc" | "cpi" or null
  },

  "modifiers": {
    "compare": ["A", "B"] or null,
    "top_n": number or null,
    "group_by": "month" | "weekday" | "hour" or null,
    "find": "max" | "min" or null
  },

  "unclear": ["what needs clarification"]
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
   - event_filter for market events:
     * "OPEX", "expiration", "экспирация" → "opex"
     * "NFP", "non-farm", "нонфарм" → "nfp"
     * "Quad Witching", "квадвитчинг" → "quad_witching"
     * "VIX expiration" → "vix_exp"
     * "FOMC", "ставка", "rate decision" → "fomc"
     * "CPI", "инфляция" → "cpi"

4. Modifiers — special requests:
   - "compare X vs Y" → compare: ["X", "Y"]
   - "top 10" → top_n: 10
   - "by year", "год", "по годам" → group_by: "year"
   - "by month", "месяц", "по месяцам" → group_by: "month"
   - "by weekday", "день недели", "по дням недели" → group_by: "weekday"
   - "by hour", "час", "по часам" → group_by: "hour"
   - "by session", "сессия", "по сессиям" → group_by: "session"
   - Superlatives → find: "max" or "min":
     * "самый", "наиболее", "most", "highest", "largest", "best" → find: "max"
     * "наименее", "lowest", "smallest", "worst", "quietest" → find: "min"
     * Example: "какой час самый волатильный?" → find: "max", group_by: "hour"

5. Unclear — ONLY for missing required info:
   - Date without year → ["year"] (need to know which year)
   - Specific date WITH year but without session → ["session"] (need to know RTH/ETH/full day)
   - Do NOT mark subjective terms (huge, volatile, crazy, etc.) as unclear — interpret as top_n instead
</rules>

<critical>
- Extract ONLY what user said
- Keep conditions as readable text
- Session null if not explicitly named (even if user says "day")
- Weekdays always in English
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
  "unclear": []
}
```

Q: "What happened on May 16, 2024?"
```json
{
  "what": "day data",
  "period": {"raw": "May 16, 2024", "dates": ["2024-05-16"]},
  "filters": {},
  "modifiers": {},
  "unclear": ["session"]
}
```

Q: "What happened May 16?"
```json
{
  "what": "day data",
  "period": {"raw": "May 16"},
  "filters": {},
  "modifiers": {},
  "unclear": ["year"]
}
```

Q: "When is high usually formed?"
```json
{
  "what": "time of high",
  "period": {},
  "filters": {},
  "modifiers": {},
  "unclear": []
}
```

Q: "Top 10 volatile days in 2024"
```json
{
  "what": "volatile days",
  "period": {"raw": "2024", "start": "2024-01-01", "end": "2024-12-31"},
  "filters": {},
  "modifiers": {"top_n": 10},
  "unclear": []
}
```

Q: "Find me days with huge moves last year"
```json
{
  "what": "huge moves days",
  "period": {"raw": "last year", "start": "2025-01-01", "end": "2025-12-31"},
  "filters": {},
  "modifiers": {"top_n": 10},
  "unclear": []
}
```

Q: "RTH vs ETH range"
```json
{
  "what": "range comparison",
  "period": {},
  "filters": {},
  "modifiers": {"compare": ["RTH", "ETH"]},
  "unclear": []
}
```

Q: "Show me OPEX days for 2024"
```json
{
  "what": "OPEX days",
  "period": {"raw": "2024", "start": "2024-01-01", "end": "2024-12-31"},
  "filters": {"event_filter": "opex"},
  "modifiers": {},
  "unclear": []
}
```

Q: "NFP statistics for 2023-2024"
```json
{
  "what": "NFP statistics",
  "period": {"raw": "2023-2024", "start": "2023-01-01", "end": "2024-12-31"},
  "filters": {"event_filter": "nfp"},
  "modifiers": {},
  "unclear": []
}
```

Q: "Статистика по дням экспирации"
```json
{
  "what": "expiration statistics",
  "period": {},
  "filters": {"event_filter": "opex"},
  "modifiers": {},
  "unclear": []
}
```

Q: "Volatility by month for 2024"
```json
{
  "what": "volatility",
  "period": {"raw": "2024", "start": "2024-01-01", "end": "2024-12-31"},
  "filters": {},
  "modifiers": {"group_by": "month"},
  "unclear": []
}
```

Q: "Какой час самый волатильный?"
```json
{
  "what": "most volatile hour",
  "period": {},
  "filters": {},
  "modifiers": {"group_by": "hour", "find": "max"},
  "unclear": []
}
```

Q: "Which day had the lowest range in 2024?"
```json
{
  "what": "lowest range day",
  "period": {"raw": "2024", "start": "2024-01-01", "end": "2024-12-31"},
  "filters": {},
  "modifiers": {"find": "min"},
  "unclear": []
}
```

Q: "What is gap?"
```json
{
  "what": "explain gap",
  "period": null,
  "filters": null,
  "modifiers": null,
  "unclear": []
}
```

Q: "Hello"
```json
{
  "what": "greeting",
  "period": null,
  "filters": null,
  "modifiers": null,
  "unclear": []
}
```

History: "User: what was jan 10\\nAssistant: Which year?"
Q: "2024"
```json
{
  "what": "day data",
  "period": {"raw": "jan 10 2024", "dates": ["2024-01-10"]},
  "filters": {},
  "modifiers": {},
  "unclear": ["session"]
}
```

History: "User: 2024\\nAssistant: Looking at January 10, 2024. Which session — RTH or full day?"
Q: "RTH"
```json
{
  "what": "day data",
  "period": {"raw": "January 10, 2024", "dates": ["2024-01-10"]},
  "filters": {"session": "RTH"},
  "modifiers": {},
  "unclear": []
}
```

History: "User: What was May 16, 2024?\\nAssistant: Which session — RTH or full day?"
Q: "Calendar day"
```json
{
  "what": "day data",
  "period": {"raw": "May 16, 2024", "dates": ["2024-05-16"]},
  "filters": {"time_start": "00:00", "time_end": "23:59"},
  "modifiers": {},
  "unclear": []
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


def _format_previous_parsed(parsed) -> str:
    """Format previous ParsedQuery for prompt."""
    if not parsed:
        return ""

    parts = [f"what: {parsed.what}"]

    if parsed.period:
        period_str = parsed.period.raw or f"{parsed.period.start} - {parsed.period.end}"
        parts.append(f"period: {period_str}")

    if parsed.filters:
        filters = {}
        if parsed.filters.weekdays:
            filters["weekdays"] = parsed.filters.weekdays
        if parsed.filters.session:
            filters["session"] = parsed.filters.session
        if parsed.filters.event_filter:
            filters["event"] = parsed.filters.event_filter
        if filters:
            parts.append(f"filters: {filters}")

    if parsed.modifiers:
        mods = {}
        if parsed.modifiers.group_by:
            mods["group_by"] = parsed.modifiers.group_by
        if parsed.modifiers.top_n:
            mods["top_n"] = parsed.modifiers.top_n
        if parsed.modifiers.compare:
            mods["compare"] = parsed.modifiers.compare
        if parsed.modifiers.find:
            mods["find"] = parsed.modifiers.find
        if mods:
            parts.append(f"modifiers: {mods}")

    return "\n".join(parts)


def get_parser_prompt(
    question: str,
    chat_history: str = "",
    today: str = "",
    symbol: str = "NQ",
    previous_parsed=None,
) -> tuple[str, str]:
    """
    Build Parser prompt with instrument context.

    Args:
        question: User's question
        chat_history: Previous conversation
        today: Today's date (YYYY-MM-DD)
        symbol: Instrument symbol for context
        previous_parsed: Previous ParsedQuery for follow-up context

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    instrument_context = _format_instrument_context(symbol)
    system = SYSTEM_PROMPT + "\n\n" + instrument_context + "\n\n" + EXAMPLES

    # Build user prompt with optional previous_parsed
    previous_section = ""
    if previous_parsed:
        formatted = _format_previous_parsed(previous_parsed)
        previous_section = f"""<previous_parsed>
{formatted}
</previous_parsed>

If the current question modifies or refines the previous query, update it.
If it's a new unrelated question, ignore previous and extract fresh.

"""

    if chat_history:
        user = f"""<today>{today}</today>

{previous_section}<history>
{chat_history}
</history>

<question>
{question}
</question>

Extract entities. Return JSON only."""
    else:
        user = f"""<today>{today}</today>

{previous_section}<question>
{question}
</question>

Extract entities. Return JSON only."""

    return system, user
