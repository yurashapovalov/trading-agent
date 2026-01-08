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
        get_statistics
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
                "dataset": {
                    "type": "string",
                    "enum": ["train", "test"],
                    "description": "Which dataset to use. ALWAYS use 'train' for finding strategies! Never optimize on 'test' data - that's only for validation.",
                    "default": "train"
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
                "dataset": {
                    "type": "string",
                    "enum": ["train", "test"],
                    "description": "Which dataset to use: 'train' for in-sample (strategy development), 'test' for out-of-sample (validation). IMPORTANT: Always validate on 'test' after finding strategies on 'train'!",
                    "default": "train"
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
                "dataset": {
                    "type": "string",
                    "enum": ["train", "test"],
                    "description": "Which dataset to use: 'train' or 'test'",
                    "default": "train"
                }
            },
            "required": ["symbol"]
        },
        function=get_statistics
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
        """Build system prompt with dynamic data info."""
        from data import get_data_info

        # Get loaded data info
        data_info = "No data loaded."
        symbols_list = []
        try:
            df = get_data_info()
            if not df.empty:
                data_lines = []
                for _, row in df.iterrows():
                    symbols_list.append(row['symbol'])
                    data_lines.append(f"- {row['symbol']}: {row['bars']:,} bars, {row['start_date'].strftime('%Y-%m-%d')} to {row['end_date'].strftime('%Y-%m-%d')} ({row['trading_days']} days)")
                data_info = "\n".join(data_lines)
        except:
            pass

        symbols_str = ", ".join(symbols_list) if symbols_list else "none"

        return f"""You are a trading data analyst. You help analyze historical futures data.

Available data:
{data_info}

Available symbols: {symbols_str}
ONLY use symbols that are listed above. Do not mention or suggest symbols without data.

Tools:
- query_ohlcv: custom SQL queries on OHLCV data
- find_optimal_entries: find best entry times by criteria
- backtest_strategy: test a strategy with statistics
- get_statistics: market stats (volatility, volume, ranges)

Tick values: NQ=0.25 ($5), ES=0.25 ($12.50), CL=0.01 ($10)

Rules:
- Be concise, no long introductions
- Use markdown tables for results
- Mention sample size when showing statistics
- Respond in user's language (English/Russian)"""

    def chat(self, user_message: str) -> str:
        """Send message and get response, handling tool calls."""

        self.messages.append({
            "role": "user",
            "content": user_message
        })

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
                return text_response

            # Execute tools and add results
            tool_results = []
            for tool_use in tool_uses:
                result = self.registry.execute(tool_use.name, tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result, default=str)
                })

            self.messages.append({
                "role": "user",
                "content": tool_results
            })

    def reset(self):
        """Reset conversation history."""
        self.messages = []

    def get_tool_history(self) -> List[ToolCall]:
        """Get history of tool calls."""
        return self.registry.get_call_history()
