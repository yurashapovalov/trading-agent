# SQL Agent

**File:** `agent/agents/sql_agent.py`

**Type:** LLM (Gemini 2.5 Flash Lite — дешёвая модель для генерации SQL)

## Purpose

Генерирует SQL запросы для фильтрации данных на основе Intent от Understander.

## Principle

Understander (LLM) понимает ЧТО искать (natural language).
SQL Agent (LLM) пишет КАК искать (SQL для DuckDB).
DataFetcher (код) выполняет SQL.
Analyst (LLM) анализирует результат.

**Почему нужен отдельный агент:**
- LLM плохо фильтрует большие массивы данных (5000+ строк)
- SQL точно находит все совпадения
- Разделение ответственности: понимание vs исполнение

## Input

```python
{
    "intent": Intent(
        type="data",
        symbol="NQ",
        period_start="2008-01-02",
        period_end="2026-01-07",
        granularity="daily",
        search_condition="days where change_pct < -2% AND previous day change_pct > +1%"
    )
}
```

## Output

```python
{
    "sql_query": """
        WITH daily AS (
            SELECT
                timestamp::date as date,
                FIRST(open ORDER BY timestamp) as open,
                MAX(high) as high,
                MIN(low) as low,
                LAST(close ORDER BY timestamp) as close,
                SUM(volume) as volume,
                ROUND(MAX(high) - MIN(low), 2) as range,
                ROUND((LAST(close ORDER BY timestamp) - FIRST(open ORDER BY timestamp))
                      / FIRST(open ORDER BY timestamp) * 100, 2) as change_pct
            FROM ohlcv_1min
            WHERE symbol = 'NQ'
              AND timestamp >= '2008-01-02'
              AND timestamp < '2026-01-07'
            GROUP BY date
            ORDER BY date
        ),
        with_prev AS (
            SELECT
                *,
                LAG(change_pct) OVER (ORDER BY date) as prev_change_pct
            FROM daily
        )
        SELECT date, open, high, low, close, volume, range, change_pct, prev_change_pct
        FROM with_prev
        WHERE change_pct < -2 AND prev_change_pct > 1
        ORDER BY date
    """,
    "usage": UsageStats(...)
}
```

## Schema Knowledge

SQL Agent знает схему данных:

```sql
-- Базовая таблица
ohlcv_1min (
    symbol VARCHAR,      -- 'NQ', 'ES', etc.
    timestamp TIMESTAMP, -- минутные данные
    open FLOAT,
    high FLOAT,
    low FLOAT,
    close FLOAT,
    volume FLOAT
)

-- Агрегированные колонки (вычисляются)
date DATE,              -- timestamp::date
range FLOAT,            -- high - low
change_pct FLOAT,       -- (close - open) / open * 100
prev_change_pct FLOAT,  -- LAG(change_pct)
gap_pct FLOAT,          -- (open - prev_close) / prev_close * 100
```

## DuckDB Features

SQL Agent знает особенности DuckDB:

```sql
-- Window Functions
LAG(column) OVER (ORDER BY date)      -- предыдущее значение
LEAD(column) OVER (ORDER BY date)     -- следующее значение
SUM(column) OVER (ROWS 3 PRECEDING)   -- скользящая сумма

-- Aggregations
FIRST(column ORDER BY timestamp)       -- первое значение
LAST(column ORDER BY timestamp)        -- последнее значение

-- Date Functions
timestamp::date                        -- извлечь дату
EXTRACT(HOUR FROM timestamp)           -- извлечь час
DAYOFWEEK(date)                        -- день недели (1-7)
DAYNAME(date)                          -- название дня
DATE_TRUNC('month', date)              -- округлить до месяца
```

## Query Patterns

### Simple Filter
```
"Найди дни падения > 2%"
```
```sql
WHERE change_pct < -2
```

### Previous Day Condition
```
"Падение после роста"
```
```sql
WITH daily AS (...),
with_prev AS (
    SELECT *, LAG(change_pct) OVER (ORDER BY date) as prev_change_pct
    FROM daily
)
SELECT * FROM with_prev
WHERE change_pct < -2 AND prev_change_pct > 1
```

### Gap Analysis
```
"Гэп вверх > 1%"
```
```sql
WITH daily AS (...),
with_gap AS (
    SELECT *,
        ROUND((open - LAG(close) OVER (ORDER BY date))
              / LAG(close) OVER (ORDER BY date) * 100, 2) as gap_pct
    FROM daily
)
SELECT * FROM with_gap
WHERE gap_pct > 1
```

