"""
LangGraph v3 — Responder-centric Flow

Flow:
Question ─► Barb ─► Responder ─┬─ greeting/concept/clarification/not_supported ─► END
                               │
                               └─ query ─► QueryBuilder ─► DataFetcher ─► [routing]
                                                                │
                                           ┌────────────────────┴────────────────────┐
                                           ↓                                         ↓
                                    [row_count ≤ 5]                           [row_count > 5]
                                           ↓                                         ↓
                                    Responder_summary ─► END            UI: button ─► Analyst ─► END

Agents:
- Barb: Parser (LLM) + Composer (code) — extracts entities, builds QuerySpec
- Responder: User-facing communication — expert preview, clarifications, summaries
- QueryBuilder: Deterministic SQL generation
- DataFetcher: Execute SQL
- Analyst: Deep data analysis (on-demand)
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from agent.state import AgentState, create_initial_input, get_current_question, get_chat_history
from langchain_core.messages import AIMessage
from agent.agents.data_fetcher import DataFetcher
from agent.agents.analyst import Analyst
from agent.agents.validator import Validator
from agent.agents.responder import Responder
from agent.query_builder import QueryBuilder
from agent.checkpointer import get_checkpointer
from agent.agents.barb import Barb
import config


# =============================================================================
# Initialize agents (singletons)
# =============================================================================

barb = Barb()
responder_agent = Responder()
query_builder = QueryBuilder()
data_fetcher = DataFetcher()
analyst = Analyst()
validator = Validator()


# =============================================================================
# Node Functions
# =============================================================================

def ask_barb(state: AgentState) -> dict:
    """
    Barb node — Parser + Composer flow.

    - Parser (LLM) extracts entities only
    - Composer (code) makes all business decisions
    - Always routes to Responder (Responder handles user communication)

    Output:
    - intent: type, parser_output, query_spec (if query), etc.
    - query_spec_obj: QuerySpec object for QueryBuilder
    """
    question = get_current_question(state)
    chat_history = get_chat_history(state)
    history_str = _format_chat_history(chat_history)

    result = barb.ask(question, chat_history=history_str)

    # Build update dict
    update = {
        "usage": {
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": result.cost_usd,
        },
        "agents_used": ["barb"],
        "step_number": state.get("step_number", 0) + 1,
    }

    # Common debug info
    parser_output = result.parser_output

    if result.type == "query":
        # Pass QuerySpec directly — no dict conversion!
        update["intent"] = {
            "type": "data",
            "parser_output": parser_output,
            "symbol": result.spec.symbol,  # Instrument for Responder/Analyst context
            "holiday_info": result.holiday_info,  # Holiday info
            "event_info": result.event_info,  # Event info (OPEX, NFP, etc.)
            # Dict version for SSE streaming / tests
            "query_spec": {
                "special_op": result.spec.special_op.value if result.spec else None,
                "source": result.spec.source.value if result.spec else None,
                "grouping": result.spec.grouping.value if result.spec else None,
            },
        }
        update["query_spec_obj"] = result.spec  # QuerySpec object directly

    elif result.type == "clarification":
        update["intent"] = {
            "type": "clarification",
            "field": result.field,
            "suggestions": result.options or [],
            "response_text": result.summary or "",  # For year/text clarifications
            "parser_output": parser_output,
            "symbol": "NQ",
        }

    elif result.type == "concept":
        update["intent"] = {
            "type": "concept",
            "concept": result.concept,
            "parser_output": parser_output,
            "symbol": "NQ",
        }

    elif result.type == "greeting":
        update["intent"] = {
            "type": "chitchat",
            "parser_output": parser_output,
            "symbol": "NQ",
        }

    elif result.type == "not_supported":
        update["intent"] = {
            "type": "out_of_scope",
            "response_text": result.reason,
            "parser_output": parser_output,
            "symbol": "NQ",
        }

    else:
        update["intent"] = {
            "type": "chitchat",
            "parser_output": parser_output,
            "symbol": "NQ",
        }

    # Always go to Responder (Responder handles all user communication)
    return update


def _format_chat_history(chat_history: list) -> str:
    """Format chat history for Barb."""
    if not chat_history:
        return ""
    history_str = ""
    for msg in chat_history[-config.CHAT_HISTORY_LIMIT:]:
        role = "User" if msg.get("role") == "user" else "Assistant"
        history_str += f"{role}: {msg.get('content', '')}\n"
    return history_str


def build_query(state: AgentState) -> dict:
    """
    QueryBuilder node — builds SQL from QuerySpec.

    Deterministic, no LLM, always valid SQL.
    Barb passes QuerySpec directly via query_spec_obj.
    """
    try:
        query_spec = state.get("query_spec_obj")
        if query_spec is None:
            raise ValueError("query_spec_obj is required but not found in state")

        sql = query_builder.build(query_spec)

        return {
            "sql_query": sql,
            "agents_used": ["query_builder"],
            "step_number": state.get("step_number", 0) + 1,
        }

    except Exception as e:
        print(f"[QueryBuilder] Error: {e}")
        return {
            "sql_query": None,
            "query_builder_error": str(e),
            "agents_used": ["query_builder"],
            "step_number": state.get("step_number", 0) + 1,
        }


def fetch_data(state: AgentState) -> dict:
    """DataFetcher node — получает данные."""
    return data_fetcher(state)


def analyze_data(state: AgentState) -> dict:
    """Analyst node — интерпретирует данные и пишет ответ."""
    return analyst(state)


def validate_response(state: AgentState) -> dict:
    """Validator node — проверяет корректность статистики."""
    return validator(state)


def respond_to_user(state: AgentState) -> Command:
    """
    Responder node — handles ALL user communication.

    Uses Responder agent (LLM) for natural, expert responses.
    Routes based on intent type:
    - data/query → query_builder (continue to fetch data)
    - others → END (response complete)
    """
    # Call Responder agent
    result = responder_agent(state)

    intent = state.get("intent") or {}
    intent_type = intent.get("type", "chitchat")

    # Determine next node based on intent
    if intent_type in ("data", "query"):
        # For data queries, continue to query_builder
        next_node = "query_builder"
    else:
        # For greeting, concept, clarification, not_supported — we're done
        next_node = END

    return Command(update=result, goto=next_node)


def offer_analysis(state: AgentState) -> dict:
    """
    Offer detailed analysis for large datasets (>5 rows).

    Uses Responder to generate a human message about data being ready
    and offering detailed analysis.
    """
    full_data = state.get("full_data") or {}
    row_count = full_data.get("row_count", 0)
    intent = state.get("intent") or {}

    # Build state for Responder with offer_analysis type
    offer_state = {
        **state,
        "intent": {
            **intent,
            "type": "offer_analysis",
            "row_count": row_count,
        },
    }

    # Call Responder for human response
    result = responder_agent(offer_state)

    # Preserve data_title from earlier responder call
    return {
        "response": result.get("response", ""),
        "data_title": state.get("data_title"),  # Preserve from responder node
        "offer_analysis": True,  # Signal for frontend to show Analyze button
        "usage": result.get("usage"),
        "agents_used": ["responder_offer"],
        "step_number": state.get("step_number", 0) + 1,
        "messages": result.get("messages", []),
    }


def summarize_data(state: AgentState) -> dict:
    """
    Responder summarizes small datasets (≤5 rows).

    For small results, Responder gives a brief summary without full Analyst.
    Uses the same Responder agent but with data context.
    """
    from agent.prompts.responder import get_responder_prompt

    data = state.get("data") or {}
    full_data = state.get("full_data") or {}
    intent = state.get("intent") or {}

    # Build summary prompt with data
    question = get_current_question(state)
    rows = full_data.get("rows", [])
    columns = full_data.get("columns", [])

    # Format data for Responder
    data_summary = ""
    if rows and columns:
        # Simple table format
        data_summary = f"Columns: {', '.join(columns)}\n"
        for row in rows[:5]:
            data_summary += f"  {row}\n"

    # Update state with data summary for Responder
    summary_state = {
        **state,
        "intent": {
            **intent,
            "type": "data_summary",  # Special type for summarization
            "data_preview": data_summary,
            "row_count": full_data.get("row_count", 0),
        },
    }

    # Call Responder for summary
    result = responder_agent(summary_state)

    # Preserve data_title from earlier responder call
    return {
        "response": result.get("response", ""),
        "data_title": state.get("data_title"),  # Preserve from responder node
        "usage": result.get("usage"),
        "agents_used": ["responder_summary"],
        "step_number": state.get("step_number", 0) + 1,
        "messages": result.get("messages", []),
    }


# =============================================================================
# Conditional Edges
# =============================================================================

# Threshold for auto-summarization vs manual analysis
AUTO_SUMMARIZE_THRESHOLD = 5


def after_data_fetcher(state: AgentState) -> Literal["summarize", "offer_analysis"]:
    """
    Route after data is fetched based on row count.

    - ≤5 rows: auto-summarize with Responder (quick answer)
    - >5 rows: offer detailed analysis with Analyst button
    """
    full_data = state.get("full_data") or {}
    row_count = full_data.get("row_count", 0)

    if row_count <= AUTO_SUMMARIZE_THRESHOLD:
        return "summarize"
    else:
        return "offer_analysis"


def after_validation(state: AgentState) -> Literal["end", "analyst"]:
    """Решает, закончить или переписать ответ."""
    validation = state.get("validation") or {}
    status = validation.get("status", "ok")
    attempts = state.get("validation_attempts", 0)

    # Максимум 3 попытки
    if attempts >= 3:
        return "end"

    if status == "ok":
        return "end"
    else:
        return "analyst"


# =============================================================================
# Graph Builder
# =============================================================================

def build_graph() -> StateGraph:
    """
    Build agent graph with Responder-centric flow.

    Flow:
    Question ─► Barb ─► Responder ─┬─ greeting/concept/clarification ─► END
                                   │
                                   └─ query ─► QueryBuilder ─► DataFetcher ─┬─ ≤5 rows ─► Summarize ─► END
                                                                            │
                                                                            └─ >5 rows ─► END (+ Analyze button)

    Analyst is on-demand (triggered via button/separate request).
    """

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("barb", ask_barb)
    graph.add_node("responder", respond_to_user)
    graph.add_node("query_builder", build_query)
    graph.add_node("data_fetcher", fetch_data)
    graph.add_node("summarize", summarize_data)
    graph.add_node("offer_analysis", offer_analysis)
    # Analyst/Validator kept for on-demand analysis
    graph.add_node("analyst", analyze_data)
    graph.add_node("validator", validate_response)

    # Flow: START → barb → responder → [routing via Command]
    graph.add_edge(START, "barb")
    graph.add_edge("barb", "responder")

    # responder uses Command API for routing:
    # - data/query → query_builder
    # - others → END

    # query_builder → data_fetcher → [conditional routing]
    graph.add_edge("query_builder", "data_fetcher")

    # After data_fetcher: route based on row count
    graph.add_conditional_edges(
        "data_fetcher",
        after_data_fetcher,
        {
            "summarize": "summarize",
            "offer_analysis": "offer_analysis",
        }
    )

    # summarize → END
    graph.add_edge("summarize", END)

    # offer_analysis → END (button triggers separate Analyst request)
    graph.add_edge("offer_analysis", END)

    # Analyst flow (for on-demand analysis)
    graph.add_edge("analyst", "validator")
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
    """Компилирует граф с checkpointer."""
    graph = build_graph()

    if checkpointer is None:
        checkpointer = get_checkpointer()

    return graph.compile(checkpointer=checkpointer)


def get_app():
    """Возвращает скомпилированное приложение."""
    return compile_graph(get_checkpointer())


# =============================================================================
# TradingGraph Wrapper
# =============================================================================

class TradingGraph:
    """
    Обёртка для графа v2 с QueryBuilder.

    Использование:
        graph = TradingGraph()
        result = graph.invoke("Покажи статистику", "user1")
    """

    def __init__(self):
        self._app = None
        self._checkpointer = None

    @property
    def app(self):
        """Ленивая инициализация графа."""
        if self._app is None:
            self._checkpointer = get_checkpointer()
            self._app = compile_graph(self._checkpointer)
        return self._app

    def invoke(
        self,
        question: str,
        user_id: str,
        session_id: str = "default",
        chat_history: list = None,  # DEPRECATED: ignored, checkpointer manages history
    ) -> AgentState:
        """Синхронный запуск графа.

        Note: chat_history parameter is deprecated and ignored.
        The checkpointer automatically restores previous messages by thread_id.
        """
        # Only pass the NEW message - checkpointer restores previous messages
        initial_input = create_initial_input(
            question=question,
            user_id=user_id,
            session_id=session_id,
        )

        config = {
            "configurable": {
                "thread_id": f"{user_id}_{session_id}"
            }
        }

        return self.app.invoke(initial_input, config)

    def stream_sse(
        self,
        question: str,
        user_id: str,
        session_id: str = "default",
        request_id: str | None = None,
        chat_history: list = None,  # DEPRECATED: ignored, checkpointer manages history
    ):
        """
        Streaming с SSE событиями для frontend.

        Events:
        - step_start: агент начал работу
        - step_end: агент закончил
        - text_delta: текст ответа
        - usage: токены
        - done: завершение

        Note: chat_history parameter is deprecated and ignored.
        The checkpointer automatically restores previous messages by thread_id.
        """
        import time

        start_time = time.time()
        last_step_time = start_time

        # Only pass the NEW message - checkpointer restores previous messages
        initial_input = create_initial_input(
            question=question,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
        )

        config = {
            "configurable": {
                "thread_id": f"{user_id}_{session_id}"
            }
        }

        # Track state for SSE events (not for LLM context!)
        accumulated_state = {
            "question": question,
        }
        # Track usage separately - sum from all agents in this request
        accumulated_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "cost_usd": 0.0,
        }

        # Сразу отправить step_start для barb — моментальный фидбек
        yield {
            "type": "step_start",
            "agent": "barb",
            "message": self._get_agent_message("barb")
        }

        for event in self.app.stream(initial_input, config, stream_mode=["updates", "custom"]):
            stream_type, data = event

            # Custom events (text_delta) — пробрасываем напрямую
            if stream_type == "custom":
                yield data
                continue

            # Updates events
            for node_name, updates in data.items():
                current_time = time.time()
                step_duration_ms = int((current_time - last_step_time) * 1000)
                last_step_time = current_time

                # step_start (skip barb — already sent before stream)
                if node_name != "barb":
                    yield {
                        "type": "step_start",
                        "agent": node_name,
                        "message": self._get_agent_message(node_name)
                    }

                # Handle by node type
                if node_name == "barb":
                    intent = updates.get("intent") or {}
                    usage = updates.get("usage") or {}

                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "input": {
                            "question": accumulated_state.get("question"),
                        },
                        "result": {
                            "type": intent.get("type"),
                            "symbol": intent.get("symbol", "NQ"),
                        },
                        "output": {
                            "intent": intent,
                            "usage": usage,
                        }
                    }
                    accumulated_state["intent"] = intent

                    # Accumulate usage from barb
                    if usage:
                        accumulated_usage["input_tokens"] += usage.get("input_tokens", 0)
                        accumulated_usage["output_tokens"] += usage.get("output_tokens", 0)
                        accumulated_usage["thinking_tokens"] += usage.get("thinking_tokens", 0)
                        accumulated_usage["cost_usd"] += usage.get("cost_usd", 0.0)

                elif node_name == "query_builder":
                    sql_query = updates.get("sql_query")
                    error = updates.get("query_builder_error")

                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "input": {
                            "query_spec": accumulated_state.get("intent", {}).get("query_spec"),
                        },
                        "result": {
                            "sql_generated": sql_query is not None,
                            "error": error,
                        },
                        "output": {
                            "sql_query": sql_query,
                        }
                    }
                    accumulated_state["sql_query"] = sql_query

                elif node_name == "data_fetcher":
                    data_result = updates.get("data") or {}
                    full_data = updates.get("full_data") or {}
                    row_count = full_data.get("row_count", data_result.get("row_count", 0))

                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "input": {
                            "sql_query": accumulated_state.get("sql_query"),
                        },
                        "result": {
                            "rows": row_count,
                            "showing": data_result.get("showing", data_result.get("row_count", 0)),
                            "truncated": data_result.get("truncated", False),
                            "granularity": data_result.get("granularity"),
                        },
                        "output": {
                            "summary": data_result,   # Top-N for Analyst
                            "full_data": full_data,   # All rows (saved to logs + UI)
                        },
                    }
                    accumulated_state["data"] = data_result
                    accumulated_state["full_data"] = full_data

                    # Signal that data is ready for UI
                    yield {
                        "type": "data_ready",
                        "row_count": row_count,
                        "data": full_data,
                    }

                elif node_name == "analyst":
                    response = updates.get("response") or ""
                    stats = updates.get("stats") or {}
                    usage = updates.get("usage") or {}

                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "input": {
                            "data": accumulated_state.get("data"),  # Summary that Analyst sees
                            "data_row_count": accumulated_state.get("data", {}).get("row_count", 0),
                        },
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
                    accumulated_state["response"] = response
                    # Accumulate usage from analyst
                    if usage:
                        accumulated_usage["input_tokens"] += usage.get("input_tokens", 0)
                        accumulated_usage["output_tokens"] += usage.get("output_tokens", 0)
                        accumulated_usage["thinking_tokens"] += usage.get("thinking_tokens", 0)
                        accumulated_usage["cost_usd"] += usage.get("cost_usd", 0.0)

                elif node_name == "validator":
                    validation = updates.get("validation") or {}
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {"status": validation.get("status")},
                        "output": validation
                    }

                elif node_name == "responder":
                    response = updates.get("response") or ""
                    data_title = updates.get("data_title")
                    usage = updates.get("usage") or {}
                    intent = updates.get("intent") or accumulated_state.get("intent", {})
                    suggestions = intent.get("suggestions") or []

                    # Send data_title if present (for query types)
                    if data_title:
                        yield {
                            "type": "data_title",
                            "title": data_title
                        }

                    # Send suggestions for clarification
                    if suggestions:
                        yield {
                            "type": "suggestions",
                            "suggestions": suggestions
                        }

                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {
                            "response_length": len(response),
                            "has_data_title": data_title is not None,
                        },
                        "output": {
                            "response": response,
                            "data_title": data_title,
                            "suggestions": suggestions,
                        }
                    }

                    # Accumulate usage from responder
                    if usage:
                        accumulated_usage["input_tokens"] += usage.get("input_tokens", 0)
                        accumulated_usage["output_tokens"] += usage.get("output_tokens", 0)
                        accumulated_usage["cost_usd"] += usage.get("cost_usd", 0.0)

                elif node_name == "summarize":
                    response = updates.get("response") or ""
                    usage = updates.get("usage") or {}

                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {
                            "response_length": len(response),
                        },
                        "output": {
                            "response": response,
                        }
                    }
                    accumulated_state["response"] = response

                    # Accumulate usage from summarize
                    if usage:
                        accumulated_usage["input_tokens"] += usage.get("input_tokens", 0)
                        accumulated_usage["output_tokens"] += usage.get("output_tokens", 0)
                        accumulated_usage["cost_usd"] += usage.get("cost_usd", 0.0)

                elif node_name == "offer_analysis":
                    response = updates.get("response") or ""
                    offer_analysis_flag = updates.get("offer_analysis", False)
                    usage = updates.get("usage") or {}

                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {
                            "response_length": len(response),
                            "offer_analysis": offer_analysis_flag,
                        },
                        "output": {
                            "response": response,
                        }
                    }
                    accumulated_state["response"] = response

                    # Accumulate usage from offer_analysis (Responder call)
                    if usage:
                        accumulated_usage["input_tokens"] += usage.get("input_tokens", 0)
                        accumulated_usage["output_tokens"] += usage.get("output_tokens", 0)
                        accumulated_usage["cost_usd"] += usage.get("cost_usd", 0.0)

                    # Signal frontend to show Analyze button
                    if offer_analysis_flag:
                        yield {
                            "type": "offer_analysis",
                            "message": response,
                        }

        # Final events
        duration_ms = int((time.time() - start_time) * 1000)

        # Use accumulated_usage (summed from step_end events) instead of final_state
        # This ensures we only count this request's usage, not accumulated from checkpointer
        yield {
            "type": "usage",
            "input_tokens": accumulated_usage["input_tokens"],
            "output_tokens": accumulated_usage["output_tokens"],
            "thinking_tokens": accumulated_usage["thinking_tokens"],
            "cost": accumulated_usage["cost_usd"]
        }

        yield {
            "type": "done",
            "total_duration_ms": duration_ms,
            "request_id": initial_input.get("request_id")
        }

    def _get_agent_message(self, agent: str) -> str:
        """Return status message for agent."""
        messages = {
            "barb": "Understanding question...",
            "responder": "Preparing response...",
            "query_builder": "Building SQL query...",
            "data_fetcher": "Fetching data...",
            "summarize": "Summarizing results...",
            "offer_analysis": "Data ready...",
            "analyst": "Analyzing data...",
            "validator": "Validating response...",
        }
        return messages.get(agent, f"Running {agent}...")


# Singleton
trading_graph = TradingGraph()
