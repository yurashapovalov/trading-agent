# Orchestrator Architecture Refactoring

## Проблемы текущей архитектуры

### 1. Контекст теряется между агентами
```
Intent → Understander → Parser → Executor → Presenter
```
Каждый агент видит только часть контекста. Follow-up вопросы ломаются.

### 2. Дублирование логики
- Session logic в Understander И в Parser
- Language handling в Intent, Understander, Clarifier
- Examples дублируются в промптах

### 3. Слишком много точек принятия решений
- Intent решает: chitchat/concept/data
- Understander решает: understood/need_clarification
- Router решает: куда дальше
- Каждая точка — потенциальная потеря контекста

### 4. Clarification размазана
- Understander определяет ЧТО уточнить
- Clarifier формулирует вопрос
- Graph routing обрабатывает ответы
- State management в нескольких местах

---

## Новая архитектура: Orchestrator + Tools

### Принцип
**Один умный агент с полным контекстом + тупые tools**

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                          │
│                                                          │
│  Input:                                                  │
│    - current_message                                     │
│    - conversation_history (last 5 turns)                │
│    - previous_data_summary (что показали)               │
│    - user_preferences (из memory)                       │
│                                                          │
│  Capabilities:                                           │
│    - Понимает язык юзера                                │
│    - Понимает follow-up ("из них" = предыдущие данные)  │
│    - Решает нужна ли clarification                      │
│    - Генерит ВСЕ user-facing текст                      │
│    - Вызывает tools когда нужны данные                  │
│                                                          │
│  Tools:                                                  │
│    - parse_query(query) → ExecutionPlan                 │
│    - execute(plan) → Data                               │
│    - get_patterns_info(pattern) → Description           │
│    - get_events_info(event) → Description               │
└─────────────────────────────────────────────────────────┘
```

### Tools (не агенты, просто функции)

#### 1. parse_query
```python
def parse_query(query: str) -> ExecutionPlan:
    """
    Парсит natural language в структурированный план.

    Input: "top 10 Fridays by volatility in 2024"
    Output: ExecutionPlan(
        operations=[Operation(type="list", what="range", params={"n": 10, "sort": "desc"})],
        filters=[Filter(type="weekday", value=4), Filter(type="period", year=2024)]
    )

    Внутри: LLM call с domain-specific prompt.
    НЕ принимает решений — только парсит.
    """
```

#### 2. execute
```python
def execute(plan: ExecutionPlan) -> ExecutionResult:
    """
    Выполняет план, возвращает данные.

    Input: ExecutionPlan
    Output: ExecutionResult(rows=[...], summary={...})

    Детерминированная функция, без LLM.
    """
```

#### 3. get_patterns_info / get_events_info
```python
def get_patterns_info(pattern_name: str) -> str:
    """Возвращает описание паттерна из config."""

def get_events_info(event_type: str) -> str:
    """Возвращает описание события из config."""
```

---

## Flow примеры

### Example 1: Simple query
```
User: "покажи все пятницы 2024"

Orchestrator думает:
  - Язык: ru
  - Intent: data query
  - Понятно что хотят: list all Fridays in 2024
  - Clarification не нужна

Orchestrator actions:
  1. acknowledge: "Понял, вывожу все пятницы 2024..."
  2. call parse_query("list all Fridays in 2024")
  3. call execute(plan)
  4. format response with data
```

### Example 2: Follow-up query
```
User: "какие из них самые волатильные"
Context: previous_data_summary = "51 Friday in 2024, sorted by change"

Orchestrator думает:
  - Язык: ru
  - "из них" = из предыдущих 51 пятницы
  - Хотят: отсортировать по волатильности (range)
  - Полный запрос: "top Fridays by range from 2024"

Orchestrator actions:
  1. acknowledge: "Сортирую пятницы по волатильности..."
  2. call parse_query("list Fridays 2024 sorted by range descending")
  3. call execute(plan)
  4. format response
```

### Example 3: Needs clarification
```
User: "average range"

Orchestrator думает:
  - Язык: en
  - Intent: data query
  - НО: range сильно отличается RTH vs ETH
  - Нужна clarification

Orchestrator response:
  "Range differs significantly between sessions:
   - RTH: ~100 points
   - ETH: ~200 points
   Which session interests you?"

State: awaiting_clarification = true, original_query = "average range"
```

### Example 4: Chitchat
```
User: "спасибо"

Orchestrator думает:
  - Язык: ru
  - Intent: chitchat (благодарность)
  - Tools не нужны

Orchestrator response:
  "Пожалуйста! Обращайся если будут вопросы."
```

### Example 5: Concept explanation
```
User: "что такое OPEX"

Orchestrator думает:
  - Язык: ru
  - Intent: concept (объяснить термин)
  - Могу использовать get_events_info для деталей

Orchestrator actions:
  1. call get_events_info("OPEX")
  2. format explanation in Russian
