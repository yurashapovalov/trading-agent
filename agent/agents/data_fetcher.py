"""DataFetcher agent - executes SQL and fetches data from DuckDB.

Pure Python agent (no LLM). Executes SQL from QueryBuilder or falls back
to template queries for simple requests.

Architecture:
    QueryBuilder → SQL → DataFetcher → rows → Analyst

Example:
    fetcher = DataFetcher()
    result = fetcher({"sql_query": "SELECT ...", "intent": {...}})
    # result["data"]["rows"] contains query results
"""

import time
import duckdb
from typing import Any

import config
from agent.state import AgentState, Intent
from agent.modules import sql


class DataFetcher:
    """Fetches trading data based on Intent from Understander.

    Pure Python agent (no LLM). Routes to appropriate data source:
    - sql_query exists: Execute SQL from QueryBuilder
    - type="concept": No data needed
    - else: Use template queries from sql.py

    Attributes:
        name: Agent name for logging.
        agent_type: Agent type ("data" - fetches data).
    """

    name = "data_fetcher"
    agent_type = "data"

    def __call__(self, state: AgentState) -> dict:
        """Fetch data based on intent.

        Args:
            state: Agent state with sql_query, intent, and sql_validation.

        Returns:
            Dict with data (rows, row_count, granularity), agents_used.
        """
        start_time = time.time()

        intent = state.get("intent")
        if not intent:
            return {
                "data": {},
                "error": "No intent provided",
                "agents_used": [self.name],
            }

        intent_type = intent.get("type", "data")

        # Check for SQL query (from QueryBuilder or SQL Agent)
        sql_validation = state.get("sql_validation") or {}
        sql_query = state.get("sql_query")

        # Route to appropriate handler
        # 1. SQL from QueryBuilder (no validation needed - deterministically valid)
        # 2. SQL from SQL Agent (needs sql_validation.status == "ok")
        # 3. Concept - no data needed
        # 4. Fallback - use templates
        if sql_query and (sql_validation.get("status") == "ok" or not sql_validation):
            # Execute SQL (from QueryBuilder or validated SQL Agent)
            data = self._execute_sql(sql_query, intent)
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

    def _execute_sql(self, sql_query: str, intent: Intent = None) -> dict[str, Any]:
        """Execute SQL query in DuckDB.

        Args:
            sql_query: SQL query string from QueryBuilder.
            intent: Optional intent to determine granularity from query_spec.

        Returns:
            Dict with rows, row_count, granularity, columns, sql_query, source.
        """
        try:
            with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
                df = conn.execute(sql_query).df()
                rows = df.to_dict(orient='records')

                # Convert numpy types to Python types
                rows = sql._convert_numpy_types(rows)

                # Determine granularity from query_spec or default
                granularity = "daily"
                source = "query_builder"

                if intent:
                    query_spec = intent.get("query_spec", {})
                    if query_spec:
                        source = "query_builder"
                        # Map source to granularity
                        spec_source = query_spec.get("source", "daily")
                        if spec_source == "minutes":
                            granularity = "minute"
                        elif spec_source in ("daily", "daily_with_prev"):
                            granularity = "daily"

                        # Special ops have their own granularity
                        special_op = query_spec.get("special_op", "none")
                        if special_op == "event_time":
                            granularity = "distribution"

                return {
                    "rows": rows,
                    "row_count": len(rows),
                    "granularity": granularity,
                    "columns": list(df.columns) if len(df) > 0 else [],
                    "sql_query": sql_query,
                    "source": source,
                }
        except Exception as e:
            return {
                "error": str(e),
                "sql_query": sql_query,
                "rows": [],
                "row_count": 0,
            }

    def _handle_data(self, intent: Intent) -> dict[str, Any]:
        """Handle type=data using template queries from sql.py."""
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
        """Handle type=concept - no data needed for concept explanations."""
        return {
            "type": "concept",
            "concept": intent.get("concept", ""),
            "message": "No data needed for concept explanation",
        }
