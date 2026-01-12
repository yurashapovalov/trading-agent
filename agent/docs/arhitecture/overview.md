# AskBar v2 Overview

Multi-agent trading analytics system.

## Core Principle

**LLM решает ЧТО, код решает КАК**

| Agent | Type | Purpose |
|-------|------|---------|
| Understander | LLM | Парсит вопрос → Intent |
| DataFetcher | Code | Intent → данные из БД |
| Analyst | LLM | Данные → ответ + Stats (включая фильтрацию по search_condition) |
| Validator | Code | Проверяет Stats |

## Data Flow

```
User Question
     │
     ▼
┌─────────────────┐
│  Understander   │  "Как NQ в январе?" → Intent(type=data, daily)
└────────┬────────┘  "Найди падения >2%" → Intent(type=data, daily, search_condition="...")
         │
         ▼
┌─────────────────┐
│  DataFetcher    │  Intent → SQL → rows
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Analyst      │  rows + search_condition → filters → response + Stats
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Validator     │  Stats vs Data → OK or Rewrite
└────────┬────────┘
         │
         ▼
      Response
```

## Files Structure

```
agent/
├── state.py             # AgentState, Intent, Stats
├── graph.py             # LangGraph pipeline
├── capabilities.py      # DATA_CAPABILITIES
├── agents/
│   ├── understander.py  # LLM
│   ├── data_fetcher.py  # Code
│   ├── analyst.py       # LLM
│   └── validator.py     # Code
├── prompts/
│   ├── understander.py
│   └── analyst.py
├── modules/
│   └── sql.py           # DuckDB queries
└── docs/
    ├── overview.md      # (this file)
    ├── agents/
    │   ├── understander.md
    │   ├── data_fetcher.md
    │   ├── analyst.md
    │   └── validator.md
    └── modules/
        └── sql.md
```

## Quick Start

```python
from agent.graph import TradingGraph

graph = TradingGraph()

# Sync invoke
result = graph.invoke(
    question="Как NQ вел себя в январе 2024?",
    user_id="user123",
    session_id="session1"
)
print(result["response"])

# Stream SSE
for event in graph.stream_sse(question, user_id, session_id):
    if event["type"] == "text_delta":
        print(event["content"], end="")
```

## Intent Types

| Type | Description | Example |
|------|-------------|---------|
| `data` | Data queries + search | "Как NQ в январе?", "Найди падения >2%" |
| `concept` | Explain concepts | "Что такое MACD?" |
| `chitchat` | Small talk | "Привет!" |
| `out_of_scope` | Non-trading questions | "Какая погода?" |

## Search Queries

Для поисковых запросов ("найди", "когда", "покажи дни где..."):

```python
Intent(
    type="data",
    granularity="daily",
    search_condition="days where change_pct < -2% AND previous day > +1%"
)
```

- DataFetcher отдаёт ВСЕ дневные данные
- Analyst фильтрует по search_condition
- Никакого хардкода паттернов - любой запрос работает

## Granularity

| Value | Returns | Use Case |
|-------|---------|----------|
| `period` | 1 aggregated row | "За месяц вырос на X%" |
| `daily` | 1 row per day | "По дням", поиск паттернов |
| `hourly` | 1 row per hour | "Какой час самый волатильный" |
| `weekday` | 1 row per weekday | "Понедельник vs пятница" |
| `monthly` | 1 row per month | "По месяцам за год" |

## Validation Loop

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
      END   Analyst (fix errors)
              │
              ▼
           Validator (again)
              │
           Max 3 attempts
```

## Testing

```bash
python test_v2.py
```

## API

```python
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, user_id: str):
    for event in trading_graph.stream_sse(
        question=request.message,
        user_id=user_id,
        session_id=request.session_id
    ):
        yield f"data: {json.dumps(event)}\n\n"
```

## SSE Events

| Type | Description |
|------|-------------|
| `step_start` | Agent starting |
| `step_end` | Agent finished |
| `text_delta` | Response chunk |
| `validation` | Validation result |
| `usage` | Token usage |
| `done` | Complete |
