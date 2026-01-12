# Multi-Agent Architecture v2 для AskBar

## Концепция

**AskBar** — "ChatGPT для трейдеров". Пользователь задаёт вопрос на естественном языке, система анализирует исторические данные и даёт ответ с реальной статистикой.

---

## Проблемы текущей системы (v1)

### Архитектурные
1. **LLM пишет SQL** → галлюцинирует, возвращает 10k сырых баров вместо агрегации
2. **Нет уточнений** — один выстрел, надежда что угадали
3. **Тупой роутинг** — Router просто классифицирует, не думает
4. **Validator постфактум** — проверяет когда уже поздно

### Примеры проблем
```
User: "Покажи статистику за март"
System: SELECT * FROM ohlcv_1min ... LIMIT 10000
Result: 10,000 сырых баров вместо дневной агрегации

User: "Что было после роста на 15%?"
System: ??? (не понимает что это многошаговый анализ)
```

---

## Новая архитектура v2

### Ключевой принцип

**LLM решает ЧТО получить, КОД решает КАК.**

```
LLM: "Нужны дневные stats по NQ за март"
     ↓
Структурированный запрос: {action: "get_period_stats", params: {...}}
     ↓
КОД строит SQL: SELECT date_trunc('day'...) GROUP BY day...
```

LLM **никогда не пишет SQL**. Только выбирает действия и параметры.

---

## Граф агентов v2

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  User Question + Chat History                                      │
│       │                                                            │
│       ↓                                                            │
│  ┌──────────────┐                                                  │
│  │ Understander │ Что хочет пользователь?                          │
│  │              │ Достаточно ли информации?                        │
│  └──────────────┘                                                  │
│       │                                                            │
│       ├─→ Нужно уточнить → [INTERRUPT: вопрос юзеру] ←─────┐      │
│       │                              │                      │      │
│       │                              ↓                      │      │
│       │                    User отвечает → назад            │      │
│       │                                                     │      │
│       ↓ Понятно                                             │      │
│  ┌──────────────┐                                           │      │
│  │   Planner    │ Какие данные нужны?                       │      │
│  │              │ Какая гранулярность?                      │      │
│  │              │ Сколько шагов?                            │      │
│  └──────────────┘                                           │      │
│       │                                                     │      │
│       ↓ Структурированный план                              │      │
│  ┌──────────────┐                                           │      │
│  │Query Builder │ ← ЭТО КОД, НЕ LLM!                        │      │
│  │              │ План → SQL запросы                        │      │
│  └──────────────┘                                           │      │
│       │                                                     │      │
│       ↓                                                     │      │
│  ┌──────────────┐                                           │      │
│  │   Executor   │ Выполняет SQL                             │      │
│  │              │ Собирает данные                           │      │
│  │              │ (цикл если несколько шагов)               │      │
│  └──────────────┘                                           │      │
│       │                                                     │      │
│       ├─→ Нет данных → [INTERRUPT: "Данных нет, изменить?"] │      │
│       │                                                     │      │
│       ↓ Данные есть                                         │      │
│  ┌──────────────┐                                           │      │
│  │   Analyst    │ Интерпретирует данные                     │      │
│  │              │ Формирует ответ                           │      │
│  └──────────────┘                                           │      │
│       │                                                     │      │
│       ↓                                                     │      │
│  ┌──────────────┐                                           │      │
│  │  Validator   │ Ответ соответствует данным?               │      │
│  └──────────────┘                                           │      │
│       │                                                     │      │
│       ├─→ OK → Response                                     │      │
│       ├─→ Rewrite → назад к Analyst с feedback              │      │
│       └─→ Need more data → назад к Planner ─────────────────┘      │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Агенты: роли и ответственности

### 1. Understander (Понимающий)

**Задача:** Понять что хочет пользователь, решить нужно ли уточнять.

**Input:**
- question: текущий вопрос
- chat_history: история диалога

