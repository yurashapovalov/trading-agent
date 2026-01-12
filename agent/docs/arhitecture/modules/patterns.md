# Patterns Module

**File:** `agent/modules/patterns.py`

## Purpose

Поиск торговых паттернов в данных.

## Main Function

```python
def search(
    symbol: str,
    period_start: str,
    period_end: str,
    pattern_name: str,
    params: dict
) -> dict
```

## Available Patterns

### 1. consecutive_days

N дней подряд вверх или вниз.

**Params:**
```python
{
    "direction": "up" | "down",  # направление
    "min_days": 3                # минимум дней подряд
}
```

**Example:**
```python
result = patterns.search(
    symbol="NQ",
    period_start="2024-01-01",
    period_end="2024-06-30",
    pattern_name="consecutive_days",
    params={"direction": "up", "min_days": 3}
)
```

**Response:**
```python
{
    "pattern": "consecutive_days",
    "params": {"direction": "up", "min_days": 3},
    "matches": [
        {
            "start_date": "2024-01-08",
            "end_date": "2024-01-10",
            "days": 3,
            "total_change_pct": 3.31,
            "direction": "up"
        },
        ...
    ],
    "matches_count": 13
}
```

### 2. big_move

Дни с большим процентным изменением.

**Params:**
```python
{
    "threshold_pct": 2.0,        # минимум % изменения
    "direction": "up" | "down" | "any"  # опционально
}
```

**Example:**
```python
result = patterns.search(
    symbol="NQ",
    period_start="2024-01-01",
    period_end="2024-06-30",
    pattern_name="big_move",
    params={"threshold_pct": 2.0, "direction": "up"}
)
```

**Response:**
```python
{
    "pattern": "big_move",
    "params": {"threshold_pct": 2.0, "direction": "up"},
    "matches": [
        {
            "date": "2024-03-15",
            "change_pct": 2.5,
            "change_points": 425.0,
            "direction": "up"
        },
        ...
    ],
    "matches_count": 5
}
```

### 3. reversal

Внутридневной разворот (большая тень).

**Params:**
```python
{
    "threshold_pct": 1.0         # минимум % разворота
}
```

**Logic:**
- `up_reversal`: low очень низко, но close высоко (hammer)
- `down_reversal`: high очень высоко, но close низко (shooting star)

**Response:**
```python
{
    "pattern": "reversal",
    "matches": [
        {
            "date": "2024-02-10",
            "type": "up_reversal",
            "reversal_pct": 1.5,
            "open": 17000,
            "high": 17100,
            "low": 16850,
            "close": 17050
        }
    ]
}
```

### 4. gap

Гэп вверх или вниз на открытии.

**Params:**
```python
{
    "min_gap_pct": 0.5,          # минимум % гэпа
    "direction": "up" | "down" | "any"
}
```

**Logic:**
- `gap_up`: open > previous_close
- `gap_down`: open < previous_close

**Response:**
```python
{
    "pattern": "gap",
    "matches": [
        {
            "date": "2024-03-20",
            "direction": "up",
            "gap_pct": 1.2,
            "gap_points": 200,
            "previous_close": 17000,
            "open": 17200
        }
    ]
}
```

### 5. range_breakout

Пробой максимума/минимума за N дней.

**Params:**
```python
{
    "lookback_days": 20          # период для определения range
}
```

**Logic:**
- `high_breakout`: high > max(high) за lookback дней
- `low_breakout`: low < min(low) за lookback дней

**Response:**
```python
{
    "pattern": "range_breakout",
    "matches": [
        {
            "date": "2024-04-15",
            "type": "high_breakout",
            "breakout_price": 18000,
            "previous_high": 17800,
            "lookback_days": 20
        }
    ]
}
```

## Pattern Registry

```python
PATTERNS: dict[str, Callable] = {
    "consecutive_days": find_consecutive_days,
    "big_move": find_big_moves,
    "reversal": find_reversals,
    "gap": find_gaps,
    "range_breakout": find_range_breakouts,
}
```

## Adding New Pattern

1. Создать функцию в `patterns.py`:
```python
def find_my_pattern(
    rows: list[dict],
    params: dict
) -> list[dict]:
    matches = []
    # ... логика поиска
    return matches
```

2. Добавить в `PATTERNS`:
```python
PATTERNS["my_pattern"] = find_my_pattern
```

3. Добавить в `DATA_CAPABILITIES` (`agent/capabilities.py`):
```python
DATA_CAPABILITIES = """
...
Patterns:
- my_pattern: описание
"""
```

4. Добавить пример в промпт Understander

## Error Handling

Unknown pattern:
```python
{
    "pattern": "unknown_pattern",
    "error": "Unknown pattern: unknown_pattern",
    "available_patterns": ["consecutive_days", "big_move", ...]
}
```

No data:
```python
{
    "pattern": "big_move",
    "matches": [],
    "matches_count": 0,
    "message": "No matches found"
}
```

## Performance

Все паттерны работают на Python после загрузки данных из DuckDB.
Для больших периодов (годы) может быть медленно.

Оптимизация: добавить SQL-based поиск для простых паттернов.
