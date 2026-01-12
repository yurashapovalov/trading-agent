"""
DataFetcher agent - fetches data based on Intent.

No LLM here. Pure Python routing to modules.
Central hub: executes validated SQL from SQL Agent or uses templates.
"""

import time
import duckdb
from typing import Any

import config
from agent.state import AgentState, Intent
from agent.modules import sql


class DataFetcher:
    """
    Fetches data based on structured Intent.

    Routes:
    - sql_validation.status == "ok" + sql_query → execute SQL from SQL Agent
    - type="concept" → no data needed
    - else → use standard templates from sql.py
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

        # Check for validated SQL from SQL Agent
        sql_validation = state.get("sql_validation") or {}
        sql_query = state.get("sql_query")

        # Route to appropriate handler
        if sql_validation.get("status") == "ok" and sql_query:
            # Execute validated SQL from SQL Agent
            data = self._execute_sql(sql_query)
        elif intent_type == "concept":
            data = self._handle_concept(intent)
        else:  # "data" or default - use templates
            data = self._handle_data(intent)

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "data": data,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
            "total_duration_ms": state.get("total_duration_ms", 0) + duration_ms,
        }

    def _execute_sql(self, sql_query: str) -> dict[str, Any]:
        """Execute validated SQL from SQL Agent."""
        try:
            with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
                df = conn.execute(sql_query).df()
                rows = df.to_dict(orient='records')

                # Convert numpy types to Python types
                rows = sql._convert_numpy_types(rows)

                return {
                    "rows": rows,
                    "row_count": len(rows),
                    "granularity": "daily",
                    "sql_query": sql_query,
                    "source": "sql_agent",
                }
        except Exception as e:
            return {
                "error": str(e),
                "sql_query": sql_query,
                "rows": [],
                "row_count": 0,
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

    def _handle_concept(self, intent: Intent) -> dict[str, Any]:
        """Handle type=concept: no data needed."""
        return {
            "type": "concept",
            "concept": intent.get("concept", ""),
            "message": "No data needed for concept explanation",
        }
