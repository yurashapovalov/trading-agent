# SQL Module

**File:** `agent/modules/sql.py`

## Purpose

Запросы к DuckDB для получения OHLCV данных.

## Main Function

```python
def fetch(
    symbol: str,
    period_start: str,
    period_end: str,
    granularity: Literal["period", "daily", "hourly"]
) -> dict
```

## Granularity Modes

### Period (Aggregated)

Одна строка с агрегированными данными за весь период.

```python
result = sql.fetch(
    symbol="NQ",
    period_start="2024-01-01",
    period_end="2024-01-31",
    granularity="period"
)
```

Response:
```python
{
    "rows": [{
        "symbol": "NQ",
        "period_start": "2024-01-01",
        "period_end": "2024-01-30",
        "trading_days": 26,
        "open_price": 17019.0,
        "close_price": 17449.5,
        "max_price": 17793.5,
        "min_price": 16334.25,
        "total_volume": 12886739,
        "change_pct": 2.53,
        "change_points": 430.5
    }],
    "row_count": 1,
    "granularity": "period"
}
```

SQL:
```sql
SELECT
    symbol,
    MIN(date) as period_start,
    MAX(date) as period_end,
    COUNT(*) as trading_days,
    FIRST(open) as open_price,
    LAST(close) as close_price,
    MAX(high) as max_price,
    MIN(low) as min_price,
    SUM(volume) as total_volume,
    ROUND((LAST(close) - FIRST(open)) / FIRST(open) * 100, 2) as change_pct,
    ROUND(LAST(close) - FIRST(open), 2) as change_points
FROM ohlcv
WHERE symbol = ? AND date >= ? AND date <= ?
GROUP BY symbol
```

### Daily

Одна строка на каждый торговый день.

```python
result = sql.fetch(
    symbol="NQ",
    period_start="2024-01-01",
    period_end="2024-01-10",
    granularity="daily"
)
```

Response:
```python
{
    "rows": [
        {
            "date": "2024-01-02",
            "open": 17019.0,
            "high": 17038.5,
            "low": 17001.0,
            "close": 17007.75,
            "volume": 19198,
            "range": 37.5,          # high - low
            "change_pct": -0.07     # (close - open) / open * 100
        },
        ...
    ],
    "row_count": 8,
    "granularity": "daily"
}
```

SQL:
```sql
SELECT
    date,
    FIRST(open) as open,
    MAX(high) as high,
    MIN(low) as low,
    LAST(close) as close,
    SUM(volume) as volume,
    ROUND(MAX(high) - MIN(low), 2) as range,
    ROUND((LAST(close) - FIRST(open)) / FIRST(open) * 100, 2) as change_pct
FROM ohlcv
WHERE symbol = ? AND date >= ? AND date <= ?
GROUP BY date
ORDER BY date
```

### Hourly

Одна строка на каждый час торговой сессии.

```python
result = sql.fetch(
    symbol="NQ",
    period_start="2024-01-02",
    period_end="2024-01-02",
    granularity="hourly"
)
```

Response:
```python
{
    "rows": [
        {
            "date": "2024-01-02",
            "hour": 9,
            "open": 17019.0,
            "high": 17025.0,
            "low": 17010.0,
            "close": 17020.5,
            "volume": 1234
        },
        ...
    ],
    "row_count": 24,
    "granularity": "hourly"
}
```

## Helper Functions

### get_data_range

```python
def get_data_range(symbol: str) -> dict | None
```

Возвращает доступный диапазон данных:
```python
{
    "symbol": "NQ",
    "start_date": "2008-01-02",
    "end_date": "2026-01-07",
    "trading_days": 5602
}
```

### get_trading_days

```python
def get_trading_days(symbol: str, start: str, end: str) -> int
```

Количество торговых дней в периоде.

## Database

DuckDB с таблицей `ohlcv`:

```sql
CREATE TABLE ohlcv (
    symbol VARCHAR,
    date DATE,
    time TIME,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume BIGINT
)
```

Путь к базе: `config.DATABASE_PATH` (default: `data/trading.db`)

## Error Handling

Если данных нет:
```python
{
    "rows": [],
    "row_count": 0,
    "granularity": "daily",
    "message": "No data found for the specified period"
}
```

Если ошибка:
```python
{
    "error": "Database error: ..."
}
```
