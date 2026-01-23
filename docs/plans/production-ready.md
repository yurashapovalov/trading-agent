# Production Ready Plan

Code review от 2026-01-23. Оценка: 70/100.

## Phase 1: Critical (блокируют продакшен)

### 1.1 SQL Injection в data/bars.py

**Проблема:** f-strings в SQL запросах (строки 62-152)

```python
# ❌ Сейчас
sql = f"""
    SELECT ... FROM ohlcv_1min
    WHERE symbol = '{symbol}'
      AND timestamp >= '{start}'
"""

# ✅ Нужно
sql = """
    SELECT ... FROM ohlcv_1min
    WHERE symbol = ?
      AND timestamp >= ?
"""
df = con.execute(sql, [symbol, start]).fetchdf()
```

**Файлы:** `agent/data/bars.py`
**Усилия:** 1 час

---

### 1.2 DRY: Extract shared utilities

**Проблема:** Дублирование кода в операциях

#### 1.2.1 `_what_to_column()` — 7 копий

Файлы:
- `operations/compare.py:69`
- `operations/correlation.py:70`
- `operations/count.py:31`
- `operations/distribution.py:61`
- `operations/list.py:43`
- `operations/probability.py:192`
- `operations/streak.py:139`

**Решение:** Создать `agent/operations/_utils.py`

```python
# agent/operations/_utils.py
"""Shared utilities for operations."""

from agent.rules.metrics import get_column

def metric_to_column(metric: str) -> str:
    """Map metric name to DataFrame column.

    Uses rules/metrics.py as source of truth.
    Falls back to metric name if not found.
    """
    return get_column(metric)
```

#### 1.2.2 `_find_consecutive_events()` — 3 копии

Файлы:
- `operations/streak.py:105-144`
- `operations/probability.py:105-162`
- `operations/around.py:83-124`

**Решение:** Добавить в `agent/operations/_utils.py`

```python
def find_consecutive_events(
    df: pd.DataFrame,
    color: str,
    op: str,
    length: int
) -> pd.DataFrame:
    """Find last day of each consecutive streak.

    Args:
        df: DataFrame with is_green column
        color: "green" or "red"
        op: ">=", ">", "="
        length: minimum streak length

    Returns:
        DataFrame with last day of each matching streak
    """
    if "is_green" not in df.columns:
        return pd.DataFrame()

    mask = df["is_green"] if color == "green" else ~df["is_green"]

    df = df.copy()
    df["_streak_id"] = (mask != mask.shift()).cumsum()

    streak_lengths = df.groupby("_streak_id").size()

    if op == ">=":
        valid = streak_lengths[streak_lengths >= length].index
    elif op == ">":
        valid = streak_lengths[streak_lengths > length].index
    elif op == "=":
        valid = streak_lengths[streak_lengths == length].index
    else:
        valid = streak_lengths[streak_lengths >= length].index

    result = []
    for streak_id in valid:
        streak_rows = df[(df["_streak_id"] == streak_id) & mask]
        if not streak_rows.empty:
            result.append(streak_rows.iloc[-1])

    if not result:
        return pd.DataFrame()

    return pd.DataFrame(result)
```

**Усилия:** 1.5 часа

---

### 1.3 Parser error handling

**Проблема:** Bare Exception, silent failures (`parser.py:77-79`)

```python
# ❌ Сейчас
except Exception as e:
    logger.error(f"Parse error: {e}")
    # Returns empty steps, graph continues

# ✅ Нужно
except json.JSONDecodeError as e:
    logger.error(f"JSON parse failed: {e}")
    raise ParserError(f"Invalid JSON from LLM: {e}") from e
except ValidationError as e:
    logger.error(f"Schema validation failed: {e}")
    raise ParserError(f"Invalid parser output: {e}") from e
```

**Решение:**
1. Создать `ParserError` exception
2. Обрабатывать в `graph.py` с понятным сообщением пользователю

**Усилия:** 0.5 часа

---

### 1.4 Event filtering incomplete

**Проблема:** `executor.py:258-260` — TODO stub

