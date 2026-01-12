"""
LangGraph definition for multi-agent trading system v2.

Flow: Understander → DataFetcher → Analyst → Validator → END
                                     ↑_________| (rewrite loop)
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END

from agent.state import AgentState, create_initial_state
from agent.agents.understander import Understander
from agent.agents.data_fetcher import DataFetcher
from agent.agents.analyst import Analyst
from agent.agents.validator import Validator
from agent.checkpointer import get_checkpointer


# Initialize agents (singletons)
understander = Understander()
data_fetcher = DataFetcher()
analyst = Analyst()
validator = Validator()


# =============================================================================
# Node Functions
# =============================================================================

def understand_question(state: AgentState) -> dict:
    """Understander node - parses question into Intent."""
    return understander(state)


def fetch_data(state: AgentState) -> dict:
    """DataFetcher node - fetches data based on Intent."""
    return data_fetcher(state)


def analyze_data(state: AgentState) -> dict:
    """Analyst node - interprets data and writes response."""
    return analyst(state)


def validate_response(state: AgentState) -> dict:
    """Validator node - checks stats against data."""
    return validator(state)


# =============================================================================
# Conditional Edges
# =============================================================================

def after_validation(state: AgentState) -> Literal["end", "analyst"]:
    """Decide whether to end or rewrite."""
    validation = state.get("validation", {})
    status = validation.get("status", "ok")
    attempts = state.get("validation_attempts", 0)

    # Max 3 attempts
    if attempts >= 3:
        return "end"

    if status == "ok":
        return "end"
    else:  # rewrite
        return "analyst"


# =============================================================================
# Graph Builder
# =============================================================================

def build_graph() -> StateGraph:
    """Build the multi-agent graph."""

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("understander", understand_question)
    graph.add_node("data_fetcher", fetch_data)
    graph.add_node("analyst", analyze_data)
    graph.add_node("validator", validate_response)

    # Linear flow: START → understander → data_fetcher → analyst → validator
    graph.add_edge(START, "understander")
    graph.add_edge("understander", "data_fetcher")
    graph.add_edge("data_fetcher", "analyst")
    graph.add_edge("analyst", "validator")

    # Validation loop
    graph.add_conditional_edges(
        "validator",
        after_validation,
        {
            "end": END,
            "analyst": "analyst",
        }
    )

    return graph


def compile_graph(checkpointer=None):
    """Compile graph with optional checkpointer."""
    graph = build_graph()

    if checkpointer is None:
        checkpointer = get_checkpointer()

    return graph.compile(checkpointer=checkpointer)


def get_app():
    """Get compiled graph application."""
    return compile_graph(get_checkpointer())


# =============================================================================
# TradingGraph Wrapper
# =============================================================================

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
        session_id: str = "default",
        chat_history: list = None,
    ) -> AgentState:
        """
        Run the graph synchronously.

        Args:
            question: User's question
            user_id: User ID for logging
            session_id: Session/thread ID for persistence
            chat_history: Optional chat history for context

        Returns:
            Final state with response
        """
        initial_state = create_initial_state(
            question=question,
            user_id=user_id,
            session_id=session_id,
            chat_history=chat_history,
        )

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
        session_id: str = "default",
        chat_history: list = None,
    ):
        """
        Run the graph with streaming.
        Yields events for each step.
        """
        initial_state = create_initial_state(
            question=question,
            user_id=user_id,
            session_id=session_id,
            chat_history=chat_history,
        )

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
        session_id: str = "default",
        chat_history: list = None,
    ):
        """
        Run the graph with SSE-formatted events for frontend.

        Yields dict events:
        - step_start: agent starting
        - step_end: agent finished
        - text_delta: streaming text
        - validation: validation result
        - usage: token usage
        - done: completion
        """
        import time

        start_time = time.time()
        step_number = 0
        last_step_time = start_time

        initial_state = create_initial_state(
            question=question,
            user_id=user_id,
            session_id=session_id,
            chat_history=chat_history,
        )

        config = {
            "configurable": {
                "thread_id": f"{user_id}_{session_id}"
            }
        }

        final_state = None

        for event in self.app.stream(initial_state, config, stream_mode="updates"):
            for node_name, updates in event.items():
                step_number += 1
                current_time = time.time()
                step_duration_ms = int((current_time - last_step_time) * 1000)
                last_step_time = current_time

                # Emit step_start
                yield {
                    "type": "step_start",
                    "agent": node_name,
                    "message": self._get_agent_message(node_name)
                }

                # Emit specific events based on node
                # Each step_end has:
                #   - result: summary for UI display
                #   - output: full data for logging/traces
                if node_name == "understander":
                    intent = updates.get("intent", {})
                    usage = updates.get("usage", {})
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {
                            "type": intent.get("type"),
                            "symbol": intent.get("symbol"),
                            "period": f"{intent.get('period_start')} — {intent.get('period_end')}" if intent.get("period_start") else None,
                            "granularity": intent.get("granularity"),
                        },
                        "output": {
                            "intent": intent,
                            "usage": usage,
                        }
                    }

                elif node_name == "data_fetcher":
                    data = updates.get("data", {})
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {
                            "rows": data.get("row_count") or data.get("matches_count", 0),
                            "granularity": data.get("granularity"),
                            "pattern": data.get("pattern"),
                        },
                        "output": data
                    }

                elif node_name == "analyst":
                    response = updates.get("response", "")
                    stats = updates.get("stats", {})
                    usage = updates.get("usage", {})

                    # Stream response in chunks
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
                        "duration_ms": step_duration_ms,
                        "result": {
                            "response_length": len(response),
                            "stats_count": len(stats) if stats else 0,
                        },
                        "output": {
                            "response": response,
                            "stats": stats,
                            "usage": usage,
                        }
                    }

                elif node_name == "validator":
                    validation = updates.get("validation", {})
                    yield {
                        "type": "validation",
                        "status": validation.get("status", "ok"),
                        "issues": validation.get("issues", []),
                    }
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {"status": validation.get("status")},
                        "output": validation
                    }

                # Track final state (manually merge usage)
                if final_state is None:
                    final_state = dict(updates)
                else:
                    # Merge usage instead of overwriting
                    if "usage" in updates and "usage" in final_state:
                        old_usage = final_state.get("usage", {})
                        new_usage = updates.get("usage", {})
                        final_state["usage"] = {
                            "input_tokens": (old_usage.get("input_tokens") or 0) + (new_usage.get("input_tokens") or 0),
                            "output_tokens": (old_usage.get("output_tokens") or 0) + (new_usage.get("output_tokens") or 0),
                            "thinking_tokens": (old_usage.get("thinking_tokens") or 0) + (new_usage.get("thinking_tokens") or 0),
                            "cost_usd": (old_usage.get("cost_usd") or 0) + (new_usage.get("cost_usd") or 0),
                        }
                        # Update other fields without overwriting usage
                        for key, value in updates.items():
                            if key != "usage":
                                final_state[key] = value
                    else:
                        final_state.update(updates)

        # Emit usage and done
        duration_ms = int((time.time() - start_time) * 1000)
        usage = final_state.get("usage", {}) if final_state else {}

        yield {
            "type": "usage",
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost": usage.get("cost_usd", 0)
        }

        yield {
            "type": "done",
            "total_duration_ms": duration_ms,
            "request_id": initial_state.get("request_id")
        }

    def _get_agent_message(self, agent: str) -> str:
        """Get human-readable message for agent."""
        messages = {
            "understander": "Understanding question...",
            "data_fetcher": "Fetching data...",
            "analyst": "Analyzing data...",
            "validator": "Validating response...",
        }
        return messages.get(agent, f"Running {agent}...")


# Singleton instance
trading_graph = TradingGraph()
