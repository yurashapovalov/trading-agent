# DataFetcher Agent

**File:** `agent/agents/data_fetcher.py`

**Type:** Code (Python, без LLM)

## Purpose

Выполняет SQL от QueryBuilder и отдаёт данные Analyst'у.

## Architecture

```
Understander → QueryBuilder → DataFetcher → Analyst → Validator
                    │              ▲
                    │              │
                    └──── SQL ─────┘
```

DataFetcher — чистый исполнитель:
- Получает детерминированный SQL от QueryBuilder
- Выполняет запрос в DuckDB
- Возвращает данные

## Input

```python
{
    "sql_query": "WITH daily AS (...) SELECT ...",
    "intent": {
        "type": "data",
        "symbol": "NQ",
        "query_spec": {...}
    }
}
```

## Output

```python
{
    "data": {
        "rows": [
            {"time_bucket": "09:00", "frequency": 487, "percentage": 8.69},
            {"time_bucket": "10:00", "frequency": 439, "percentage": 7.84},
            ...
        ],
        "row_count": 24,
        "granularity": "distribution",
        "columns": ["time_bucket", "frequency", "percentage"]
    }
}
```

## Routing Logic

```python
def __call__(self, state: AgentState) -> dict:
    sql_query = state.get("sql_query")
    intent = state.get("intent")

    # 1. SQL от QueryBuilder
    if sql_query:
        data = self._execute_sql(sql_query, intent)

    # 2. Concept - данные не нужны
    elif intent.get("type") == "concept":
        data = self._handle_concept(intent)

    # 3. Fallback - стандартные шаблоны
    else:
        data = self._handle_data(intent)

    return {"data": data}
```

## SQL Execution

```python
def _execute_sql(self, sql_query: str, intent: Intent) -> dict:
    """Выполняет SQL от QueryBuilder."""
    with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
        df = conn.execute(sql_query).df()
        rows = df.to_dict(orient='records')

        # Определяем granularity из query_spec
        query_spec = intent.get("query_spec", {})
        granularity = self._detect_granularity(query_spec)

        return {
            "rows": rows,
            "row_count": len(rows),
            "granularity": granularity,
            "columns": list(df.columns),
        }
```

## Granularity Detection

```python
def _detect_granularity(self, query_spec: dict) -> str:
    """Определяет тип данных из query_spec."""
    special_op = query_spec.get("special_op")

    if special_op == "event_time":
        return "distribution"
    elif special_op == "top_n":
        return "ranking"

    source = query_spec.get("source", "daily")
    if source == "minutes":
        return "minute"

    grouping = query_spec.get("grouping", "none")
    if grouping == "total":
        return "period"
    elif grouping in ("weekday", "session"):
        return grouping

    return "daily"
```

## Data Flow

```
QueryBuilder generates SQL (deterministic)
         │
         ▼
DataFetcher executes in DuckDB
         │
         ▼
Returns rows + metadata
         │
         ▼
Analyst analyzes and responds
```

## Error Handling

SQL от QueryBuilder **всегда валидный** (детерминированная генерация).
Но на всякий случай:

```python
try:
    df = conn.execute(sql_query).df()
except Exception as e:
    return {
        "error": str(e),
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
        sql_query = state.get("sql_query")
        intent = state.get("intent")

        if sql_query:
            data = self._execute_sql(sql_query, intent)
        elif intent.get("type") == "concept":
            data = self._handle_concept(intent)
        else:
            data = self._handle_data(intent)

        return {"data": data}
```

Чистый Python, без LLM — быстро (~20-50ms) и предсказуемо.

## Logging

```python
{
    "agent": "data_fetcher",
    "source": "query_builder",
    "rows_returned": 24,
    "execution_time_ms": 32
}
```
