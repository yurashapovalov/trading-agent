"""Claude API integration with tool use"""

import json
import logging
from datetime import datetime
from anthropic import Anthropic
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Tool definition with function and schema."""
    name: str
    description: str
    input_schema: dict
    function: Callable


@dataclass
class ToolCall:
    """Record of a tool call for logging."""
    timestamp: str
    tool_name: str
    inputs: dict
    result: Any
    duration_ms: float
    error: Optional[str] = None


class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._call_history: List[ToolCall] = []

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict,
        function: Callable
    ) -> None:
        """Register a new tool."""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            function=function
        )
        logger.info(f"Registered tool: {name}")

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get tool by name."""
        return self._tools.get(name)

    def get_all_definitions(self) -> List[dict]:
        """Get all tool definitions for Claude API."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, inputs: dict) -> Any:
        """Execute a tool and log the call."""
        tool = self._tools.get(name)
        if not tool:
            error = f"Unknown tool: {name}"
            logger.error(error)
            return {"error": error}

        start_time = datetime.now()
        error = None
        result = None

        try:
            result = tool.function(**inputs)
            # Convert DataFrame to dict for JSON serialization
            if hasattr(result, 'to_dict'):
                result = result.to_dict('records')
        except Exception as e:
            error = str(e)
            result = {"error": error}
            logger.error(f"Tool {name} failed: {error}")

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Log the call
        call_record = ToolCall(
            timestamp=start_time.isoformat(),
            tool_name=name,
            inputs=inputs,
            result=result,
            duration_ms=duration_ms,
            error=error
        )
        self._call_history.append(call_record)

        logger.info(
            f"Tool call: {name} | "
            f"Duration: {duration_ms:.1f}ms | "
            f"Error: {error or 'None'}"
        )

        return result

    def get_call_history(self) -> List[ToolCall]:
        """Get history of all tool calls."""
        return self._call_history.copy()

    def clear_history(self) -> None:
        """Clear call history."""
        self._call_history = []


# Global tool registry
REGISTRY = ToolRegistry()


def register_default_tools():
    """Register all default trading tools."""
    from agent.tools import (
        query_ohlcv,
        find_optimal_entries,
        backtest_strategy,
        get_statistics,
        analyze_data,
        find_market_periods
    )

    # query_ohlcv
    REGISTRY.register(
        name="query_ohlcv",
        description="""Execute a SQL query against the OHLCV (Open, High, Low, Close, Volume) historical data.

This tool allows you to run custom SQL queries to analyze trading data. Use it when you need
to perform custom analysis that isn't covered by other specialized tools, such as finding
specific price patterns, calculating custom indicators, or filtering data by complex conditions.

Available tables:
- ohlcv_1min: Contains minute-by-minute price data with columns: timestamp (DATETIME),
  symbol (VARCHAR), open (DOUBLE), high (DOUBLE), low (DOUBLE), close (DOUBLE), volume (INTEGER)
- symbols: Reference table with columns: symbol, name, tick_size, tick_value, exchange

The database is DuckDB, so you can use DuckDB-specific SQL syntax including window functions,
aggregations, and date/time functions. Always include a LIMIT clause to avoid returning too much data.

Example queries:
- "SELECT * FROM ohlcv_1min WHERE symbol = 'CL' AND timestamp >= '2025-12-01' LIMIT 100"
- "SELECT DATE(timestamp) as date, MAX(high) - MIN(low) as range FROM ohlcv_1min GROUP BY date"
""",
        input_schema={
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SQL query to execute. Must be a valid DuckDB SQL query. Always include LIMIT to avoid large result sets."
                }
            },
            "required": ["sql"]
        },
        function=query_ohlcv
    )

    # find_optimal_entries
    REGISTRY.register(
        name="find_optimal_entries",
        description="""Find optimal entry times for trading based on historical performance criteria.

This tool analyzes historical data to find the best times of day to enter trades with specified
risk/reward parameters. It scans through all available data, simulates entries at each time slot,
and returns the times that meet your criteria for stop loss, take profit, and win rate.

Use this tool when the user asks questions like:
- "When is the best time to enter a short position on CL?"
- "Find entry times with at least 70% win rate"
- "What times have good risk/reward for long trades?"

The tool returns a table with columns: hour, minute, direction, stop_loss, winrate, avg_profit, total_trades.
Results are sorted by win rate descending. Only times with sufficient sample size (at least 5 trades) are included.

