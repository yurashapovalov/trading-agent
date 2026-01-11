"""LangGraph definition for multi-agent trading system."""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from agent.state import AgentState, create_initial_state
from agent.agents import Router, DataAgent, Analyst, Educator, Validator
from agent.checkpointer import get_checkpointer


# Initialize agents (singletons)
router = Router()
data_agent = DataAgent()
analyst = Analyst()
educator = Educator()
validator = Validator()


def route_question(state: AgentState) -> dict:
    """Router node - classifies the question."""
    return router(state)


def fetch_data(state: AgentState) -> dict:
    """Data Agent node - fetches data from database."""
    return data_agent(state)


def analyze_data(state: AgentState) -> dict:
    """Analyst node - interprets data and writes response."""
    return analyst(state)


def explain_concept(state: AgentState) -> dict:
    """Educator node - explains concepts."""
    return educator(state)


def validate_response(state: AgentState) -> dict:
    """Validator node - checks response against data."""
    return validator(state)


def after_router(state: AgentState) -> Literal["data_agent", "educator", "analyst_no_data"]:
    """Conditional edge after router - decides next node."""
    route = state.get("route", "data")

    if route == "data":
        return "data_agent"
    elif route == "concept":
        return "educator"
    else:  # hypothetical
        return "analyst_no_data"


def after_validation(state: AgentState) -> Literal["end", "analyst", "data_agent"]:
    """Conditional edge after validation - decides next action."""
    validation = state.get("validation", {})
    status = validation.get("status", "ok")
    attempts = state.get("validation_attempts", 0)

    # Max 3 attempts
    if attempts >= 3:
        return "end"

    if status == "ok":
        return "end"
    elif status == "rewrite":
        return "analyst"
    elif status == "need_more_data":
        return "data_agent"
    else:
        return "end"


def build_graph() -> StateGraph:
    """Build the multi-agent graph."""

    # Create graph with our state schema
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", route_question)
    graph.add_node("data_agent", fetch_data)
    graph.add_node("analyst", analyze_data)
    graph.add_node("analyst_no_data", analyze_data)  # Same function, different entry point
    graph.add_node("educator", explain_concept)
    graph.add_node("validator", validate_response)

    # Add edges from START
    graph.add_edge(START, "router")

    # Conditional routing after router
    graph.add_conditional_edges(
        "router",
        after_router,
        {
            "data_agent": "data_agent",
            "educator": "educator",
            "analyst_no_data": "analyst_no_data",
        }
    )

    # Data agent -> Analyst
    graph.add_edge("data_agent", "analyst")

    # All output agents -> Validator
    graph.add_edge("analyst", "validator")
    graph.add_edge("analyst_no_data", "validator")
    graph.add_edge("educator", "validator")

    # Conditional edges after validation (the loop)
    graph.add_conditional_edges(
        "validator",
        after_validation,
        {
            "end": END,
            "analyst": "analyst",
            "data_agent": "data_agent",
        }
    )

    return graph


def compile_graph(checkpointer=None):
    """Compile graph with optional checkpointer."""
    graph = build_graph()

    if checkpointer is None:
        checkpointer = get_checkpointer()

    return graph.compile(checkpointer=checkpointer)


# Pre-compiled graph for import
# Usage: from agent.graph import app
# result = app.invoke(state, config={"configurable": {"thread_id": "user_123"}})
def get_app():
    """Get compiled graph application."""
    return compile_graph(get_checkpointer())


