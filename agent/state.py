"""LangGraph state types for multi-agent trading analytics system.

Defines all TypedDict types that flow through the agent pipeline:
- Intent: Parsed user intent from Understander
- Stats: Structured numbers from Analyst for validation
- TradingState: Main state object (extends MessagesState for native memory)

Uses MessagesState from LangGraph for automatic message accumulation.
The checkpointer handles message persistence - no need to load from Supabase.

Example:
    # First message in session
    result = graph.invoke(
        {"messages": [HumanMessage(content="What was NQ range?")]},
        {"configurable": {"thread_id": "user_123_session_456"}}
    )
    # Follow-up - checkpointer restores previous messages automatically
    result = graph.invoke(
        {"messages": [HumanMessage(content="Compare to yesterday")]},
        {"configurable": {"thread_id": "user_123_session_456"}}
    )
"""

from typing import TypedDict, Literal, Annotated
from uuid import uuid4
import operator

from langgraph.graph import MessagesState
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage


def merge_lists(a: list, b: list) -> list:
    """Merge two lists, used for accumulating agents_used."""
    return a + b


def merge_usage(a: dict, b: dict) -> dict:
    """Sum usage stats from multiple agents."""
    if not a:
        return b
    if not b:
        return a
    return {
        "input_tokens": (a.get("input_tokens") or 0) + (b.get("input_tokens") or 0),
        "output_tokens": (a.get("output_tokens") or 0) + (b.get("output_tokens") or 0),
        "thinking_tokens": (a.get("thinking_tokens") or 0) + (b.get("thinking_tokens") or 0),
        "cost_usd": (a.get("cost_usd") or 0) + (b.get("cost_usd") or 0),
    }


# =============================================================================
# Intent Types (from Understander)
# =============================================================================

class StrategyDef(TypedDict, total=False):
    """Strategy definition for backtesting."""
    name: str                     # "consecutive_down", "breakout", etc.
    params: dict                  # {"down_days": 3, "hold_days": 1}


class Intent(TypedDict, total=False):
    """
    Structured intent parsed by Understander.

    Understander parses user question into query_spec (building blocks).
    QueryBuilder converts query_spec to SQL.
    DataFetcher executes SQL and returns data.
    """
    # Type of request
    type: Literal["data", "concept", "chitchat", "out_of_scope", "clarification"]

    # Symbol (for type="data")
    symbol: str | None            # "NQ", "ES", etc.

    # Query specification - building blocks for QueryBuilder
    query_spec: dict | None       # {source, filters, grouping, metrics, special_op, ...}

    # Period (extracted from query_spec for convenience)
    period_start: str | None      # ISO date "2025-01-01"
    period_end: str | None        # ISO date "2025-01-31"

    # For strategy/backtest requests (future)
    strategy: StrategyDef | None

    # For concept requests (type="concept")
    concept: str | None           # "RSI", "MACD", "support/resistance"

    # For chitchat/out_of_scope/clarification
    response_text: str | None     # Direct response from Understander

    # Suggestions for follow-up questions
    suggestions: list[str]


# =============================================================================
# Stats Types (from Analyst, validated by Validator)
# =============================================================================

class Stats(TypedDict, total=False):
    """
    Structured statistics from Analyst response.

    Analyst fills this with numbers from their response.
    Validator checks these against actual data.
    """
    # Period info
    period_start: str
    period_end: str
    trading_days: int

    # Price stats
    open_price: float
    close_price: float
    change_pct: float             # Percentage change
    change_points: float          # Absolute change
    max_price: float
    min_price: float

    # Volume stats
    total_volume: int
    avg_daily_volume: float

    # Backtest stats (if applicable)
    total_return_pct: float
    trades_count: int
    win_rate: float
    max_drawdown_pct: float
    sharpe_ratio: float


# =============================================================================
# Existing Types
# =============================================================================

class SQLResult(TypedDict, total=False):
    """Result of a SQL query execution."""
    query: str
    rows: list[dict]
    row_count: int
    error: str | None
    duration_ms: int


class ValidationResult(TypedDict, total=False):
    """Result from Validator agent."""
    status: Literal["ok", "rewrite", "need_more_data"]
    issues: list[str]
    feedback: str


# SQLValidation removed - no longer using SQL Validator


class UsageStats(TypedDict, total=False):
    """Token usage and cost tracking."""
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cost_usd: float