**Output:**
```python
{
    "intent": {
        "type": "data_query" | "concept" | "complex_analysis",
        "symbol": "NQ" | None,
        "period": {...} | None,
        "metrics": [...] | None,
        "analysis_type": "stats" | "pattern" | "backtest" | None
    },
    "needs_clarification": bool,
    "clarifying_questions": ["За какой период?", ...],
    "confidence": 0.0-1.0
}
```

**Когда уточнять:**
- Не указан символ и непонятно из контекста
- Не указан период для data_query
- Неоднозначный вопрос ("большое движение" - сколько?)
- Сложный анализ требует деталей

**Когда НЕ уточнять (использовать defaults):**
- Очевидный контекст из истории
- Есть разумный default (последний месяц)
- Простой вопрос с понятным intent

---

### 2. Planner (Планировщик)

**Задача:** Превратить понятый intent в структурированный план действий.

**Input:**
- intent от Understander
- available_data: какие данные есть в базе

**Output:**
```python
{
    "steps": [
        {
            "action": "get_period_stats",
            "params": {
                "symbol": "NQ",
                "start_date": "2025-03-01",
                "end_date": "2025-04-01",
                "granularity": "daily",
                "metrics": ["open", "close", "high", "low", "volume"]
            }
        }
    ]
}
```

**Доступные actions:**
```python
# Получение данных
"get_period_stats"      # Агрегированная статистика за период
"get_intraday_data"     # Данные внутри дня (сырые бары)
"get_price_extremes"    # MIN/MAX за период
"get_volume_profile"    # Распределение объёма

# Сложный анализ
"find_events"           # Найти события по условию (рост >15%)
"get_periods_after"     # Данные после найденных событий
"compare_periods"       # Сравнить два периода
"aggregate_patterns"    # Агрегировать паттерны
```

**Правила гранулярности:**
| Период | Гранулярность |
|--------|---------------|
| > 1 год | weekly |
| 1-12 месяцев | daily |
| 1-7 дней | hourly |
| < 1 дня | 1min (raw) |

---

### 3. Query Builder (Строитель запросов) — КОД, НЕ LLM!

**Задача:** Детерминированно превратить структурированный план в SQL.

```python
def build_query(step: dict) -> str:
    action = step["action"]
    params = step["params"]

    if action == "get_period_stats":
        granularity = params.get("granularity", "daily")

        if granularity == "daily":
            return f"""
                SELECT
                    date_trunc('day', timestamp) as day,
                    FIRST_VALUE(open) OVER (PARTITION BY date_trunc('day', timestamp) ORDER BY timestamp) as open,
                    MAX(high) as high,
                    MIN(low) as low,
                    LAST_VALUE(close) OVER (PARTITION BY date_trunc('day', timestamp) ORDER BY timestamp) as close,
                    SUM(volume) as volume
                FROM ohlcv_1min
                WHERE symbol = '{params["symbol"]}'
                  AND timestamp >= '{params["start_date"]}'
                  AND timestamp < '{params["end_date"]}'
                GROUP BY date_trunc('day', timestamp)
                ORDER BY day
            """
        elif granularity == "hourly":
            # ...

    elif action == "find_events":
        condition = params["condition"]
        # Парсим condition и строим SQL
        # ...
```

**Почему КОД а не LLM:**
- Детерминированный результат
- Нет галлюцинаций
- Легко тестировать
- Гарантированно правильная агрегация

---

### 4. Executor (Исполнитель)

**Задача:** Выполнить SQL запросы, собрать результаты.

**Input:**
- plan от Planner
- built_queries от Query Builder

**Output:**
```python
{
    "results": [
        {
            "step": 0,
            "action": "get_period_stats",
            "query": "SELECT ...",
            "data": [...],
            "row_count": 31,
            "duration_ms": 45
        }
    ],
    "total_rows": 31,
    "has_data": True
}
```

**Валидация результатов:**
- Если 0 строк → может предложить расширить период
- Если ошибка SQL → логировать, вернуть ошибку
- Если слишком много данных → предупредить (но не лимитировать искусственно)

---

### 5. Analyst (Аналитик)

