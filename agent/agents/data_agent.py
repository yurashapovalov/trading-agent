"""Data Agent - executes SQL queries to fetch trading data using Gemini function calling."""

import time
import pandas as pd
from google import genai
from google.genai import types

import config
from agent.base import BaseDataAgent
from agent.state import AgentState, SQLResult
from agent.tools import query_ohlcv, analyze_data
from data import get_data_info


# Define function declarations for Gemini function calling
QUERY_OHLCV_DECLARATION = types.FunctionDeclaration(
    name="query_ohlcv",
    description="Execute SQL query on OHLCV database. IMPORTANT: For period queries (week/month/year), MUST use GROUP BY date_trunc('day', timestamp) with aggregations. Never return raw 1-min bars for periods.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "sql": types.Schema(
                type=types.Type.STRING,
                description="SQL query. Table: ohlcv_1min (timestamp, symbol, open, high, low, close, volume). For period stats: SELECT date_trunc('day', timestamp) AS day, AVG(open), AVG(close), SUM(volume) ... GROUP BY day. Max LIMIT 1000."
            )
        },
        required=["sql"]
    )
)

ANALYZE_DATA_DECLARATION = types.FunctionDeclaration(
    name="analyze_data",
    description="Run standard analysis on trading data. Use for common analysis types.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "symbol": types.Schema(
                type=types.Type.STRING,
                description="Trading symbol (e.g., NQ, ES, CL)"
            ),
            "period": types.Schema(
                type=types.Type.STRING,
                description="Time period: today, yesterday, last_week, last_month, last_year, all",
                enum=["today", "yesterday", "last_week", "last_month", "last_year", "all"]
            ),
            "analysis": types.Schema(
                type=types.Type.STRING,
                description="Analysis type: summary, daily, anomalies, hourly, trend",
                enum=["summary", "daily", "anomalies", "hourly", "trend"]
            )
        },
        required=["symbol", "period", "analysis"]
    )
)

# Tool definition
DATA_TOOLS = types.Tool(
    function_declarations=[QUERY_OHLCV_DECLARATION, ANALYZE_DATA_DECLARATION]
)


class DataAgent(BaseDataAgent):
    """
    Fetches data from the database using SQL with Gemini function calling.

    This agent:
    1. Receives user question
    2. Uses Gemini function calling to decide which tool to use
    3. Executes the tool with proper parameters
    4. Returns raw data for the Analyst
    """

    name = "data_agent"
    agent_type = "data"
    min_sample_size = 5

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = "gemini-2.0-flash"
        self._last_usage = {}
        self._tool_calls = []  # Track tool calls for logging

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

    def _execute_tool(self, name: str, args: dict) -> tuple[any, str, int]:
        """Execute a tool and return (result, query_description, duration_ms)."""
        start_time = time.time()

        if name == "analyze_data":
            result = analyze_data(
                symbol=args.get("symbol", "NQ"),
                period=args.get("period", "last_month"),
                analysis=args.get("analysis", "summary")
            )
            query_desc = f"analyze_data(symbol='{args.get('symbol')}', period='{args.get('period')}', analysis='{args.get('analysis')}')"
        elif name == "query_ohlcv":
            sql = args.get("sql", "SELECT 1")
            result = query_ohlcv(sql)
            query_desc = sql
        else:
            result = {"error": f"Unknown tool: {name}"}
            query_desc = f"unknown_tool({name})"

        duration_ms = int((time.time() - start_time) * 1000)
        return result, query_desc, duration_ms

    def _result_to_sql_result(self, result: any, query: str, duration_ms: int) -> SQLResult:
        """Convert tool result to SQLResult format."""
        if isinstance(result, dict) and "error" in result:
            return SQLResult(
                query=query,
                rows=[],
                row_count=0,
                error=result["error"],
                duration_ms=duration_ms
            )
        elif isinstance(result, pd.DataFrame):
            rows = result.to_dict(orient='records')
            return SQLResult(
                query=query,
                rows=rows,
                row_count=len(rows),
                error=None,
                duration_ms=duration_ms
            )
        elif isinstance(result, list):
            return SQLResult(
                query=query,
                rows=result,
                row_count=len(result),
                error=None,
                duration_ms=duration_ms
            )
        elif isinstance(result, dict):
            return SQLResult(
                query=query,
                rows=[result],
                row_count=1,
                error=None,
                duration_ms=duration_ms
            )
        else:
            return SQLResult(
                query=query,
                rows=[{"result": str(result)}],
                row_count=1,
                error=None,
                duration_ms=duration_ms
            )

    def execute(self, state: AgentState) -> list[SQLResult]:
        """Generate and execute SQL queries using function calling."""
        question = state.get("question", "")
        data_info = self._get_data_info()
        self._tool_calls = []

        # System instruction for the model
        system = f"""You are a data agent for a trading analytics system.

Available data:
{data_info}

Your task: Analyze the user's question and call the appropriate function to get the data.

CRITICAL SQL RULES:
1. For period statistics (week, month, year), ALWAYS use GROUP BY with aggregations:
   - GROUP BY date_trunc('day', timestamp) for daily stats
   - Use AVG(open), AVG(high), AVG(low), AVG(close), SUM(volume)
   - Example: SELECT date_trunc('day', timestamp) AS day, AVG(open), AVG(close), SUM(volume) FROM ohlcv_1min WHERE symbol='NQ' AND timestamp >= '2025-03-01' AND timestamp < '2025-04-01' GROUP BY day ORDER BY day LIMIT 100

2. NEVER return raw 1-minute bars for period queries - always aggregate!

3. Only return raw bars for intraday queries (specific hours/minutes)

4. Always include LIMIT (max 1000 for aggregated, 100 for raw)

Table schema: ohlcv_1min (timestamp, symbol, open, high, low, close, volume)"""

        # Initial request with function calling
        response = self.client.models.generate_content(
            model=self.model,
            contents=f"User question: {question}",
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0,
                tools=[DATA_TOOLS],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode=types.FunctionCallingConfigMode.AUTO
                    )
                )
            )
        )

        # Track usage
        if response.usage_metadata:
            self._last_usage = {
                "input_tokens": response.usage_metadata.prompt_token_count or 0,
                "output_tokens": response.usage_metadata.candidates_token_count or 0,
            }

        results = []

        # Process function calls
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    func_call = part.function_call
                    tool_name = func_call.name
                    tool_args = dict(func_call.args) if func_call.args else {}

                    # Track tool call for logging
                    self._tool_calls.append({
                        "tool": tool_name,
                        "args": tool_args
                    })

                    # Execute the tool
                    result, query_desc, duration_ms = self._execute_tool(tool_name, tool_args)

                    # Convert to SQLResult
                    sql_result = self._result_to_sql_result(result, query_desc, duration_ms)
                    results.append(sql_result)

        # If no function calls, return empty result
        if not results:
            results.append(SQLResult(
                query="no_tool_called",
                rows=[],
                row_count=0,
                error="Model did not call any function",
                duration_ms=0
            ))

        return results

    def get_usage(self) -> dict:
        """Return usage from last execution."""
        return self._last_usage

    def get_tool_calls(self) -> list[dict]:
        """Return tool calls from last execution for logging."""
        return self._tool_calls