```python
elif f.get("event"):
    # TODO: implement event filtering
    pass
```

**Решение:** Либо реализовать, либо убрать из поддерживаемых фильтров.

События для реализации:
- `fomc` — FOMC meeting days
- `opex` — Options expiration
- `cpi` — CPI release days

**Файлы:**
- `agent/agents/executor.py`
- `agent/config/market/events.py` (создать)

**Усилия:** 2 часа (или 0.5 если просто убрать)

---

## Phase 2: Hardening

### 2.1 Logging в операциях

**Проблема:** Нет логов, сложно дебажить в продакшене

**Решение:** Добавить logging во все операции

```python
import logging

logger = logging.getLogger(__name__)

def op_list(df: pd.DataFrame, what: str, params: dict) -> dict:
    logger.debug(f"op_list: what={what}, params={params}, rows={len(df)}")

    if df.empty:
        logger.warning(f"op_list: empty dataframe")
        return {"rows": [], "summary": {"count": 0}}
```

**Файлы:** Все `operations/*.py`
**Усилия:** 2 часа

---

### 2.2 Config validation

**Проблема:** `config.py` — нет валидации при старте

**Решение:** Pydantic Settings

```python
# config.py
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator

class Settings(BaseSettings):
    google_api_key: str = Field(..., env="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash")
    database_path: str = Field(..., env="DATABASE_PATH")

    @field_validator("google_api_key")
    @classmethod
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError("GOOGLE_API_KEY invalid or not set")
        return v

    class Config:
        env_file = ".env"

# Validate at import time
settings = Settings()
```

**Усилия:** 1 час

---

### 2.3 Fix circular imports

**Проблема:** `planner.py:256` — late import from executor

**Решение:** Вынести `resolve_date()` в отдельный модуль

```
agent/
├── date_resolver.py  ← уже существует, расширить
```

**Усилия:** 1 час

---

### 2.4 Standardize error responses

**Проблема:** Разные форматы ошибок в операциях

```python
# Где-то
return {"error": "message"}

# Где-то
return {"rows": [], "summary": {"error": "message"}}
```

**Решение:** Единый формат

```python
# Всегда возвращать
{
    "rows": [...],
    "summary": {...},
    "error": "message" | None
}
```

**Усилия:** 1 час

---

### ~~2.5 Weak parameter validation~~ — НЕ АКТУАЛЬНО

Rules система (`agent/rules/filters.py`) уже валидирует параметры:
- `parse_filters()` возвращает типизированные dict
- metric, op, value уже провалидированы regex'ом
- Невалидные фильтры возвращают None и игнорируются

Executor использует `parse_filters` → валидация есть.

---

## Phase 3: Polish

### 3.1 Type hints consistency

Везде использовать `X | None` вместо `Optional[X]`

### 3.2 Unit tests

Создать:
```
agent/tests/
├── test_operations.py
├── test_executor.py
├── test_filters.py
└── test_date_resolver.py
```

### 3.3 State typing

Использовать TypedDict для graph state

---

## Checklist

### Phase 1: Critical
- [x] 1.1 SQL injection fix → parameterized queries в bars.py
- [x] 1.2.1 ~~Extract `_what_to_column()` to `_utils.py`~~ → используем `get_column` из rules
- [x] 1.2.2 Extract `_find_consecutive_events()` to `_utils.py`
- [x] 1.3 Parser error handling → конкретные exceptions вместо bare Exception
- [x] 1.4 Event filtering → warning log вместо silent pass

### Phase 2: Hardening
- [ ] 2.1 Add logging to operations
- [ ] 2.2 Config validation with Pydantic
- [ ] 2.3 Fix circular imports
- [ ] 2.4 Standardize error responses

### Phase 3: Polish
- [ ] 3.1 Type hints consistency
- [ ] 3.2 Unit tests
- [ ] 3.3 State typing

---

## Estimated Effort

| Phase | Hours |
|-------|-------|
| Phase 1 | 5-6 |
| Phase 2 | 5-6 |
| Phase 3 | 3-4 |
| **Total** | **13-16** |