Important: The tool tests entries at each minute within the specified hour range. For CL (Crude Oil),
the most volatile and tradeable hours are typically 9:00-11:00 and 13:00-14:30 ET.
""",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol to analyze. Currently supported: 'CL' (Crude Oil), 'NQ' (Nasdaq), 'ES' (S&P 500)"
                },
                "direction": {
                    "type": "string",
                    "enum": ["long", "short", "both"],
                    "description": "Trade direction to analyze: 'long' for buy entries, 'short' for sell entries, 'both' to analyze both directions"
                },
                "risk_reward": {
                    "type": "number",
                    "description": "Target risk/reward ratio. For example, 1.5 means take_profit = stop_loss * 1.5. Common values: 1.0 (1:1), 1.5 (1:1.5), 2.0 (1:2)"
                },
                "max_stop_loss": {
                    "type": "number",
                    "description": "Maximum stop loss in ticks. For CL: 1 tick = $0.01 = $10. Typical range: 10-30 ticks"
                },
                "min_winrate": {
                    "type": "number",
                    "description": "Minimum win rate percentage (0-100). Results below this threshold are filtered out. Typical: 50-70%"
                },
                "start_hour": {
                    "type": "integer",
                    "description": "Start of hour range to analyze (0-23, in exchange timezone). Default: 0",
                    "default": 0
                },
                "end_hour": {
                    "type": "integer",
                    "description": "End of hour range to analyze (0-23, in exchange timezone). Default: 23",
                    "default": 23
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date for analysis (YYYY-MM-DD). Use this to limit data to training period."
                },
                "end_date": {
                    "type": "string",
                    "description": "End date for analysis (YYYY-MM-DD). Use this to limit data to training period."
                }
            },
            "required": ["symbol", "direction", "risk_reward", "max_stop_loss", "min_winrate"]
        },
        function=find_optimal_entries
    )

    # backtest_strategy
    REGISTRY.register(
        name="backtest_strategy",
        description="""Backtest a specific trading strategy on historical data.

This tool simulates trading a specific strategy: entering at a fixed time each day with
predetermined stop loss and take profit levels. It calculates comprehensive statistics
including win rate, total profit, maximum drawdown, and profit factor.

Use this tool when the user wants to:
- Test a specific entry time and stop/take profit combination
- Validate findings from find_optimal_entries
- Compare different stop loss and take profit levels
- Get detailed trade-by-trade results

The strategy logic:
1. Each trading day, enter a position at the specified time (hour:minute)
2. Set stop loss and take profit based on the entry price
3. Exit when either stop or target is hit, or at end of session
4. Track all trades and calculate statistics

Returns a detailed report with:
- total_trades: Number of trades executed
- wins/losses: Count of winning and losing trades
- winrate: Percentage of winning trades
- total_profit: Net profit in ticks (multiply by tick_value for dollar amount)
- max_drawdown: Largest peak-to-trough decline in ticks
- profit_factor: Gross profit / Gross loss (>1 is profitable)
- trades: List of individual trades with entry/exit details
""",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol: 'CL' (Crude Oil, tick=$10), 'NQ' (Nasdaq, tick=$5), 'ES' (S&P 500, tick=$12.50)"
                },
                "entry_hour": {
                    "type": "integer",
                    "description": "Hour to enter the trade (0-23 in exchange timezone). For example, 9 for 9:00 AM"
                },
                "entry_minute": {
                    "type": "integer",
                    "description": "Minute to enter the trade (0-59). For example, 30 for half past the hour"
                },
                "direction": {
                    "type": "string",
                    "enum": ["long", "short"],
                    "description": "'long' to buy (profit when price goes up), 'short' to sell (profit when price goes down)"
                },
                "stop_loss": {
                    "type": "number",
                    "description": "Stop loss distance in ticks from entry price. For CL: 20 ticks = $0.20 = $200 risk per contract"
                },
                "take_profit": {
                    "type": "number",
                    "description": "Take profit distance in ticks from entry price. For CL: 30 ticks = $0.30 = $300 target per contract"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date for backtest (YYYY-MM-DD). Use to test on specific period."
                },
                "end_date": {
                    "type": "string",
                    "description": "End date for backtest (YYYY-MM-DD). Use to test on specific period."
                }
            },
            "required": ["symbol", "entry_hour", "entry_minute", "direction", "stop_loss", "take_profit"]
        },
        function=backtest_strategy
    )

    # get_statistics
    REGISTRY.register(
        name="get_statistics",
        description="""Get comprehensive statistics for a trading symbol.

