"""
Barb — askbar.ai assistant.

COMPATIBILITY LAYER: Wraps Parser + Composer agents.
Use Parser and ComposerAgent directly for new code.

Clean Parser + Composer flow:
    Question → Parser (LLM) → entities
            → Composer (code) → QuerySpec / Clarification / Concept / Greeting
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.agents.parser import Parser, ParserResult
from agent.agents.composer_agent import ComposerAgent, ComposerAgentResult
from agent.query_builder.types import (
    QuerySpec,
    ClarificationState,
)


@dataclass
class BarbResult:
    """Result from Barb (compatibility layer)."""
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

    COMPATIBILITY LAYER: Wraps Parser + Composer agents.
    For new code, use Parser and ComposerAgent directly.

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
        """Initialize Barb with Parser and Composer."""
        self.symbol = symbol
        self.parser = Parser(symbol=symbol)
        self.composer = ComposerAgent(symbol=symbol)

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
        # Track original question for state
        original_question = state.original_question if state else question

        # Step 1: Parser (LLM) — extract entities
        parser_result = self.parser.parse(question, chat_history=chat_history, today=today)

        # Step 2: Merge with previous state (deterministic, not LLM-dependent)
        parsed_query = parser_result.parsed_query
        if state and state.resolved:
            parsed_query = state.resolved.merge_with(parsed_query)

        # Step 3: Composer (code) — business decisions
        composer_result = self.composer.compose(
            parsed_query,
            original_question=original_question,
            state=state,
        )

        # Step 4: Convert to BarbResult
        return self._to_barb_result(parser_result, composer_result)

    def _to_barb_result(
        self,
        parser_result: ParserResult,
        composer_result: ComposerAgentResult,
    ) -> BarbResult:
        """Convert Parser + Composer results to BarbResult."""
        base = {
            "type": composer_result.type,
            "summary": composer_result.summary,
            "holiday_info": composer_result.holiday_info,
            "event_info": composer_result.event_info,
            "parser_output": parser_result.raw_output,
            "input_tokens": parser_result.input_tokens,
            "output_tokens": parser_result.output_tokens,
            "cost_usd": parser_result.cost_usd,
            "parse_time_ms": parser_result.parse_time_ms,
        }

        if composer_result.type == "query":
            return BarbResult(**base, spec=composer_result.spec)

        if composer_result.type == "clarification":
            return BarbResult(
                **base,
                field=composer_result.field,
                options=composer_result.options,
                state=composer_result.state,
            )

        if composer_result.type == "concept":
            return BarbResult(**base, concept=composer_result.concept)

        if composer_result.type == "greeting":
            return BarbResult(**base)

        if composer_result.type == "not_supported":
            return BarbResult(**base, reason=composer_result.reason)

        return BarbResult(**base)


# Singleton for easy import
barb = Barb()
