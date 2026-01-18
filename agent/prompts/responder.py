"""
Responder prompt — user-facing communication.

Responder is the voice of the system. It:
- Gives expert context BEFORE data arrives
- Handles all dialog types (greeting, concept, clarification, query)
- Generates data card title
- Speaks the user's language
"""

from agent.market.instruments import get_instrument


def _format_instrument_context(symbol: str) -> str:
    """Generate instrument context for Responder."""
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
Available data: {instrument.get('data_start', 'unknown')} to {instrument.get('data_end', 'unknown')}
Timezone: {instrument['data_timezone']} (all times in ET)
Sessions: {session_list}
</instrument>"""


SYSTEM_PROMPT = """<role>
You are the voice of askbar.ai — a trading data assistant for {symbol}.
You communicate with users: give expert context, explain concepts, ask clarifications.

Your personality:
- Expert in {symbol} and market structure
- Concise but insightful
- Friendly, not robotic
- You must respond in the same language as the user's question
</role>

{instrument_context}

<task>
Based on the composer result type, respond appropriately:

**greeting** — Welcome the user, offer help with {symbol} data
**concept** — Explain the trading concept clearly
**clarification** — Ask for missing info with helpful context
**not_supported** — Explain why politely, suggest alternatives
**query** — Give expert preview while data loads, generate title for data card
**data_summary** — Summarize the data results briefly (data already fetched)
**offer_analysis** — Data is ready (large dataset), offer detailed analysis with Analyst
</task>

<output_format>
Return JSON:
{{
  "title": "Data card title (for query/data types, null otherwise)",
  "response": "Your response to the user"
}}
</output_format>

<guidelines>
For QUERY/DATA type:
- Title: short, descriptive (e.g., "Hourly volatility NQ", "May 16 2024, RTH", "Top-10 by range 2024")
- Response: expert context BEFORE data arrives
  - What patterns to expect
  - Relevant market context (events, typical behavior)
  - Keep it 1-3 sentences

For CLARIFICATION:
- Explain what you need and why
- Give helpful context about the options

For CONCEPT:
- Clear, practical explanation
- Use {symbol} examples when relevant

For GREETING:
- Brief, friendly
- Mention you can help with {symbol} data analysis

For NOT_SUPPORTED:
- Explain limitation
- Suggest what IS possible

For DATA_SUMMARY:
- ALWAYS include the data table as markdown at the START of your response
- Then add 1-2 sentences with key insights
- Format: table first, then brief commentary
- Example:
  | metric | value |
  |--------|-------|
  | avg_range | 138.15 |

  Average range is 138 points over 4800 days.

For OFFER_ANALYSIS:
- Data is already loaded (large dataset with many rows)
- Acknowledge the data is ready and mention row count naturally
- Briefly note what the data contains based on the question context
- Offer detailed analysis (user will see "Analyze" button)
- Keep it friendly and helpful (1-2 sentences)
- Example: "Here's 214 days of RTH data for NQ. Want me to analyze the patterns?"
</guidelines>"""


USER_PROMPT = """<composer_result>
Type: {result_type}
{type_specific_info}
</composer_result>

<parsed_entities>
What: {what}
Period: {period}
Filters: {filters}
Modifiers: {modifiers}
</parsed_entities>

{context_info}

<user_question>
{question}
</user_question>

Respond as JSON."""


def get_responder_prompt(
    question: str,
    result_type: str,
    parsed_entities: dict,
    symbol: str = "NQ",
    query_spec: dict | None = None,
    clarification_field: str | None = None,
    clarification_options: list[str] | None = None,
    concept: str | None = None,
    not_supported_reason: str | None = None,
    event_info: dict | None = None,
    holiday_info: dict | None = None,
    data_preview: str | None = None,
    row_count: int | None = None,
) -> tuple[str, str]:
    """
    Build Responder prompt.

    Args:
        question: User's original question
        result_type: From Composer (query, clarification, concept, greeting, not_supported, data_summary)
        parsed_entities: From Parser (what, period, filters, modifiers)
        symbol: Instrument symbol
        query_spec: QuerySpec dict (for query type)
        clarification_field: Field needing clarification
        clarification_options: Options to show user
        concept: Concept to explain (for concept type)
        not_supported_reason: Why not supported
        event_info: Events on requested dates (OPEX, NFP, etc.)
        holiday_info: Holidays on requested dates
        data_preview: Data to summarize (for data_summary type)
        row_count: Number of rows in data (for data_summary type)

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    instrument_context = _format_instrument_context(symbol)

    # Build system prompt
    system = SYSTEM_PROMPT.format(
        symbol=symbol,
        instrument_context=instrument_context,
    )

    # Build type-specific info
    if result_type in ("query", "data") and query_spec:
        type_info = f"""QuerySpec:
  Source: {query_spec.get('source', 'DAILY')}
  Special op: {query_spec.get('special_op', 'NONE')}
  Grouping: {query_spec.get('grouping', 'NONE')}"""
    elif result_type == "clarification":
        type_info = f"""Field: {clarification_field}
Options: {clarification_options}"""
    elif result_type == "concept":
        type_info = f"Concept to explain: {concept}"
    elif result_type == "not_supported":
        type_info = f"Reason: {not_supported_reason}"
    elif result_type == "data_summary":
        type_info = f"""Data ({row_count} rows):
{data_preview}"""
    elif result_type == "offer_analysis":
        type_info = f"""Data ready: {row_count} rows
This is a large dataset. Offer detailed analysis."""
    else:
        type_info = ""

    # Build context info
    context_parts = []
    if event_info:
        events = event_info.get("events", [])
        if events:
            context_parts.append(f"<events>\n{events}\n</events>")
    if holiday_info:
        names = holiday_info.get("names", [])
        if names:
            context_parts.append(f"<holidays>\n{names}\n</holidays>")
    context_info = "\n".join(context_parts)

    # Build user prompt
    user = USER_PROMPT.format(
        result_type=result_type,
        type_specific_info=type_info,
        what=parsed_entities.get("what", ""),
        period=parsed_entities.get("period", {}),
        filters=parsed_entities.get("filters", {}),
        modifiers=parsed_entities.get("modifiers", {}),
        context_info=context_info,
        question=question,
    )

    return system, user
