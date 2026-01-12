# Рефакторинг request_traces

## Финальное решение

**Принцип**: JSONB для гибкости, минимум колонок.

### Новая схема

```sql
CREATE TABLE request_traces (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID REFERENCES chat_logs(request_id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,

    step_number INTEGER NOT NULL,
    agent_name TEXT NOT NULL,

    input_data JSONB,     -- что пришло в агента
    output_data JSONB,    -- что вышло из агента

    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Удалённые колонки

| Колонка | Причина удаления |
|---------|------------------|
| `agent_type` | Дублирует agent_name |
| `sql_query` | → output_data.query |
| `sql_result` | → output_data.rows |
| `sql_rows_returned` | → output_data.row_count |
| `sql_error` | → output_data.error |
| `validation_status` | → output_data.status |
| `validation_issues` | → output_data.issues |
| `validation_feedback` | → output_data.feedback |
| `prompt_template` | → output_data.prompt (если нужно) |
| `model_used` | → output_data.model |
| `input_tokens` | → output_data.usage.input_tokens |
| `output_tokens` | → output_data.usage.output_tokens |
| `thinking_tokens` | → output_data.usage.thinking_tokens |
| `cost_usd` | → output_data.usage.cost_usd |
| `started_at` | Не нужно, есть duration_ms |
| `finished_at` | Не нужно, есть duration_ms |

---

## Структура JSONB по агентам

### understander
```json
{
  "input_data": {
    "question": "Покажи статистику по NQ за прошлую неделю"
  },
  "output_data": {
    "intent": {
      "type": "data",
      "symbol": "NQ",
      "period_start": "2026-01-05",
      "period_end": "2026-01-07",
      "granularity": "daily"
    },
    "usage": {
      "input_tokens": 150,
      "output_tokens": 50,
      "cost_usd": 0.0001
    }
  }
}
```

### data_fetcher
```json
{
  "input_data": {
    "intent": { "type": "data", "symbol": "NQ", ... }
  },
  "output_data": {
    "query": "SELECT ... FROM ohlcv_1min ...",
    "granularity": "daily",
    "row_count": 3,
    "rows": [{ "date": "2026-01-05", "open": 25488, ... }, ...]
  }
}
```

### analyst
```json
{
  "input_data": {
    "question": "...",
    "data": { "rows": [...], "row_count": 3 }
  },
  "output_data": {
    "response": "Статистика по инструменту NQ...",
    "stats": {
      "max_price": 25996.25,
      "min_price": 25455.0,
      "trading_days": 3
    },
    "usage": {
      "input_tokens": 840,
      "output_tokens": 448,
      "cost_usd": 0.0074
    }
  }
}
```

### validator
```json
{
  "input_data": {
    "response": "...",
    "stats": { ... },
    "data": { ... }
  },
  "output_data": {
    "status": "ok",
    "issues": [],
    "feedback": ""
  }
}
```

---

## SQL для Dashboard

```sql
-- Удалить все лишние колонки
ALTER TABLE request_traces DROP COLUMN IF EXISTS agent_type;
ALTER TABLE request_traces DROP COLUMN IF EXISTS sql_query;
ALTER TABLE request_traces DROP COLUMN IF EXISTS sql_result;
ALTER TABLE request_traces DROP COLUMN IF EXISTS sql_rows_returned;
ALTER TABLE request_traces DROP COLUMN IF EXISTS sql_error;
ALTER TABLE request_traces DROP COLUMN IF EXISTS validation_status;
ALTER TABLE request_traces DROP COLUMN IF EXISTS validation_issues;
ALTER TABLE request_traces DROP COLUMN IF EXISTS validation_feedback;
ALTER TABLE request_traces DROP COLUMN IF EXISTS prompt_template;
ALTER TABLE request_traces DROP COLUMN IF EXISTS model_used;
ALTER TABLE request_traces DROP COLUMN IF EXISTS input_tokens;
ALTER TABLE request_traces DROP COLUMN IF EXISTS output_tokens;
ALTER TABLE request_traces DROP COLUMN IF EXISTS thinking_tokens;
ALTER TABLE request_traces DROP COLUMN IF EXISTS cost_usd;
ALTER TABLE request_traces DROP COLUMN IF EXISTS started_at;
ALTER TABLE request_traces DROP COLUMN IF EXISTS finished_at;

-- Удалить неиспользуемые индексы
DROP INDEX IF EXISTS idx_traces_agent_type;
DROP INDEX IF EXISTS idx_traces_validation_status;
DROP INDEX IF EXISTS idx_traces_sql_error;
```

---

## Изменения в коде

### 1. graph.py — stream_sse
Передавать полные данные в SSE events:
```python
# step_end для understander
yield {
    "type": "step_end",
    "agent": "understander",
    "result": updates.get("intent"),  # полный intent
    "usage": updates.get("usage"),
}
```

### 2. api.py — log_trace_step
```python
await log_trace_step(
    request_id=request_id,
    user_id=user_id,
    step_number=step_number,
    agent_name=agent_name,
    input_data=input_for_agent,   # полный input
    output_data=updates,          # полный output
    duration_ms=duration_ms,
)
```

### 3. logging/supabase.py
Упростить функцию — убрать все удалённые параметры.

### 4. Агенты — возвращать usage
Каждый LLM-агент должен возвращать usage в output:
```python
return {
    "intent": intent,
    "usage": {
        "input_tokens": ...,
        "output_tokens": ...,
        "cost_usd": ...
    }
}
```
