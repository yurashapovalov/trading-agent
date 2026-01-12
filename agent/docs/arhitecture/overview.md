# AskBar v2 Overview

Multi-agent trading analytics system.

## Core Principle

**LLM решает ЧТО, код решает КАК и ПРОВЕРЯЕТ**

| Agent | Type | Purpose |
|-------|------|---------|
| Understander | LLM | Парсит вопрос → Intent |
| Clarification | Interrupt | Human-in-the-loop - уточняет вопрос |
| SQL Agent | LLM | Intent → SQL запрос |
| SQL Validator | Code | Проверяет SQL |
| DataFetcher | Code | Выполняет SQL → данные |
| Analyst | LLM | Данные → ответ + Stats |
| Validator | Code | Проверяет Stats |

## Architecture Symmetry

```
┌─────────────┐     ┌─────────────────┐
│  SQL Agent  │ ←── │  SQL Validator  │
│   (LLM)     │ ──→ │     (Code)      │
└─────────────┘     └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   DataFetcher   │
                    │     (Code)      │
                    └────────┬────────┘
                             │
                             ▼
┌─────────────┐     ┌─────────────────┐
│   Analyst   │ ←── │    Validator    │
│   (LLM)     │ ──→ │     (Code)      │
└─────────────┘     └─────────────────┘
```

**Симметрия:**
- SQL Agent генерирует SQL → SQL Validator проверяет
- Analyst генерирует ответ → Validator проверяет

**DataFetcher** - центральный хаб, выполняет валидный SQL и отдаёт данные.

## Data Flow

### Standard Query (без search_condition)

```
User Question: "Как NQ вел себя в январе 2024?"
     │
     ▼
┌─────────────────┐
│  Understander   │  → Intent(type=data, daily, period=январь)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DataFetcher    │  → стандартный SQL шаблон → 22 строки
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│    Analyst      │ ←─→ │    Validator    │  retry loop
└────────┬────────┘     └─────────────────┘
         │
         ▼
      Response
```

### Search Query (с search_condition)

```
User Question: "Найди дни когда NQ упал >2% после роста >1%"
     │
     ▼
┌─────────────────┐
│  Understander   │  → Intent(search_condition="...")
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│   SQL Agent     │ ←─→ │  SQL Validator  │  retry loop
└────────┬────────┘     └─────────────────┘
         │ ✓ валидный SQL
         ▼
┌─────────────────┐
│  DataFetcher    │  → выполняет SQL → 77 строк
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│    Analyst      │ ←─→ │    Validator    │  retry loop
└────────┬────────┘     └─────────────────┘
         │
         ▼
      Response
```

## Why This Architecture?

**Проблема:** LLM ненадёжен для точных задач.
- SQL Agent может сгенерировать неправильный SQL
- Analyst может неправильно посчитать числа

**Решение:** Код валидирует результаты LLM.
- SQL Validator проверяет SQL перед выполнением
- Validator проверяет Stats перед ответом

**Результат:** Точные данные, надёжные ответы.

## Files Structure

```
agent/
├── state.py             # AgentState, Intent, Stats
├── graph.py             # LangGraph pipeline
├── agents/
│   ├── understander.py  # LLM - парсит вопрос
│   ├── sql_agent.py     # LLM - генерирует SQL
│   ├── sql_validator.py # Code - проверяет SQL
│   ├── data_fetcher.py  # Code - выполняет SQL
│   ├── analyst.py       # LLM - анализирует данные
│   └── validator.py     # Code - проверяет stats
├── prompts/
│   ├── understander.py
│   ├── sql_agent.py
│   └── analyst.py
├── modules/
│   └── sql.py           # DuckDB шаблоны запросов
└── docs/
    └── arhitecture/
        ├── overview.md
        └── agents/
            ├── understander.md
            ├── sql_agent.md
            ├── sql_validator.md
            ├── data_fetcher.md
            ├── analyst.md
            └── validator.md
```

## Agent Types

| Type | Agents | Purpose |
|------|--------|---------|
| LLM | Understander, SQL Agent, Analyst | Понимание, генерация |
| Code | SQL Validator, DataFetcher, Validator | Проверка, выполнение |

## Validation Loops

