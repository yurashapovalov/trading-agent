"""
LangGraph v2

Упрощённый flow:
                    ┌─ chitchat/out_of_scope/clarification ─► Responder ──► END
                    │
Question ─► Understander ─┤
                    │
                    └─ data ─► QueryBuilder ─► DataFetcher ─► Analyst ─► Validator ─► END

Преимущества:
- Нет SQL Agent (LLM для генерации SQL)
- Нет SQL Validator + retry loop
- QueryBuilder генерирует SQL детерминированно
- Быстрее и надёжнее
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from agent.state import AgentState, create_initial_state
from agent.agents.understander import Understander, query_spec_to_builder
from agent.agents.data_fetcher import DataFetcher
from agent.agents.analyst import Analyst
from agent.agents.validator import Validator
from agent.query_builder import QueryBuilder
from agent.checkpointer import get_checkpointer


# =============================================================================
# Initialize agents (singletons)
# =============================================================================

understander = Understander()
query_builder = QueryBuilder()
data_fetcher = DataFetcher()
analyst = Analyst()
validator = Validator()


# =============================================================================
# Node Functions
# =============================================================================

def understand_question(state: AgentState) -> Command:
    """
    Understander node — парсит вопрос и возвращает query_spec.

    Routing:
    - chitchat/out_of_scope/concept/clarification → responder
    - data с query_spec → query_builder
    - data без query_spec → data_fetcher (простые запросы)
    """
    result = understander(state)
    intent = result.get("intent") or {}
    intent_type = intent.get("type", "data")

    # Определяем следующий node
    if intent_type in ("chitchat", "out_of_scope", "concept", "clarification"):
        next_node = "responder"
    elif intent.get("query_spec"):
        next_node = "query_builder"
    else:
        # Простой запрос без query_spec — сразу в data_fetcher
        next_node = "data_fetcher"

    return Command(update=result, goto=next_node)


def build_query(state: AgentState) -> dict:
    """
    QueryBuilder node — строит SQL из query_spec.

    Детерминированно, без LLM, всегда валидный SQL.
    """
    intent = state.get("intent") or {}
    query_spec_dict = intent.get("query_spec", {})

    try:
        # Конвертируем JSON в объект QuerySpec
        query_spec = query_spec_to_builder(query_spec_dict)

        # Строим SQL
        sql = query_builder.build(query_spec)

        return {
            "sql_query": sql,
            "agents_used": ["query_builder"],
            "step_number": state.get("step_number", 0) + 1,
        }

    except Exception as e:
        print(f"[QueryBuilder] Error: {e}")
        # Fallback — пустой SQL, data_fetcher использует дефолтный
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


def simple_respond(state: AgentState) -> dict:
    """
    Responder node — для chitchat/out_of_scope/concept/clarification.
    Без данных, просто возвращает response_text.
    """
    intent = state.get("intent") or {}

    response_text = intent.get(
        "response_text",
        "Чем могу помочь с анализом торговых данных?"
    )

    result = {
        "response": response_text,
        "agents_used": ["responder"],
    }

    # Suggestions для clarification (кнопки в UI)
    if intent.get("suggestions"):
        result["suggestions"] = intent.get("suggestions")

    return result


# =============================================================================
# Conditional Edges
# =============================================================================

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
    """Строит граф агентов."""

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("understander", understand_question)
    graph.add_node("responder", simple_respond)
    graph.add_node("query_builder", build_query)
    graph.add_node("data_fetcher", fetch_data)
    graph.add_node("analyst", analyze_data)
    graph.add_node("validator", validate_response)

    # START → understander
    graph.add_edge(START, "understander")

    # understander использует Command API для routing

    # responder → END
    graph.add_edge("responder", END)

    # query_builder → data_fetcher → analyst → validator
    graph.add_edge("query_builder", "data_fetcher")
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
        chat_history: list = None,
    ) -> AgentState:
        """Синхронный запуск графа."""
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

    def stream_sse(
        self,
        question: str,
        user_id: str,
        session_id: str = "default",
        chat_history: list = None,
    ):
        """
        Streaming с SSE событиями для frontend.

        Events:
        - step_start: агент начал работу
        - step_end: агент закончил
        - text_delta: текст ответа
        - usage: токены
        - done: завершение
        """
        import time

        start_time = time.time()
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

        accumulated_state = {
            "question": question,
            "chat_history": chat_history,
        }

        for event in self.app.stream(initial_state, config, stream_mode=["updates", "custom"]):
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

                # step_start
                yield {
                    "type": "step_start",
                    "agent": node_name,
                    "message": self._get_agent_message(node_name)
                }

                # Обработка по типу node
                if node_name == "understander":
                    intent = updates.get("intent") or {}
                    usage = updates.get("usage") or {}
                    query_spec = intent.get("query_spec", {})

                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {
                            "type": intent.get("type"),
                            "symbol": "NQ",
                            "source": query_spec.get("source"),
                            "grouping": query_spec.get("grouping"),
                            "special_op": query_spec.get("special_op"),
                        },
                        "output": {
                            "intent": intent,
                            "usage": usage,
                        }
                    }
                    accumulated_state["intent"] = intent

                elif node_name == "query_builder":
                    sql_query = updates.get("sql_query")
                    error = updates.get("query_builder_error")

                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
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
                    yield {
                        "type": "step_end",
                        "agent": node_name,
                        "duration_ms": step_duration_ms,
                        "result": {
                            "rows": data_result.get("row_count", 0),
                            "granularity": data_result.get("granularity"),
                        },
                        "output": data_result
                    }
                    accumulated_state["data"] = data_result

                elif node_name == "analyst":
                    response = updates.get("response") or ""
                    stats = updates.get("stats") or {}
                    usage = updates.get("usage") or {}

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
                    accumulated_state["response"] = response

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
                    suggestions = updates.get("suggestions") or []

                    # Stream response
                    chunk_size = 50
                    for i in range(0, len(response), chunk_size):
                        yield {
                            "type": "text_delta",
                            "agent": node_name,
                            "content": response[i:i+chunk_size]
                        }

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
                        "output": {"response": response, "suggestions": suggestions}
                    }

        # Final events
        duration_ms = int((time.time() - start_time) * 1000)
        final_state = self.app.get_state(config)
        usage = (final_state.values.get("usage") or {}) if final_state else {}

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
        """Возвращает сообщение для агента."""
        messages = {
            "understander": "Understanding question...",
            "responder": "Responding...",
            "query_builder": "Building SQL query...",
            "data_fetcher": "Fetching data...",
            "analyst": "Analyzing data...",
            "validator": "Validating response...",
        }
        return messages.get(agent, f"Running {agent}...")


# Singleton
trading_graph = TradingGraph()
