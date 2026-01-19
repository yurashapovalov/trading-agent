"""
Composer agent — business logic for query classification.

Input: ParsedQuery (from Parser)
Output: type (query/greeting/concept/clarification/not_supported) + QuerySpec if query

No LLM here — pure code logic.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    ParsedQuery,
    QuerySpec,
    ClarificationState,
)
from agent.market.holidays import check_dates_for_holidays
from agent.market.events import check_dates_for_events


@dataclass
class ComposerAgentResult:
    """Result from Composer agent."""
    type: str  # "query", "clarification", "concept", "greeting", "not_supported"
    summary: str

    # For query type
    spec: QuerySpec | None = None

    # For clarification type
    field: str | None = None
    options: list[str] | None = None
    state: ClarificationState | None = None

    # For concept type
    concept: str | None = None

    # For not_supported type
    reason: str | None = None

    # Context info
    holiday_info: dict | None = None
    event_info: dict | None = None

    # Debug
    composer_result: ComposerResult | None = None


class ComposerAgent:
    """
    Composer agent — makes business decisions based on parsed entities.

    Uses deterministic code logic (no LLM).
    Decides: query type, source, special_op, grouping, etc.

    Usage:
        composer = ComposerAgent()
        result = composer.compose(parsed_query)
        # result.type = "query" | "greeting" | "concept" | "clarification" | "not_supported"
    """

    name = "composer"

    def __init__(self, symbol: str = "NQ"):
        """Initialize Composer with symbol."""
        self.symbol = symbol

    def compose(
        self,
        parsed_query: ParsedQuery,
        original_question: str = "",
        state: ClarificationState | None = None,
    ) -> ComposerAgentResult:
        """
        Process parsed query and determine type + build QuerySpec.

        Args:
            parsed_query: Typed entities from Parser
            original_question: Original user question (for state tracking)
            state: Previous clarification state (for multi-turn clarification)

        Returns:
            ComposerAgentResult with type and relevant data
        """
        # Merge with previous clarification state if needed
        if state and state.resolved:
            parsed_query = state.resolved.merge_with(parsed_query)

        # Call composer logic
        result = compose(parsed_query, symbol=self.symbol)

        # Check holidays
        holiday_info = self._check_holidays(parsed_query)

        # Check events
        event_info = self._check_events(parsed_query)

        # Build next state for clarification
        next_state = None
        if result.type == "clarification":
            next_state = ClarificationState(
                original_question=original_question or "",
                resolved=parsed_query,
            )

        # Convert to agent result
        return self._to_result(result, holiday_info, event_info, next_state)

    def _check_holidays(self, parsed: ParsedQuery) -> dict | None:
        """Check if requested dates fall on holidays."""
        dates = parsed.period.dates if parsed.period else []
        if not dates:
            return None

        holiday_check = check_dates_for_holidays(dates, self.symbol)
        if not holiday_check:
            return None

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
        return event_check  # {dates, events, high_impact_count} or None

    def _to_result(
        self,
        result: ComposerResult,
        holiday_info: dict | None,
        event_info: dict | None,
        state: ClarificationState | None,
    ) -> ComposerAgentResult:
        """Convert composer result to agent result."""
        base = {
            "type": result.type,
            "summary": result.summary,
            "holiday_info": holiday_info,
            "event_info": event_info,
            "composer_result": result,
        }

        if isinstance(result, QueryWithSummary):
            return ComposerAgentResult(**base, spec=result.spec)

        if isinstance(result, ClarificationResult):
            return ComposerAgentResult(
                **base,
                field=result.field,
                options=result.options,
                state=state,
            )

        if isinstance(result, ConceptResult):
            return ComposerAgentResult(**base, concept=result.concept)

        if isinstance(result, GreetingResult):
            return ComposerAgentResult(**base)

        if isinstance(result, NotSupportedResult):
            return ComposerAgentResult(**base, reason=result.reason)

        return ComposerAgentResult(**base)


# Singleton for easy import
composer_agent = ComposerAgent()
