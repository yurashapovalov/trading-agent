"""
SQL Agent - generates DuckDB SQL queries for search conditions.

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
    Generates SQL queries from natural language search conditions.

    Principle: LLM understands search condition and writes SQL.
    SQL Validator checks the SQL before execution.
    """

    name = "sql_agent"
    agent_type = "query"

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_LITE_MODEL  # Use cheaper model for SQL generation
        self._last_usage = UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def __call__(self, state: AgentState) -> dict:
        """Generate SQL query from search condition."""
        intent = state.get("intent") or {}
        search_condition = intent.get("search_condition")

        # No search condition - skip SQL Agent
        if not search_condition:
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

        # Build prompt
        prompt = get_sql_agent_prompt(
            symbol=symbol,
            period_start=period_start,
            period_end=period_end,
            search_condition=search_condition,
            previous_sql=previous_sql,
            error=error,
        )

        # Call LLM
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
            thinking_tokens = 0
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
