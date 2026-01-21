"""
LangGraph v2 — Simplified Flow

Flow:
    Question → Parser → Router
                          ├── chitchat → END
                          ├── concept → END
                          ├── unclear → ClarificationResponder → END (or loop)
                          └── data → Executor → DataResponder → END
"""

from typing import Literal
from datetime import date
import uuid

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage

from agent.state import AgentState, get_current_question
from agent.types import ParsedQuery
from agent.agents.parser import Parser
from agent.agents.clarifier import Clarifier
from agent.agents.responder import Responder
from agent.executor import execute
from agent.memory import get_memory_manager


# =============================================================================
# Node Functions
# =============================================================================

def load_memory(state: AgentState) -> dict:
    """
    Load conversation memory and add current user message.

    Runs at the start of each invoke to:
    1. Get/create memory for session (loads from Supabase if exists)
    2. Add user message to memory
    3. Put memory context into state for downstream nodes
    """
    # session_id is actually chat_id from API
    chat_id = state.get("session_id") or str(uuid.uuid4())
    user_id = state.get("user_id")
    question = get_current_question(state)

    # Get memory for chat (auto-loads from Supabase)
    manager = get_memory_manager()
    memory = manager.get_or_create(chat_id=chat_id, user_id=user_id)

    # Add user message to memory (not saved to DB here - API does that via chat_logs)
    if question:
        memory.add_message("user", question)

    # Get context for downstream nodes
    memory_context = memory.get_context()

    return {
        "session_id": chat_id,
        "memory_context": memory_context,
    }


def parse_question(state: AgentState) -> dict:
    """
    Parser node — stateless entity extraction.

    Just takes a question and parses it.
    Uses memory_context for conversation history.
    If there's a clarified_query from Clarifier, parse that instead.
    """
    # Use clarified_query if available (from Clarifier), otherwise current question
    clarified = state.get("clarified_query")
    question = clarified if clarified else get_current_question(state)

    # Get memory context for Parser (conversation history)
    memory_context = state.get("memory_context", "")

    parser = Parser()
    result = parser.parse(question, today=date.today(), context=memory_context)

    return {
        "parsed_query": result.query.model_dump(),
        "parser_thoughts": result.thoughts,
        "agents_used": ["parser"],
        "step_number": state.get("step_number", 0) + 1,
        # Clear clarified_query after using it
        "clarified_query": None,
    }


def route_after_parser(state: AgentState) -> Literal["chitchat", "concept", "clarification", "executor"]:
    """
    Router — decide next step based on Parser output.
    """
    parsed = state.get("parsed_query", {})
    intent = parsed.get("intent", "data")
    unclear = parsed.get("unclear", [])

    if intent == "chitchat":
        return "chitchat"

    if intent == "concept":
        return "concept"

    if unclear:
        return "clarification"

    return "executor"


def handle_chitchat(state: AgentState) -> dict:
    """
    Chitchat node — greetings, thanks, goodbye using Responder.
    """
    question = get_current_question(state)

    responder = Responder()
    response = responder.respond(question, intent="chitchat", subtype="greeting")

    return {
        "response": response,
        "messages": [AIMessage(content=response)],
        "agents_used": state.get("agents_used", []) + ["responder"],
    }


def handle_concept(state: AgentState) -> dict:
    """
    Concept node — explain trading concept using Responder.
    """
    parsed = state.get("parsed_query", {})
    what = parsed.get("what", "")
    question = get_current_question(state)

    responder = Responder()
    response = responder.respond(question, intent="concept", topic=what)

    return {
        "response": response,
        "messages": [AIMessage(content=response)],
        "agents_used": state.get("agents_used", []) + ["responder"],
    }


def handle_clarification(state: AgentState) -> dict:
    """
    Clarification node — ask user for missing info OR confirm clarified query.

    Two modes:
    1. First time (from Parser): ask clarifying question, store context
    2. User answered: combine original + answer → generate clarified_query
    """
    question = get_current_question(state)
    parsed = state.get("parsed_query", {})
    parser_thoughts = state.get("parser_thoughts", "")

    # Build previous_context from clarification history
    history = state.get("clarification_history", [])
    original = state.get("original_question", "")

    if history:
        # Format history for Clarifier
        lines = [f"Original question: {original}"]
        for turn in history:
            if turn["role"] == "assistant":
                lines.append(f"Assistant: {turn['content']}")
            else:
                lines.append(f"User: {turn['content']}")
        previous_context = "\n".join(lines)
    else:
        previous_context = ""

    clarifier = Clarifier()
    result = clarifier.clarify(
        question=question,
        parsed=parsed,
        previous_context=previous_context,
        parser_thoughts=parser_thoughts,
    )

    update = {
        "response": result.response,
        "messages": [AIMessage(content=result.response)],
        "agents_used": state.get("agents_used", []) + ["clarifier"],
    }

    if result.clarified_query:
        # Clarifier formed complete query — pass to Parser
        update["clarified_query"] = result.clarified_query
        update["awaiting_clarification"] = False
        update["clarification_history"] = None
        update["original_question"] = None
    else:
        # Still need more info — store state and wait
        update["awaiting_clarification"] = True

        # Store original question on first clarification
        if not original:
            update["original_question"] = question

        # Add to history
        new_history = list(history) if history else []
        if history:  # User responded, add their message
            new_history.append({"role": "user", "content": question})
        new_history.append({"role": "assistant", "content": result.response})
        update["clarification_history"] = new_history

    return update


