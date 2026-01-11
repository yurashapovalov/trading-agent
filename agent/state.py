"""LangGraph state definition for multi-agent system."""

from typing import TypedDict, Literal, Annotated
from uuid import uuid4
import operator


def merge_lists(a: list, b: list) -> list:
    """Merge two lists, used for accumulating agents_used."""
    return a + b


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

    # Router output
    route: Literal["data", "concept", "hypothetical"] | None

    # Data Agent output
    sql_queries: list[SQLResult]
    data: dict  # Aggregated data for Analyst

    # Output Agent response
    response: str

    # Validation
    validation: ValidationResult
    validation_attempts: int

    # Human-in-the-loop
    was_interrupted: bool
    interrupt_reason: str

    # Tracking (use Annotated for list accumulation)
    agents_used: Annotated[list[str], merge_lists]
    step_number: int

    # Usage aggregation
    usage: UsageStats
    total_duration_ms: int

    # Error handling
    error: str | None


def create_initial_state(
    question: str,
    user_id: str,
    session_id: str = "default"
) -> AgentState:
    """Create initial state for a new request."""
    return AgentState(
        request_id=str(uuid4()),
        user_id=user_id,
        session_id=session_id,
        question=question,
        route=None,
        sql_queries=[],
        data={},
        response="",
        validation=ValidationResult(status="ok", issues=[], feedback=""),
        validation_attempts=0,
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
