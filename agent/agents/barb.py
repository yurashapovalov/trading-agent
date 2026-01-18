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
from pydantic import ValidationError

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
from agent.query_builder.types import (
    QuerySpec,
    ParsedQuery,
    ParsedPeriod,
    ParsedFilters,
    ParsedModifiers,
    ClarificationState,
)
from agent.pricing import calculate_cost
from agent.market.holidays import check_dates_for_holidays
from agent.market.events import check_dates_for_events


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

        return ParsedQuery(
            what=data.get("what", "greeting"),
            period=period,
            filters=filters,
            modifiers=modifiers,
            unclear=data.get("unclear", []),
            summary=data.get("summary", ""),
        )
    except ValidationError as e:
        print(f"[Barb] ParsedQuery validation failed: {e}")
        # Return fallback — ask for clarification
        return ParsedQuery(
            what="unknown",
            unclear=["question"],
            summary="I couldn't understand your question. Could you please rephrase it?",
        )


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
    state: ClarificationState | None = None  # Pass to next ask() call

    # For concept type
    concept: str | None = None

    # For not_supported type
    reason: str | None = None

    # Holiday info (if dates are holidays)
    holiday_info: dict | None = None

    # Event info (if dates have known events like OPEX, NFP)
    event_info: dict | None = None

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
        state: ClarificationState | None = None,
    ) -> BarbResult:
        """
        Process a question and return structured result.

        Args:
            question: User's question in any language
            chat_history: Previous conversation for context
            today: Today's date (YYYY-MM-DD), defaults to now
            state: Previous clarification state (pass result.state from previous call)

        Returns:
            BarbResult with type-specific fields.
            For clarifications, includes state to pass to next call.
        """
        if today is None:
            today = datetime.now().strftime("%Y-%m-%d")

        # Track original question for state
        original_question = state.original_question if state else question

        # Step 1: Parser (LLM) — extract entities as dict
        parsed_dict, usage = self._parse(question, chat_history, today)

        # Step 2: Convert to typed ParsedQuery
        parsed = dict_to_parsed_query(parsed_dict)

        # Step 3: Merge with previous state (deterministic, not LLM-dependent)
        if state and state.resolved:
            parsed = state.resolved.merge_with(parsed)

        # Step 4: Composer (code) — business decisions
        result = compose(parsed, symbol=self.symbol)

        # Step 5: Check for holidays in requested dates
        holiday_info = self._check_holidays(parsed, result)

        # Step 6: Check for events in requested dates (OPEX, NFP, etc.)
        event_info = self._check_events(parsed)

        # Step 7: Build state for clarification flow
        next_state = None
        if result.type == "clarification":
            next_state = ClarificationState(
                original_question=original_question,
                resolved=parsed,
            )

        # Step 8: Convert to BarbResult
        return self._to_barb_result(result, usage, parsed_dict, holiday_info, event_info, next_state)

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

    def _check_holidays(self, parsed: ParsedQuery, result: ComposerResult) -> dict | None:
        """Check if requested dates fall on holidays."""
        dates = parsed.period.dates if parsed.period else []

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

    def _check_events(self, parsed: ParsedQuery) -> dict | None:
        """Check if requested dates have known events (OPEX, NFP, etc.)."""
        dates = parsed.period.dates if parsed.period else []

        if not dates:
            return None

        event_check = check_dates_for_events(dates, self.symbol)

        if not event_check:
            return None

        return event_check  # {dates, events, high_impact_count}

    def _to_barb_result(
        self,
        result: ComposerResult,
        usage: dict,
        parsed: dict,
        holiday_info: dict | None = None,
        event_info: dict | None = None,
        state: ClarificationState | None = None,
    ) -> BarbResult:
        """Convert Composer result to BarbResult."""
        base = {
            "type": result.type,
            "summary": result.summary,
            "holiday_info": holiday_info,
            "event_info": event_info,
            "parser_output": parsed,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": usage.get("cost_usd", 0.0),
            "parse_time_ms": usage.get("parse_time_ms", 0),
        }

        if isinstance(result, QueryWithSummary):
            return BarbResult(**base, spec=result.spec)

        if isinstance(result, ClarificationResult):
            return BarbResult(
                **base,
                field=result.field,
                options=result.options,
                state=state,  # Pass state for next round
            )

        if isinstance(result, ConceptResult):
            return BarbResult(**base, concept=result.concept)

        if isinstance(result, GreetingResult):
            return BarbResult(**base)

        if isinstance(result, NotSupportedResult):
            return BarbResult(**base, reason=result.reason)

        return BarbResult(**base)


# Singleton for easy import
barb = Barb()
