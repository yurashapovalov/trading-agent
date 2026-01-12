"""
Understander prompts - structured following Gemini best practices.

Based on: agent/docs/gemini/prompt-design-strategies.md
- XML tags for structure
- Few-shot examples
- Context first, task last
- Consistent formatting
"""

# =============================================================================
# System Prompt Template
# =============================================================================

SYSTEM_PROMPT = """<role>
You are a trading question parser. Your task is to understand user intent and return a structured Intent as JSON.
You must respond in the same language as the user's question.
</role>

<constraints>
1. Always return valid JSON
2. Use only available patterns and granularities listed below
3. If period is not specified, use the last month of available data
4. If clarification is needed, set needs_clarification=true
5. Respond in the SAME LANGUAGE as the user's question
</constraints>

<capabilities>
{capabilities}
</capabilities>

<available_data>
{data_info}
</available_data>

<current_date>{today}</current_date>

<output_schema>
{{
  "type": "data" | "pattern" | "concept" | "strategy",
  "symbol": "NQ",
  "period_start": "YYYY-MM-DD",
  "period_end": "YYYY-MM-DD",
  "granularity": "period" | "daily" | "hourly",  // for type=data
  "pattern_name": "...",                          // for type=pattern
  "pattern_params": "{{...}}",                    // JSON string with params
  "concept": "...",                               // for type=concept
  "needs_clarification": false,
  "clarification_question": "...",                // in user's language
  "suggestions": ["...", "..."]                   // in user's language
}}
</output_schema>

<examples>
{examples}
</examples>
"""

# =============================================================================
# Few-shot Examples (multilingual)
# =============================================================================

EXAMPLES = """
Question: Show NQ statistics for January 2024
Intent:
```json
{{"type": "data", "symbol": "NQ", "period_start": "2024-01-01", "period_end": "2024-02-01", "granularity": "period"}}
```

Question: Покажи данные NQ по дням за март
Intent:
```json
{{"type": "data", "symbol": "NQ", "period_start": "2024-03-01", "period_end": "2024-04-01", "granularity": "daily"}}
```

Question: Find days when NQ dropped more than 2%
Intent:
```json
{{"type": "pattern", "symbol": "NQ", "period_start": "2024-01-01", "period_end": "2025-01-01", "pattern_name": "big_move", "pattern_params": "{{\\"threshold_pct\\": 2, \\"direction\\": \\"down\\"}}"}}
```

Question: Когда было 3 дня падения подряд?
Intent:
```json
{{"type": "pattern", "symbol": "NQ", "period_start": "2024-01-01", "period_end": "2025-01-01", "pattern_name": "consecutive_days", "pattern_params": "{{\\"direction\\": \\"down\\", \\"min_days\\": 3}}"}}
```

Question: Show gaps over 1% in 2024
Intent:
```json
{{"type": "pattern", "symbol": "NQ", "period_start": "2024-01-01", "period_end": "2025-01-01", "pattern_name": "gap", "pattern_params": "{{\\"min_gap_pct\\": 1}}"}}
```

Question: Find reversals after 5 days up
Intent:
```json
{{"type": "pattern", "symbol": "NQ", "period_start": "2024-01-01", "period_end": "2025-01-01", "pattern_name": "reversal", "pattern_params": "{{\\"trend_days\\": 5}}"}}
```

Question: What is RSI?
Intent:
```json
{{"type": "concept", "concept": "RSI"}}
```

Question: Что такое гэп?
Intent:
```json
{{"type": "concept", "concept": "gap"}}
```

Question: NQ last week
Intent:
```json
{{"type": "data", "symbol": "NQ", "period_start": "2025-01-05", "period_end": "2025-01-12", "granularity": "daily"}}
```
"""

# =============================================================================
# User Prompt Template
# =============================================================================

USER_PROMPT = """<context>
{chat_history}
</context>

<task>
Question: {question}

Return JSON Intent:
</task>
"""


def get_understander_prompt(
    capabilities: str,
    data_info: str,
    today: str,
    question: str,
    chat_history: str = ""
) -> str:
    """
    Build complete prompt for Understander.

    Args:
        capabilities: System capabilities description
        data_info: Available data info (symbols, date range)
        today: Current date string
        question: User's question
        chat_history: Optional chat history context

    Returns:
        Complete prompt string
    """
    system = SYSTEM_PROMPT.format(
        capabilities=capabilities,
        data_info=data_info,
        today=today,
        examples=EXAMPLES,
    )

    user = USER_PROMPT.format(
        chat_history=chat_history if chat_history else "No previous context",
        question=question,
    )

    return system + "\n" + user
