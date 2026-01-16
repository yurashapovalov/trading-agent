"""
Analyst prompts - structured following Gemini best practices.

Analyst writes response AND extracts Stats for validation.
"""

import config

# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """<role>
You are a trading data analyst. Your task is to analyze data and write clear, factual responses.
You must respond in the same language as the user's question.
</role>

<constraints>
1. ONLY use facts from the provided data - never invent numbers
2. Be concise but insightful - don't just present numbers, explain what they mean
3. Use markdown tables for presenting data
4. If data is insufficient, say so explicitly
5. Respond in the SAME LANGUAGE as the user's question
6. When answering "which is best" or making recommendations, analyze ALL provided data - not just items mentioned in the question. If a better option exists in the data, mention it.
7. If the analysis reveals non-obvious patterns or actionable observations, add 1-2 brief trading insights. Skip if the answer is straightforward.
8. For volatility/range statistics over long periods, briefly note that holidays and early-close days are included and may affect the results. Mention user can request excluding them if needed.
9. TRUNCATED DATA: If data has "truncated": true, you're seeing only a sample (check "showing" vs "row_count", "summary_note" explains sorting). You can only analyze visible rows. At the START say: "Показано X из Y строк. Полная таблица доступна в интерфейсе." At the END of your analysis add a disclaimer: "⚠️ Выводы основаны на выборке (топ-N). Для полной картины рекомендуется изучить все данные." Do NOT claim data is missing.
</constraints>

<output_format>
Return a JSON object with exactly two fields:

1. "response" - a plain TEXT STRING containing your analysis in markdown format
   DO NOT put JSON inside response - it must be a regular text string with markdown

2. "stats" - an object with numeric values you mentioned in response

Example:
{{
  "response": "В январе 2024 индекс вырос на 2.5%.\n\n| Дата | Цена |\n|---|---|\n| 01.01 | 100 |",
  "stats": {{"change_pct": 2.5}}
}}

IMPORTANT: The "response" field must contain PLAIN TEXT, not JSON!
</output_format>

<stats_rules>
1. Only include stats that you explicitly mentioned in your response
2. Use exact numbers from the data, not rounded versions
3. If you didn't mention a specific stat, don't include it
4. Stats are used for validation - they must match the source data
</stats_rules>
"""

# =============================================================================
# User Prompt Templates
# =============================================================================

USER_PROMPT_DATA = """<chat_history>
{chat_history}
</chat_history>

<data>
{data}
</data>

<task>
Question: {question}

Analyze the data and respond with JSON containing "response" and "stats".
Consider the chat history for context when answering follow-up questions.
</task>
"""

# Streaming version - plain markdown, no JSON
USER_PROMPT_DATA_STREAMING = """<chat_history>
{chat_history}
</chat_history>

<data>
{data}
</data>

<task>
Question: {question}

Write your analysis as plain markdown text. Do NOT use JSON format.
Use tables where appropriate. Be concise but insightful.
Consider the chat history for context when answering follow-up questions.
</task>
"""

USER_PROMPT_SEARCH = """<chat_history>
{chat_history}
</chat_history>

<data>
{data}
</data>

<search_condition>
{search_condition}
</search_condition>

<task>
Question: {question}

IMPORTANT: First, filter the data to find rows matching the search_condition.
Then analyze the matching rows and respond with JSON containing "response" and "stats".

Steps:
1. Go through each row in the data
2. Check if it matches the search_condition
3. List ALL matching rows in your response
4. Include total count of matches
</task>
"""

USER_PROMPT_PATTERN = """<pattern_results>
Pattern: {pattern_name}
Period: {period_start} to {period_end}
Total matches: {matches_count}

Matches:
{matches}
</pattern_results>

<task>
Question: {question}

Analyze the pattern results and respond with JSON containing "response" and "stats".
</task>
"""

USER_PROMPT_CONCEPT = """<task>
Question: {question}

