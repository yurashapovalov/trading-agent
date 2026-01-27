"""
LangGraph for trading assistant.

Flow: Question → Intent → Understander → Parser → Planner → Executor → Presenter → END
"""

import time
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
from agent.agents.presenter import Presenter
from agent.agents.responder import Responder
from agent.logging.supabase import log_trace_step_sync


def _strip_pattern_columns(results: list[dict]) -> list[dict]:
    """
    Remove is_* pattern columns from rows before logging to trace.

    Pattern columns are used internally for:
    - Filtering (e.g., "show all doji")
    - Presenter context (counts patterns for summary text)

    But they shouldn't be in the output sent to frontend:
    - Pollutes table with 30+ columns of mostly zeros
    - If user filtered by pattern, all rows match anyway (redundant)
    """
    stripped = []
    for result in results:
        rows = result.get("rows", [])
        if not rows:
            stripped.append(result)
            continue

        clean_rows = [
            {k: v for k, v in row.items() if not k.startswith("is_")}
            for row in rows
        ]
        stripped.append({**result, "rows": clean_rows})
    return stripped


def build_clarification_context(
    original: str,
    history: list[dict],
    current_answer: str,
) -> str:
    """Build context string for Understander when continuing clarification."""
    parts = [f"Original question: {original}"]
    for turn in history:
        if turn["role"] == "assistant":
            parts.append(f"Assistant asked: {turn['content']}")
        else:
            parts.append(f"User answered: {turn['content']}")
    parts.append(f"User answered: {current_answer}")
    return "\n".join(parts)


def classify_intent(state: AgentState) -> dict:
    """Classify intent and detect language."""
    start_time = time.time()
    question = get_current_question(state)

    classifier = IntentClassifier()
    result = classifier.classify(question)

    # Prepare output
    output = {
        "intent": result.intent,
        "lang": result.lang,
        "internal_query": result.internal_query,
        "usage": result.usage.model_dump(),
    }

    # Log trace step
    step_number = (state.get("step_number") or 0) + 1
    request_id = state.get("request_id")
    user_id = state.get("user_id")

    if request_id and user_id:
        duration_ms = int((time.time() - start_time) * 1000)
        log_trace_step_sync(
            request_id=request_id,
            user_id=user_id,
            step_number=step_number,
            agent_name="intent",
            input_data={"question": question},
            output_data={
                "intent": result.intent,
                "lang": result.lang,
                "internal_query": result.internal_query,
            },
            usage=result.usage.model_dump(),
            duration_ms=duration_ms,
        )

    output["step_number"] = step_number
    return output


def route_after_intent(state: AgentState) -> Literal["understander", "responder"]:
    """Route: data or awaiting_clarification → understander, else → responder."""
    # If awaiting clarification, always go to understander (it has context)
    if state.get("awaiting_clarification"):
        return "understander"
    intent = state.get("intent", "data")
    return "understander" if intent == "data" else "responder"