**Задача:** Интерпретировать данные, написать ответ пользователю.

**Input:**
- original_question
- intent
- data от Executor

**Output:**
- Текстовый ответ с выводами

**Правила:**
- ТОЛЬКО факты из полученных данных
- Никаких выдуманных цифр
- Если данных мало — сказать об этом
- Ссылаться на конкретные даты/значения

---

### 6. Validator (Валидатор)

**Задача:** Проверить что ответ соответствует данным.

**Input:**
- data от Executor
- response от Analyst
- original_question

**Output:**
```python
{
    "status": "ok" | "rewrite" | "need_more_data",
    "issues": ["Дата 2025-03-15 не найдена в данных"],
    "feedback": "Убери упоминание 2025-03-15, этой даты нет в выборке"
}
```

---

## Human-in-the-Loop: точки прерывания

### 1. Уточнение вопроса (Understander)

```python
def understander(state):
    intent = analyze_intent(state["question"], state["chat_history"])

    if intent["needs_clarification"]:
        return interrupt({
            "type": "clarification",
            "message": "Уточни пожалуйста:",
            "questions": intent["clarifying_questions"],
            "suggestions": ["NQ за последний месяц", "ES за неделю"]
        })

    return {"intent": intent}
```

### 2. Нет данных (Executor)

```python
def executor(state):
    results = execute_queries(state["queries"])

    if results["total_rows"] == 0:
        return interrupt({
            "type": "no_data",
            "message": f"Данных по {state['intent']['symbol']} за этот период нет.",
            "suggestions": [
                "Расширить период",
                "Посмотреть другой инструмент",
                "Показать доступные данные"
            ]
        })

    return {"data": results}
```

### 3. Подтверждение сложного анализа (Planner)

```python
def planner(state):
    plan = create_plan(state["intent"])

    if len(plan["steps"]) > 3:  # Сложный анализ
        return interrupt({
            "type": "confirm_plan",
            "message": "Это сложный анализ из нескольких шагов:",
            "plan_summary": summarize_plan(plan),
            "options": ["Выполнить", "Упростить", "Отмена"]
        })

    return {"plan": plan}
```

---

## State Schema

```python
from typing import TypedDict, Optional, Literal
from langgraph.graph import MessagesState

class TradingState(TypedDict):
    # Input
    question: str
    chat_history: list[dict]
    user_id: str
    session_id: str
    request_id: str

    # Understander output
    intent: Optional[dict]
    needs_clarification: bool
    clarifying_questions: list[str]

    # Planner output
    plan: Optional[dict]  # {steps: [...]}

    # Query Builder output (derived, not LLM)
    queries: list[str]

    # Executor output
    data: Optional[dict]  # {results: [...], total_rows: int}
    execution_errors: list[str]

    # Analyst output
    response: str

    # Validator output
    validation: Optional[dict]  # {status, issues, feedback}
    validation_attempts: int

    # Meta
    current_agent: str
    agents_used: list[str]

    # Usage tracking
    usage: dict  # {input_tokens, output_tokens, cost}
```

---

## Сценарии использования

### Сценарий 1: Простой запрос
```
User: "Статистика NQ за март 2025"

Understander:
  → intent: {type: "data_query", symbol: "NQ", period: "2025-03", metrics: "all"}
  → needs_clarification: false

Planner:
  → steps: [{action: "get_period_stats", params: {symbol: "NQ", ...granularity: "daily"}}]

Query Builder (код):
  → SELECT date_trunc('day'...) GROUP BY day

Executor:
  → 31 rows, has_data: true

Analyst:
  → "В марте 2025 NQ показал следующую динамику..."

Validator:
  → status: ok

→ Response
```

### Сценарий 2: Нужно уточнение
```
User: "Покажи статистику"

Understander:
  → intent: {type: "data_query", symbol: null, period: null}
  → needs_clarification: true
  → questions: ["Какой инструмент?", "За какой период?"]

[INTERRUPT]

User: "NQ за последний месяц"

Understander:
  → intent: {type: "data_query", symbol: "NQ", period: "last_month"}
  → needs_clarification: false

→ продолжение...
```