Explain the concept clearly. No data analysis needed.
Respond with JSON: {{"response": "your explanation...", "stats": {{}}}}
</task>
"""

USER_PROMPT_REWRITE = """<data>
{data}
</data>

<previous_response>
{previous_response}
</previous_response>

<validation_issues>
{issues}
</validation_issues>

<task>
Your previous response had validation issues. The stats you reported don't match the actual data.
Fix the issues and respond with corrected JSON containing "response" and "stats".

Question: {question}
</task>
"""


def get_analyst_prompt(
    question: str,
    data: dict,
    intent_type: str = "data",
    previous_response: str = "",
    issues: list = None,
    chat_history: list = None,
    search_condition: str = None,
    holiday_info: dict = None,
) -> str:
    """
    Build complete prompt for Analyst.

    Args:
        question: User's question
        data: Data from DataFetcher
        intent_type: "data" or "concept"
        previous_response: Previous response if rewriting
        issues: Validation issues if rewriting
        chat_history: Previous messages for context
        search_condition: Natural language condition for filtering data
        holiday_info: Info about holidays in requested dates (from Understander)

    Returns:
        Complete prompt string
    """
    import json

    # Format chat history
    history_str = "No previous context"
    if chat_history:
        history_str = ""
        for msg in chat_history[-config.CHAT_HISTORY_LIMIT:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_str += f"{role}: {msg.get('content', '')}\n"

    # Format holiday context if present
    holiday_context = ""
    if holiday_info:
        holiday_names = holiday_info.get("names", {})
        holiday_list = ", ".join(f"{d} ({holiday_names.get(d, 'holiday')})" for d in holiday_info.get("dates", []))

        if holiday_info.get("all_holidays"):
            holiday_context = f"\n\n<holiday_notice>\nIMPORTANT: All requested dates are market holidays: {holiday_list}. The market was closed on these days, so there is no trading data. Explain this to the user and suggest looking at adjacent trading days.\n</holiday_notice>"
        elif holiday_info.get("early_close_conflict"):
            early_close_dates = holiday_info.get("early_close_dates", [])
            early_list = ", ".join(f"{d} ({holiday_names.get(d, 'early close')})" for d in early_close_dates)
            holiday_context = f"\n\n<holiday_notice>\nIMPORTANT: Requested time conflicts with early close: {early_list}. On these days the market closed at 13:00 ET. Data after 13:00 will be missing. Explain this to the user.\n</holiday_notice>"
        elif holiday_info.get("early_close_dates"):
            early_list = ", ".join(f"{d} ({holiday_names.get(d, 'early close')})" for d in holiday_info.get("early_close_dates", []))
            holiday_context = f"\n\n<holiday_notice>\nNote: Some requested dates are early close days: {early_list}. Market closed at 13:00 ET on these days, so afternoon data is limited.\n</holiday_notice>"
        else:
            holiday_context = f"\n\n<holiday_notice>\nNote: Some requested dates are market holidays: {holiday_list}. These days will have no data in the results.\n</holiday_notice>"

    # Rewrite case
    if previous_response and issues:
        return SYSTEM_PROMPT + "\n" + USER_PROMPT_REWRITE.format(
            data=json.dumps(data, indent=2, default=str),
            previous_response=previous_response,
            issues="\n".join(f"- {issue}" for issue in issues),
            question=question,
        )

    # Concept - no data
    if intent_type == "concept":
        return SYSTEM_PROMPT + "\n" + USER_PROMPT_CONCEPT.format(
            question=question,
        )

    # Search query - Analyst filters the data
    if search_condition:
        return SYSTEM_PROMPT + "\n" + USER_PROMPT_SEARCH.format(
            chat_history=history_str,
            data=json.dumps(data, indent=2, default=str),
            search_condition=search_condition,
            question=question,
        ) + holiday_context

    # Data (default)
    return SYSTEM_PROMPT + "\n" + USER_PROMPT_DATA.format(
        chat_history=history_str,
        data=json.dumps(data, indent=2, default=str),
        question=question,
    ) + holiday_context


# =============================================================================
# Streaming Prompt (plain markdown, no JSON)
# =============================================================================

SYSTEM_PROMPT_STREAMING = """<role>
You are a trading data analyst. Your task is to analyze data and write clear, factual responses.
You must respond in the same language as the user's question.
</role>

