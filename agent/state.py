"""LangGraph state definition for multi-agent system."""

from typing import TypedDict, Literal, Annotated
from uuid import uuid4
import operator


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


class PatternDef(TypedDict, total=False):
    """
    Pattern definition for complex queries.

    LLM parses user question into pattern name + params.
    Pattern module executes the search efficiently in code.
    """
    name: str                     # "consecutive_days", "big_move", "reversal", etc.
    params: dict                  # Pattern-specific parameters


class Intent(TypedDict, total=False):
    """
    Structured intent parsed by Understander.

    LLM parses user question into this structure.
    DataFetcher uses this to decide what data to fetch.
    """
    # Type of request
    type: Literal["data", "concept", "strategy", "pattern", "chitchat", "out_of_scope"]

    # Data parameters (for type="data")
    symbol: str | None            # "NQ", "ES", etc.
    period_start: str | None      # ISO date "2025-01-01"
    period_end: str | None        # ISO date "2025-01-31"
    granularity: Literal["period", "daily", "hourly"] | None  # How to group data

    # For pattern requests (type="pattern")
    pattern: PatternDef | None    # Pattern name + params for complex queries

    # For strategy/backtest requests (type="strategy")
    strategy: StrategyDef | None

    # For concept requests (type="concept")
    concept: str | None           # "RSI", "MACD", "support/resistance"

    # For chitchat/out_of_scope (type="chitchat" or "out_of_scope")
    response_text: str | None     # Direct response from Understander (no data needed)

    # Clarification
    needs_clarification: bool
    clarification_question: str | None
    suggestions: list[str]        # Suggested answers for clarification


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


class UsageStats(TypedDict, total=False):
    """Token usage and cost tracking."""
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cost_usd: float


class AgentState(TypedDict, total=False):
    """
    Main state object passed through the LangGraph.

    Fields are optional (total=False) to allow incremental updates.
    """
    # Request identification
    request_id: str
    user_id: str
    session_id: str  # thread_id for LangGraph

    # Input
    question: str
    chat_history: list[dict]      # Previous messages for context

    # Understander output (replaces route)
    intent: Intent | None
    clarification_attempts: int

    # DataFetcher output
    sql_queries: list[SQLResult]  # Keep for logging
    data: dict                    # Aggregated data for Analyst
    missing_capabilities: list[str]  # Features we don't support yet

    # Analyst output
    response: str
    stats: Stats | None           # Structured stats for validation

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


def create_initial_state(
    question: str,
    user_id: str,
    session_id: str = "default",
    chat_history: list[dict] | None = None
) -> AgentState:
    """Create initial state for a new request."""
    return AgentState(
        request_id=str(uuid4()),
        user_id=user_id,
        session_id=session_id,
        question=question,
        chat_history=chat_history or [],
        # Understander
        intent=None,
        clarification_attempts=0,
        # DataFetcher
        sql_queries=[],
        data={},
        missing_capabilities=[],
        # Analyst
        response="",
        stats=None,
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

def get_intent_type(state: AgentState) -> str:
    """Get intent type from state, with fallback."""
    intent = state.get("intent")
    if intent:
        return intent.get("type", "data")
    return "data"