### Сценарий 3: Сложный анализ
```
User: "Что было на следующей неделе после роста на 15%?"

Understander:
  → intent: {type: "complex_analysis", analysis: "post_event"}
  → needs_clarification: true
  → questions: ["15% рост за день или за неделю?", "Какой инструмент?"]

User: "Дневной рост, NQ, за последний год"

Planner:
  → steps: [
      {action: "find_events", params: {condition: "daily_change > 0.15"}},
      {action: "get_periods_after", params: {offset_days: 7}},
      {action: "aggregate_patterns"}
    ]

Query Builder (код):
  → Multiple queries...

Executor:
  → 5 events found, week-after data collected

Analyst:
  → "Найдено 5 случаев роста >15% за день. После них..."
```

### Сценарий 4: Нет данных
```
User: "NQ за 2010 год"

Understander:
  → intent: {type: "data_query", symbol: "NQ", period: "2010"}

Planner:
  → steps: [{action: "get_period_stats", ...}]

Executor:
  → 0 rows, has_data: false

[INTERRUPT]
  → "Данных по NQ за 2010 нет. Данные доступны с 2015. Показать за 2015?"

User: "Да"

→ продолжение с 2015...
```

### Сценарий 5: Концепт (без данных)
```
User: "Что такое RSI?"

Understander:
  → intent: {type: "concept", topic: "RSI"}

→ Skip Planner, Executor
→ Go to Educator agent

Educator:
  → "RSI (Relative Strength Index) — это осциллятор..."
```

---

## Модели по агентам

| Агент | Модель | Почему | ~Цена/запрос |
|-------|--------|--------|--------------|
| Understander | Gemini Flash | Быстрый, понимание intent | $0.0005 |
| Planner | Gemini Flash | Структурированный output | $0.0005 |
| Query Builder | **КОД** | Детерминированный | $0 |
| Executor | **КОД** | SQL выполнение | $0 |
| Analyst | Gemini Pro / Flash | Качественный текст | $0.005 |
| Validator | Gemini Flash | Сверка фактов | $0.001 |
| Educator | Gemini Pro | Объяснения | $0.005 |

**Итого:** ~$0.01-0.02 за запрос (vs $0.01-0.015 сейчас)

---

## Хранение данных

### Таблицы (без изменений)
- `chat_logs` — финальные результаты
- `request_traces` — каждый шаг агента

### Что добавить в traces
```sql
-- Новые поля для v2
ALTER TABLE request_traces ADD COLUMN intent JSONB;
ALTER TABLE request_traces ADD COLUMN plan JSONB;
ALTER TABLE request_traces ADD COLUMN was_interrupted BOOLEAN DEFAULT FALSE;
ALTER TABLE request_traces ADD COLUMN interrupt_type TEXT;
ALTER TABLE request_traces ADD COLUMN user_response TEXT;
```

---

## SSE события для фронтенда

```python
# Уточнение (новое)
{
    "type": "clarification_needed",
    "questions": ["За какой период?"],
    "suggestions": ["Последний месяц", "Последняя неделя"]
}

# План (новое)
{
    "type": "plan_created",
    "steps": [
        {"action": "get_period_stats", "description": "Получить дневную статистику"}
    ]
}

# Остальные без изменений
{"type": "step_start", "agent": "executor", ...}
{"type": "sql_executed", "query": "...", "rows": 31}
{"type": "text_delta", "content": "..."}
{"type": "done", ...}
```

---

## Задачи на реализацию

### Фаза 1: Understander
- [ ] Создать `agent/agents/understander.py`
- [ ] Промпт для понимания intent
- [ ] Логика определения needs_clarification
- [ ] Интеграция с INTERRUPT

### Фаза 2: Planner
- [ ] Создать `agent/agents/planner.py`
- [ ] Определить все actions и их schemas
- [ ] Правила выбора гранулярности
- [ ] Промпт для создания плана

