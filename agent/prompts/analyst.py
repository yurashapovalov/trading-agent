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
        )

    # Data (default)
    return SYSTEM_PROMPT + "\n" + USER_PROMPT_DATA.format(
        chat_history=history_str,
        data=json.dumps(data, indent=2, default=str),
        question=question,
    )