class TradingGraph:
    """
    Wrapper class for the trading multi-agent graph.

    Provides convenient methods for invoking the graph.
    """

    def __init__(self):
        self._app = None
        self._checkpointer = None

    @property
    def app(self):
        """Lazy initialization of the compiled graph."""
        if self._app is None:
            self._checkpointer = get_checkpointer()
            self._app = compile_graph(self._checkpointer)
        return self._app

    def invoke(
        self,
        question: str,
        user_id: str,
        session_id: str = "default"
    ) -> AgentState:
        """
        Run the graph synchronously.

        Args:
            question: User's question
            user_id: User ID for logging
            session_id: Session/thread ID for persistence

        Returns:
            Final state with response
        """
        initial_state = create_initial_state(question, user_id, session_id)

        config = {
            "configurable": {
                "thread_id": f"{user_id}_{session_id}"
            }
        }

        return self.app.invoke(initial_state, config)

    def stream(
        self,
        question: str,
        user_id: str,
        session_id: str = "default"
    ):
        """
        Run the graph with streaming.

        Yields events for each step.
        """
        initial_state = create_initial_state(question, user_id, session_id)

        config = {
            "configurable": {
                "thread_id": f"{user_id}_{session_id}"
            }
        }

        for event in self.app.stream(initial_state, config, stream_mode="updates"):
            yield event

    def stream_sse(
        self,
        question: str,
        user_id: str,
        session_id: str = "default"
    ):
        """
        Run the graph with SSE-formatted events for frontend.

        Yields dict events compatible with current API format:
        - step_start: agent starting
        - step_end: agent finished
        - sql_executed: SQL query result
        - text_delta: streaming text (for analyst)
        - validation: validation result
        - usage: token usage
        - done: completion
        """
        import time
        from datetime import datetime
        from agent.logging import log_trace_step_sync

        start_time = time.time()
        step_number = 0

        initial_state = create_initial_state(question, user_id, session_id)
        request_id = initial_state.get("request_id")
        config = {
            "configurable": {
                "thread_id": f"{user_id}_{session_id}"
            }
        }

        final_state = None

        for event in self.app.stream(initial_state, config, stream_mode="updates"):
            # event is dict like {"node_name": {state_updates}}
            for node_name, updates in event.items():
                step_start_time = time.time()
                step_number += 1

                # Emit step_start
                yield {
                    "type": "step_start",
                    "agent": node_name,
                    "message": self._get_agent_message(node_name, "start")
                }

                # Emit specific events based on node
                if node_name == "router":
                    route = updates.get("route", "unknown")
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "result": {"route": route},
                        "message": f"Route: {route}"
                    }
                    # Log trace
                    log_trace_step_sync(
                        request_id=request_id,
                        user_id=user_id,
                        step_number=step_number,
                        agent_name=node_name,
                        agent_type="routing",
                        input_data={"question": question},
                        output_data={"route": route},
                        duration_ms=int((time.time() - step_start_time) * 1000),
                    )

                elif node_name == "data_agent":
                    sql_queries = updates.get("sql_queries", [])
                    data = updates.get("data", {})
                    for query in sql_queries:
                        yield {
                            "type": "sql_executed",
                            "query": query.get("query", "")[:200],
                            "rows_found": query.get("row_count", 0),
                            "error": query.get("error"),
                            "duration_ms": query.get("duration_ms", 0)
                        }
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "result": {
                            "queries": len(sql_queries),
                            "total_rows": sum(q.get("row_count", 0) for q in sql_queries)
                        }
                    }
                    # Log trace with SQL details
                    first_query = sql_queries[0] if sql_queries else {}
                    log_trace_step_sync(
                        request_id=request_id,
                        user_id=user_id,
                        step_number=step_number,
                        agent_name=node_name,
                        agent_type="data",
                        input_data={"question": question, "route": final_state.get("route") if final_state else None},
                        output_data={"validation": data.get("validation"), "total_rows": data.get("total_rows")},
                        duration_ms=int((time.time() - step_start_time) * 1000),
                        sql_query=first_query.get("query"),
                        sql_result=first_query.get("rows", [])[:10],  # First 10 rows
                        sql_rows_returned=first_query.get("row_count", 0),
                        sql_error=first_query.get("error"),
                    )

                elif node_name in ["analyst", "analyst_no_data", "educator"]:
                    response = updates.get("response", "")
                    # Stream response in chunks for better UX
                    chunk_size = 50
                    for i in range(0, len(response), chunk_size):
                        yield {
                            "type": "text_delta",
                            "agent": node_name,
                            "content": response[i:i+chunk_size]
                        }
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "result": {"response_length": len(response)}
                    }
                    # Log trace
                    log_trace_step_sync(
                        request_id=request_id,
                        user_id=user_id,
                        step_number=step_number,
                        agent_name=node_name,
                        agent_type="output",
                        input_data={"data_summary": str(final_state.get("data", {}))[:500] if final_state else None},
                        output_data={"response_length": len(response), "response_preview": response[:500]},
                        duration_ms=int((time.time() - step_start_time) * 1000),
                    )

                elif node_name == "validator":
                    validation = updates.get("validation", {})
                    yield {
                        "type": "validation",
                        "status": validation.get("status", "ok"),
                        "issues": validation.get("issues", []),
                        "feedback": validation.get("feedback", "")
                    }
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "result": {"status": validation.get("status")}
                    }
                    # Log trace
                    log_trace_step_sync(
                        request_id=request_id,
                        user_id=user_id,
                        step_number=step_number,
                        agent_name=node_name,
                        agent_type="output",
                        input_data={"response_preview": (final_state.get("response", "") if final_state else "")[:500]},
                        output_data=validation,
                        duration_ms=int((time.time() - step_start_time) * 1000),
                        validation_status=validation.get("status"),
                        validation_issues=validation.get("issues"),
                        validation_feedback=validation.get("feedback"),
                    )

                # Track final state
                if final_state is None:
                    final_state = updates
                else:
                    final_state.update(updates)

        # Emit usage and done
        duration_ms = int((time.time() - start_time) * 1000)
        usage = final_state.get("usage", {}) if final_state else {}

        yield {
            "type": "usage",
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "thinking_tokens": usage.get("thinking_tokens", 0),
            "cost": usage.get("cost_usd", 0)
        }

        yield {
            "type": "done",
            "total_duration_ms": duration_ms,
            "request_id": initial_state.get("request_id")
        }

    def _get_agent_message(self, agent: str, phase: str) -> str:
        """Get human-readable message for agent step."""
        messages = {
            "router": {"start": "Determining question type..."},
            "data_agent": {"start": "Fetching data..."},
            "analyst": {"start": "Analyzing data..."},
            "analyst_no_data": {"start": "Analyzing scenario..."},
            "educator": {"start": "Preparing explanation..."},
            "validator": {"start": "Validating response..."},
        }
        return messages.get(agent, {}).get(phase, f"{agent} {phase}")


# Singleton instance
trading_graph = TradingGraph()