### Фаза 3: Query Builder (код)
- [ ] Создать `agent/query_builder.py`
- [ ] Функция для каждого action type
- [ ] Тесты на правильность SQL
- [ ] Защита от SQL injection (параметризация)

### Фаза 4: Обновить Executor
- [ ] Принимает план, не intent
- [ ] Выполняет несколько шагов
- [ ] INTERRUPT при 0 данных

### Фаза 5: Обновить граф
- [ ] Новые nodes: understander, planner
- [ ] Убрать router (understander заменяет)
- [ ] Conditional edges с INTERRUPT
- [ ] Loops для validation

### Фаза 6: Фронтенд
- [ ] Обработка clarification_needed
- [ ] UI для ответа на уточнения
- [ ] Показ плана пользователю

---

## Критерии успеха v2

### Качество
- [ ] Нет галлюцинаций SQL — LLM не пишет SQL вообще
- [ ] Правильная агрегация — daily/hourly автоматически
- [ ] Уточнения работают — система спрашивает когда надо
- [ ] Сложный анализ — многошаговые запросы работают

### UX
- [ ] Понятные уточняющие вопросы
- [ ] Suggestions помогают
- [ ] Пользователь видит план до выполнения

### Производительность
- [ ] Стоимость ~$0.02 за запрос
- [ ] Latency < 5 сек для простых запросов
- [ ] Latency < 15 сек для сложных

---

## Решения по архитектуре

### 1. Контекст из истории
Полная история нужна — может быть длинная цепочка рассуждений.

```python
# Understander получает
{
    "question": "А за апрель?",
    "chat_history": [
        {"role": "user", "content": "Покажи статистику NQ за март"},
        {"role": "assistant", "content": "В марте NQ..."},
    ]
}
# → Понимает: символ = NQ, период = апрель
```

### 2. Как Planner узнаёт какие данные есть
**Решение:** Сначала запросить, потом планировать.

```python
# Перед планированием Planner вызывает:
available_data = get_data_info()
# → {symbols: ["NQ"], date_range: "2015-2025", total_bars: 5_000_000}

# Затем планирует с учётом этого
```

Это позволяет:
- Не хардкодить символы в промпте
- Предупреждать если данных нет
- Масштабироваться при добавлении новых инструментов

### 3. Детализация плана для юзера
**Решение:** Максимально подробно. Показываем всё.

```
Создаю план:
1. Получить дневную статистику NQ за март 2025
   SQL: SELECT date_trunc('day'...) GROUP BY day
2. Рассчитать средние значения
3. Найти экстремумы
```

### 4. Retry стратегия
**TODO:** Решить позже. Варианты:
- Автоматически 2-3 попытки
- Спрашивать после первой ошибки
- Комбинация

### 5. SQL Agent вместо паттернов (для старта)

**Решение:** Не делаем библиотеку паттернов заранее.

Фаза 1:
- SQL Agent с хорошим промптом пишет любой SQL
- Логируем все запросы
- Смотрим что работает

Фаза 2:
- Видим повторяющиеся запросы в логах
- Превращаем частые в паттерны (оптимизация)

SQL Agent промпт включает:
- Схему таблицы ohlcv_1min
- Правила оптимизации (индексы, GROUP BY)
- Примеры хороших запросов
- Лимиты и ограничения

### 6. Function Calling

**Где использовать Gemini Function Calling:**

| Агент | Выход | Function Calling |
|-------|-------|------------------|
| Understander | intent (JSON) | ✅ Гарантирует схему |
| Planner | plan (JSON) | ✅ Гарантирует схему + вызывает get_data_info() |
| SQL Agent | SQL текст | ❌ Свободный текст |
| Executor | — | Код, не LLM |
| Analyst | текст | ❌ Свободный текст |
| Validator | validation (JSON) | ✅ Гарантирует схему |