def route_entry(state: AgentState) -> Literal["parser", "clarifier"]:
    """
    Entry router — check if we're in clarification flow.

    If awaiting_clarification, user's message is an answer → go to Clarifier.
    Otherwise, it's a new question → go to Parser.
    """
    if state.get("awaiting_clarification"):
        return "clarifier"
    return "parser"


def route_after_clarification(state: AgentState) -> Literal["parser", "respond"]:
    """
    Router after Clarifier — check if we have clarified_query.

    If yes → go to Parser to parse the reformulated query.
    If no → respond to user and wait for more input.
    """
    if state.get("clarified_query"):
        return "parser"
    return "respond"


def save_memory(state: AgentState) -> dict:
    """
    Save assistant response to memory.

    Runs before END to persist the conversation turn.
    Note: Actual persistence to chat_logs is done by API layer.
    This updates in-memory state and may trigger compaction → summary save.
    """
    chat_id = state.get("session_id")
    user_id = state.get("user_id")
    response = state.get("response")

    if chat_id and response:
        manager = get_memory_manager()
        memory = manager.get_or_create(chat_id=chat_id, user_id=user_id)
        memory.add_message("assistant", response)

    return {}


def handle_executor(state: AgentState) -> dict:
    """
    Executor node — get data and compute result.
    """
    parsed_dict = state.get("parsed_query", {})
    parsed = ParsedQuery.model_validate(parsed_dict)

    result = execute(parsed, symbol="NQ", today=date.today())

    # Format response based on result
    if result["intent"] == "no_data":
        response = "По указанным критериям данные не найдены."
    elif result["intent"] == "data":
        row_count = result.get("row_count", 0)
        operation = result.get("operation", "stats")

        # Simple response for now
        response = f"Получено {row_count} записей. Операция: {operation}."

        # Add some stats if available
        op_result = result.get("result", {})
        if "count" in op_result:
            response += f" Всего дней: {op_result['count']}."
        if "green_pct" in op_result:
            response += f" Зелёных: {op_result['green_pct']}%."
    else:
        response = "Что-то пошло не так."

    return {
        "response": response,
        "messages": [AIMessage(content=response)],
        "data": result,
        "agents_used": state.get("agents_used", []) + ["executor"],
    }


# =============================================================================
# Build Graph
# =============================================================================

def build_graph() -> StateGraph:
    """
    Build the graph with memory and clarification loop.

    Flow:
        START → load_memory → route_entry
                               ├── awaiting_clarification → clarifier → route_after_clarification
                               │                                          ├── has clarified_query → parser (LOOP!)
                               │                                          └── need more info → save_memory → END
                               └── new question → parser → route_after_parser
                                                            ├── chitchat → save_memory → END
                                                            ├── concept → save_memory → END
                                                            ├── unclear → clarifier → save_memory → END
                                                            └── data → executor → save_memory → END
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("load_memory", load_memory)
    graph.add_node("parser", parse_question)
    graph.add_node("chitchat", handle_chitchat)
    graph.add_node("concept", handle_concept)
    graph.add_node("clarifier", handle_clarification)
    graph.add_node("executor", handle_executor)
    graph.add_node("save_memory", save_memory)

    # Start with loading memory
    graph.add_edge(START, "load_memory")

    # After loading memory — check if we're in clarification flow
    graph.add_conditional_edges(
        "load_memory",
        route_entry,
        {
            "parser": "parser",
            "clarifier": "clarifier",
        }
    )

    # After Parser — route based on intent/unclear
    graph.add_conditional_edges(
        "parser",
        route_after_parser,
        {
            "chitchat": "chitchat",
            "concept": "concept",
            "clarification": "clarifier",
            "executor": "executor",
        }
    )

    # After Clarifier — check if we have clarified_query (LOOP back to parser!)
    graph.add_conditional_edges(
        "clarifier",
        route_after_clarification,
        {
            "parser": "parser",  # Loop! clarified_query → parse it
            "respond": "save_memory",  # No clarified_query → save and wait for user
        }
    )

    # All response nodes go to save_memory before END
    graph.add_edge("chitchat", "save_memory")
    graph.add_edge("concept", "save_memory")
    graph.add_edge("executor", "save_memory")

    # save_memory goes to END
    graph.add_edge("save_memory", END)

    return graph


def compile_graph():
    """Compile graph for execution."""
    graph = build_graph()
    return graph.compile()


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    app = compile_graph()

    tests = [
        "привет",
        "что такое OPEX",
        "статистика за 2024",
        "волатильность за 2024",
    ]

    for q in tests:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        result = app.invoke({"messages": [HumanMessage(content=q)]})
        print(f"A: {result.get('response', 'NO RESPONSE')}")
        print(f"Agents: {result.get('agents_used', [])}")
