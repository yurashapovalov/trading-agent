"""
DataFetcher agent - fetches data based on Intent.

No LLM here. Pure Python routing to modules.
Understander (LLM) decides WHAT, DataFetcher (code) executes HOW.
"""

import time
from typing import Any

from agent.state import AgentState, Intent
from agent.modules import sql, patterns


class DataFetcher:
    """
    Fetches data based on structured Intent.

    Routes to appropriate module:
    - type="data" → sql.fetch()
    - type="pattern" → patterns.search()
    - type="concept" → no data needed
    - type="strategy" → backtest module (future)
    """

    name = "data_fetcher"
    agent_type = "data"

    def __call__(self, state: AgentState) -> dict:
        """Fetch data based on intent."""
        start_time = time.time()

        intent = state.get("intent")
        if not intent:
            return {
                "data": {},
                "error": "No intent provided",
                "agents_used": [self.name],
            }

        intent_type = intent.get("type", "data")

        # Route to appropriate handler
        if intent_type == "concept":
            data = self._handle_concept(intent)
        elif intent_type == "pattern":
            data = self._handle_pattern(intent)
        elif intent_type == "strategy":
            data = self._handle_strategy(intent)
        else:  # "data" or default
            data = self._handle_data(intent)

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "data": data,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
            "total_duration_ms": state.get("total_duration_ms", 0) + duration_ms,
        }

    def _handle_data(self, intent: Intent) -> dict[str, Any]:
        """Handle type=data: fetch with granularity."""
        symbol = intent.get("symbol", "NQ")
        period_start = intent.get("period_start")
        period_end = intent.get("period_end")
        granularity = intent.get("granularity", "daily")

        if not period_start or not period_end:
            return {"error": "Missing period_start or period_end"}

        return sql.fetch(
            symbol=symbol,
            period_start=period_start,
            period_end=period_end,
            granularity=granularity,
        )

    def _handle_pattern(self, intent: Intent) -> dict[str, Any]:
        """Handle type=pattern: search for patterns."""
        symbol = intent.get("symbol", "NQ")
        period_start = intent.get("period_start")
        period_end = intent.get("period_end")
        pattern = intent.get("pattern", {})

        if not period_start or not period_end:
            return {"error": "Missing period_start or period_end"}

        pattern_name = pattern.get("name", "")
        pattern_params = pattern.get("params", {})

        if not pattern_name:
            return {"error": "Missing pattern name"}

        return patterns.search(
            symbol=symbol,
            period_start=period_start,
            period_end=period_end,
            pattern_name=pattern_name,
            params=pattern_params,
        )

    def _handle_concept(self, intent: Intent) -> dict[str, Any]:
        """Handle type=concept: no data needed."""
        return {
            "type": "concept",
            "concept": intent.get("concept", ""),
            "message": "No data needed for concept explanation",
        }

    def _handle_strategy(self, intent: Intent) -> dict[str, Any]:
        """Handle type=strategy: backtest (future)."""
        # TODO: Implement when backtest module is ready
        return {
            "type": "strategy",
            "error": "Backtesting not implemented yet",
            "missing_capabilities": ["backtest"],
        }