class TradingState(MessagesState, total=False):
    """
    Main state object passed through the LangGraph.

    Extends MessagesState which provides:
    - messages: Annotated[list[AnyMessage], add_messages]

    The add_messages reducer automatically:
    - Accumulates messages across invocations
    - Handles message ID tracking for updates
    - Serializes/deserializes message formats

    Fields are optional (total=False) to allow incremental updates.
    """
    # Request identification
    request_id: str
    user_id: str
    session_id: str  # thread_id for LangGraph

    # NOTE: 'question' and 'chat_history' removed!
    # Use messages[-1].content for current question
    # Use messages[:-1] for chat history
    # Checkpointer manages message persistence automatically

    # Understander output
    intent: Intent | None

    # QueryBuilder output
    sql_query: str | None         # Generated SQL from QueryBuilder (deterministic)

    # DataFetcher output
    sql_queries: list[SQLResult]  # Keep for logging
    data: dict                    # Summary data for Analyst (top-N rows)
    full_data: dict               # Full data for UI (all rows, download)
    missing_capabilities: list[str]  # Features we don't support yet

    # Analyst output
    response: str
    stats: Stats | None           # Structured stats for validation
    suggestions: list[str]        # Suggestions for clarification (from Responder)

    # Validator output
    validation: ValidationResult
    validation_attempts: int

    # Human-in-the-loop
    was_interrupted: bool
    interrupt_reason: str

    # Tracking (use Annotated for list accumulation)
    agents_used: Annotated[list[str], merge_lists]
    step_number: int

    # Usage aggregation (summed across all LLM agents)
    usage: Annotated[UsageStats, merge_usage]
    total_duration_ms: int

    # Error handling
    error: str | None


# Alias for backward compatibility during migration
AgentState = TradingState


def create_initial_input(
    question: str,
    user_id: str,
    session_id: str = "default",
) -> dict:
    """
    Create initial input for graph.invoke().

    Only includes the NEW message - checkpointer will restore previous messages.

    Args:
        question: User's current question
        user_id: User identifier
        session_id: Session identifier (used in thread_id)

    Returns:
        Dict with messages and metadata for graph.invoke()
    """
    return {
        "messages": [HumanMessage(content=question)],
        "request_id": str(uuid4()),
        "user_id": user_id,
        "session_id": session_id,
    }


def create_initial_state(
    question: str,
    user_id: str,
    session_id: str = "default",
    chat_history: list[dict] | None = None
) -> TradingState:
    """
    Create initial state for a new request.

    DEPRECATED: Use create_initial_input() instead.
    This function is kept for backward compatibility during migration.
    """
    # Convert chat_history to messages format
    messages = []
    if chat_history:
        for msg in chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))

    # Add current question
    messages.append(HumanMessage(content=question))

    return TradingState(
        messages=messages,
        request_id=str(uuid4()),
        user_id=user_id,
        session_id=session_id,
        # Understander
        intent=None,
        # QueryBuilder
        sql_query=None,
        # DataFetcher
        sql_queries=[],
        data={},
        full_data={},
        missing_capabilities=[],
        # Analyst
        response="",
        stats=None,
        suggestions=[],
        # Validator
        validation=ValidationResult(status="ok", issues=[], feedback=""),
        validation_attempts=0,
        # Meta
        was_interrupted=False,
        interrupt_reason="",
        agents_used=[],
        step_number=0,
        usage=UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        ),
        total_duration_ms=0,
        error=None
    )


# =============================================================================
# Helper functions
# =============================================================================

def get_current_question(state: TradingState) -> str:
    """
    Get current question from state messages.

    The current question is the content of the last HumanMessage.
    """
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
        # Handle dict format (from serialization)
        if isinstance(msg, dict) and msg.get("type") == "human":
            return msg.get("content", "")
    return ""


def get_chat_history(state: TradingState) -> list[dict]:
    """
    Get chat history from state messages (excluding current question).

    Returns list in old format for backward compatibility:
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    messages = state.get("messages", [])
    history = []

    # All messages except the last one (current question)
    for msg in messages[:-1] if messages else []:
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            history.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, dict):
            role = "user" if msg.get("type") == "human" else "assistant"
            history.append({"role": role, "content": msg.get("content", "")})

    return history


def get_intent_type(state: TradingState) -> str:
    """Get intent type from state, with fallback."""
    intent = state.get("intent")
    if intent:
        return intent.get("type", "data")
    return "data"