def understand_question(state: AgentState) -> dict:
    """Understand what user wants. Handles both fresh questions and clarification continuations."""
    start_time = time.time()
    lang = state.get("lang", "en")
    needs_title = state.get("needs_title", False)
    memory_context = state.get("memory_context")
    awaiting_clarification = state.get("awaiting_clarification", False)
    history = state.get("clarification_history") or []

    # Safety net: max 3 rounds (6 messages = 3 questions + 3 answers)
    if awaiting_clarification and len(history) >= 6:
        msg = "Не получается понять. Попробуй сформулировать вопрос по-другому?" if lang == "ru" \
              else "Having trouble understanding. Could you rephrase your question?"
        step_number = (state.get("step_number") or 0) + 1
        return {
            "response": msg,
            "awaiting_clarification": False,
            "clarification_history": None,
            "original_question": None,
            "topic_changed": True,
            "step_number": step_number,
        }

    # Build question: with context if continuing clarification, otherwise fresh
    if awaiting_clarification:
        original = state.get("original_question", "")
        current_answer = get_current_question(state)
        question = f"{original}\n\nContext:\n{build_clarification_context(original, history, current_answer)}"
        # Add user answer to history for next round if needed
        updated_history = history + [{"role": "user", "content": current_answer}]
    else:
        question = state.get("internal_query", get_current_question(state))
        updated_history = None

    understander = Understander()
    result = understander.understand(question, lang=lang, needs_title=needs_title)

    # Aggregate usage
    prev_usage = state.get("usage") or {}
    prev = Usage.model_validate(prev_usage) if prev_usage else Usage()
    total = prev + result.usage

    # Prepare output
    output = {
        "goal": result.goal,
        "understood": result.understood,
        "topic_changed": result.topic_changed,
        "expanded_query": result.expanded_query,
        "acknowledge": result.acknowledge,
        "need_clarification": result.need_clarification.model_dump() if result.need_clarification else None,
        "suggested_title": result.suggested_title,
        "usage": total.model_dump(),
    }

    # Handle clarification state
    if result.topic_changed:
        # Topic changed — clear old clarification state, start fresh
        output["awaiting_clarification"] = False
        output["clarification_history"] = None
        output["original_question"] = None
    elif result.understood:
        # Understood — clear clarification state
        output["awaiting_clarification"] = False
        output["clarification_history"] = updated_history  # Keep for logging
    else:
        # Still need clarification — keep history
        output["clarification_history"] = updated_history

    # Special case: cancellation (not understood, no need_clarification, but has acknowledge)
    # This means Understander recognized it as cancel/chitchat
    if not result.understood and not result.need_clarification and result.acknowledge:
        output["response"] = result.acknowledge

    # Log trace step
    step_number = (state.get("step_number") or 0) + 1
    request_id = state.get("request_id")
    user_id = state.get("user_id")

    if request_id and user_id:
        duration_ms = int((time.time() - start_time) * 1000)
        log_trace_step_sync(
            request_id=request_id,
            user_id=user_id,
            step_number=step_number,
            agent_name="understander",
            input_data={
                "internal_query": question,
                "lang": lang,
                "needs_title": needs_title,
                "memory_context": memory_context,
                "awaiting_clarification": awaiting_clarification,
            },
            output_data={
                "goal": result.goal,
                "understood": result.understood,
                "topic_changed": result.topic_changed,
                "expanded_query": result.expanded_query,
                "acknowledge": result.acknowledge,
                "suggested_title": result.suggested_title,
                "need_clarification": result.need_clarification.model_dump() if result.need_clarification else None,
            },
            usage=result.usage.model_dump(),
            duration_ms=duration_ms,
        )

    output["step_number"] = step_number
    return output


def route_after_understander(state: AgentState) -> Literal["parser", "clarify", "end"]:
    """Route based on understander result.

    Simple logic:
    - response already set (safety net) → end
    - understood → parser
    - not understood → clarify
    """
    # Safety net: response already set by understander
    if state.get("response"):
        return "end"
    if state.get("understood"):
        return "parser"
    return "clarify"


def handle_clarification(state: AgentState) -> dict:
    """Use Clarifier to formulate beautiful question from Understander's tezises."""
    start_time = time.time()
    clarification = state.get("need_clarification", {})
    lang = state.get("lang", "en")
    question = state.get("original_question") or get_current_question(state)
    memory_context = state.get("memory_context")

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
        question=question,
        lang=lang,
        memory_context=memory_context,
    )

    # Aggregate usage
    prev_usage = state.get("usage") or {}
    prev = Usage.model_validate(prev_usage) if prev_usage else Usage()
    total = prev + result.usage

    # Build clarification history
    history = state.get("clarification_history") or []
    history.append({"role": "assistant", "content": result.question})

    # Prepare output
    output = {
        "response": result.question,
        "awaiting_clarification": True,
        "original_question": question,
        "clarification_history": history,
        "clarifier_question": result.question,
        "usage": total.model_dump(),
    }

    # Log trace step
    step_number = (state.get("step_number") or 0) + 1
    request_id = state.get("request_id")
    user_id = state.get("user_id")

    if request_id and user_id:
        duration_ms = int((time.time() - start_time) * 1000)
        log_trace_step_sync(
            request_id=request_id,
            user_id=user_id,
            step_number=step_number,
            agent_name="clarifier",
            input_data={
                "required": required,
                "optional": optional,
                "context": context,
                "question": question,
                "lang": lang,
                "memory_context": memory_context,
            },
            output_data={
                "response": result.question,
            },
            usage=result.usage.model_dump(),
            duration_ms=duration_ms,
        )

    output["step_number"] = step_number
    return output


