# SQL Validator Agent

**File:** `agent/agents/sql_validator.py`

**Type:** Code (Python, без LLM)

## Purpose

Валидирует SQL запросы от SQL Agent перед выполнением.

## Principle

SQL Agent (LLM) генерирует SQL - может ошибаться.
SQL Validator (код) проверяет SQL - детерминированный результат.

**Симметрия с Validator:**
| Генератор | Валидатор |
|-----------|-----------|
| SQL Agent (генерирует SQL) | SQL Validator (проверяет SQL) |
| Analyst (генерирует ответ) | Validator (проверяет ответ) |

## Input

```python
{
    "sql_query": """
        WITH daily AS (...)
        SELECT * FROM with_prev
        WHERE change_pct < -2 AND prev_change_pct > 1
    """,
    "intent": Intent(...)
}
```

## Output

### Valid SQL
```python
{
    "validation": {
        "status": "ok",
        "sql_query": "..."  # тот же SQL, прошёл проверку
    }
}
```

### Invalid SQL
```python
{
    "validation": {
        "status": "rewrite",
        "issues": ["Syntax error near 'SELEC'", "Unknown column 'pric'"],
        "feedback": "SQL validation failed:\n- Syntax error near 'SELEC'\n- Unknown column 'pric'"
    }
}
```

## Validation Checks

### 1. Safety Check
```python
def _check_safety(self, sql: str) -> list[str]:
    """Проверяет что SQL безопасен."""
    issues = []
    sql_upper = sql.upper()

    # Только SELECT разрешён
    forbidden = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
    for word in forbidden:
        if word in sql_upper:
            issues.append(f"Forbidden operation: {word}")

    # Только наши таблицы
    if 'ohlcv_1min' not in sql.lower():
        issues.append("Query must use ohlcv_1min table")

    return issues
```

### 2. Syntax Check
```python
def _check_syntax(self, sql: str) -> list[str]:
    """Проверяет синтаксис SQL."""
    issues = []
    try:
        # Пробуем распарсить через DuckDB
        with duckdb.connect(':memory:') as conn:
            conn.execute(f"EXPLAIN {sql}")
    except Exception as e:
        issues.append(f"Syntax error: {str(e)}")
    return issues
```

### 3. Schema Check
```python
def _check_schema(self, sql: str) -> list[str]:
    """Проверяет что используются правильные колонки."""
    issues = []
    allowed_columns = {
        'symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'date', 'range', 'change_pct', 'prev_change_pct', 'gap_pct'
    }

    # Извлекаем колонки из SQL и проверяем
    # (упрощённая логика, можно улучшить)

    return issues
```

### 4. Execution Check (optional)
```python
def _check_execution(self, sql: str) -> list[str]:
    """Пробуем выполнить с LIMIT 1."""
    issues = []
    try:
        with duckdb.connect(config.DATABASE_PATH, read_only=True) as conn:
            # Добавляем LIMIT для быстрой проверки
            test_sql = f"SELECT * FROM ({sql}) LIMIT 1"
            conn.execute(test_sql)
    except Exception as e:
        issues.append(f"Execution error: {str(e)}")
    return issues
```

## Validation Flow

```
SQL Agent
    │
    │ sql_query
    ▼
SQL Validator
    │
    ├─ Safety check ──────► forbidden operations?
    ├─ Syntax check ──────► parse errors?
    ├─ Schema check ──────► wrong columns?
    └─ Execution check ───► runtime errors?
    │
    ▼
┌───┴───┐
│       │
OK    Rewrite
│       │
▼       ▼
DataFetcher    SQL Agent (исправляет)
```

## Retry Loop

```python
MAX_RETRIES = 3

def validate_with_retry(state: AgentState) -> dict:
    for attempt in range(MAX_RETRIES):
        sql_query = state.get("sql_query")
        issues = validate(sql_query)

        if not issues:
            return {"validation": {"status": "ok", "sql_query": sql_query}}

        # Отправляем feedback SQL Agent'у
        state["validation"] = {
            "status": "rewrite",
            "issues": issues,
            "feedback": format_feedback(issues)
        }

        # SQL Agent генерирует новый SQL
        state = sql_agent(state)

    return {"validation": {"status": "failed", "issues": issues}}
```

## Implementation

```python
class SQLValidator:
    name = "sql_validator"
    agent_type = "validation"

    def __call__(self, state: AgentState) -> dict:
        sql_query = state.get("sql_query")

        if not sql_query:
            return {"validation": {"status": "ok"}}  # Нет SQL - нечего валидировать

        issues = []
        issues.extend(self._check_safety(sql_query))
        issues.extend(self._check_syntax(sql_query))
        issues.extend(self._check_schema(sql_query))
        issues.extend(self._check_execution(sql_query))

        if issues:
            return {
                "validation": {
                    "status": "rewrite",
                    "issues": issues,
                    "feedback": self._format_feedback(issues)
                }
            }

        return {
            "validation": {
                "status": "ok",
                "sql_query": sql_query
            }
        }

    def _format_feedback(self, issues: list[str]) -> str:
        return "SQL validation failed:\n" + "\n".join(f"- {issue}" for issue in issues)
```

## Error Messages

Feedback для SQL Agent должен быть понятным:

```
SQL validation failed:
- Syntax error: column "pric" does not exist, did you mean "price"?
- Forbidden operation: DELETE not allowed
- Unknown function: FIRST() - use FIRST_VALUE() in DuckDB
```

SQL Agent использует этот feedback для исправления запроса.

## Logging

```python
{
    "agent": "sql_validator",
    "sql_query": "...",
    "status": "rewrite",
    "issues": ["Syntax error: ..."],
    "attempt": 2
}
```

## Comparison with Validator

| | SQL Validator | Validator |
|---|---|---|
| Проверяет | SQL запрос | Ответ Analyst |
| От кого | SQL Agent | Analyst |
| Тип проверки | Синтаксис, безопасность | Числа vs данные |
| При ошибке | SQL Agent переписывает | Analyst переписывает |
