"""
LangGraph for trading assistant.

Flow: Question → Intent → Parser → Planner → Executor → END
"""

from typing import Literal

from langgraph.graph import StateGraph, START, END

from agent.state import AgentState, get_current_question
from agent.types import Usage, Step
from agent.agents.intent import IntentClassifier
from agent.agents.parser import Parser
from agent.agents.planner import plan_step, ExecutionPlan
from agent.agents.executor import execute_plan


def classify_intent(state: AgentState) -> dict:
    """Classify intent and detect language."""
    question = get_current_question(state)

    classifier = IntentClassifier()
    result = classifier.classify(question)

    return {
        "intent": result.intent,
        "lang": result.lang,
        "question_en": result.question_en,
        "usage": result.usage.model_dump(),
    }


def route_after_intent(state: AgentState) -> Literal["parser", "end"]:
    """Route: data → parser, else → end."""
    intent = state.get("intent", "data")
    return "parser" if intent == "data" else "end"


def parse_question(state: AgentState) -> dict:
    """Parse question into steps."""
    question = state.get("question_en", get_current_question(state))

    parser = Parser()
    result = parser.parse(question)

    # Aggregate usage
    prev_usage = state.get("usage") or {}
    prev = Usage.model_validate(prev_usage) if prev_usage else Usage()
    total = prev + result.usage

    # Convert to dicts for state
    steps = [s.model_dump(by_alias=True, exclude_none=True) for s in result.steps]

    return {
        "parsed_query": steps,
        "parser_thoughts": result.thoughts,
        "usage": total.model_dump(),
    }


def plan_execution(state: AgentState) -> dict:
    """Create execution plans from parsed steps."""
    steps_dict = state.get("parsed_query", [])

    plans = []
    errors = []

    for step_dict in steps_dict:
        try:
            step = Step.model_validate(step_dict)
            plan = plan_step(step)
            plans.append({
                "step_id": step.id,
                "mode": plan.mode,
                "operation": plan.operation,
                "requests": [
                    {
                        "period": r.period,
                        "timeframe": r.timeframe,
                        "filters": r.filters,
                        "label": r.label,
                    }
                    for r in plan.requests
                ],
                "params": plan.params,
                "metrics": plan.metrics,
            })
        except Exception as e:
            errors.append(f"Step {step_dict.get('id', '?')}: {str(e)}")

    return {
        "execution_plan": plans,
        "plan_errors": errors if errors else None,
    }


def execute_query(state: AgentState) -> dict:
    """Execute plans."""
    plans_dict = state.get("execution_plan", [])
    steps_dict = state.get("parsed_query", [])

    results = []

    for plan_dict, step_dict in zip(plans_dict, steps_dict):
        # Reconstruct ExecutionPlan
        from agent.agents.planner import DataRequest
        plan = ExecutionPlan(
            mode=plan_dict["mode"],
            operation=plan_dict["operation"],
            requests=[
                DataRequest(
                    period=tuple(r["period"]),
                    timeframe=r["timeframe"],
                    filters=r["filters"],
                    label=r["label"],
                )
                for r in plan_dict["requests"]
            ],
            params=plan_dict.get("params", {}),
            metrics=plan_dict.get("metrics", []),
        )

        result = execute_plan(plan)
        result["step_id"] = step_dict.get("id", "?")
        results.append(result)

    return {
        "data": results,
    }


def handle_end(state: AgentState) -> dict:
    """Handle non-data intents."""
    return {"response": f"Intent: {state.get('intent')}"}


def build_graph() -> StateGraph:
    """Build graph: Intent → Parser → Planner → Executor → END."""
    graph = StateGraph(AgentState)

    graph.add_node("intent", classify_intent)
    graph.add_node("parser", parse_question)
    graph.add_node("planner", plan_execution)
    graph.add_node("executor", execute_query)
    graph.add_node("end", handle_end)

    graph.add_edge(START, "intent")
    graph.add_conditional_edges(
        "intent",
        route_after_intent,
        {"parser": "parser", "end": "end"}
    )
    graph.add_edge("parser", "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", END)
    graph.add_edge("end", END)

    return graph


def compile_graph():
    """Compile graph for execution."""
    return build_graph().compile()


import threading

_graph = None
_graph_lock = threading.Lock()


def get_graph():
    """Get singleton graph instance (thread-safe)."""
    global _graph
    if _graph is None:
        with _graph_lock:
            if _graph is None:
                _graph = compile_graph()
    return _graph
