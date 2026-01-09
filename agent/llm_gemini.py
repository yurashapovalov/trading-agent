"""Google Gemini API integration with tool use"""

import json
import logging
from datetime import datetime
from google import genai
from google.genai import types
from typing import Any, Callable, Dict, List, Optional

import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeminiToolRegistry:
    """Registry for managing tools in Gemini format."""

    def __init__(self):
        self._tools: Dict[str, dict] = {}
        self._functions: Dict[str, Callable] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        function: Callable
    ) -> None:
        """Register a new tool."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters
        }
        self._functions[name] = function
        logger.info(f"Registered tool: {name}")

    def get_declarations(self) -> List[dict]:
        """Get all tool declarations for Gemini API."""
        return list(self._tools.values())

    def execute(self, name: str, args: dict) -> Any:
        """Execute a tool by name."""
        func = self._functions.get(name)
        if not func:
            error = f"Unknown tool: {name}"
            logger.error(error)
            return {"error": error}

        try:
            result = func(**args)
            if hasattr(result, 'to_dict'):
                result = result.to_dict('records')
            return result
        except Exception as e:
            error = str(e)
            logger.error(f"Tool {name} failed: {error}")
            return {"error": error}


# Global registry
GEMINI_REGISTRY = GeminiToolRegistry()


def register_gemini_tools():
    """Register all trading tools for Gemini."""
    from agent.tools import (
        query_ohlcv,
        find_optimal_entries,
        backtest_strategy,
        get_statistics,
        analyze_data,
        find_market_periods
    )

    # analyze_data - PRIMARY TOOL
    GEMINI_REGISTRY.register(
        name="analyze_data",
        description="""PRIMARY TOOL for analyzing trading data. Use this tool FIRST for any data analysis questions.

This tool automatically handles date calculations - you don't need to calculate dates yourself!

Parameters:
- symbol: Trading symbol (NQ)
- period: Time period in natural language: "today", "yesterday", "last_week", "last_month", "last_3_months", "last_year", "all", or "YYYY-MM-DD to YYYY-MM-DD"
- analysis: Type of analysis: "summary", "daily", "anomalies", "hourly", "trend"

IMPORTANT: Always use this tool instead of query_ohlcv for standard analysis.""",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol: NQ"
                },
                "period": {
                    "type": "string",
                    "description": "Time period: today, yesterday, last_week, last_month, last_3_months, last_year, all, or 'YYYY-MM-DD to YYYY-MM-DD'"
                },
                "analysis": {
                    "type": "string",
                    "enum": ["summary", "daily", "anomalies", "hourly", "trend"],
                    "description": "Type of analysis"
                }
            },
            "required": ["symbol"]
        },
        function=analyze_data
    )

    # backtest_strategy
    GEMINI_REGISTRY.register(
        name="backtest_strategy",
        description="""Backtest a specific trading strategy on historical data.

Tests entering at a fixed time each day with predetermined stop loss and take profit levels.
Returns win rate, total profit, maximum drawdown, and profit factor.""",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol: NQ"
                },
                "entry_hour": {
                    "type": "integer",
                    "description": "Hour to enter (0-23)"
                },
                "entry_minute": {
                    "type": "integer",
                    "description": "Minute to enter (0-59)"
                },
                "direction": {
                    "type": "string",
                    "enum": ["long", "short"],
                    "description": "Trade direction"
                },
                "stop_loss": {
                    "type": "number",
                    "description": "Stop loss in ticks"
                },
                "take_profit": {
                    "type": "number",
                    "description": "Take profit in ticks"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD)"
                }
            },
            "required": ["symbol", "entry_hour", "entry_minute", "direction", "stop_loss", "take_profit"]
        },
        function=backtest_strategy
    )

    # find_optimal_entries
    GEMINI_REGISTRY.register(
        name="find_optimal_entries",
        description="""Find optimal entry times for trading based on historical performance.