```

---

## Миграция

### Phase 1: Подготовка tools

**Файлы:**
- `agent/tools/parser.py` — parse_query tool (wrapper над текущим Parser)
- `agent/tools/executor.py` — execute tool (wrapper над текущим Executor)
- `agent/tools/domain.py` — get_patterns_info, get_events_info

**Что делаем:**
- Извлекаем core logic из текущих агентов
- Оборачиваем в simple functions
- Убираем всю "умность" — только execution

### Phase 2: Orchestrator agent

**Файлы:**
- `agent/orchestrator.py` — новый главный агент
- `agent/prompts/orchestrator/base.md` — короткий base prompt
- `agent/prompts/orchestrator/chunks/` — RAP chunks

**Orchestrator prompt structure:**
```
<role>
Trading assistant для NQ futures.
Ты единственный агент который общается с юзером.
</role>

<context>
{conversation_history}
{previous_data_summary}
</context>

<tools>
- parse_query: парсит запрос в план
- execute: выполняет план
- get_patterns_info: информация о паттернах
- get_events_info: информация о событиях
</tools>

<behavior>
1. Всегда отвечай на языке юзера
2. Для data queries: сначала acknowledge, потом tools
3. Clarification только когда ДЕЙСТВИТЕЛЬНО неоднозначно
4. Follow-up понимай из контекста
</behavior>
```

### Phase 3: Новый LangGraph

**Файл:** `agent/graph.py`

```python
from langgraph.graph import StateGraph

def build_graph():
    graph = StateGraph(OrchestratorState)

    # Один node — orchestrator
    graph.add_node("orchestrator", orchestrator_node)

    # Tool nodes (вызываются через tool calling)
    graph.add_node("parse_query", parse_query_node)
    graph.add_node("execute", execute_node)

    # Routing based on tool calls
    graph.add_conditional_edges(
        "orchestrator",
        route_tool_calls,
        {
            "parse_query": "parse_query",
            "execute": "execute",
            "end": END,
        }
    )

    # Tools return to orchestrator
    graph.add_edge("parse_query", "orchestrator")
    graph.add_edge("execute", "orchestrator")

    graph.set_entry_point("orchestrator")
    return graph.compile()
```

### Phase 4: Cleanup

**Удаляем:**
- `agent/agents/intent.py` — больше не нужен
- `agent/agents/understander.py` — логика в orchestrator
- `agent/agents/clarifier.py` — логика в orchestrator
- `agent/agents/responder.py` — логика в orchestrator
- `agent/agents/presenter.py` — логика в orchestrator

**Оставляем (как tools):**
- `agent/agents/parser.py` → `agent/tools/parser.py`
- `agent/executor.py` → `agent/tools/executor.py`

**Рефакторим:**
- `agent/prompts/` — только orchestrator + parser prompts
- `agent/graph.py` — новый простой граф

---

## State

```python
class OrchestratorState(TypedDict):
    # Input
    messages: list[BaseMessage]
    user_id: str
    chat_id: str

    # Context (built at start)
    conversation_history: list[dict]  # [{role, content}, ...]
    previous_data_summary: str | None  # "51 Fridays 2024, sorted by change"
    user_language: str  # detected from first message

    # Tool results
    execution_plan: ExecutionPlan | None
    execution_result: ExecutionResult | None

    # Output
    response: str | None
    data_card: DataCard | None

    # Clarification
    awaiting_clarification: bool
    clarification_context: str | None
```

---

## Метрики успеха

1. **Follow-up работает:** "из них", "что это значит" понимаются корректно
2. **Latency:** Первый acknowledge < 500ms (сейчас ~800ms)
3. **Код проще:** Меньше файлов, меньше routing logic
4. **Нет дублирования:** Session logic в одном месте

---

## Риски

1. **Orchestrator prompt слишком большой** → RAP для загрузки релевантных chunks
2. **Tool calling latency** → Можно кэшировать parse_query для похожих запросов
3. **Регрессии** → Нужны integration tests для всех use cases

---

## Порядок работы

1. [ ] Написать tools (parser, executor, domain)
2. [ ] Написать orchestrator prompt
3. [ ] Реализовать новый graph
4. [ ] Integration tests
5. [ ] Миграция trading_graph.py
6. [ ] Cleanup старых файлов
7. [ ] Frontend адаптация (если нужна)

---

## Оценка объёма

- **Phase 1 (tools):** 2-3 часа — в основном рефакторинг существующего кода
- **Phase 2 (orchestrator):** 4-6 часов — новый агент + prompt engineering
- **Phase 3 (graph):** 2-3 часа — новый граф
- **Phase 4 (cleanup):** 1-2 часа — удаление старого
- **Testing:** 2-3 часа — проверка всех use cases

**Итого:** ~15-20 часов работы

Можно делать инкрементально — Phase 1-2 уже дадут улучшение.
