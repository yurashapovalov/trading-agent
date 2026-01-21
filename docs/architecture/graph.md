# Граф (LangGraph)

Агенты связаны в граф с условными переходами.

## Основной поток

```
START
  │
  ▼
┌─────────────┐
│ load_memory │ загружаем контекст разговора
└──────┬──────┘
       │
       ▼
   ┌───────┐     awaiting_clarification?
   │ route │────────────────────────────┐
   └───┬───┘                            │
       │ new question                   │ user answered
       ▼                                ▼
┌──────────┐                    ┌────────────┐
│  Parser  │                    │ Clarifier  │
└────┬─────┘                    └─────┬──────┘
     │                                │
     ▼                                │ has clarified_query?
 ┌───────┐                            │
 │ route │                      ┌─────┴─────┐
 └───┬───┘                      │           │
     │                          ▼           ▼
     ├── chitchat ──► Responder    Parser   save_memory → END
     │                    │          │      (wait for more)
     ├── concept ───► Responder      │
     │                    │          │
     ├── unclear ───► Clarifier      │
     │                    │          │
     └── data ──────► Executor ◄─────┘
                          │
                          ▼
                     Presenter
                          │
                          ▼
                    save_memory
                          │
                          ▼
                         END
```

## Роутинг

После Parser смотрим на результат:

| Условие | Куда идём |
|---------|-----------|
| `intent == "chitchat"` | Responder |
| `intent == "concept"` | Responder |
| `unclear` не пустой | Clarifier |
| иначе | Executor |

## Clarification Loop

Если Clarifier не получил полный ответ — ждём следующее сообщение:

```
User: "статистика"
      ↓
Parser: unclear = ["period"]
      ↓
Clarifier: "За какой период?"
      → awaiting_clarification = true
      → END (ждём)

User: "2024"
      ↓
load_memory: awaiting_clarification? да
      ↓
Clarifier: "Ок, статистика за 2024"
      → clarified_query = "статистика за 2024"
      ↓
Parser: (парсит полный запрос)
      ↓
Executor → Presenter → END
```

## State

Граф хранит состояние между шагами:

```python
class TradingState:
    messages: list          # история сообщений
    session_id: str         # ID сессии
    parsed_query: dict      # результат Parser
    response: str           # финальный ответ
    
    # Clarification flow
    awaiting_clarification: bool
    clarified_query: str    # полный запрос после уточнения
```

State автоматически накапливает messages — не нужно передавать вручную.