This tool calculates various market statistics to help understand the behavior of an instrument.
Use it to analyze volatility patterns, volume distribution, and price ranges before developing
trading strategies.

Use this tool when the user asks:
- "What's the average daily range for CL?"
- "Show me volatility by hour"
- "What's the typical volume distribution?"
- "Give me an overview of the market data"

Returns a dictionary with:
- avg_daily_range: Average high-low range per day in ticks
- avg_volume: Average volume per bar
- volatility_by_hour: Breakdown of average range for each hour of the day (helps identify
  the most active trading hours)
- trend_stats: Statistics about directional moves (up days vs down days, average move size)
- data_summary: Date range, total bars, trading days covered

The volatility_by_hour data is particularly useful for identifying:
- Best times to trade (high volatility = more opportunity)
- Times to avoid (low volatility = choppy, hard to trade)
- Session opens/closes that show increased activity
""",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol to analyze: 'CL', 'NQ', 'ES'"
                },
                "group_by": {
                    "type": "string",
                    "enum": ["hour", "day", "week", "month"],
                    "description": "Time period for grouping statistics. 'hour' shows intraday patterns, 'day' shows daily stats, etc.",
                    "default": "hour"
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date filter (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date filter (YYYY-MM-DD)"
                }
            },
            "required": ["symbol"]
        },
        function=get_statistics
    )

    # analyze_data - PRIMARY TOOL for data analysis
    REGISTRY.register(
        name="analyze_data",
        description="""PRIMARY TOOL for analyzing trading data. Use this tool FIRST for any data analysis questions.

This tool automatically handles date calculations - you don't need to calculate dates yourself!

Parameters:
- symbol: Trading symbol (NQ, ES, CL)
- period: Time period in natural language:
  - "today", "yesterday" - single day
  - "last_week", "last_month", "last_3_months", "last_year" - relative periods
  - "all" - entire available data range
  - "2025-01-01 to 2025-01-31" - exact date range
  - "30" or "30d" - last N days
- analysis: Type of analysis to perform:
  - "summary" - key statistics overview
  - "daily" - day-by-day breakdown with OHLCV
  - "anomalies" - find unusual days (high volatility/volume)
  - "hourly" - volatility pattern by hour
  - "trend" - price trend and momentum

The tool returns:
- actual_range: The actual dates used (resolved from your period)
- Relevant analysis data based on analysis type

IMPORTANT: Always use this tool instead of query_ohlcv for standard analysis.
The tool automatically determines correct dates based on available data.

Example uses:
- User asks "what happened last month?" → analyze_data(symbol="NQ", period="last_month", analysis="summary")
- User asks "any anomalies recently?" → analyze_data(symbol="NQ", period="last_month", analysis="anomalies")
- User asks "daily breakdown" → analyze_data(symbol="NQ", period="last_week", analysis="daily")
""",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol: NQ, ES, CL"
                },
                "period": {
                    "type": "string",
                    "description": "Time period: today, yesterday, last_week, last_month, last_3_months, last_year, all, or 'YYYY-MM-DD to YYYY-MM-DD'",
                    "default": "last_month"
                },
                "analysis": {
                    "type": "string",
                    "enum": ["summary", "daily", "anomalies", "hourly", "trend"],
                    "description": "Type of analysis: summary, daily, anomalies, hourly, trend",
                    "default": "summary"
                },
                "group_by": {
                    "type": "string",
                    "enum": ["hour", "day", "week"],
                    "description": "Grouping for breakdown analysis",
                    "default": "day"
                }
            },
            "required": ["symbol"]
        },
        function=analyze_data
    )

    # find_market_periods - Find market periods by condition
    REGISTRY.register(
        name="find_market_periods",
        description="""Find periods in the market that match specific conditions (trend, volatility, etc.).

Use this tool when:
- User asks to find trending periods ("find uptrend periods")
- User wants to build strategies for specific market conditions
- Need to identify volatile or calm market phases

Available conditions:
- "uptrend": Consecutive days where price closes higher than opens
- "downtrend": Consecutive days where price closes lower than opens
- "sideways": Days with minimal directional movement (<0.3% change)
- "high_volatility": Days with above-average daily ranges
- "low_volatility": Days with below-average daily ranges

Returns list of periods with:
- start_date, end_date: Period boundaries
- days: Number of consecutive days
- metrics: price_change, price_change_pct, avg_daily_range, total_volume

