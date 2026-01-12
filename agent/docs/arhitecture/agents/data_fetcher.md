# DataFetcher Agent

**File:** `agent/agents/data_fetcher.py`

**Type:** Code (Python, без LLM)

## Purpose

Центральный хаб для получения данных. Выполняет валидный SQL и отдаёт данные Analyst'у.

## Principle

DataFetcher - чистый исполнитель:
- Получает валидный SQL (от SQL Validator или шаблоны из sql.py)
- Выполняет запрос
- Возвращает данные

**Не валидирует** - это работа SQL Validator.
**Не генерирует SQL** - это работа SQL Agent или шаблоны.

## Position in Architecture

```
SQL Agent → SQL Validator → DataFetcher → Analyst → Validator
                               ▲
                               │
                          Центральный хаб
```

## Input

### From SQL Validator (search query)

```python
{
    "validation": {
        "status": "ok",
        "sql_query": "WITH daily AS (...) SELECT * WHERE change_pct < -2"
    },
    "intent": Intent(...)
}
```

### Direct (standard query, no search_condition)

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
        "rows": [
            {"date": "2024-01-02", "open": 17019, "high": 17038, "change_pct": -1.84, ...},
            ...
        ],
        "row_count": 77,
        "granularity": "daily",
        "sql_query": "..."  # для логирования
    }
}
```

## Routing Logic

```python
def __call__(self, state: AgentState) -> dict:
    validation = state.get("validation", {})
    intent = state.get("intent")

    # 1. Если есть валидный SQL от SQL Validator
    if validation.get("status") == "ok" and validation.get("sql_query"):
        data = self._execute_sql(validation["sql_query"])

    # 2. Concept - данные не нужны
    elif intent.get("type") == "concept":
        data = self._handle_concept(intent)

    # 3. Standard query - используем шаблоны
    else:
        data = self._handle_standard(intent)

    return {"data": data}
```

## Handlers

### Execute Custom SQL (from SQL Agent)

```python
def _execute_sql(self, sql_query: str) -> dict:
    """Выполняет SQL от SQL Agent (уже провалидированный)."""
    with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
        df = conn.execute(sql_query).df()
        rows = df.to_dict(orient='records')

        return {
            "rows": _convert_numpy_types(rows),
            "row_count": len(rows),
            "granularity": "daily",
            "sql_query": sql_query,
        }
```

### Standard Query (templates)

```python
def _handle_standard(self, intent: Intent) -> dict:
    """Использует шаблоны из sql.py."""
    return sql.fetch(
        symbol=intent["symbol"],
        period_start=intent["period_start"],
        period_end=intent["period_end"],
        granularity=intent["granularity"]
    )
```

### Concept (no data)

```python
def _handle_concept(self, intent: Intent) -> dict:
    """Для концепций данные не нужны."""
    return {
        "type": "concept",
        "concept": intent.get("concept"),
        "message": "No data needed for concept explanation"
    }
```

## Data Flow

### Search Query
```
SQL Agent generates SQL
         │
         ▼
SQL Validator validates
         │
         ▼
DataFetcher executes → 77 rows
         │
         ▼
Analyst analyzes
```

### Standard Query
```
Intent(granularity=daily)
         │
         ▼
DataFetcher uses sql.py template → 22 rows
         │
         ▼
Analyst analyzes
```

## Error Handling

DataFetcher получает уже валидный SQL, поэтому ошибки редки.
Но на всякий случай:

```python
try:
    df = conn.execute(sql_query).df()
except Exception as e:
    return {
        "error": str(e),
        "sql_query": sql_query,
        "rows": [],
        "row_count": 0
    }
```

## Implementation

```python
class DataFetcher:
    name = "data_fetcher"
    agent_type = "data"

    def __call__(self, state: AgentState) -> dict:
        validation = state.get("validation", {})
        intent = state.get("intent")

        if validation.get("status") == "ok" and validation.get("sql_query"):
            data = self._execute_sql(validation["sql_query"])
        elif intent.get("type") == "concept":
            data = self._handle_concept(intent)
        else:
            data = self._handle_standard(intent)

        return {
            "data": data,
            "step_number": state.get("step_number", 0) + 1
        }
```

Чистый Python, без LLM - быстро и предсказуемо.

## Logging

```python
{
    "agent": "data_fetcher",
    "source": "sql_agent" | "template",
    "sql_query": "...",
    "rows_returned": 77,
    "execution_time_ms": 45
}
```
