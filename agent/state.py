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

    # Intent classification
    intent: str | None
    lang: str | None  # User's language (ISO 639-1: en, ru, es, etc.)
    question_en: str | None  # Question translated to English

    # Parser output
    parsed_query: dict | None
    parser_thoughts: str | None  # Parser's reasoning (for Clarifier)
    parser_chunks_used: list[str] | None  # RAP chunks used (for logging)
    parser_cached: bool | None  # Was explicit cache used (for logging)

    # Clarifier output
    clarifier_thoughts: str | None  # Clarifier's reasoning (for logging)

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
    clarifier_question: str | None  # Question Clarifier asked (for relevance check)

    # Tracking
    agents_used: list[str]
    step_number: int

    # Usage (token counts, cost)
    usage: dict | None  # Stored as dict, convert with Usage.model_validate()


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