def parse_question(state: AgentState) -> dict:
    """Parse question into steps."""
    start_time = time.time()
    # Use expanded_query from Understander, fallback to internal_query
    question = state.get("expanded_query") or state.get("internal_query", get_current_question(state))

    parser = Parser()
    result = parser.parse(question)

    # Aggregate usage
    prev_usage = state.get("usage") or {}
    prev = Usage.model_validate(prev_usage) if prev_usage else Usage()
    total = prev + result.usage

    # Convert to dicts for state
    steps = [s.model_dump(by_alias=True, exclude_none=True) for s in result.steps]
    validator_changes = [c.to_dict() for c in result.validator_changes]

    # Prepare output
    output = {
        "parsed_query": steps,
        "parser_thoughts": result.thoughts,
        "parser_raw_output": result.raw_output,
        "parser_chunks_used": result.chunk_ids,
        "parser_validator_changes": validator_changes,
        "usage": total.model_dump(),
    }

    # Log trace step
    step_number = (state.get("step_number") or 0) + 1
    request_id = state.get("request_id")
    user_id = state.get("user_id")

    if request_id and user_id:
        duration_ms = int((time.time() - start_time) * 1000)
        log_trace_step_sync(
            request_id=request_id,
            user_id=user_id,
            step_number=step_number,
            agent_name="parser",
            input_data={
                "question": question,
                "chunks_used": result.chunk_ids,
            },
            output_data={
                "raw_output": result.raw_output,
                "parsed_query": steps,
                "thoughts": result.thoughts,
                "validator_changes": validator_changes,
            },
            usage=result.usage.model_dump(),
            duration_ms=duration_ms,
        )

    output["step_number"] = step_number
    return output


def plan_execution(state: AgentState) -> dict:
    """Create execution plans from parsed steps."""
    start_time = time.time()
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
                        "session": r.session,
                    }
                    for r in plan.requests
                ],
                "params": plan.params,
                "metrics": plan.metrics,
            })
        except Exception as e:
            errors.append(f"Step {step_dict.get('id', '?')}: {str(e)}")

    # Prepare output
    output = {
        "execution_plan": plans,
        "plan_errors": errors if errors else None,
    }

    # Log trace step
    step_number = (state.get("step_number") or 0) + 1
    request_id = state.get("request_id")
    user_id = state.get("user_id")

    if request_id and user_id:
        duration_ms = int((time.time() - start_time) * 1000)
        log_trace_step_sync(
            request_id=request_id,
            user_id=user_id,
            step_number=step_number,
            agent_name="planner",
            input_data={"parsed_query": steps_dict},
            output_data={
                "execution_plan": plans,
                "plan_errors": errors if errors else None,
            },
            usage=None,  # No LLM usage
            duration_ms=duration_ms,
        )

    output["step_number"] = step_number
    return output


def execute_query(state: AgentState) -> dict:
    """Execute plans."""
    start_time = time.time()
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
                    session=r.get("session"),
                )
                for r in plan_dict["requests"]
            ],
            params=plan_dict.get("params", {}),
            metrics=plan_dict.get("metrics", []),
        )

        result = execute_plan(plan)
        result["step_id"] = step_dict.get("id", "?")
        results.append(result)

    # Prepare output
    output = {
        "data": results,
    }

    # Log trace step
    step_number = (state.get("step_number") or 0) + 1
    request_id = state.get("request_id")
    user_id = state.get("user_id")

    if request_id and user_id:
        duration_ms = int((time.time() - start_time) * 1000)
        log_trace_step_sync(
            request_id=request_id,
            user_id=user_id,
            step_number=step_number,
            agent_name="executor",
            input_data={"execution_plan": plans_dict},
            output_data={"data": _strip_pattern_columns(results)},
            usage=None,  # No LLM usage
            duration_ms=duration_ms,
        )

    output["step_number"] = step_number
    return output


