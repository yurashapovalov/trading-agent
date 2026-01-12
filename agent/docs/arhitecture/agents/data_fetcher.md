# DataFetcher Agent

**File:** `agent/agents/data_fetcher.py`

**Type:** Code (Python, без LLM)

## Purpose

Получает данные на основе Intent. Роутинг к нужному модулю.

## Principle

Understander (LLM) решил ЧТО нужно.
DataFetcher (код) выполняет КАК получить данные.

## Input

```python
{
    "intent": Intent(
        type="data",
        symbol="NQ",
        period_start="2024-01-01",
        period_end="2024-01-31",
        granularity="daily"
    )
}
```

## Output

```python
{
    "data": {
        "rows": [...],
        "row_count": 26,
        "granularity": "daily"
    }
}
```

## Routing Table

| Intent Type | Module | Function |
|-------------|--------|----------|
| `data` | `agent.modules.sql` | `sql.fetch()` |
| `pattern` | `agent.modules.patterns` | `patterns.search()` |
| `concept` | — | Возвращает имя концепции |
| `strategy` | — | Не реализовано |

## Handler: Data

```python
def _handle_data(self, intent: Intent) -> dict:
    return sql.fetch(
        symbol=intent["symbol"],
        period_start=intent["period_start"],
        period_end=intent["period_end"],
        granularity=intent["granularity"]
    )
```

Возвращает:
```python
{
    "rows": [
        {"date": "2024-01-02", "open": 17019, "high": 17038, ...},
        ...
    ],
    "row_count": 26,
    "granularity": "daily"
}
```

## Handler: Pattern

```python
def _handle_pattern(self, intent: Intent) -> dict:
    pattern = intent["pattern"]
    return patterns.search(
        symbol=intent["symbol"],
        period_start=intent["period_start"],
        period_end=intent["period_end"],
        pattern_name=pattern["name"],
        params=pattern["params"]
    )
```

Возвращает:
```python
{
    "pattern": "big_move",
    "params": {"threshold_pct": 2.0},
    "matches": [
        {"date": "2024-03-15", "change_pct": 2.5, "direction": "up"},
        ...
    ],
    "matches_count": 5
}
```

## Handler: Concept

```python
def _handle_concept(self, intent: Intent) -> dict:
    return {
        "type": "concept",
        "concept": intent["concept"],
        "message": "No data needed for concept explanation"
    }
```

Для концепций данные из БД не нужны - Analyst объяснит из своих знаний.

## Handler: Strategy (Future)

```python
def _handle_strategy(self, intent: Intent) -> dict:
    return {
        "type": "strategy",
        "error": "Backtesting not implemented yet"
    }
```

## Error Handling

Если нет intent:
```python
return {
    "data": {},
    "error": "No intent provided"
}
```

Если нет периода:
```python
return {"error": "Missing period_start or period_end"}
```

## Implementation

```python
class DataFetcher:
    name = "data_fetcher"
    agent_type = "data"

    def __call__(self, state: AgentState) -> dict:
        intent = state.get("intent")
        intent_type = intent.get("type", "data")

        if intent_type == "concept":
            data = self._handle_concept(intent)
        elif intent_type == "pattern":
            data = self._handle_pattern(intent)
        else:
            data = self._handle_data(intent)

        return {"data": data}
```

Чистый Python, без LLM - быстро и предсказуемо.