### SQL Validation Loop
```
SQL Agent generates SQL
         │
         ▼
SQL Validator checks syntax, safety
         │
     ┌───┴───┐
     │       │
    OK     Rewrite
     │       │
     ▼       ▼
DataFetcher  SQL Agent (fix errors)
                 │
                 ▼
            SQL Validator (again)
                 │
            Max 3 attempts
```

### Response Validation Loop
```
Analyst generates response with Stats
         │
         ▼
Validator checks Stats vs actual data
         │
     ┌───┴───┐
     │       │
    OK     Rewrite
     │       │
     ▼       ▼
   END    Analyst (fix errors)
              │
              ▼
          Validator (again)
              │
          Max 3 attempts
```

## Intent Types

| Type | Description | Example |
|------|-------------|---------|
| `data` | Data queries + search | "Как NQ в январе?", "Найди падения >2%" |
| `concept` | Explain concepts | "Что такое MACD?" |
| `chitchat` | Small talk | "Привет!" |
| `out_of_scope` | Non-trading questions | "Какая погода?" |

## Human-in-the-Loop

Когда Understander не может однозначно понять вопрос, он возвращает `needs_clarification: true`.

### Flow

```
User: "Покажи данные"
         │
         ▼
    Understander
         │
    needs_clarification: true
    clarification_question: "Какой символ и период?"
    suggestions: ["NQ за последний месяц", "ES за 2024"]
         │
         ▼
    Clarification (interrupt)
         │
    ← ждём ответ пользователя →
         │
         ▼
User: "NQ за январь 2024"
         │
         ▼
    Understander (re-parse)
         │
         ▼
    ... нормальный flow ...
```

### Implementation

Использует LangGraph `interrupt()` функцию:

```python
def ask_clarification(state):
    question = intent.get("clarification_question")
    suggestions = intent.get("suggestions", [])

    # Прерывает flow, ждёт ответа
    user_response = interrupt({
        "question": question,
        "suggestions": suggestions
    })

    return {"question": user_response}
```

### Resume

```python
# Frontend получает clarification_needed событие
# После ответа пользователя:
graph.resume_with_clarification(
    user_response="NQ за январь 2024",
    user_id="user123",
    session_id="session1"
)
```

### Limits

- Max 3 clarification attempts
- После лимита - fallback to default Intent

## Granularity

| Value | Returns | Use Case |
|-------|---------|----------|
| `period` | 1 aggregated row | "За месяц вырос на X%" |
| `daily` | 1 row per day | "По дням", поиск паттернов |
| `hourly` | 1 row per hour | "Какой час самый волатильный" |
| `weekday` | 1 row per weekday | "Понедельник vs пятница" |
| `monthly` | 1 row per month | "По месяцам за год" |

## Future: Technical Indicators

Архитектура расширяется для сложных индикаторов:

```
Understander
     │
     ├─── SQL Agent ────→ SQL Validator ───┐
     ├─── RSI Agent ────→ RSI Validator ───┼──→ DataFetcher
     ├─── MACD Agent ───→ MACD Validator ──┘
     └─── Pattern Agent → Pattern Validator
                                           │
                                           ▼
                                       Analyst
                                           │
                                           ▼
                                       Validator
```

Каждый LLM агент имеет свой Code валидатор.

## Quick Start

```python
from agent.graph import TradingGraph

graph = TradingGraph()

result = graph.invoke(
    question="Найди дни падения >2%",
    user_id="user123",
    session_id="session1"
)
print(result["response"])
```

## SSE Events

| Type | Description |
|------|-------------|
| `step_start` | Agent starting |
| `step_end` | Agent finished |
| `text_delta` | Response chunk |
| `sql_generated` | SQL Agent generated query |
| `sql_validated` | SQL Validator result |
| `validation` | Response validation result |
| `clarification_needed` | Need user input (human-in-the-loop) |
| `usage` | Token usage |
| `done` | Complete |

### clarification_needed Event

```json
{
  "type": "clarification_needed",
  "question": "Какой символ вас интересует?",
  "suggestions": ["NQ", "ES"],
  "thread_id": "user123_session1"
}
```

Frontend должен показать вопрос пользователю и после ответа вызвать `resume_with_clarification()`.