**Пример для Understander:**
```python
PARSE_INTENT = types.FunctionDeclaration(
    name="parse_intent",
    description="Parse user question into structured intent",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "type": types.Schema(
                type=types.Type.STRING,
                enum=["data_query", "concept", "complex"]
            ),
            "symbol": types.Schema(type=types.Type.STRING),
            "period_start": types.Schema(type=types.Type.STRING),
            "period_end": types.Schema(type=types.Type.STRING),
            "needs_clarification": types.Schema(type=types.Type.BOOLEAN),
            "clarifying_questions": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(type=types.Type.STRING)
            ),
        },
        required=["type", "needs_clarification"]
    )
)
```

**Пример для Planner:**
```python
CREATE_PLAN = types.FunctionDeclaration(
    name="create_plan",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "steps": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "step_number": types.Schema(type=types.Type.INTEGER),
                        "description": types.Schema(type=types.Type.STRING),
                        "depends_on": types.Schema(type=types.Type.INTEGER),
                    }
                )
            ),
            "granularity": types.Schema(
                type=types.Type.STRING,
                enum=["1min", "hourly", "daily", "weekly"]
            ),
        }
    )
)

GET_DATA_INFO = types.FunctionDeclaration(
    name="get_data_info",
    description="Get available symbols and date ranges",
    parameters=types.Schema(type=types.Type.OBJECT, properties={})
)
```

**Преимущества:**
- Не парсим JSON из текста
- Схема гарантирована
- Меньше ошибок парсинга

### 7. Chat History — последние 10 сообщений

**Решение:** Не нужна вся история. Достаточно последних 10 сообщений.

```python
def get_context(messages):
    return messages[-10:]  # последние 10
```

**Почему:**
- Покрывает текущий контекст разговора
- Не раздувает промпт
- Пользователь не спрашивает "что я спрашивал месяц назад"

### 8. Validator через Claims

**Решение:** Analyst возвращает claims + response. Validator проверяет claims кодом.

**Analyst output (через function calling):**
```python
{
    "claims": [
        {"type": "percent", "value": 6.97, "context": "monthly change"},
        {"type": "max_price", "value": 21800, "date": "2025-03-22"},
        {"type": "avg_volume", "value": 1500000},
    ],
    "response": "В марте NQ вырос на 6.97%. Максимум 21800 был 22 марта."
}
```

**Validator (код, не LLM):**
```python
def validate_claims(claims: list, raw_data: list) -> ValidationResult:
    issues = []

    for claim in claims:
        if claim["type"] == "percent":
            actual = calculate_percent_change(raw_data)
            if abs(claim["value"] - actual) > 0.5:  # tolerance
                issues.append(f"Указано {claim['value']}%, реально {actual}%")

        elif claim["type"] == "max_price":
            actual_price, actual_date = find_max_price(raw_data)
            if claim["value"] != actual_price:
                issues.append(f"Макс цена {actual_price}, не {claim['value']}")
            if claim["date"] != actual_date:
                issues.append(f"Макс был {actual_date}, не {claim['date']}")

        elif claim["type"] == "avg_volume":
            actual = calculate_avg_volume(raw_data)
            if abs(claim["value"] - actual) / actual > 0.05:  # 5% tolerance
                issues.append(f"Средний объём {actual}, не {claim['value']}")

    if issues:
        return ValidationResult(status="rewrite", issues=issues)
    return ValidationResult(status="ok")
```

**Преимущества:**
- Analyst гибкий — работает с реальными данными
- Validator быстрый — код, не LLM
- Проверяемо — каждый факт верифицирован
- Юзер видит только response, claims — внутренняя механика

### 9. Расширяемость архитектуры

**Принцип:** Система всегда даёт полезный ответ. Если capability нет — честно говорит и предлагает альтернативу.

#### Mixed Mode — правильный подход

```
User: "Покажи RSI по NQ за март"

Understander:
  → intent: {
      type: "mixed",
      concept: "RSI",           # нужно объяснить
      data_request: true,       # хотят данные
      symbol: "NQ",
      period: "2025-03"
    }

Planner:
  → checks capabilities
  → has_rsi_calculation: false  # пока нет

Analyst:
  → "RSI (Relative Strength Index) — осциллятор импульса...

     К сожалению, расчёт RSI пока не реализован в системе.
     Могу показать сырые данные цен, по которым вы можете
     рассчитать RSI самостоятельно."
```

