"""
Minimal LangGraph state for trading assistant.

Uses MessagesState for automatic message accumulation.
Kept simple — complex state goes to Supabase.
"""

from langgraph.graph import MessagesState
from langchain_core.messages import HumanMessage, AIMessage


class TradingState(MessagesState):
    """
    Minimal state for LangGraph.

    Inherits `messages` from MessagesState (auto-accumulates).
    Other fields are per-request, not persisted in state.
    """

    # Session identification (for Supabase lookups)
    session_id: str
    user_id: str

    # Parser output
    parsed_query: dict | None
    parser_thoughts: str | None  # Parser's reasoning (for Clarifier)
    intent: str | None

    # Memory
    memory_context: str | None  # Formatted context from ConversationMemory

    # Execution results
    data: dict | None
    context: str | None

    # Response
    response: str | None

    # Clarification flow
    awaiting_clarification: bool  # True = waiting for user to clarify
    original_question: str | None  # First question that triggered clarification
    clarification_history: list[dict] | None  # [{role, content}, ...] turns
    clarified_query: str | None  # Final reformulated query (when clarification done)

    # Tracking
    agents_used: list[str]
    step_number: int


# Alias for compatibility
AgentState = TradingState


def get_current_question(state: TradingState) -> str:
    """Get current question from state messages."""
    messages = state.get("messages", [])

    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
        if isinstance(msg, dict) and msg.get("type") == "human":
            return msg.get("content", "")

    return ""


def get_chat_history(state: TradingState, limit: int = 10) -> list[dict]:
    """Get chat history as list of dicts (excluding current question)."""
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

    return history[-limit:] if limit else history


def get_clarification_context(state: TradingState) -> str:
    """
    Build context string for Parser when in clarification flow.

    Returns formatted context with original question and clarification history.
    """
    if not state.get("awaiting_clarification"):
        return ""

    original = state.get("original_question", "")
    history = state.get("clarification_history", [])

    if not original:
        return ""

    # Build context string
    lines = [f"Original question: {original}"]

    for turn in history or []:
        role = turn.get("role", "")
        content = turn.get("content", "")
        if role == "assistant":
            lines.append(f"Assistant asked: {content}")
        elif role == "user":
            lines.append(f"User clarified: {content}")

    return "\n".join(lines)
