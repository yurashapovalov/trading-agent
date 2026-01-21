"""
Clarifier agent — asks user for missing information.

Single responsibility: handle unclear queries → return clarification or reformulated query.

Uses:
- prompts/clarification.py for prompt constants
- types.py for ClarificationOutput schema
- memory/cache.py for explicit caching
- Gemini with response_schema for structured output
"""

from google import genai
from google.genai import types

import config
from agent.types import ClarificationOutput
from agent.prompts.clarification import SYSTEM_PROMPT, USER_PROMPT
from agent.memory.cache import get_cache_manager


class Clarifier:
    """
    Handles clarification flow for unclear queries.

    Takes parsed query with unclear fields, returns either:
    - A clarifying question (clarified_query=None)
    - Confirmed reformulated query (clarified_query="...")

    Features:
    - Explicit caching for system prompt (cost savings)
    - Multi-language support (responds in user's language)

    Usage:
        clarifier = Clarifier()

        # First turn — ask user
        result = clarifier.clarify(
            question="статистика за 2024",
            parsed={"unclear": ["metric"], "period": {"type": "year", "value": "2024"}},
        )
        # result.response = "Что посчитать? Волатильность, доходность?"
        # result.clarified_query = None

        # Second turn — user answered
        result = clarifier.clarify(
            question="волатильность",
            parsed={},
            previous_context="Asked about: 2024 stats",
        )
        # result.response = "Хорошо, смотрим волатильность за 2024."
        # result.clarified_query = "волатильность за 2024 год"
    """

    # Cache settings
    CACHE_KEY = "clarifier_system_v1"
    CACHE_TTL = 3600  # 1 hour

    def __init__(self, model: str | None = None, use_cache: bool = True):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = model or config.GEMINI_LITE_MODEL
        self.use_cache = use_cache
        self._cache_manager = get_cache_manager() if use_cache else None

    def clarify(
        self,
        question: str,
        parsed: dict,
        previous_context: str = "",
        parser_thoughts: str = "",
    ) -> ClarificationOutput:
        """
        Generate clarification response or confirm reformulated query.

        Args:
            question: Current user message
            parsed: Parsed query dict (period, unclear, what, etc.)
            previous_context: Context from previous clarification turns
            parser_thoughts: Parser's thinking about what's unclear and why

        Returns:
            ClarificationOutput with response and optional clarified_query
        """
        # Determine mode based on context
        mode = "confirming" if previous_context else "asking"

        # Extract fields from parsed
        period = parsed.get("period", {})
        unclear = parsed.get("unclear", [])
        what = parsed.get("what", "")

        # Build user prompt
        user_prompt = USER_PROMPT.format(
            question=question,
            period=period,
            unclear=unclear,
            what=what,
            previous_context=previous_context or "None",
            mode=mode,
            parser_thoughts=parser_thoughts or "None",
        )

        # Try cached request first
        cache_name = None
        if self.use_cache and self._cache_manager:
            cache_name = self._cache_manager.get_or_create(
                key=self.CACHE_KEY,
                content=SYSTEM_PROMPT,
                ttl_seconds=self.CACHE_TTL,
            )

        # Call LLM with structured output
        if cache_name:
            # Cached: system prompt is in cache
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    cached_content=cache_name,
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=ClarificationOutput,
                ),
            )
        else:
            # Not cached: include system prompt in contents
            response = self.client.models.generate_content(
                model=self.model,
                contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=ClarificationOutput,
                ),
            )

        return ClarificationOutput.model_validate_json(response.text)


# =============================================================================
# Simple API
# =============================================================================

def clarify(
    question: str,
    parsed: dict,
    previous_context: str = "",
    parser_thoughts: str = "",
) -> ClarificationOutput:
    """
    Handle clarification for unclear query.

    Simple wrapper for Clarifier class.

    Args:
        question: User's message
        parsed: Parsed query dict
        previous_context: Previous clarification context
        parser_thoughts: Parser's reasoning about unclear fields

    Returns:
        ClarificationOutput with response and optional clarified_query
    """
    clarifier = Clarifier()
    return clarifier.clarify(question, parsed, previous_context, parser_thoughts)
