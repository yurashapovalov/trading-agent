"""LangGraph state types for trading analytics system.

Defines TypedDict types that flow through the agent pipeline:
- TradingState: Main state object (extends MessagesState)
- Stats: Structured numbers from Analyst
- Helper functions for accessing state

Uses MessagesState from LangGraph for automatic message accumulation.
Checkpointer handles message persistence.

Example:
    result = graph.invoke(
        {"messages": [HumanMessage(content="What was NQ range?")]},
        {"configurable": {"thread_id": "user_123_session_456"}}
    )
"""

from typing import TypedDict, Literal
from uuid import uuid4

from langgraph.graph import MessagesState
from langchain_core.messages import HumanMessage, AIMessage


# =============================================================================
# Stats Types (from Analyst, validated by Validator)
# =============================================================================

class Stats(TypedDict, total=False):
    """Structured statistics from Analyst response."""
    # Period info
    period_start: str
    period_end: str
    trading_days: int

    # Price stats
    open_price: float
    close_price: float
    change_pct: float
    change_points: float
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
# Result Types
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


class UsageStats(TypedDict, total=False):
    """Token usage and cost tracking."""
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cost_usd: float


# =============================================================================
# Main State
# =============================================================================

class TradingState(MessagesState, total=False):
    """
    Main state object passed through the LangGraph.

    Extends MessagesState which provides:
    - messages: Annotated[list[AnyMessage], add_messages]

    Flow:
        Parser → MolecularQuery → Expander → AtomicQuery → DataBuilder → SQL
    """
    # Request identification
    request_id: str
    user_id: str
    session_id: str

    # Parser output
    molecular_query: object | None  # MolecularQuery from Parser
    parser_raw_output: dict | None  # Raw LLM output for debugging

    # Expander output
    atomic_query: object | None  # AtomicQuery from Expander

    # DataBuilder output
    sql_query: str | None  # Generated SQL

    # DataFetcher output
    sql_queries: list[SQLResult]  # Keep for logging
    data: dict  # Summary data for Analyst (top-N rows)
    full_data: dict  # Full data for UI (all rows)

    # Responder output
    response: str
    data_title: str | None  # Title for DataCard
    offer_analysis: bool  # Flag to show Analyze button
    suggestions: list[str]  # For clarification

    # Analyst output
    stats: Stats | None  # Structured stats for validation

    # Validator output
    validation: ValidationResult
    validation_attempts: int

    # Human-in-the-loop
    was_interrupted: bool
    interrupt_reason: str

    # Tracking
    agents_used: list[str]
    step_number: int
    usage: UsageStats
    total_duration_ms: int

    # Error handling
    error: str | None


# Alias for backward compatibility
AgentState = TradingState


# =============================================================================
# Factory Functions
# =============================================================================

def create_initial_input(
    question: str,
    user_id: str,
    session_id: str = "default",
    request_id: str | None = None,
) -> dict:
    """
    Create initial input for graph.invoke().

    Only includes the NEW message - checkpointer restores previous messages.
    """
    return {
        "messages": [HumanMessage(content=question)],
        "request_id": request_id or str(uuid4()),
        "user_id": user_id,
        "session_id": session_id,
        # Reset per-request fields
        "agents_used": [],
        "step_number": 0,
        "validation_attempts": 0,
        "usage": UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0,
        ),
    }


# =============================================================================
# Helper Functions
# =============================================================================

def get_current_question(state: TradingState) -> str:
    """Get current question from state messages."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
        if isinstance(msg, dict) and msg.get("type") == "human":
            return msg.get("content", "")
    return ""


def get_chat_history(state: TradingState) -> list[dict]:
    """Get chat history (excluding current question)."""
    messages = state.get("messages", [])
    history = []

    for msg in messages[:-1] if messages else []:
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            history.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, dict):
            role = "user" if msg.get("type") == "human" else "assistant"
            history.append({"role": role, "content": msg.get("content", "")})

    return history
