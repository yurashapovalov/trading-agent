"""Data Agent - executes SQL queries to fetch trading data."""

import time
from google import genai
from google.genai import types

import config
from agent.base import BaseDataAgent
from agent.state import AgentState, SQLResult
from agent.prompts import get_prompt
from agent.tools import query_ohlcv, analyze_data
from data import get_data_info


class DataAgent(BaseDataAgent):
    """
    Fetches data from the database using SQL.

    This agent:
    1. Understands the question
    2. Writes appropriate SQL queries
    3. Executes them using existing tools
    4. Returns raw data for the Analyst
    """

    name = "data_agent"
    agent_type = "data"
    min_sample_size = 5

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = "gemini-2.0-flash"
        self._last_usage = {}

    def _get_data_info(self) -> str:
        """Get available data description."""
        try:
            df = get_data_info()
            if df.empty:
                return "No data available."

            lines = []
            for _, row in df.iterrows():
                lines.append(
                    f"- {row['symbol']}: {row['bars']:,} bars, "
                    f"{row['start_date'].strftime('%Y-%m-%d')} to "
                    f"{row['end_date'].strftime('%Y-%m-%d')}"
                )
            return "\n".join(lines)
        except Exception:
            return "Data info unavailable."

    def execute(self, state: AgentState) -> list[SQLResult]:
        """Generate and execute SQL queries."""
        question = state.get("question", "")
        data_info = self._get_data_info()

        prompt = get_prompt("data_agent", question=question, data_info=data_info)

        # Ask LLM to decide which tool to use and with what parameters
        system = """You are a data agent. Analyze the question and decide how to get the data.

You have these tools:
1. analyze_data(symbol, period, analysis) - for standard analysis
   - period: "today", "yesterday", "last_week", "last_month", "last_year", "all"
   - analysis: "summary", "daily", "anomalies", "hourly", "trend"

2. query_ohlcv(sql) - for custom SQL queries
   - Table: ohlcv_1min (timestamp, symbol, open, high, low, close, volume)
   - Always use LIMIT

Respond with JSON:
{
  "tool": "analyze_data" or "query_ohlcv",
  "params": { ... }
}

Only respond with valid JSON."""

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0,
                max_output_tokens=500,
            )
        )

        # Track usage
        if response.usage_metadata:
            self._last_usage = {
                "input_tokens": response.usage_metadata.prompt_token_count or 0,
                "output_tokens": response.usage_metadata.candidates_token_count or 0,
            }

        # Parse response and execute tool
        results = []
        try:
            import json
            text = response.text.strip()
            # Remove markdown code blocks if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            decision = json.loads(text)
            tool_name = decision.get("tool", "analyze_data")
            params = decision.get("params", {})

            start_time = time.time()

            if tool_name == "analyze_data":
                result = analyze_data(
                    symbol=params.get("symbol", "NQ"),
                    period=params.get("period", "last_month"),
                    analysis=params.get("analysis", "summary")
                )
                sql_query = f"analyze_data({params})"
            else:
                sql = params.get("sql", "SELECT 1")
                result = query_ohlcv(sql)
                sql_query = sql

            duration_ms = int((time.time() - start_time) * 1000)

            # Convert result to SQLResult format
            if isinstance(result, dict) and "error" in result:
                results.append(SQLResult(
                    query=sql_query,
                    rows=[],
                    row_count=0,
                    error=result["error"],
                    duration_ms=duration_ms
                ))
            elif isinstance(result, list):
                results.append(SQLResult(
                    query=sql_query,
                    rows=result,
                    row_count=len(result),
                    error=None,
                    duration_ms=duration_ms
                ))
            elif isinstance(result, dict):
                # Single dict result (like from analyze_data)
                results.append(SQLResult(
                    query=sql_query,
                    rows=[result],
                    row_count=1,
                    error=None,
                    duration_ms=duration_ms
                ))
            else:
                results.append(SQLResult(
                    query=sql_query,
                    rows=[{"result": str(result)}],
                    row_count=1,
                    error=None,
                    duration_ms=duration_ms
                ))

        except Exception as e:
            results.append(SQLResult(
                query="failed_to_parse",
                rows=[],
                row_count=0,
                error=str(e),
                duration_ms=0
            ))

        return results

    def get_usage(self) -> dict:
        """Return usage from last execution."""
        return self._last_usage