#### Три уровня расширяемости

**1. Новые индикаторы (RSI, MACD, Bollinger)**

```python
# Вариант A: Предрассчитанные (добавляем в data pipeline)
# Таблица indicators_daily: symbol, date, rsi_14, macd, bollinger_upper...

# Вариант B: Вычисляемые на лету (добавляем функцию)
def calculate_rsi(symbol: str, period: str, window: int = 14) -> DataFrame:
    """SQL Agent может вызвать эту функцию"""
    prices = get_closes(symbol, period)
    return compute_rsi(prices, window)
```

**2. Новые паттерны анализа**

```python
# patterns.py — библиотека растёт на основе реальных запросов
PATTERNS = {
    # Базовые (уже есть)
    "daily_stats": "SELECT date_trunc('day', ...) GROUP BY ...",
    "hourly_profile": "SELECT extract(hour from ...) GROUP BY ...",

    # Добавляем по мере надобности
    "gap_analysis": "SELECT ... WHERE open > prev_close * 1.01",
    "volume_spikes": "SELECT ... WHERE volume > avg_volume * 3",
    "price_levels": "SELECT ... найти уровни поддержки/сопротивления",
}
```

**3. Новые типы анализа**

```python
# Можно добавлять специализированных агентов
class TechnicalAnalyst(BaseAgent):
    """Анализ технических индикаторов"""

class PatternRecognizer(BaseAgent):
    """Распознавание свечных паттернов"""

class BacktestAgent(BaseAgent):
    """Бэктестинг стратегий"""
```

#### Capabilities Registry

```python
# capabilities.py — центральный реестр возможностей
CAPABILITIES = {
    # Данные
    "ohlcv": True,              # базовые OHLCV
    "daily_aggregation": True,   # агрегация по дням
    "hourly_aggregation": True,  # агрегация по часам

    # Индикаторы
    "rsi": False,               # пока нет
    "macd": False,              # пока нет
    "bollinger": False,         # пока нет
    "moving_averages": False,   # пока нет

    # Анализ
    "pattern_recognition": False,  # пока нет
    "backtesting": False,          # пока нет
    "correlation": False,          # пока нет
}

def check_capability(name: str) -> bool:
    return CAPABILITIES.get(name, False)
```

#### Процесс добавления новой фичи

```
1. Пользователь спрашивает → Нет capability → Логируем запрос
                                    ↓
2. Видим в логах: "RSI спрашивают 50 раз в неделю"
                                    ↓
3. Добавляем capability:
   - Функция calculate_rsi()
   - CAPABILITIES["rsi"] = True
   - Тесты
                                    ↓
4. Planner автоматически видит новую capability
                                    ↓
5. Mixed mode теперь выполняет полностью
```

#### Принцип graceful degradation

| Capability | Есть | Нет |
|------------|------|-----|
| RSI | Показываем RSI с графиком | Объясняем что такое RSI + предлагаем сырые данные |
| Бэктест | Выполняем бэктест | Объясняем как работает стратегия + показываем исторические данные |
| Паттерны | Находим паттерны | Объясняем паттерн + показываем данные для ручного поиска |

**Ключевое:** Архитектура не ломается от отсутствия фичи. Добавление = добавление кода, не переписывание системы.

### 10. Error Handling Strategy

**Принцип:** Юзер всегда получает ПОЛЬЗУ или ЧЕСТНОСТЬ (не бесполезный ответ).

```
Ошибка → Retry (если transient) → CODE fallback → Честное сообщение
```

#### Timeout Budget — 45 секунд на весь запрос

