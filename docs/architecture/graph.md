# Граф (LangGraph)

Агенты связаны в граф с условными переходами.

## Основной поток

```
START
  │
  ▼
┌─────────────┐
│   Intent    │ классифицируем намерение + язык
└──────┬──────┘
       │
       ▼
   ┌───────┐
   │ route │
   └───┬───┘
       │
       ├── data ────────────────────┐
       │                            │
       └── chitchat/concept ───► end │
                                    │
                                    ▼
                            ┌──────────┐
                            │  Parser  │ NL → структурированный запрос
                            └────┬─────┘
                                 │
                                 ▼
                            ┌──────────┐
                            │ Planner  │ запрос → план выполнения
                            └────┬─────┘
                                 │
                                 ▼
                            ┌──────────┐
                            │ Executor │ план → данные
                            └────┬─────┘
                                 │
                                 ▼
                                END
```

## Ноды

| Нода | Функция | Выход |
|------|---------|-------|
| `intent` | `classify_intent` | intent, lang, internal_query |
| `parser` | `parse_question` | parsed_query (steps), thoughts |
| `planner` | `plan_execution` | execution_plan (requests) |
| `executor` | `execute_query` | data (results) |
| `end` | `handle_end` | response (для non-data) |

## Роутинг

После Intent смотрим на результат:

| Intent | Куда |
|--------|------|
| `data` | Parser → Planner → Executor |
| `chitchat` | end |
| `concept` | end |

## State

Граф хранит состояние между шагами:

```python
class AgentState(TypedDict):
    # Input
    messages: list[dict]      # история сообщений

    # Intent
    intent: str               # data, chitchat, concept
    lang: str                 # ru, en
    internal_query: str          # вопрос на английском

    # Parser
    parsed_query: list[dict]  # steps с atoms
    parser_thoughts: str      # размышления LLM

    # Planner
    execution_plan: list[dict]  # DataRequest'ы
    plan_errors: list[str]      # ошибки планирования

    # Executor
    data: list[dict]          # результаты выполнения

    # Usage tracking
    usage: dict               # input/output tokens
```

## Edges

```python
graph.add_edge(START, "intent")
graph.add_conditional_edges("intent", route_after_intent)
graph.add_edge("parser", "planner")
graph.add_edge("planner", "executor")
graph.add_edge("executor", END)
graph.add_edge("end", END)
```

## Singleton

Граф компилируется один раз и переиспользуется:

```python
from agent.graph import get_graph

graph = get_graph()  # thread-safe singleton
result = graph.invoke({"messages": [{"role": "user", "content": "..."}]})
```
