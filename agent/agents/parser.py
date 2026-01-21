"""
Parser agent — extracts entities from user question.

Single responsibility: parse question → return ParsedQuery.

Features:
- RAP (Retrieval-Augmented Prompting) for dynamic prompts
- Explicit caching for system prompt (cost savings)
- Thinking with small budget (better quality)
- Thought logging (debugging)

Uses:
- prompts/parser/rap.py for RAP engine
- prompts/parser.py for static prompt (fallback)
- types.py for ParsedQuery schema
- memory/cache.py for explicit caching
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from google import genai
from google.genai import types

import config
from agent.types import ParsedQuery, Usage
from agent.prompts.parser_static import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from agent.prompts.parser.rap import get_rap
from agent.memory.cache import get_cache_manager

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Parser result with optional thinking summary."""
    query: ParsedQuery
    thoughts: Optional[str] = None
    cached: bool = False
    chunks_used: Optional[list[str]] = None  # RAP chunks used
    usage: Usage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = Usage()


class Parser:
    """
    Entity extraction from trading questions.

    Takes user question, returns structured ParsedQuery.
    Uses thinking for better quality and logs thought process.

    Supports RAP (Retrieval-Augmented Prompting) for dynamic prompts.

    Usage:
        parser = Parser()
        result = parser.parse("волатильность за 2024")
        # result.query.metric = "range"
        # result.thoughts = "User asks about volatility..."
        # result.chunks_used = ["metric/metrics", "period/absolute"]
    """

    # Cache settings (explicit caching needs stable model version like gemini-2.0-flash-001)
    # Preview models don't support explicit caching, so we rely on implicit
    CACHE_KEY = "parser_system_v1"
    CACHE_TTL = 3600  # 1 hour

    # Thinking budget (small for simple extraction)
    THINKING_BUDGET = 512

    # RAP settings
    RAP_TOP_K = 5  # Number of chunks to retrieve

    def __init__(
        self,
        model: str | None = None,
        use_cache: bool = True,  # Explicit caching for system prompt
        use_thinking: bool = True,
        use_rap: bool = True,  # Use RAP for dynamic prompts
    ):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = model or config.GEMINI_LITE_MODEL
        self.use_cache = use_cache
        self.use_thinking = use_thinking
        self.use_rap = use_rap
        self._cache_manager = get_cache_manager() if use_cache else None
        self._rap = get_rap() if use_rap else None

    def parse(
        self,
        question: str,
        today: date | None = None,
        context: str = "",
    ) -> ParseResult:
        """
        Parse user question into structured entities.

        Args:
            question: User's question (should be in English, pre-translated)
            today: Current date (defaults to today)
            context: Optional conversation context

        Returns:
            ParseResult with query, thoughts, and chunks_used
        """
        if today is None:
            today = date.today()

        weekday = today.strftime("%A")

        # Build user prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            today=today.isoformat(),
            weekday=weekday,
            question=question,
        )

        # Add context if provided
        if context:
            user_prompt = f"<context>\n{context}\n</context>\n\n{user_prompt}"

        # Build system prompt (RAP or static)
        chunks_used = None
        if self.use_rap and self._rap:
            system_prompt, chunks_used = self._rap.build(question, top_k=self.RAP_TOP_K)
            logger.info(f"RAP chunks: {chunks_used}")
        else:
            system_prompt = SYSTEM_PROMPT

        # Build config
        gen_config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=ParsedQuery,
        )

        # Add thinking if enabled
        if self.use_thinking:
            gen_config.thinking_config = types.ThinkingConfig(
                thinking_budget=self.THINKING_BUDGET,
                include_thoughts=True,
            )

        # Try cached request first (only for static prompt, RAP prompts vary)
        cache_name = None
        if self.use_cache and self._cache_manager and not self.use_rap:
            cache_name = self._cache_manager.get_or_create(
                key=self.CACHE_KEY,
                content=system_prompt,
                ttl_seconds=self.CACHE_TTL,
            )

        # Make request
        if cache_name:
            # Cached: system prompt is in cache
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    cached_content=cache_name,
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=ParsedQuery,
                    thinking_config=gen_config.thinking_config if self.use_thinking else None,
                ),
            )
            cached = True
        else:
            # Not cached: include system prompt in contents
            response = self.client.models.generate_content(
                model=self.model,
                contents=f"{system_prompt}\n\n{user_prompt}",
                config=gen_config,
            )
            cached = False

        # Extract thoughts and response
        thoughts = None
        response_text = None

        for part in response.candidates[0].content.parts:
            if not part.text:
                continue
            if hasattr(part, 'thought') and part.thought:
                thoughts = part.text
                logger.debug(f"Parser thinking: {thoughts[:200]}...")
            else:
                response_text = part.text

        # Parse response
        if response_text:
            query = ParsedQuery.model_validate_json(response_text)
        else:
            # Fallback to response.text
            query = ParsedQuery.model_validate_json(response.text)

        # Extract usage
        usage = Usage.from_response(response)

        # Log for debugging
        logger.info(f"Parsed: intent={query.intent}, cached={cached}, tokens={usage.input_tokens}+{usage.output_tokens}")
        if chunks_used:
            logger.info(f"Chunks used: {chunks_used}")
        if thoughts:
            logger.debug(f"Thoughts: {thoughts}")

        return ParseResult(query=query, thoughts=thoughts, cached=cached, chunks_used=chunks_used, usage=usage)


# =============================================================================
# Simple API
# =============================================================================

def parse(
    question: str,
    today: date | None = None,
    context: str = "",
) -> ParsedQuery:
    """
    Parse question into structured entities.

    Simple wrapper — returns just ParsedQuery (no thoughts).

    Args:
        question: User's question
        today: Current date (optional)
        context: Conversation context (optional)

    Returns:
        ParsedQuery with extracted entities
    """
    parser = Parser()
    result = parser.parse(question, today, context)
    return result.query
