"""
Analyst prompts - structured following Gemini best practices.

Analyst writes response AND extracts Stats for validation.
"""

# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """<role>
You are a trading data analyst. Your task is to analyze data and write clear, factual responses.
You must respond in the same language as the user's question.
</role>

<constraints>
1. ONLY use facts from the provided data - never invent numbers
2. Be concise and factual
3. Use markdown tables for presenting data
4. If data is insufficient, say so explicitly
5. Respond in the SAME LANGUAGE as the user's question
</constraints>

<output_format>
Your response must be valid JSON with two fields:
{{
  "response": "Your analysis in markdown format...",
  "stats": {{
    // Include ONLY numbers you mentioned in response
    "change_pct": 1.76,        // if you mentioned percentage change
    "trading_days": 27,        // if you mentioned trading days
    "max_price": 17793.5,      // if you mentioned max price
    "min_price": 16334.25,     // if you mentioned min price
    "total_volume": 13689749,  // if you mentioned volume
    // ... only fields you actually used
  }}
}}
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

USER_PROMPT_DATA = """<data>
{data}
</data>

<task>
Question: {question}

Analyze the data and respond with JSON containing "response" and "stats".
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
) -> str:
    """
    Build complete prompt for Analyst.

    Args:
        question: User's question
        data: Data from DataFetcher
        intent_type: "data", "pattern", or "concept"
        previous_response: Previous response if rewriting
        issues: Validation issues if rewriting

    Returns:
        Complete prompt string
    """
    import json

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

    # Pattern results
    if intent_type == "pattern":
        matches_str = ""
        if data.get("matches"):
            for m in data["matches"][:20]:  # Limit to 20 matches
                matches_str += f"- {json.dumps(m, default=str)}\n"

        return SYSTEM_PROMPT + "\n" + USER_PROMPT_PATTERN.format(
            pattern_name=data.get("pattern", "unknown"),
            period_start=data.get("period_start", ""),
            period_end=data.get("period_end", ""),
            matches_count=data.get("matches_count", 0),
            matches=matches_str or "No matches found",
            question=question,
        )

    # Data (default)
    return SYSTEM_PROMPT + "\n" + USER_PROMPT_DATA.format(
        data=json.dumps(data, indent=2, default=str),
        question=question,
    )
