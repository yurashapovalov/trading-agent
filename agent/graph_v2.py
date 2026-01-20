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

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
from google import genai
from google.genai import types

from agent.state import AgentState, get_current_question, get_chat_history
from agent.types import ParsedQuery
from agent.prompts.parser import get_parser_prompt
from agent.prompts.clarification import get_clarification_prompt, ClarificationOutput
from agent.executor import execute
import config


# =============================================================================
# LLM Client
# =============================================================================

client = genai.Client(api_key=config.GOOGLE_API_KEY)


# =============================================================================
# Node Functions
# =============================================================================

def parse_question(state: AgentState) -> dict:
    """
    Parser node — extract entities from question using LLM.

    Uses response_schema for structured output.
    """
    question = get_current_question(state)
    today = date.today()
    weekday = today.strftime("%A")

    system, user = get_parser_prompt(question, today.isoformat(), weekday)

    response = client.models.generate_content(
        model=config.GEMINI_LITE_MODEL,
        contents=f"{system}\n\n{user}",
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=ParsedQuery,
        ),
    )

    parsed = ParsedQuery.model_validate_json(response.text)

    return {
        "parsed_query": parsed.model_dump(),
        "agents_used": ["parser"],
        "step_number": state.get("step_number", 0) + 1,
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
    Chitchat node — simple greeting response.
    """
    question = get_current_question(state)

    # Detect language
    is_russian = any('\u0400' <= c <= '\u04FF' for c in question)

    if is_russian:
        response = "Привет! Я помогу с анализом торговых данных NQ. Что интересует?"
    else:
        response = "Hi! I can help analyze NQ trading data. What would you like to know?"

    return {
        "response": response,
        "messages": [AIMessage(content=response)],
        "agents_used": state.get("agents_used", []) + ["chitchat"],
    }


def handle_concept(state: AgentState) -> dict:
    """
    Concept node — explain trading concept.

    TODO: Add LLM call for proper explanation.
    """
    parsed = state.get("parsed_query", {})
    what = parsed.get("what", "")
    question = get_current_question(state)

    is_russian = any('\u0400' <= c <= '\u04FF' for c in question)

    if is_russian:
        response = f"TODO: объяснить что такое {what}"
    else:
        response = f"TODO: explain what {what} is"

    return {
        "response": response,
        "messages": [AIMessage(content=response)],
        "agents_used": state.get("agents_used", []) + ["concept"],
    }


def handle_clarification(state: AgentState) -> dict:
    """
    Clarification node — ask user for missing info.

    Uses ClarificationResponder prompt.
    """
    question = get_current_question(state)
    parsed = state.get("parsed_query", {})
    previous_context = state.get("clarification_context", "")

    # Determine mode
    mode = "confirming" if previous_context else "asking"

    system, user = get_clarification_prompt(
        question=question,
        parsed=parsed,
        previous_context=previous_context,
        mode=mode,
    )

    response = client.models.generate_content(
        model=config.GEMINI_LITE_MODEL,
        contents=f"{system}\n\n{user}",
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=ClarificationOutput,
        ),
    )

    result = ClarificationOutput.model_validate_json(response.text)

    update = {
        "response": result.response,
        "messages": [AIMessage(content=result.response)],
        "agents_used": state.get("agents_used", []) + ["clarification"],
    }

    # Store context for next turn
    if result.clarified_query:
        update["clarified_query"] = result.clarified_query
    else:
        # Store context so next turn knows we're in clarification flow
        update["clarification_context"] = f"Asked about: {parsed.get('what', question)}"

    return update


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
    """Build the v2 graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("parser", parse_question)
    graph.add_node("chitchat", handle_chitchat)
    graph.add_node("concept", handle_concept)
    graph.add_node("clarification", handle_clarification)
    graph.add_node("executor", handle_executor)

    # Add edges
    graph.add_edge(START, "parser")

    graph.add_conditional_edges(
        "parser",
        route_after_parser,
        {
            "chitchat": "chitchat",
            "concept": "concept",
            "clarification": "clarification",
            "executor": "executor",
        }
    )

    # All end nodes go to END
    graph.add_edge("chitchat", END)
    graph.add_edge("concept", END)
    graph.add_edge("clarification", END)
    graph.add_edge("executor", END)

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