Use these periods as date ranges for find_optimal_entries or backtest_strategy
to build strategies specific to market conditions.
""",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Trading symbol: NQ, ES, CL"
                },
                "condition": {
                    "type": "string",
                    "enum": ["uptrend", "downtrend", "sideways", "high_volatility", "low_volatility"],
                    "description": "Market condition to find"
                },
                "min_days": {
                    "type": "integer",
                    "description": "Minimum consecutive days for a period (default: 5)",
                    "default": 5
                }
            },
            "required": ["symbol", "condition"]
        },
        function=find_market_periods
    )


class TradingAgent:
    """Trading analytics agent powered by Claude."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.model = config.MODEL_NAME
        self.messages: List[dict] = []
        self.registry = registry or REGISTRY

        # Register default tools if registry is empty
        if not self.registry._tools:
            register_default_tools()

        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build system prompt with dynamic data info and train/test periods."""
        from data import get_data_info
        from datetime import timedelta

        # Get loaded data info
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

                    # Calculate 80/20 split
                    train_days = int(total_days * 0.8)
                    train_end = start + timedelta(days=int((end - start).days * 0.8))
                    test_start = train_end + timedelta(days=1)

                    data_lines.append(f"- {row['symbol']}: {row['bars']:,} bars, {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} ({total_days} days)")
                    train_test_lines.append(f"- {row['symbol']}: TRAIN {start.strftime('%Y-%m-%d')} to {train_end.strftime('%Y-%m-%d')} (~{train_days} days) | TEST {test_start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')} (~{total_days - train_days} days)")

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
ONLY use symbols that are listed above. Do not mention or suggest symbols without data.

## Strategy Development Workflow

When building trading strategies, follow this process:

1. **Find patterns on TRAIN data** - use start_date/end_date to limit to training period
   - find_optimal_entries with start_date/end_date from TRAIN period
   - Identify promising entry times and parameters

2. **Validate on TEST data** - backtest on unseen data
   - backtest_strategy with start_date/end_date from TEST period
   - Compare metrics to training results (watch for overfitting)

3. **Final validation on ALL data** - if test results are good
   - backtest_strategy without date filters to see full picture

## Market Condition Analysis

Use find_market_periods to find specific market conditions:
- "uptrend" - rising market periods
- "downtrend" - falling market periods
- "high_volatility" - volatile periods
- "low_volatility" - calm periods

Then use those periods as start_date/end_date for other tools.
Example: User asks "build strategy for rising market" →
1. find_market_periods(symbol, "uptrend") → get periods
2. find_optimal_entries with those date ranges

## Tools (in order of preference)

1. **analyze_data** - PRIMARY for data analysis
   - Automatically handles date calculations
   - period: "last_month", "last_week", "yesterday", "today", "all"
   - analysis: "summary", "daily", "anomalies", "hourly", "trend"

2. **find_market_periods** - find periods by market condition
   - Use to identify trending, volatile, or calm periods
   - Returns date ranges you can use in other tools

3. **find_optimal_entries** - find best entry times
   - Use start_date/end_date for train/test separation
   - Always specify date range for reproducible results

4. **backtest_strategy** - test strategy with full stats
   - Use start_date/end_date for train/test separation
   - Compare train vs test results to detect overfitting

5. **get_statistics** - detailed market stats
6. **query_ohlcv** - ONLY for complex custom queries

## Important Rules
- Use train/test split when developing strategies
- Be concise, use markdown tables for results
- Respond in user's language (English/Russian)
- Always mention which period (train/test) you're analyzing

## Follow-up Suggestions
At the END of EVERY response, add 2-3 relevant follow-up questions the user might want to ask.
Format them EXACTLY like this (on separate lines at the very end):
[SUGGESTIONS]
Вопрос 1?
Вопрос 2?
Вопрос 3?
[/SUGGESTIONS]

These should be contextual to what was just discussed, not generic.

Tick values: NQ=0.25 ($5), ES=0.25 ($12.50), CL=0.01 ($10)"""

    def chat(self, user_message: str) -> dict:
        """Send message and get response, handling tool calls.

        Returns:
            dict with 'response' (str) and 'tools_used' (list)
        """
        self.messages.append({
            "role": "user",
            "content": user_message
        })

        tools_used = []

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                tools=self.registry.get_all_definitions(),
                messages=self.messages
            )

            # Collect assistant response
            assistant_content = []
            text_response = ""
            tool_uses = []

            for block in response.content:
                if block.type == "text":
                    text_response += block.text
                    assistant_content.append(block)
                elif block.type == "tool_use":
                    tool_uses.append(block)
                    assistant_content.append(block)

            self.messages.append({
                "role": "assistant",
                "content": assistant_content
            })

            # If no tool calls, we're done
            if not tool_uses:
                return {
                    "response": text_response,
                    "tools_used": tools_used
                }

            # Execute tools and add results
            tool_results = []
            for tool_use in tool_uses:
                start_time = datetime.now()
                result = self.registry.execute(tool_use.name, tool_use.input)
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                tools_used.append({
                    "name": tool_use.name,
                    "input": tool_use.input,
                    "result": result,
                    "duration_ms": duration_ms
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result, default=str)
                })

            self.messages.append({
                "role": "user",
                "content": tool_results
            })

    def chat_stream(self, user_message: str):
        """Stream chat response with tool events.

        Yields:
            dict events: {type: 'tool_start'|'tool_end'|'text_delta'|'done', ...}
        """
        self.messages.append({
            "role": "user",
            "content": user_message
        })

        while True:
            # Use streaming API
            assistant_content = []
            text_response = ""
            tool_uses = []
            current_tool = None

            usage_data = None
            with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=self.system_prompt,
                tools=self.registry.get_all_definitions(),
                messages=self.messages
            ) as stream:
                for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            current_tool = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": ""
                            }
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            text_response += event.delta.text
                            yield {"type": "text_delta", "content": event.delta.text}
                        elif event.delta.type == "input_json_delta":
                            if current_tool:
                                current_tool["input"] += event.delta.partial_json
                    elif event.type == "content_block_stop":
                        if current_tool:
                            try:
                                current_tool["input"] = json.loads(current_tool["input"])
                            except:
                                current_tool["input"] = {}
                            tool_uses.append(current_tool)
                            current_tool = None

                # Get usage from final message
                try:
                    final_msg = stream.get_final_message()
                    if final_msg and final_msg.usage:
                        input_tokens = final_msg.usage.input_tokens
                        output_tokens = final_msg.usage.output_tokens
                        # Dynamic pricing based on model
                        if "haiku" in self.model.lower():
                            # Haiku 4.5: $1/1M input, $5/1M output
                            cost = (input_tokens * 1 + output_tokens * 5) / 1_000_000
                        else:
                            # Sonnet: $3/1M input, $15/1M output
                            cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000
                        usage_data = {
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "cost": cost
                        }
                except:
                    pass

            # Build assistant content for message history
            if text_response:
                assistant_content.append({"type": "text", "text": text_response})
            for tool in tool_uses:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tool["id"],
                    "name": tool["name"],
                    "input": tool["input"]
                })

            self.messages.append({
                "role": "assistant",
                "content": assistant_content
            })

            # If no tool calls, we're done
            if not tool_uses:
                # Parse suggestions from response
                suggestions = self._parse_suggestions(text_response)
                if suggestions:
                    yield {"type": "suggestions", "suggestions": suggestions}
                # Send usage data
                if usage_data:
                    yield {"type": "usage", **usage_data}
                yield {"type": "done"}
                return

            # Execute tools with events
            tool_results = []
            for tool in tool_uses:
                # Emit tool_start
                yield {
                    "type": "tool_start",
                    "name": tool["name"],
                    "input": tool["input"]
                }

                start_time = datetime.now()
                result = self.registry.execute(tool["name"], tool["input"])
                duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                # Emit tool_end
                yield {
                    "type": "tool_end",
                    "name": tool["name"],
                    "input": tool["input"],
                    "result": result,
                    "duration_ms": duration_ms
                }

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool["id"],
                    "content": json.dumps(result, default=str)
                })

            self.messages.append({
                "role": "user",
                "content": tool_results
            })

    def _parse_suggestions(self, text: str) -> list[str]:
        """Parse [SUGGESTIONS]...[/SUGGESTIONS] block from response."""
        import re
        pattern = r'\[SUGGESTIONS\]\s*(.*?)\s*\[/SUGGESTIONS\]'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            suggestions_text = match.group(1).strip()
            # Split by newlines and clean up
            suggestions = [s.strip() for s in suggestions_text.split('\n') if s.strip()]
            return suggestions[:4]  # Max 4 suggestions
        return []

    def reset(self):
        """Reset conversation history."""
        self.messages = []

    def get_tool_history(self) -> List[ToolCall]:
        """Get history of tool calls."""
        return self.registry.get_call_history()
