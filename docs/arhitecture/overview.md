# Trading Analytics Agent

Multi-agent system for trading data analysis using natural language.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Gemini 3 Flash (configurable via `GEMINI_MODEL` env var) |
| **Framework** | LangGraph (state machine) |
| **Backend** | FastAPI + SSE streaming |
| **Frontend** | Next.js 15 + React |
| **Database** | DuckDB (trading data) + Supabase (auth, logs) |
| **Deploy** | Hetzner VPS (backend) + Vercel (frontend) |

## Core Principles

**1. LLM классифицирует, не генерирует.**

Вместо генерации SQL, LLM выбирает из готовых "кубиков" (building blocks).
QueryBuilder детерминировано превращает кубики в SQL.

**2. Single Source of Truth.**

Все типы определены в `types.py`. JSON Schema для LLM генерируется автоматически.
Добавление нового кубика = изменение в одном месте.

**3. Hybrid Agent Architecture.**

LLM используется там где нужно понимание (NLU, генерация текста).
Детерминированный код — там где нужна надёжность (SQL, валидация).

## Architecture

```
                    ┌─ chitchat/concept/clarification ─► Responder ──► END
                    │
Question ─► Understander ─┼─────────────────────────────────────────────────────┐
                    │                                                            │
                    └─ data ─► QueryBuilder ─► DataFetcher ─► Analyst ─► Validator ─► END
                                                                 ↑_________| (retry)
```

## Agents

| Agent | Type | Purpose |
|-------|------|---------|
| **Understander** | LLM | Вопрос → query_spec (JSON кубиков) |
| **QueryBuilder** | Code | query_spec → SQL (детерминированно) |
| **DataFetcher** | Code | Выполняет SQL → данные |
| **Analyst** | LLM | Данные → ответ + Stats |
| **Validator** | Code | Проверяет Stats против данных |
| **Responder** | Code | Chitchat/concept/clarification ответы |

**Note:** Understander и Analyst используют одну модель (`GEMINI_MODEL`). Это упрощает конфигурацию.

## Query Spec — Кубики

Understander возвращает структурированную спецификацию:

```yaml
query_spec:
  source: minutes | daily | daily_with_prev
  filters:
    period_start: "2024-01-01"
    period_end: "2024-12-31"
    session: RTH | ETH | OVERNIGHT | ...
    weekdays: ["Monday", "Friday"]
    months: [1, 6, 12]
    conditions: [{column, operator, value}]
  grouping: none | total | 5min..hour | day..year | weekday | session
  metrics: [{metric, column, alias}]
  special_op: none | event_time | find_extremum | top_n | compare
  # Для special_op добавляются соответствующие spec:
  event_time_spec: {find: high | low | both}
  find_extremum_spec: {find: high | low | both}
  top_n_spec: {n: 10, order_by: range, direction: DESC}
```

QueryBuilder детерминированно превращает это в валидный SQL.

## Data Flow

```
User: "когда формируется high дня за RTH?"
     │
     ▼
Understander → query_spec:
     │           source: minutes
     │           session: RTH
     │           grouping: 15min
     │           special_op: event_time
     │           event_time_spec: {find: high}
     ▼
QueryBuilder → SQL (deterministic)
     │
     ▼
DataFetcher → executes → 27 rows
     │
     ▼
Analyst ←─→ Validator (retry if needed)
     │
     ▼
Response: "High дня чаще всего формируется в 18:00 (9.19%)
           или в первые часы RTH (09:00-10:00, ~16%)..."
```

## Determinism

**10/10 идентичных запусков** — 100% детерминизм.

Достигается за счёт:
1. LLM выбирает из enum значений (не генерирует текст)
2. JSON Schema валидация ответа
3. `period: "all"` вместо угадывания дат
4. QueryBuilder — чистый код без LLM

## Sessions (15 сессий)

```
RTH (09:30-16:00)      ETH (not RTH)         OVERNIGHT (18:00-09:30)
GLOBEX (18:00-17:00)   ASIAN (18:00-03:00)   EUROPEAN (03:00-09:30)
US (09:30-16:00)       PREMARKET (04:00-09:30)  POSTMARKET (16:00-20:00)
MORNING (09:30-12:00)  AFTERNOON (12:00-16:00)  LUNCH (12:00-14:00)
LONDON_OPEN (03:00-04:00)  NY_OPEN (09:30-10:30)  NY_CLOSE (15:00-16:00)
```

## Special Operations

| Operation | Описание | Пример |
|-----------|----------|--------|
| `event_time` | Распределение времени события по bucket'ам | "в какое время чаще формируется high?" |
| `find_extremum` | Точное время и значение high/low | "во сколько был хай 10 января?" |
| `top_n` | Топ N записей | "10 самых волатильных дней" |
| `compare` | Сравнение категорий | "RTH vs ETH" |

**Разница event_time vs find_extremum:**
- `event_time`: "в какое время **обычно**" → распределение (frequency, percentage)
- `find_extremum`: "во сколько **конкретно**" → точные значения (timestamp, value)

## Performance

| Метрика | Значение |
|---------|----------|
| Understander | ~1.5s |
| QueryBuilder | ~1ms |
| DataFetcher | ~30ms |
| Analyst | ~8s |
| **Total** | ~10s |
| **Cost** | ~$0.003/request |

## Files

```
agent/
├── graph.py                    # LangGraph pipeline
├── agents/
│   ├── understander.py         # LLM: вопрос → query_spec
│   ├── data_fetcher.py         # Code: SQL → данные
│   ├── analyst.py              # LLM: данные → ответ
│   └── validator.py            # Code: проверка Stats
├── prompts/
│   ├── understander.py         # Промпт с кубиками
│   └── analyst.py
└── query_builder/
    ├── types.py                # Dataclasses, enums (Single Source of Truth)
    ├── schema.py               # Auto-generation JSON Schema из types.py
    ├── builder.py              # query_spec → SQL
    ├── sql_utils.py            # SQL security (validation, escaping)
    ├── filters/                # Calendar, time filters
    ├── source/                 # Daily, minutes builders
    └── special_ops/            # event_time, find_extremum, top_n builders
```

## Future: Кубики как Data Layer

QueryBuilder — фундамент для всех будущих агентов:

```
┌─────────────────────────────────────────┐
│           Future Agents                  │
├───────────┬───────────┬─────────────────┤
│ Backtest  │  Entry    │   Indicator     │
│ Agent     │  Finder   │   Agent         │
└─────┬─────┴─────┬─────┴────────┬────────┘
      └───────────┴──────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │    QueryBuilder     │
        │      (кубики)       │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │      DuckDB         │
        └─────────────────────┘
```

Все агенты получают данные через кубики.
Кубики = универсальный Data Access Layer.
