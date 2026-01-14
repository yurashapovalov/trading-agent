# Understander Agent

**File:** `agent/agents/understander.py`

**Type:** LLM (Gemini 2.5 Flash Lite)

## Purpose

Парсит вопрос пользователя в структурированный `query_spec` — набор "кубиков" для QueryBuilder.

## Architecture

```
Вопрос → Understander → query_spec (JSON) → QueryBuilder → SQL
```

**Принцип:** LLM классифицирует, не генерирует. Вместо генерации SQL, LLM выбирает из готовых блоков.

## Input

```python
{
    "question": "когда обычно формируется high дня за RTH?",
    "chat_history": [...]  # optional
}
```

## Output

```python
{
    "intent": {
        "type": "data",
        "symbol": "NQ",
        "query_spec": {
            "source": "minutes",
            "filters": {
                "period_start": "2008-01-02",
                "period_end": "2026-01-07",
                "session": "RTH"
            },
            "grouping": "15min",
            "metrics": [],
            "special_op": "event_time",
            "event_time_spec": {"find": "high"}
        }
    }
}
```

## Intent Types

| Type | Когда | Пример |
|------|-------|--------|
| `data` | Запросы про данные | "Как NQ в январе?", "Когда high дня?" |
| `concept` | Объяснение концепций | "Что такое MACD?" |
| `chitchat` | Приветствия | "Привет!" |
| `out_of_scope` | Не про трейдинг | "Какая погода?" |
| `clarification` | Нужно уточнение | Неясный запрос |

## Query Spec — Кубики

### Source (откуда данные)

| Value | Описание |
|-------|----------|
| `minutes` | Минутные свечи |
| `daily` | Дневные агрегации |
| `daily_with_prev` | Дневные + данные предыдущего дня (для гэпов) |

### Filters (фильтры)

| Field | Описание |
|-------|----------|
| `period_start` | Начало периода (YYYY-MM-DD) или "all" |
| `period_end` | Конец периода (YYYY-MM-DD) или "all" |
| `session` | Торговая сессия (RTH, ETH, OVERNIGHT, etc.) |
| `conditions` | Дополнительные условия [{column, operator, value}] |

### Sessions (15 сессий)

```
RTH, ETH, OVERNIGHT, GLOBEX,
ASIAN, EUROPEAN, US,
PREMARKET, POSTMARKET, MORNING, AFTERNOON, LUNCH,
LONDON_OPEN, NY_OPEN, NY_CLOSE
```

### Grouping (группировка)

| Value | Описание |
|-------|----------|
| `none` | Без группировки (все строки) |
| `total` | Одна агрегированная строка |
| `5min`..`hour` | По временным интервалам |
| `day`..`year` | По календарным периодам |
| `weekday` | По дням недели |
| `session` | По сессиям |

### Metrics (метрики)

| Value | Описание |
|-------|----------|
| `open`, `high`, `low`, `close`, `volume` | OHLCV |
| `range` | high - low |
| `change_pct` | % изменения |
| `gap_pct` | % гэпа от предыдущего close |
| `count`, `avg`, `sum`, `min`, `max`, `stddev`, `median` | Агрегаты |

### Special Operations

| Value | Описание |
|-------|----------|
| `none` | Обычный запрос |
| `event_time` | Распределение времени события (high/low) |
| `top_n` | Топ N записей |
| `compare` | Сравнение категорий |

## Period Handling

- **Период указан** → используем как есть
- **Период НЕ указан** → LLM возвращает `"all"`, Python заполняет из БД

```python
# LLM возвращает:
"period_start": "all", "period_end": "all"

# Python заменяет на реальные даты из БД:
"period_start": "2008-01-02", "period_end": "2026-01-07"
```

Это обеспечивает **детерминизм** — LLM не гадает даты.

## Examples

### Статистика за период

```
Q: "средний range за 2024"
→ source: daily
  filters: {period: 2024-01-01 — 2024-12-31}
  grouping: total
  metrics: [{metric: avg, column: range}]
```

### Распределение времени

```
Q: "когда формируется high дня за RTH?"
→ source: minutes
  filters: {period: all, session: RTH}
  grouping: 15min
  special_op: event_time
  event_time_spec: {find: high}
```

### Поиск экстремумов

```
Q: "топ 10 самых волатильных дней"
→ source: daily
  filters: {period: all}
  special_op: top_n
  top_n_spec: {n: 10, order_by: range, direction: DESC}
```

## Implementation

```python
class Understander:
    name = "understander"
    agent_type = "routing"
    model = "gemini-2.5-flash-lite"  # Быстрая модель

    def __call__(self, state: AgentState) -> dict:
        question = state["question"]
        intent = self._parse_with_llm(question)
        return {"intent": intent}
```

- JSON mode для структурированного вывода
- JSON Schema для валидации query_spec
- Температура 0.3 для детерминизма
- ~1.5s на запрос

## Prompt

Промпт в `agent/prompts/understander.py` содержит:
- Описание всех кубиков
- Правила выбора source/grouping/metrics
- Примеры маппинга вопрос → query_spec
- JSON schema для ответа

## Determinism

10/10 идентичных запусков на один вопрос — **100% детерминизм**.

Достигается за счёт:
1. Низкой температуры (0.3)
2. JSON schema валидации
3. Ограниченного набора enum значений
4. `"all"` вместо угадывания дат