def present_response(state: AgentState) -> dict:
    """Format data for user using Presenter."""
    start_time = time.time()
    data = state.get("data", [])
    lang = state.get("lang", "en")
    goal = state.get("goal")
    question = state.get("internal_query") or get_current_question(state)
    context_compacted = state.get("context_compacted", False)

    # If no data, return simple message
    if not data:
        msg = "Данных не найдено." if lang == "ru" else "No data found."
        output = {"response": msg}
        # Log even for no data
        step_number = (state.get("step_number") or 0) + 1
        request_id = state.get("request_id")
        user_id = state.get("user_id")
        if request_id and user_id:
            duration_ms = int((time.time() - start_time) * 1000)
            log_trace_step_sync(
                request_id=request_id,
                user_id=user_id,
                step_number=step_number,
                agent_name="presenter",
                input_data={"data": [], "question": question, "lang": lang},
                output_data={"response": msg, "type": "no_data", "row_count": 0},
                duration_ms=duration_ms,
            )
        output["step_number"] = step_number
        return output

    presenter = Presenter()

    # Present each result
    responses = []
    total_usage = Usage()
    for i, result in enumerate(data):
        # Build data dict for presenter
        presenter_data = {
            "result": {
                "rows": result.get("rows", []),
                "summary": result.get("summary", {}),
            },
            "row_count": len(result.get("rows", [])),
        }

        response = presenter.present(
            data=presenter_data,
            question=question,
            lang=lang,
            context_compacted=context_compacted,
        )

        responses.append(response)
        if hasattr(response, "usage") and response.usage:
            total_usage = total_usage + response.usage

    # Combine responses
    if len(responses) == 1:
        r = responses[0]
        output = {
            "response": r.summary,
            "presenter_title": r.title,
            "presenter_summary": r.summary,
            "presenter_type": r.type.value,
            "presenter_row_count": r.row_count,
        }
    else:
        # Multiple results — combine summaries
        combined = "\n\n".join(r.summary for r in responses)
        total_rows = sum(r.row_count for r in responses)
        output = {
            "response": combined,
            "presenter_summary": combined,
            "presenter_type": "multi",
            "presenter_row_count": total_rows,
        }

    # Log trace step
    step_number = (state.get("step_number") or 0) + 1
    request_id = state.get("request_id")
    user_id = state.get("user_id")

    if request_id and user_id:
        duration_ms = int((time.time() - start_time) * 1000)
        row_count = output.get("presenter_row_count", 0)
        log_trace_step_sync(
            request_id=request_id,
            user_id=user_id,
            step_number=step_number,
            agent_name="presenter",
            input_data={
                "row_count": row_count,
                "summary": data[0].get("summary") if data else None,
                "question": question,
                "lang": lang,
                "context_compacted": context_compacted,
            },
            output_data={
                "title": output.get("presenter_title"),
                "summary": output.get("presenter_summary"),
                "type": output.get("presenter_type"),
                "row_count": row_count,
            },
            usage=total_usage.model_dump() if total_usage.input_tokens > 0 else None,
            duration_ms=duration_ms,
        )

    output["step_number"] = step_number
    output["usage"] = total_usage.model_dump()
    return output


def respond_to_user(state: AgentState) -> dict:
    """Handle non-data queries using Responder."""
    start_time = time.time()
    question = state.get("internal_query") or get_current_question(state)
    lang = state.get("lang", "en")

    responder = Responder()
    result = responder.respond(question=question, lang=lang)

    # Aggregate usage
    prev_usage = state.get("usage") or {}
    prev = Usage.model_validate(prev_usage) if prev_usage else Usage()
    total = prev + result.usage

    # Prepare output
    output = {
        "response": result.text,
        "usage": total.model_dump(),
    }

    # Log trace step
    step_number = (state.get("step_number") or 0) + 1
    request_id = state.get("request_id")
    user_id = state.get("user_id")

    if request_id and user_id:
        duration_ms = int((time.time() - start_time) * 1000)
        log_trace_step_sync(
            request_id=request_id,
            user_id=user_id,
            step_number=step_number,
            agent_name="responder",
            input_data={
                "question": question,
                "lang": lang,
            },
            output_data={
                "response": result.text,
            },
            usage=result.usage.model_dump(),
            duration_ms=duration_ms,
        )

    output["step_number"] = step_number
    return output


def handle_end(state: AgentState) -> dict:
    """Pass-through node for ending flow when response is already set.

    Used when safety net triggered (max clarification rounds).
    """
    return {}


def build_graph() -> StateGraph:
    """Build graph with simple clarification handling.

    Flow:
        Data understood: Intent → Understander → Parser → Planner → Executor → Presenter → END
        Data unclear: Intent → Understander → Clarify → END
        Chitchat/Concept: Intent → Responder → END
        Safety net: Intent → Understander → End → END
    """
    graph = StateGraph(AgentState)

    graph.add_node("intent", classify_intent)
    graph.add_node("understander", understand_question)
    graph.add_node("parser", parse_question)
    graph.add_node("planner", plan_execution)
    graph.add_node("executor", execute_query)
    graph.add_node("presenter", present_response)
    graph.add_node("clarify", handle_clarification)
    graph.add_node("responder", respond_to_user)
    graph.add_node("end", handle_end)

    graph.add_edge(START, "intent")
    graph.add_conditional_edges(
        "intent",
        route_after_intent,
        {"understander": "understander", "responder": "responder"},
    )
    graph.add_conditional_edges(
        "understander",
        route_after_understander,
        {"parser": "parser", "clarify": "clarify", "end": "end"},
    )
    graph.add_edge("parser", "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "presenter")
    graph.add_edge("presenter", END)
    graph.add_edge("clarify", END)
    graph.add_edge("responder", END)
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
