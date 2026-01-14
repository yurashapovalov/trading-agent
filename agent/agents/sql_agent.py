"""
SQL Agent v2 - generates DuckDB SQL from detailed specifications.

Receives detailed_spec from Understander with:
- Task description
- Analysis type (FILTER, EVENT, DISTRIBUTION, etc.)
- Step-by-step logic
- SQL hints

Returns:
- sql_query: Generated SQL query for DataFetcher to execute
"""

from google import genai
from google.genai import types

import config
from agent.state import AgentState, UsageStats
from agent.prompts.sql_agent import get_sql_agent_prompt
from agent.pricing import calculate_cost


class SQLAgent:
    """
    Generates SQL queries from detailed specifications.

    Receives detailed_spec from Understander and writes precise SQL.
    SQL Validator checks the SQL before execution.
    """

    name = "sql_agent"
    agent_type = "query"

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_MODEL  # Use same model as Analyst for better reasoning
        self._last_usage = UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def __call__(self, state: AgentState) -> dict:
        """Generate SQL query from detailed_spec or search_condition."""
        intent = state.get("intent") or {}

        # Prefer detailed_spec, fallback to search_condition for backwards compatibility
        detailed_spec = intent.get("detailed_spec")
        search_condition = intent.get("search_condition")

        # No spec - skip SQL Agent
        if not detailed_spec and not search_condition:
            return {
                "sql_query": None,
                "usage": self._last_usage,
                "agents_used": [],
                "step_number": state.get("step_number", 0),
            }

        # Get parameters from intent
        symbol = intent.get("symbol", "NQ")
        period_start = intent.get("period_start", "2008-01-01")
        period_end = intent.get("period_end", "2026-01-01")

        # Check if rewriting after validation error
        validation = state.get("sql_validation") or {}
        previous_sql = None
        error = None
        if validation.get("status") == "rewrite":
            previous_sql = state.get("sql_query")
            error = validation.get("feedback")

        # Build prompt - use detailed_spec if available
        prompt = get_sql_agent_prompt(
            symbol=symbol,
            period_start=period_start,
            period_end=period_end,
            detailed_spec=detailed_spec,
            search_condition=search_condition,  # Fallback
            previous_sql=previous_sql,
            error=error,
        )

        # Call LLM - no thinking needed, detailed_spec provides SQL hints
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for precise SQL
                )
            )

            # Track usage
            self._track_usage(response)

            # Extract SQL from response
            sql_query = self._extract_sql(response.text)

        except Exception as e:
            sql_query = None
            print(f"SQL Agent error: {e}")

        return {
            "sql_query": sql_query,
            "usage": self._last_usage,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
        }

    def _extract_sql(self, text: str) -> str:
        """Extract SQL from response, removing any markdown formatting."""
        sql = text.strip()

        # Remove markdown code blocks if present
        if sql.startswith("```sql"):
            sql = sql[6:]
        elif sql.startswith("```"):
            sql = sql[3:]

        if sql.endswith("```"):
            sql = sql[:-3]

        return sql.strip()

    def _track_usage(self, response) -> None:
        """Track token usage from response."""
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0
            thinking_tokens = getattr(response.usage_metadata, 'thoughts_token_count', 0) or 0
            cost = calculate_cost(input_tokens, output_tokens, thinking_tokens)

            self._last_usage = UsageStats(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                cost_usd=cost
            )

    def get_usage(self) -> UsageStats:
        """Return usage from last generation."""
        return self._last_usage