<constraints>
1. ONLY use facts from the provided data - never invent numbers
2. Be concise but insightful - don't just present numbers, explain what they mean
3. Use markdown tables for presenting data
4. If data is insufficient, say so explicitly
5. Respond in the SAME LANGUAGE as the user's question
6. Write plain markdown text - do NOT use JSON format
7. For volatility/range statistics over long periods, briefly note that holidays and early-close days are included and may affect the results. Mention user can request excluding them if needed.
8. TRUNCATED DATA: If data has "truncated": true, you're seeing only a sample (check "showing" vs "row_count", "summary_note" explains sorting). You can only analyze visible rows. At the START say: "Показано X из Y строк. Полная таблица доступна в интерфейсе." At the END of your analysis add a disclaimer: "⚠️ Выводы основаны на выборке (топ-N). Для полной картины рекомендуется изучить все данные." Do NOT claim data is missing.
</constraints>
"""


def get_analyst_prompt_streaming(
    question: str,
    data: dict,
    chat_history: list = None,
    search_condition: str = None,
    holiday_info: dict = None,
) -> str:
    """
    Build prompt for streaming mode (plain markdown, no JSON).

    Used when real-time streaming is enabled via get_stream_writer().
    Stats extraction happens via _extract_stats_from_text after streaming.
    """
    import json as json_module

    # Format chat history
    history_str = "No previous context"
    if chat_history:
        history_str = ""
        for msg in chat_history[-config.CHAT_HISTORY_LIMIT:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_str += f"{role}: {msg.get('content', '')}\n"

    # Format holiday context if present
    holiday_context = ""
    if holiday_info:
        holiday_names = holiday_info.get("names", {})
        holiday_list = ", ".join(f"{d} ({holiday_names.get(d, 'holiday')})" for d in holiday_info.get("dates", []))

        if holiday_info.get("all_holidays"):
            holiday_context = f"\n\n<holiday_notice>\nIMPORTANT: All requested dates are market holidays: {holiday_list}. The market was closed on these days, so there is no trading data. Explain this to the user and suggest looking at adjacent trading days.\n</holiday_notice>"
        elif holiday_info.get("early_close_conflict"):
            early_close_dates = holiday_info.get("early_close_dates", [])
            early_list = ", ".join(f"{d} ({holiday_names.get(d, 'early close')})" for d in early_close_dates)
            holiday_context = f"\n\n<holiday_notice>\nIMPORTANT: Requested time conflicts with early close: {early_list}. On these days the market closed at 13:00 ET. Data after 13:00 will be missing. Explain this to the user.\n</holiday_notice>"
        elif holiday_info.get("early_close_dates"):
            early_list = ", ".join(f"{d} ({holiday_names.get(d, 'early close')})" for d in holiday_info.get("early_close_dates", []))
            holiday_context = f"\n\n<holiday_notice>\nNote: Some requested dates are early close days: {early_list}. Market closed at 13:00 ET on these days, so afternoon data is limited.\n</holiday_notice>"
        else:
            holiday_context = f"\n\n<holiday_notice>\nNote: Some requested dates are market holidays: {holiday_list}. These days will have no data in the results.\n</holiday_notice>"

    # Add search condition hint if present
    task_suffix = ""
    if search_condition:
        task_suffix = f"\n\nNote: Filter the data to find rows matching: {search_condition}"

    prompt = SYSTEM_PROMPT_STREAMING + "\n" + USER_PROMPT_DATA_STREAMING.format(
        chat_history=history_str,
        data=json_module.dumps(data, indent=2, default=str),
        question=question,
    )

    return prompt + task_suffix + holiday_context