```python
TOTAL_TIMEOUT = 45  # секунд на весь запрос

AGENT_TIMEOUTS = {
    "understander": 8,   # быстрый
    "planner": 8,        # быстрый
    "sql_agent": 10,     # может думать
    "executor": 15,      # DB может тормозить
    "analyst": 12,       # генерация текста
    "validator": 5,      # простая проверка
}

def run_pipeline(question: str):
    deadline = time.time() + TOTAL_TIMEOUT

    for agent in pipeline:
        remaining = deadline - time.time()
        if remaining <= 5:  # меньше 5 сек — не успеем
            return partial_result_with_disclaimer(state)

        agent_timeout = min(remaining, AGENT_TIMEOUTS[agent.name])
        result = agent.run(timeout=agent_timeout)
```

#### CODE Fallbacks (гарантированно работают)

```python
def analyst_code_fallback(data: list[dict]) -> str:
    """Если Analyst упал — CODE генерирует базовую сводку"""
    df = pd.DataFrame(data)

    return f"""
**Автоматическая сводка** _(детальный анализ недоступен)_

Период: {df['timestamp'].min().date()} — {df['timestamp'].max().date()}
Записей: {len(df):,}
Цена: {df['low'].min():.2f} — {df['high'].max():.2f}
Изменение: {((df.iloc[-1]['close'] / df.iloc[0]['open']) - 1) * 100:+.2f}%
Средний объём: {df['volume'].mean():,.0f}
"""
```

#### Таблица обработки ошибок

| Ошибка | Retry? | Fallback | Сообщение юзеру |
|--------|--------|----------|-----------------|
| LLM Rate Limit | 2 раза, пауза 2с | — | _(прозрачно)_ |
| LLM Timeout | **НЕТ** | — | "Сервис медленно отвечает" |
| LLM Down | **НЕТ** | — | "Сервис недоступен" |
| DB Connection | 1 раз | — | _(прозрачно)_ |
| DB Timeout | **НЕТ** | Упростить запрос | "Уменьшите период" |
| SQL Syntax | **НЕТ** | Назад к Planner | _(прозрачно)_ |
| No Data | — | — | "Данных нет за период" |
| Understander Fail | — | INTERRUPT | "Уточните вопрос" |
| Planner Fail | — | Simple plan | _(прозрачно)_ |
| SQL Agent Fail | — | Назад к Planner | _(прозрачно)_ |
| Analyst Fail | — | **CODE summary** | _(авто-сводка)_ |
| Validator Fail | — | Skip + disclaimer | _(прозрачно)_ |

#### Partial Results

```python
def partial_result_with_disclaimer(state: AgentState) -> str:
    """Если не успели всё — показываем что есть"""

    if state.get("data"):
        # Есть данные, но Analyst не успел
        return analyst_code_fallback(state["data"]) + \
               "\n\n_Анализ не завершён из-за таймаута._"

    elif state.get("intent"):
        # Поняли вопрос, но данные не получили
        return "Не удалось получить данные. Попробуйте ещё раз."

    else:
        # Вообще ничего
        return "Не удалось обработать запрос. Попробуйте переформулировать."
```

#### Что НЕ делаем (и почему)

| Подход | Почему НЕ делаем |
|--------|------------------|
| Circuit Breaker | Слишком сложно для MVP, низкий трафик |
| Cache похожих вопросов | Опасно — может вернуть неверный ответ |
| Fallback Pro → Flash | Бесполезно — тот же провайдер, те же проблемы |
| Показать raw data | Бесполезно — 10k строк юзер не прочитает |
| Retry timeout ошибок | Бесполезно — если timeout, повтор тоже timeout |

#### Logging

```python
def log_error(error: Exception, context: dict, severity: str):
    # Всегда в traces
    log_to_traces(
        error_type=type(error).__name__,
        error_message=str(error),
        agent=context.get("agent"),
        request_id=context.get("request_id"),
        severity=severity
    )

    # Метрики
    increment_metric(f"errors.{type(error).__name__}")

# Severity
# low: ValidationSkipped, PartialResult
# medium: LLMTimeout, QueryTimeout
# high: LLMError, DBError
# critical: AllRetriesFailed (алерт)
```