Scans through all data, simulates entries at each time slot, returns times that meet criteria.""",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol: NQ"
                },
                "direction": {
                    "type": "string",
                    "enum": ["long", "short", "both"],
                    "description": "Trade direction"
                },
                "risk_reward": {
                    "type": "number",
                    "description": "Target risk/reward ratio (e.g., 1.5 means TP = SL * 1.5)"
                },
                "max_stop_loss": {
                    "type": "number",
                    "description": "Maximum stop loss in ticks"
                },
                "min_winrate": {
                    "type": "number",
                    "description": "Minimum win rate percentage (0-100)"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD)"
                }
            },
            "required": ["symbol", "direction", "risk_reward", "max_stop_loss", "min_winrate"]
        },
        function=find_optimal_entries
    )

    # find_market_periods
    GEMINI_REGISTRY.register(
        name="find_market_periods",
        description="""Find periods in the market that match specific conditions.

Use to identify trending, volatile, or calm market phases.""",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol: NQ"
                },
                "condition": {
                    "type": "string",
                    "enum": ["uptrend", "downtrend", "sideways", "high_volatility", "low_volatility"],
                    "description": "Market condition to find"
                },
                "min_days": {
                    "type": "integer",
                    "description": "Minimum consecutive days (default: 5)"
                }
            },
            "required": ["symbol", "condition"]
        },
        function=find_market_periods
    )

    # get_statistics
    GEMINI_REGISTRY.register(
        name="get_statistics",
        description="""Get comprehensive statistics for a trading symbol.

Returns avg daily range, volatility by hour, trend stats.""",
        parameters={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol: NQ"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date (YYYY-MM-DD)"
                }
            },
            "required": ["symbol"]
        },
        function=get_statistics
    )

    # query_ohlcv - only for complex queries
    GEMINI_REGISTRY.register(
        name="query_ohlcv",
        description="""Execute SQL query against OHLCV data. ONLY use for complex custom queries.

Tables: ohlcv_1min (timestamp, symbol, open, high, low, close, volume)
Always include LIMIT clause.""",
        parameters={
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL query with LIMIT clause"
                }
            },
            "required": ["sql"]
        },
        function=query_ohlcv
    )


class GeminiAgent:
    """Trading analytics agent powered by Google Gemini."""

    def __init__(self, registry: Optional[GeminiToolRegistry] = None):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_MODEL
        self.registry = registry or GEMINI_REGISTRY
        self.contents: List[types.Content] = []

        # Register tools if registry is empty
        if not self.registry._tools:
            register_gemini_tools()

        self.system_instruction = self._build_system_instruction()

    def _build_system_instruction(self) -> str:
        """Build system instruction with dynamic data info."""
        from data import get_data_info
        from datetime import timedelta

        data_info = "No data loaded."
        symbols_list = []
        train_test_info = ""

        try:
            df = get_data_info()
            if not df.empty:
                data_lines = []
                train_test_lines = []
                for _, row in df.iterrows():
                    symbols_list.append(row['symbol'])
                    start = row['start_date']
                    end = row['end_date']
                    total_days = row['trading_days']

                    train_days = int(total_days * 0.8)
                    train_end = start + timedelta(days=int((end - start).days * 0.8))
                    test_start = train_end + timedelta(days=1)

                    data_lines.append(f"- {row['symbol']}: {row['bars']:,} bars, {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} ({total_days} days)")
                    train_test_lines.append(f"- {row['symbol']}: TRAIN {start.strftime('%Y-%m-%d')} to {train_end.strftime('%Y-%m-%d')} | TEST {test_start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")

                data_info = "\n".join(data_lines)
                train_test_info = "\n".join(train_test_lines)
        except:
            pass

        symbols_str = ", ".join(symbols_list) if symbols_list else "none"

        return f"""You are a trading data analyst. You help analyze historical futures data.

## Available Data
{data_info}

## Train/Test Split (80/20)
{train_test_info}

Available symbols: {symbols_str}
ONLY use symbols that are listed above.

## Tools (in order of preference)
1. analyze_data - PRIMARY for data analysis
2. find_market_periods - find periods by market condition
3. find_optimal_entries - find best entry times
4. backtest_strategy - test strategy with full stats
5. get_statistics - detailed market stats
6. query_ohlcv - ONLY for complex custom queries

## Rules
- Use train/test split when developing strategies
- Be concise, use markdown tables for results
- Respond in user's language (English/Russian)

## Follow-up Suggestions
At the END of EVERY response, add 2-3 relevant follow-up questions:
[SUGGESTIONS]
Question 1?
Question 2?
[/SUGGESTIONS]

