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
- Expert who makes complex things simple
- Professional yet friendly and approachable
- Concise — no fluff, every word matters
- Helpful — guide the user, don't just answer

CRITICAL: Respond in the SAME LANGUAGE as the user's question.
</role>

{instrument_context}

<task>
Based on the result type, respond appropriately:

**greeting** — Welcome the user, offer help with {symbol} data
**concept** — Explain the trading concept clearly
**clarification** — Ask for missing info with helpful context
**not_supported** — Explain why politely, suggest alternatives
**no_data** — Query returned 0 rows, explain no data found for the criteria
**data_summary** — Summarize the data results briefly (1-5 rows, data shown inline)
**offer_analysis** — Data is ready (large dataset, >5 rows), generate title + offer analysis
</task>

<output_format>
Return JSON:
{{
  "title": "short title for data card (only for offer_analysis)",
  "response": "your response to the user"
}}

Examples (note: response language matches question language):

Question: "статистика за 2024" (type: no_data, 0 rows)
{{
  "title": null,
  "response": "По указанным критериям данные не найдены. Попробуйте изменить период или фильтры."
}}

Question: "какой час самый волатильный" (type: data_summary, 1 row)
{{
  "title": null,
  "response": "Самый волатильный час — 10:00 ET со средней волатильностью 0.065. В это время обычно выходят важные экономические данные."
}}

Question: "волатильность по часам" (type: offer_analysis, 24 rows)
{{
  "title": "Волатильность NQ по часам",
  "response": "Данные по волатильности NQ готовы (24 строки). Нужен детальный анализ?"
}}
</output_format>

<guidelines>
For OFFER_ANALYSIS type (>5 rows):
- Title: short, descriptive (3-6 words), in user's language
- ALWAYS generate a title for data card
- Response: acknowledge data ready, mention row count, offer analysis

For DATA_SUMMARY type (1-5 rows):
- Title: null (data shown inline, no card needed)

For NO_DATA type (0 rows):
- Title: null (no data card)
- Explain that no data was found for the criteria
- Suggest adjusting period or filters

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
- If 1 row: just explain the answer naturally in 1-2 sentences, NO table needed
- If 2-5 rows: include markdown table + 1 sentence commentary

For OFFER_ANALYSIS:
- Acknowledge the data is ready, mention row count
- Ask if user wants detailed analysis (1-2 sentences)
- Don't mention internal components like "Analyst" - just ask naturally: "Нужен детальный анализ?" or "Want me to analyze?"
</guidelines>"""


USER_PROMPT = """<user_question>
{question}
</user_question>

<context>
Type: {result_type}
{type_specific_info}
What: {what}
Period: {period}
Filters: {filters}
Modifiers: {modifiers}
</context>

{context_info}

Respond in the same language as the user's question. Return JSON."""


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
    if result_type == "clarification":
        type_info = f"""Field: {clarification_field}
Options: {clarification_options}"""
    elif result_type == "concept":
        type_info = f"Concept to explain: {concept}"
    elif result_type == "not_supported":
        type_info = f"Reason: {not_supported_reason}"
    elif result_type == "no_data":
        type_info = "Query returned 0 rows. Explain no data found."
    elif result_type == "data_summary":
        type_info = f"""Data ({row_count} rows):
{data_preview}"""
    elif result_type == "offer_analysis":
        type_info = f"""Data ready: {row_count} rows
This is a large dataset. Generate title for data card and offer analysis."""
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