### Consecutive Days
```
"3 дня подряд роста"
```
```sql
WITH daily AS (...),
with_streak AS (
    SELECT *,
        CASE WHEN change_pct > 0 THEN 1 ELSE 0 END as up_day,
        SUM(CASE WHEN change_pct > 0 THEN 1 ELSE 0 END)
            OVER (ORDER BY date ROWS 2 PRECEDING) as up_streak
    FROM daily
)
SELECT * FROM with_streak
WHERE up_streak = 3
```

### Volume Spike
```
"Объём выше среднего в 2 раза"
```
```sql
WITH daily AS (...),
with_avg AS (
    SELECT *, AVG(volume) OVER () as avg_volume
    FROM daily
)
SELECT * FROM with_avg
WHERE volume > avg_volume * 2
```

## Prompt Structure

```xml
<role>
You are a SQL query generator for DuckDB trading database.
Generate precise SQL queries based on search conditions.
</role>

<schema>
Table: ohlcv_1min
Columns: symbol, timestamp, open, high, low, close, volume

Computed columns (in CTE):
- date: timestamp::date
- range: high - low
- change_pct: (close - open) / open * 100
- prev_change_pct: LAG(change_pct) OVER (ORDER BY date)
- gap_pct: (open - LAG(close)) / LAG(close) * 100
</schema>

<duckdb_features>
- Use LAG/LEAD for previous/next day
- Use FIRST/LAST with ORDER BY for open/close
- Always use CTE for readability
- Round floats to 2 decimal places
</duckdb_features>

<rules>
1. Always start with daily CTE that aggregates from ohlcv_1min
2. Add additional CTEs for window functions (prev_change_pct, gap_pct)
3. Apply filters in final SELECT
4. Order by date
5. Include all useful columns in output
</rules>

<examples>
... (примеры из Query Patterns выше)
</examples>

<task>
Symbol: {symbol}
Period: {period_start} to {period_end}
Search condition: {search_condition}

Generate SQL query.
</task>
```

## Validation

SQL Agent только генерирует SQL. Валидация - отдельный агент (SQL Validator).

```
SQL Agent → SQL Validator → DataFetcher
              │
              └─→ feedback если ошибка
```

При ошибке SQL Validator возвращает feedback, SQL Agent исправляет (до 3 попыток).

## No Search Condition

Если `search_condition` отсутствует, SQL Agent не нужен.
DataFetcher использует стандартные шаблоны из `sql.py`.

```python
def should_use_sql_agent(intent: Intent) -> bool:
    return bool(intent.get("search_condition"))
```

## Logging

Каждый сгенерированный SQL логируется:

```python
{
    "agent": "sql_agent",
    "search_condition": "days where change_pct < -2%",
    "generated_sql": "...",
    "execution_time_ms": 45,
    "rows_returned": 77,
    "error": null
}
```

Это позволяет:
- Отлаживать неправильные запросы
- Собирать примеры для улучшения промпта
- Мониторить производительность

## Future: Technical Indicators

Для сложных индикаторов (MACD, RSI, EMA) SQL Agent может быть расширен или заменён специализированными агентами:

```
Understander
     │
     ├─── SQL Agent (простые фильтры)
     ├─── RSI Agent (Python, расчёт RSI)
     ├─── MACD Agent (Python, расчёт MACD)
     └─── Pattern Agent (сложные паттерны)
```

Каждый агент - специалист в своей области.

## Implementation

```python
class SQLAgent:
    name = "sql_agent"
    agent_type = "query"

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_LITE_MODEL  # Дешёвая модель для SQL генерации

    def __call__(self, state: AgentState) -> dict:
        intent = state["intent"]
        search_condition = intent.get("search_condition")

        if not search_condition:
            return {"sql_query": None}  # Используем стандартные шаблоны

        prompt = self._build_prompt(intent)
        sql_query = self._generate_sql(prompt)

        # Validate
        if error := self._validate_sql(sql_query):
            sql_query = self._retry_with_feedback(prompt, error)

        return {
            "sql_query": sql_query,
            "usage": self._last_usage
        }
```

## Usage Tracking

```python
usage = sql_agent.get_usage()
# UsageStats(input_tokens=2700, output_tokens=400, cost_usd=0.00043)
```

SQL Agent использует `GEMINI_2_5_FLASH_LITE` pricing:
- Input: $0.10 / 1M tokens
- Output: $0.40 / 1M tokens

Дешевле чем основная модель в ~6 раз.
