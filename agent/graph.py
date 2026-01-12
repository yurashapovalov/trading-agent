"""
LangGraph definition for multi-agent trading system v2.

Flow:
                    ┌─ chitchat/out_of_scope/clarification ─► Responder ──► END
                    │
Question ─► Understander ─┼────────────────────────────────────────────────────────────┐
                    │                            ┌──────────────────────────────────────┤
                    │                            │ (rewrite loop)                       │
                    └─ data ─► SQL Agent ─► SQL Validator ─► DataFetcher ─► Analyst ─► Validator ─► END
                                   ↑_______________|                           ↑____________| (rewrite loop)

Clarification (stateless):
- When Understander returns needs_clarification=true, Responder returns the question
- Response is saved to chat_logs like normal
- User answers with new message
- Understander sees context and combines original question with clarification

Note: SQL Agent only runs if search_condition exists in Intent.
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
# Note: Command and interrupt not used in stateless clarification approach
# from langgraph.types import Command, interrupt

from agent.state import AgentState, create_initial_state
from agent.agents.understander import Understander
from agent.agents.sql_agent import SQLAgent
from agent.agents.sql_validator import SQLValidator
from agent.agents.data_fetcher import DataFetcher
from agent.agents.analyst import Analyst
from agent.agents.validator import Validator
from agent.checkpointer import get_checkpointer


# Initialize agents (singletons)
understander = Understander()
sql_agent = SQLAgent()
sql_validator = SQLValidator()
data_fetcher = DataFetcher()
analyst = Analyst()
validator = Validator()


# =============================================================================
# Node Functions
# =============================================================================

def understand_question(state: AgentState) -> dict:
    """Understander node - parses question into Intent."""
    return understander(state)


def generate_sql(state: AgentState) -> dict:
    """SQL Agent node - generates SQL from search_condition."""
    return sql_agent(state)


def validate_sql(state: AgentState) -> dict:
    """SQL Validator node - validates SQL before execution."""
    return sql_validator(state)


def fetch_data(state: AgentState) -> dict:
    """DataFetcher node - fetches data based on Intent."""
    return data_fetcher(state)


def analyze_data(state: AgentState) -> dict:
    """Analyst node - interprets data and writes response."""
    return analyst(state)


def validate_response(state: AgentState) -> dict:
    """Validator node - checks stats against data."""
    return validator(state)


def simple_respond(state: AgentState) -> dict:
    """
    Responder node - returns response_text for chitchat/out_of_scope/clarification.
    No data fetching or analysis needed.
    """
    intent = state.get("intent", {})

    # Handle clarification - return question with suggestions
    if intent.get("needs_clarification"):
        question = intent.get("clarification_question", "Уточните ваш вопрос")
        suggestions = intent.get("suggestions", [])

        # Format response with suggestions
        response_text = question
        if suggestions:
            response_text += "\n\nВарианты:\n" + "\n".join(f"• {s}" for s in suggestions)

        return {
            "response": response_text,
            "suggestions": suggestions,  # Pass to frontend for buttons
            "agents_used": ["responder"],
        }

    # Normal response
    response_text = intent.get("response_text", "Чем могу помочь с анализом торговых данных?")
    return {
        "response": response_text,
        "agents_used": ["responder"],
    }


# =============================================================================
# Conditional Edges
# =============================================================================

def after_understander(state: AgentState) -> Literal["responder", "sql_agent", "data_fetcher"]:
    """Route based on intent type after understanding."""
    intent = state.get("intent", {})
    intent_type = intent.get("type", "data")

    # Clarification goes to responder (stateless approach)
    if intent.get("needs_clarification"):
        return "responder"

    # Non-data types go to responder
    if intent_type in ("chitchat", "out_of_scope", "concept"):
        return "responder"

    # If search_condition exists, use SQL Agent
    if intent.get("search_condition"):
        return "sql_agent"

    # Otherwise go directly to DataFetcher
    return "data_fetcher"


def after_sql_validation(state: AgentState) -> Literal["data_fetcher", "sql_agent"]:
    """Route based on SQL validation result."""
    sql_validation = state.get("sql_validation", {})
    status = sql_validation.get("status", "ok")
    step_number = state.get("step_number", 0)

    # Max 3 attempts
    if step_number >= 6:  # 2 cycles of sql_agent + sql_validator
        return "data_fetcher"

    if status == "ok":
        return "data_fetcher"
    else:  # rewrite
        return "sql_agent"


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
    graph.add_node("responder", simple_respond)  # For chitchat/out_of_scope/clarification
    graph.add_node("sql_agent", generate_sql)
    graph.add_node("sql_validator", validate_sql)
    graph.add_node("data_fetcher", fetch_data)
    graph.add_node("analyst", analyze_data)
    graph.add_node("validator", validate_response)

    # START → understander
    graph.add_edge(START, "understander")

    # Conditional routing after understander
    graph.add_conditional_edges(
        "understander",
        after_understander,
        {
            "responder": "responder",
            "sql_agent": "sql_agent",
            "data_fetcher": "data_fetcher",
        }
    )

    # Responder → END (no validation needed for chitchat/clarification)
    graph.add_edge("responder", END)

    # SQL flow: sql_agent → sql_validator → conditional routing
    graph.add_edge("sql_agent", "sql_validator")

    # After SQL validation: ok → data_fetcher, rewrite → sql_agent
    graph.add_conditional_edges(
        "sql_validator",
        after_sql_validation,
        {
            "data_fetcher": "data_fetcher",
            "sql_agent": "sql_agent",
        }
    )

    # Data flow: data_fetcher → analyst → validator
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
        # Track accumulated state for input_data
        accumulated_state = {
            "question": question,
            "chat_history": chat_history,
        }

        for event in self.app.stream(initial_state, config, stream_mode="updates"):
            for node_name, updates in event.items():
                step_number += 1
                current_time = time.time()
                step_duration_ms = int((current_time - last_step_time) * 1000)
                last_step_time = current_time

                # Build input_data based on what this agent received
                input_data = self._get_agent_input(node_name, accumulated_state)

                # Emit step_start
                yield {
                    "type": "step_start",
                    "agent": node_name,
                    "message": self._get_agent_message(node_name)
                }

                # Emit specific events based on node
                # Each step_end has:
                #   - result: summary for UI display
                #   - input: what agent received
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
                            "search_condition": intent.get("search_condition"),
                        },
                        "input": input_data,
                        "output": {
                            "intent": intent,
                            "usage": usage,
                        }
                    }
                    # Update accumulated state
                    accumulated_state["intent"] = intent

                elif node_name == "sql_agent":
                    sql_query = updates.get("sql_query")
                    usage = updates.get("usage", {})
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {
                            "sql_generated": sql_query is not None,
                        },
                        "input": input_data,
                        "output": {
                            "sql_query": sql_query,
                            "usage": usage,
                        }
                    }
                    # Update accumulated state
                    accumulated_state["sql_query"] = sql_query

                elif node_name == "sql_validator":
                    sql_validation = updates.get("sql_validation", {})
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {
                            "status": sql_validation.get("status"),
                            "issues": sql_validation.get("issues"),
                        },
                        "input": input_data,
                        "output": sql_validation
                    }
                    # Update accumulated state
                    accumulated_state["sql_validation"] = sql_validation

                elif node_name == "data_fetcher":
                    data = updates.get("data", {})
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {
                            "rows": data.get("row_count") or data.get("matches_count", 0),
                            "granularity": data.get("granularity"),
                        },
                        "input": input_data,
                        "output": data
                    }
                    # Update accumulated state
                    accumulated_state["data"] = data

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
                        "input": input_data,
                        "output": {
                            "response": response,
                            "stats": stats,
                            "usage": usage,
                        }
                    }
                    # Update accumulated state
                    accumulated_state["response"] = response
                    accumulated_state["stats"] = stats

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
                        "input": input_data,
                        "output": validation
                    }

                elif node_name == "responder":
                    # Responder handles chitchat/out_of_scope/clarification
                    response = updates.get("response", "")
                    suggestions = updates.get("suggestions", [])

                    # Stream response in chunks
                    chunk_size = 50
                    for i in range(0, len(response), chunk_size):
                        yield {
                            "type": "text_delta",
                            "agent": node_name,
                            "content": response[i:i+chunk_size]
                        }

                    # Emit suggestions if present (for clarification)
                    if suggestions:
                        yield {
                            "type": "suggestions",
                            "suggestions": suggestions
                        }

                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {"response_length": len(response)},
                        "input": input_data,
                        "output": {"response": response, "suggestions": suggestions}
                    }
                    # Update accumulated state
                    accumulated_state["response"] = response

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
            "thinking_tokens": usage.get("thinking_tokens", 0),
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
            "responder": "Responding...",
            "sql_agent": "Generating SQL...",
            "sql_validator": "Validating SQL...",
            "data_fetcher": "Fetching data...",
            "analyst": "Analyzing data...",
            "validator": "Validating response...",
        }
        return messages.get(agent, f"Running {agent}...")

    def _get_agent_input(self, agent: str, state: dict) -> dict:
        """Get input data for agent based on accumulated state."""
        if agent == "understander":
            return {
                "question": state.get("question"),
            }
        elif agent == "responder":
            return {
                "intent": state.get("intent"),
            }
        elif agent == "sql_agent":
            return {
                "intent": state.get("intent"),
                "sql_validation": state.get("sql_validation"),  # For rewrite
            }
        elif agent == "sql_validator":
            return {
                "sql_query": state.get("sql_query"),
            }
        elif agent == "data_fetcher":
            return {
                "intent": state.get("intent"),
                "sql_query": state.get("sql_query"),
                "sql_validation": state.get("sql_validation"),
            }
        elif agent == "analyst":
            return {
                "question": state.get("question"),
                "data": state.get("data"),
            }
        elif agent == "validator":
            return {
                "response": state.get("response"),
                "stats": state.get("stats"),
                "data": state.get("data"),
            }
        return {}


# Singleton instance
trading_graph = TradingGraph()
