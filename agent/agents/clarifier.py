"""
Clarifier agent — asks user for missing information.

Single responsibility: handle unclear queries → return clarification or reformulated query.

Uses:
- prompts/clarification.py for prompt constants
- types.py for ClarificationOutput schema
- memory/cache.py for explicit caching
- Gemini with response_schema for structured output
- Thinking for relevance evaluation
"""

import logging
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import types

import config
from agent.types import ClarificationOutput, Usage
from agent.prompts.clarification import SYSTEM_PROMPT, USER_PROMPT
from agent.memory.cache import get_cache_manager

logger = logging.getLogger(__name__)


@dataclass
class ClarifierResult:
    """Clarifier result with usage and thoughts."""
    response: str
    clarified_query: str | None
    thoughts: Optional[str] = None
    usage: Usage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = Usage()


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
    CACHE_KEY = "clarifier_system_v2"
    CACHE_TTL = 3600  # 1 hour

    # Thinking budget for relevance evaluation
    THINKING_BUDGET = 512

    def __init__(
        self,
        model: str | None = None,
        use_cache: bool = True,
        use_thinking: bool = True,
    ):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = model or config.GEMINI_LITE_MODEL
        self.use_cache = use_cache
        self.use_thinking = use_thinking
        self._cache_manager = get_cache_manager() if use_cache else None

    def clarify(
        self,
        question: str,
        parsed: dict,
        previous_context: str = "",
        parser_thoughts: str = "",
        clarifier_question: str = "",
        lang: str = "en",
    ) -> ClarifierResult:
        """
        Generate clarification response or confirm reformulated query.

        Args:
            question: Current user message (in English from IntentClassifier)
            parsed: Parsed query dict (period, unclear, what, etc.)
            previous_context: Context from previous clarification turns
            parser_thoughts: Parser's thinking about what's unclear and why
            clarifier_question: The question Clarifier asked the user (to evaluate relevance)
            lang: User's language code for response (e.g., "ru", "en", "es")

        Returns:
            ClarifierResult with response, clarified_query, thoughts, and usage
        """
        # Determine mode: CONFIRMING if we asked a question before, otherwise ASKING
        mode = "confirming" if clarifier_question else "asking"

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
            clarifier_question=clarifier_question or "None",
            lang=lang,
        )

        # Build generation config
        gen_config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=ClarificationOutput,
        )

        # Add thinking if enabled
        if self.use_thinking:
            gen_config.thinking_config = types.ThinkingConfig(
                thinking_budget=self.THINKING_BUDGET,
                include_thoughts=True,
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
                    thinking_config=gen_config.thinking_config if self.use_thinking else None,
                ),
            )
        else:
            # Not cached: include system prompt in contents
            response = self.client.models.generate_content(
                model=self.model,
                contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
                config=gen_config,
            )

        # Extract thoughts and response
        thoughts = None
        response_text = None

        for part in response.candidates[0].content.parts:
            if not part.text:
                continue
            if hasattr(part, 'thought') and part.thought:
                thoughts = part.text
                logger.debug(f"Clarifier thinking: {thoughts[:200]}...")
            else:
                response_text = part.text

        # Parse response
        if response_text:
            output = ClarificationOutput.model_validate_json(response_text)
        else:
            output = ClarificationOutput.model_validate_json(response.text)

        usage = Usage.from_response(response)

        logger.info(f"Clarifier: mode={mode}, has_clarified_query={output.clarified_query is not None}")
        if thoughts:
            logger.debug(f"Thoughts: {thoughts}")

        return ClarifierResult(
            response=output.response,
            clarified_query=output.clarified_query,
            thoughts=thoughts,
            usage=usage,
        )


# =============================================================================
# Simple API
# =============================================================================

def clarify(
    question: str,
    parsed: dict,
    previous_context: str = "",
    parser_thoughts: str = "",
    clarifier_question: str = "",
    lang: str = "en",
) -> ClarifierResult:
    """
    Handle clarification for unclear query.

    Simple wrapper for Clarifier class.

    Args:
        question: User's message (in English)
        parsed: Parsed query dict
        previous_context: Previous clarification context
        parser_thoughts: Parser's reasoning about unclear fields
        clarifier_question: The question Clarifier asked (for relevance check)
        lang: User's language for response

    Returns:
        ClarifierResult with response, clarified_query, thoughts, and usage
    """
    clarifier = Clarifier()
    return clarifier.clarify(
        question, parsed, previous_context, parser_thoughts, clarifier_question, lang
    )
