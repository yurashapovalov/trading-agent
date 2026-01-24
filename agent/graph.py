"""
LangGraph for trading assistant.

Flow: Question → Intent → Understander → Parser → Planner → Executor → END
"""

from typing import Literal

from langgraph.graph import StateGraph, START, END

from agent.state import AgentState, get_current_question
from agent.types import Usage, Step
from agent.agents.intent import IntentClassifier
from agent.agents.understander import Understander
from agent.agents.clarifier import Clarifier
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


def route_after_intent(state: AgentState) -> Literal["understander", "clarify_continue", "end"]:
    """Route: awaiting_clarification → continue clarification, data → understander, else → end."""
    # If awaiting clarification, route to continue flow
    if state.get("awaiting_clarification"):
        return "clarify_continue"

    intent = state.get("intent", "data")
    return "understander" if intent == "data" else "end"


def understand_question(state: AgentState) -> dict:
    """Understand what user wants."""
    question = state.get("question_en", get_current_question(state))
    lang = state.get("lang", "en")

    understander = Understander()
    result = understander.understand(question, lang=lang)

    # Aggregate usage
    prev_usage = state.get("usage") or {}
    prev = Usage.model_validate(prev_usage) if prev_usage else Usage()
    total = prev + result.usage

    return {
        "goal": result.goal,
        "understood": result.understood,
        "expanded_query": result.expanded_query,
        "need_clarification": result.need_clarification.model_dump() if result.need_clarification else None,
        "usage": total.model_dump(),
    }


def route_after_understander(state: AgentState) -> Literal["parser", "clarify"]:
    """Route: understood → parser, else → clarify."""
    understood = state.get("understood", False)
    return "parser" if understood else "clarify"


def handle_clarification(state: AgentState) -> dict:
    """Use Clarifier to formulate beautiful question from Understander's tezises."""
    clarification = state.get("need_clarification", {})
    lang = state.get("lang", "en")
    original = state.get("original_question") or get_current_question(state)

    # Extract tezises from Understander
    required = clarification.get("required", [])
    optional = clarification.get("optional", [])
    context = clarification.get("context", "")

    # Use Clarifier to formulate question
    clarifier = Clarifier()
    result = clarifier.clarify(
        required=required,
        optional=optional,
        context=context,
        original_question=original,
        lang=lang,
    )

    # Aggregate usage
    prev_usage = state.get("usage") or {}
    prev = Usage.model_validate(prev_usage) if prev_usage else Usage()
    total = prev + result.usage

    # Build clarification history
    history = state.get("clarification_history") or []
    history.append({"role": "assistant", "content": result.question})

    return {
        "response": result.question,
        "awaiting_clarification": True,
        "original_question": original,
        "clarification_history": history,
        "clarifier_question": result.question,
        "usage": total.model_dump(),
    }


def continue_clarification(state: AgentState) -> dict:
    """Continue clarification: send user's answer back to Understander with context."""
    user_answer = get_current_question(state)
    original = state.get("original_question", "")
    lang = state.get("lang", "en")

    # Add user answer to history
    history = state.get("clarification_history") or []
    history.append({"role": "user", "content": user_answer})

    # Build context for Understander
    context_parts = [f"Original question: {original}"]
    for turn in history:
        if turn["role"] == "assistant":
            context_parts.append(f"Assistant asked: {turn['content']}")
        else:
            context_parts.append(f"User answered: {turn['content']}")
    context = "\n".join(context_parts)

    # Call Understander with context
    understander = Understander()
    result = understander.understand(
        question=f"{original}\n\nContext:\n{context}",
        lang=lang,
    )

    # Aggregate usage
    prev_usage = state.get("usage") or {}
    prev = Usage.model_validate(prev_usage) if prev_usage else Usage()
    total = prev + result.usage

    # If understood, clear clarification state
    if result.understood:
        return {
            "goal": result.goal,
            "understood": result.understood,
            "expanded_query": result.expanded_query,
            "need_clarification": None,
            "usage": total.model_dump(),
            "awaiting_clarification": False,
            "clarification_history": history,
        }
    else:
        # Still need clarification
        return {
            "goal": result.goal,
            "understood": result.understood,
            "expanded_query": result.expanded_query,
            "need_clarification": result.need_clarification.model_dump() if result.need_clarification else None,
            "usage": total.model_dump(),
            "clarification_history": history,
        }


def parse_question(state: AgentState) -> dict:
    """Parse question into steps."""
    # Use expanded_query from Understander, fallback to question_en
    question = state.get("expanded_query") or state.get("question_en", get_current_question(state))

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


def route_after_clarify_continue(state: AgentState) -> Literal["parser", "clarify"]:
    """Route after continue_clarification: understood → parser, else → clarify again."""
    understood = state.get("understood", False)
    return "parser" if understood else "clarify"


def build_graph() -> StateGraph:
    """Build graph with multi-turn clarification support.

    Flow:
        New question: Intent → Understander → Parser → Planner → Executor → END
        Clarification: Intent → clarify_continue → Parser (if understood) or clarify (if not)
    """
    graph = StateGraph(AgentState)

    graph.add_node("intent", classify_intent)
    graph.add_node("understander", understand_question)
    graph.add_node("clarify_continue", continue_clarification)
    graph.add_node("parser", parse_question)
    graph.add_node("planner", plan_execution)
    graph.add_node("executor", execute_query)
    graph.add_node("clarify", handle_clarification)
    graph.add_node("end", handle_end)

    graph.add_edge(START, "intent")
    graph.add_conditional_edges(
        "intent",
        route_after_intent,
        {"understander": "understander", "clarify_continue": "clarify_continue", "end": "end"}
    )
    graph.add_conditional_edges(
        "understander",
        route_after_understander,
        {"parser": "parser", "clarify": "clarify"}
    )
    graph.add_conditional_edges(
        "clarify_continue",
        route_after_clarify_continue,
        {"parser": "parser", "clarify": "clarify"}
    )
    graph.add_edge("parser", "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", END)
    graph.add_edge("clarify", END)
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