Tick values: NQ=0.25 ($5), ES=0.25 ($12.50)"""

    def chat(self, user_message: str) -> dict:
        """Send message and get response, handling tool calls."""
        self.contents.append(
            types.Content(role="user", parts=[types.Part(text=user_message)])
        )

        tools_used = []
        tool_declarations = self.registry.get_declarations()

        while True:
            response = self.client.models.generate_content(
                model=self.model,
                contents=self.contents,
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    tools=[types.Tool(function_declarations=tool_declarations)]
                )
            )

            # Check for function calls
            if response.function_calls:
                # Add model response to contents
                self.contents.append(response.candidates[0].content)

                # Execute each function call
                function_responses = []
                for fc in response.function_calls:
                    start_time = datetime.now()
                    result = self.registry.execute(fc.name, dict(fc.args))
                    duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                    tools_used.append({
                        "name": fc.name,
                        "input": dict(fc.args),
                        "result": result,
                        "duration_ms": duration_ms
                    })

                    function_responses.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": result}
                        )
                    )

                # Add function responses
                self.contents.append(
                    types.Content(role="user", parts=function_responses)
                )
            else:
                # No more function calls, return text response
                text_response = response.text or ""
                self.contents.append(response.candidates[0].content)
                return {
                    "response": text_response,
                    "tools_used": tools_used
                }

    def chat_stream(self, user_message: str):
        """Stream chat response with tool events. True streaming with function call support."""
        self.contents.append(
            types.Content(role="user", parts=[types.Part(text=user_message)])
        )

        tool_declarations = self.registry.get_declarations()
        config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            tools=[types.Tool(function_declarations=tool_declarations)]
        )

        total_input_tokens = 0
        total_output_tokens = 0

        while True:
            full_text = ""
            model_content = None
            has_function_calls = False

            # Stream response
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=self.contents,
                config=config
            ):
                # Track usage
                if chunk.usage_metadata:
                    total_input_tokens = chunk.usage_metadata.prompt_token_count or 0
                    total_output_tokens = chunk.usage_metadata.candidates_token_count or 0

                # Check for function calls (comes in first chunk)
                if chunk.function_calls:
                    has_function_calls = True
                    # Save model content for history
                    if chunk.candidates:
                        model_content = chunk.candidates[0].content

                    # Execute function calls
                    function_responses = []
                    for fc in chunk.function_calls:
                        yield {
                            "type": "tool_start",
                            "name": fc.name,
                            "input": dict(fc.args)
                        }

                        start_time = datetime.now()
                        result = self.registry.execute(fc.name, dict(fc.args))
                        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                        yield {
                            "type": "tool_end",
                            "name": fc.name,
                            "input": dict(fc.args),
                            "result": result,
                            "duration_ms": duration_ms
                        }

                        function_responses.append(
                            types.Part.from_function_response(
                                name=fc.name,
                                response={"result": result}
                            )
                        )

                    # Add model response and function results to history
                    if model_content:
                        self.contents.append(model_content)
                    self.contents.append(
                        types.Content(role="user", parts=function_responses)
                    )
                    break  # Exit stream loop to continue with new request

                # Stream text
                if chunk.text:
                    yield {"type": "text_delta", "content": chunk.text}
                    full_text += chunk.text

            # If we had function calls, continue loop to get final response
            if has_function_calls:
                continue

            # No function calls - we're done
            if full_text:
                self.contents.append(
                    types.Content(role="model", parts=[types.Part(text=full_text)])
                )

            # Parse suggestions
            suggestions = self._parse_suggestions(full_text)
            if suggestions:
                yield {"type": "suggestions", "suggestions": suggestions}

            # Usage data - Gemini 3 Flash: $0.10/1M input, $0.40/1M output
            cost = (total_input_tokens * 0.10 + total_output_tokens * 0.40) / 1_000_000
            yield {
                "type": "usage",
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cost": cost
            }

            yield {"type": "done"}
            return

    def _parse_suggestions(self, text: str) -> list[str]:
        """Parse [SUGGESTIONS]...[/SUGGESTIONS] block from response."""
        import re
        pattern = r'\[SUGGESTIONS\]\s*(.*?)\s*\[/SUGGESTIONS\]'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            suggestions_text = match.group(1).strip()
            suggestions = [s.strip() for s in suggestions_text.split('\n') if s.strip()]
            return suggestions[:4]
        return []

    def reset(self):
        """Reset conversation history."""
        self.contents = []
