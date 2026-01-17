"""
Barb — askbar.ai assistant.

Clean Parser + Composer flow:
    Question → Parser (LLM) → entities
            → Composer (code) → QuerySpec / Clarification / Concept / Greeting

No legacy Understander code. Pure and simple.
"""

from __future__ import annotations

import json
from datetime import datetime
from dataclasses import dataclass

from google import genai
from google.genai import types

import config
from agent.prompts.parser import get_parser_prompt
from agent.composer import (
    compose,
    ComposerResult,
    QueryWithSummary,
    ClarificationResult,
    ConceptResult,
    GreetingResult,
    NotSupportedResult,
)
from agent.query_builder.types import QuerySpec
from agent.pricing import calculate_cost
from agent.agents.understander import check_dates_for_holidays


@dataclass
class BarbResult:
    """Result from Barb."""
    type: str  # "query", "clarification", "concept", "greeting", "not_supported"
    summary: str  # Human-readable summary in user's language

    # For query type
    spec: QuerySpec | None = None

    # For clarification type
    field: str | None = None
    options: list[str] | None = None

    # For concept type
    concept: str | None = None

    # For not_supported type
    reason: str | None = None

    # Holiday info (if dates are holidays)
    holiday_info: dict | None = None

    # Debug info (for analysis)
    parser_output: dict | None = None  # Raw LLM output

    # Usage stats
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    parse_time_ms: int = 0


class Barb:
    """
    Barb — the askbar.ai assistant.

    Understands trading questions and converts them to QuerySpec.

    Usage:
        barb = Barb()
        result = barb.ask("Statistics for Fridays 2020-2025")

        if result.type == "query":
            sql = query_builder.build(result.spec)
        elif result.type == "clarification":
            show_options(result.options)
    """

    name = "barb"

    def __init__(self, symbol: str = "NQ"):
        """Initialize Barb with Gemini client."""
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_LITE_MODEL  # Fast model for parsing
        self.symbol = symbol

    def ask(
        self,
        question: str,
        chat_history: str = "",
        today: str | None = None,
    ) -> BarbResult:
        """
        Process a question and return structured result.

        Args:
            question: User's question in any language
            chat_history: Previous conversation for context
            today: Today's date (YYYY-MM-DD), defaults to now

        Returns:
            BarbResult with type-specific fields
        """
        if today is None:
            today = datetime.now().strftime("%Y-%m-%d")

        # Step 1: Parser (LLM) — extract entities
        parsed, usage = self._parse(question, chat_history, today)

        # Step 2: Composer (code) — business decisions
        result = compose(parsed, symbol=self.symbol)

        # Step 3: Check for holidays in requested dates
        holiday_info = self._check_holidays(parsed, result)

        # Step 4: Convert to BarbResult (include parsed for debugging)
        return self._to_barb_result(result, usage, parsed, holiday_info)

    def _parse(
        self,
        question: str,
        chat_history: str,
        today: str,
    ) -> tuple[dict, dict]:
        """Call Parser LLM to extract entities."""
        system, user = get_parser_prompt(question, chat_history, today, symbol=self.symbol)
        full_prompt = f"{system}\n\n{user}"

        start = datetime.now()

        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        parse_time_ms = int((datetime.now() - start).total_seconds() * 1000)

        # Parse response
        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError:
            parsed = {"what": "greeting", "summary": "Hello!"}

        # Track usage
        usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "parse_time_ms": parse_time_ms,
        }

        if response.usage_metadata:
            usage["input_tokens"] = response.usage_metadata.prompt_token_count or 0
            usage["output_tokens"] = response.usage_metadata.candidates_token_count or 0
            usage["cost_usd"] = calculate_cost(
                usage["input_tokens"],
                usage["output_tokens"],
                0,
            )

        return parsed, usage

    def _check_holidays(self, parsed: dict, result: ComposerResult) -> dict | None:
        """Check if requested dates fall on holidays."""
        # Get dates from parser output
        period = parsed.get("period") or {}
        dates = period.get("dates") or []

        if not dates:
            return None

        # Check dates for holidays
        holiday_check = check_dates_for_holidays(dates, self.symbol)

        if not holiday_check:
            return None

        # Build holiday_info structure for Analyst
        all_dates = holiday_check.get("holiday_dates", []) + holiday_check.get("early_close_dates", [])
        if not all_dates:
            return None

        return {
            "dates": all_dates,
            "names": holiday_check["holiday_names"],
            "all_holidays": holiday_check.get("all_holidays", False),
            "early_close_dates": holiday_check.get("early_close_dates", []),
            "early_close_conflict": holiday_check.get("early_close_conflict", False),
            "count": len(all_dates),
        }

    def _to_barb_result(self, result: ComposerResult, usage: dict, parsed: dict, holiday_info: dict | None = None) -> BarbResult:
        """Convert Composer result to BarbResult."""
        base = {
            "type": result.type,
            "summary": result.summary,
            "holiday_info": holiday_info,  # Holiday info for Analyst
            "parser_output": parsed,  # Raw LLM output for debugging
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": usage.get("cost_usd", 0.0),
            "parse_time_ms": usage.get("parse_time_ms", 0),
        }

        if isinstance(result, QueryWithSummary):
            return BarbResult(**base, spec=result.spec)

        elif isinstance(result, ClarificationResult):
            return BarbResult(
                **base,
                field=result.field,
                options=result.options,
            )

        elif isinstance(result, ConceptResult):
            return BarbResult(**base, concept=result.concept)

        elif isinstance(result, GreetingResult):
            return BarbResult(**base)

        elif isinstance(result, NotSupportedResult):
            return BarbResult(**base, reason=result.reason)

        # Fallback
        return BarbResult(**base)


# Singleton for easy import
barb = Barb()
