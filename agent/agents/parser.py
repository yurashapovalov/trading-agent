"""
Parser agent — extracts entities from user question using LLM.

Input: question, chat_history, today
Output: ParsedQuery (what, period, filters, modifiers, unclear)

No business logic here — just entity extraction.
"""

from __future__ import annotations

import json
from datetime import datetime
from dataclasses import dataclass

from google import genai
from google.genai import types
from pydantic import ValidationError

import config
from agent.prompts.parser import get_parser_prompt
from agent.query_builder.types import (
    ParsedQuery,
    ParsedPeriod,
    ParsedFilters,
    ParsedModifiers,
)
from agent.pricing import calculate_cost


def dict_to_parsed_query(data: dict) -> ParsedQuery:
    """Convert raw LLM dict output to typed ParsedQuery.

    Validates LLM output against Pydantic models.
    Returns fallback ParsedQuery on validation errors.
    """
    try:
        period_data = data.get("period")
        period = ParsedPeriod(**period_data) if period_data else None

        filters_data = data.get("filters")
        filters = ParsedFilters(**filters_data) if filters_data else None

        modifiers_data = data.get("modifiers")
        modifiers = ParsedModifiers(**modifiers_data) if modifiers_data else None

        # Parse intent with fallback to "data"
        intent = data.get("intent", "data")
        if intent not in ("data", "chitchat", "concept"):
            intent = "data"

        return ParsedQuery(
            intent=intent,
            what=data.get("what", "greeting"),
            period=period,
            filters=filters,
            modifiers=modifiers,
            unclear=data.get("unclear", []),
            summary=data.get("summary", ""),
        )
    except ValidationError as e:
        print(f"[Parser] ParsedQuery validation failed: {e}")
        # Return fallback — ask for clarification
        return ParsedQuery(
            intent="data",
            what="unknown",
            unclear=["question"],
            summary="I couldn't understand your question. Could you please rephrase it?",
        )


@dataclass
class ParserResult:
    """Result from Parser agent."""
    parsed_query: ParsedQuery
    raw_output: dict  # Original LLM output for debugging

    # Usage stats
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    parse_time_ms: int = 0


class Parser:
    """
    Parser agent — extracts entities from user question.

    Uses Gemini LLM to parse the question into structured entities.
    Does NOT make business decisions (that's Composer's job).

    Usage:
        parser = Parser()
        result = parser.parse("Volatility by hour for Fridays")
        # result.parsed_query contains: what="volatility", period=..., filters=...
    """

    name = "parser"

    def __init__(self, symbol: str = "NQ"):
        """Initialize Parser with Gemini client."""
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_LITE_MODEL
        self.symbol = symbol

    def parse(
        self,
        question: str,
        chat_history: str = "",
        today: str | None = None,
        previous_parsed: ParsedQuery | None = None,
    ) -> ParserResult:
        """
        Parse question and extract entities.

        Args:
            question: User's question in any language
            chat_history: Previous conversation for context
            today: Today's date (YYYY-MM-DD), defaults to now
            previous_parsed: Previous ParsedQuery for follow-up context

        Returns:
            ParserResult with parsed_query and usage stats
        """
        if today is None:
            today = datetime.now().strftime("%Y-%m-%d")

        # Build prompt
        system, user = get_parser_prompt(
            question,
            chat_history,
            today,
            symbol=self.symbol,
            previous_parsed=previous_parsed,
        )
        full_prompt = f"{system}\n\n{user}"

        start = datetime.now()

        # Call LLM with thinking enabled for better reasoning
        # Use response_schema to enforce valid JSON structure
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=ParsedQuery,  # Enforce JSON schema
                thinking_config=types.ThinkingConfig(thinking_budget=512),
            ),
        )

        parse_time_ms = int((datetime.now() - start).total_seconds() * 1000)

        # Parse JSON response
        try:
            raw_output = json.loads(response.text)
        except json.JSONDecodeError:
            raw_output = {"what": "greeting", "summary": "Hello!"}

        # Convert to typed ParsedQuery
        parsed_query = dict_to_parsed_query(raw_output)

        # Track usage
        input_tokens = 0
        output_tokens = 0
        thinking_tokens = 0
        cached_tokens = 0
        cost_usd = 0.0

        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0
            thinking_tokens = getattr(response.usage_metadata, 'thoughts_token_count', 0) or 0
            cached_tokens = getattr(response.usage_metadata, 'cached_content_token_count', 0) or 0
            cost_usd = calculate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                cached_tokens=cached_tokens,
                model=self.model,
            )

        return ParserResult(
            parsed_query=parsed_query,
            raw_output=raw_output,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
            cached_tokens=cached_tokens,
            cost_usd=cost_usd,
            parse_time_ms=parse_time_ms,
        )


# Singleton for easy import
parser = Parser()
