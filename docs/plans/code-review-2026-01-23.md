# Code Review: agent/

**Дата:** 2026-01-23
**Оценка:** 72/100 (Senior level)
**Цель:** Staff BigTech level

---

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 1 | DONE |
| High | 4 | 3 DONE, 1 WONTFIX |
| Medium | 6 | ALL DONE |
| Low | 6 | Backlog |

---

## Critical

### C1. SQL string interpolation в логах

**Файл:** `agent/modules/sql.py:311`

```python
# ❌ Сейчас — опасный паттерн
sql_query = template.replace("$1", f"'{symbol}'").replace("$2", f"'{period_start}'")

# ✅ Нужно — безопасное логирование
sql_query = f"template={granularity}, symbol={symbol}, period={period_start}..{period_end}"
```

**Риск:** Если кто-то скопирует этот паттерн для реального запроса — SQL injection.

---

## High

### H1. Race condition в синглтонах

**Файлы:**
- `agent/prompts/semantic_parser/rap.py:258-266`
- `agent/graph.py:167-174`
- `agent/logging/supabase.py:29-37`

```python
# ❌ Сейчас — не thread-safe
_instance = None
def get_instance():
    global _instance
    if _instance is None:
        _instance = create()
    return _instance

# ✅ Нужно — double-check locking
import threading
_instance = None
_lock = threading.Lock()

def get_instance():
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = create()
    return _instance
```

---

### H2. Asyncio anti-patterns

**Файлы:**
- `agent/logging/supabase.py:221-234`
- `agent/memory/conversation.py:166-176, 260-269`

```python
# ❌ Сейчас — fire-and-forget теряет exceptions
asyncio.create_task(log_trace_step(...))

# ❌ Deprecated в Python 3.10+
loop = asyncio.get_event_loop()

# ✅ Нужно
async def _safe_log(...):
    try:
        await log_trace_step(...)
    except Exception as e:
        logger.error(f"Logging failed: {e}")

# Или использовать run_in_executor для sync context
```

---

### H3. Silent failures скрывают ошибки

**Файл:** `agent/modules/sql.py:383-396`

```python
# ❌ Сейчас
except Exception:
    return None  # Что случилось? БД упала? Нет данных?

# ✅ Нужно
except Exception as e:
    logger.error(f"get_data_range failed for {symbol}: {e}")
    return None
```

---

### H4. API key в атрибутах объектов

**Файлы:** `agent/prompts/semantic_parser/rap.py:76`, `agent/agents/parser.py:38`

```python
# ❌ Риск утечки при сериализации/логировании
self.client = genai.Client(api_key=config.GOOGLE_API_KEY)

# ✅ Защита
def __repr__(self):
    return f"<{self.__class__.__name__} model={self.model}>"  # Без client
```

---

## Medium

### M1. Нет валидации входных строк

**Файл:** `agent/date_resolver.py`

```python
# ❌ Regex DoS возможен с длинными строками
def resolve_date(when: str, ...):
    when_lower = when.lower().strip()

# ✅ Нужно
def resolve_date(when: str, ...):
    if not when or len(when) > 100:
        raise ValueError("Invalid date specification")
```

---

### M2. Inconsistent error handling в operations

**Проблема:** Разные операции возвращают ошибки по-разному.

```python
# around.py
return {"rows": [], "summary": {"error": "..."}}

# другие файлы — могут raise или return {}
```

**Решение:** Единый helper:

```python
# agent/operations/_utils.py
def error_result(message: str) -> dict:
    return {"rows": [], "summary": {"error": message, "count": 0}}
```

---

### M3. Incomplete type hints

**Файл:** `agent/agents/planner.py`

```python
# ❌ Сейчас
def execute_plan(plan) -> dict:

# ✅ Нужно
def execute_plan(plan: ExecutionPlan) -> ExecutionResult:
```

---

### M4. Magic numbers должны быть в config

**Файл:** `agent/memory/conversation.py:63-65`

```python
# ❌ Сейчас
recent_limit: int = 10
summary_chunk_size: int = 6
max_summaries: int = 3

# ✅ Нужно — в config.py
MEMORY_RECENT_LIMIT = 10
MEMORY_SUMMARY_CHUNK_SIZE = 6
MEMORY_MAX_SUMMARIES = 3
```

---

### M5. Memory leak в PatternDetector

**Файл:** `agent/patterns/scanner.py:28-86`

```python
# ❌ Держит большие numpy arrays
class PatternDetector:
    def __init__(self, df: pd.DataFrame):
        self.o = df["open"].values.astype(float)
        self.h = df["high"].values.astype(float)
        # ... ещё 10 массивов

# ✅ Stateless функция
def detect_patterns(df: pd.DataFrame, patterns: list[str]) -> pd.DataFrame:
    ...
```

---

### M6. Unbounded cache

**Файл:** `agent/prompts/semantic_parser/rap.py:76-119`

```python
# ❌ Растёт бесконечно
self.embeddings: dict[str, list[float]] = {}

# ✅ Нужен TTL или size limit
from functools import lru_cache
# Или добавить created_at и очищать старые
```

---

## Low

### L1. print() вместо logger

**Файл:** `agent/logging/supabase.py:67, 102`

```python
# ❌
print(f"Error: {e}")

# ✅
logger.error(f"Error: {e}")
```

---

### L2. Hardcoded start year

**Файл:** `agent/date_resolver.py:35`

```python
# ❌
return "2008-01-01", today.isoformat()

# ✅ Из конфига инструмента
start = config.DATA_START_DATE  # или из instruments.py
```

---

### L3. Test coverage gaps

**Не покрыты тестами:**
- `agent/prompts/semantic_parser/rap.py`
- `agent/logging/supabase.py`
- `agent/memory/conversation.py`
- Error paths во всех operations

---

### L4. Missing docstrings

**Файл:** `agent/rules/filters.py`

```python
# ❌
def is_always_where(filter_type: str) -> bool:
    return filter_type in ALWAYS_WHERE

# ✅
def is_always_where(filter_type: str) -> bool:
    """Check if filter type is always a WHERE clause (pre-filter)."""
    return filter_type in ALWAYS_WHERE
```

---

### L5. Duplicate imports

**Файл:** `agent/prompts/analyst.py` — `json` импортируется дважды в разных функциях.

---

### L6. Timestamp truncation loses data

**Файл:** `agent/modules/sql.py:317-320`

```python
# Обрезает время, может быть нужно
df[col] = df[col].astype(str).str[:10]
```

---

## Roadmap to Staff Level

### Phase 1: Safety (4 hours)
- [ ] C1: Fix SQL logging
- [ ] H1: Thread-safe singletons
- [ ] H3: Add logging to silent failures
- [ ] M1: Input validation

### Phase 2: Consistency (3 hours)
- [ ] M2: Standardize error handling
- [ ] M3: Complete type hints
- [ ] M4: Move magic numbers to config

### Phase 3: Reliability (4 hours)
- [ ] H2: Fix asyncio patterns
- [ ] M5: Fix PatternDetector memory
- [ ] M6: Add cache limits

### Phase 4: Polish (2 hours)
- [ ] L1-L6: All low priority items
- [ ] Add missing tests

**Total: ~13 hours to Staff level**

---

## Staff Engineer Checklist

После всех исправлений код должен соответствовать:

- [ ] **Thread safety**: Все синглтоны thread-safe
- [ ] **Error handling**: Typed exceptions, Result pattern, no bare except
- [ ] **Observability**: Structured logging везде, metrics ready
- [ ] **Input validation**: Paranoid validation на границах системы
- [ ] **Type safety**: 100% typed, mypy strict mode passes
- [ ] **Test coverage**: 80%+, all error paths covered
- [ ] **Memory safety**: No unbounded caches, no leaks
- [ ] **Documentation**: All public APIs documented

---

## Что отличает Staff от Senior

### 1. Defensive Programming

Senior пишет код который работает. Staff пишет код который **не может сломаться**.

```python
# Senior — работает
def get_user(id: str) -> User:
    return db.query(User).filter_by(id=id).first()

# Staff — защищён от всего
def get_user(id: str) -> User | None:
    if not id or len(id) > 36:
        logger.warning(f"Invalid user id format: {id[:20]}...")
        return None
    try:
        return db.query(User).filter_by(id=id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB error fetching user {id}: {e}")
        raise UserFetchError(id) from e
```

### 2. Думает о Production с первой строки

| Аспект | Senior | Staff |
|--------|--------|-------|
| Logging | Добавляет когда дебажит | Планирует структуру логов заранее |
| Errors | `try/except` когда падает | Error taxonomy с первого дня |
| Metrics | "Потом добавим" | Instrumentation в каждой функции |
| Concurrency | "У нас один поток" | Lock на всякий случай |

### 3. Typed Errors вместо строк

```python
# Senior
return {"error": "User not found"}

# Staff
class AppError(Exception):
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}

class UserNotFoundError(AppError):
    def __init__(self, user_id: str):
        super().__init__(
            code="USER_NOT_FOUND",
            message=f"User {user_id} not found",
            details={"user_id": user_id}
        )

# Теперь можно:
# - Ловить конкретные ошибки
# - Автоматически конвертить в HTTP codes
# - Логировать structured data
# - Мониторить по error codes
```

### 4. Result Pattern вместо exceptions

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")

@dataclass
class Ok(Generic[T]):
    value: T

@dataclass
class Err(Generic[E]):
    error: E

Result = Ok[T] | Err[E]

# Использование
def divide(a: int, b: int) -> Result[float, str]:
    if b == 0:
        return Err("Division by zero")
    return Ok(a / b)

# Caller вынужден обработать оба случая
match divide(10, 0):
    case Ok(value):
        print(f"Result: {value}")
    case Err(error):
        print(f"Error: {error}")
```

### 5. Observability by Design

```python
# Staff добавляет в каждую важную функцию:

import structlog
from prometheus_client import Counter, Histogram

logger = structlog.get_logger()

OPERATION_COUNT = Counter("operation_total", "Operations", ["operation", "status"])
OPERATION_DURATION = Histogram("operation_seconds", "Duration", ["operation"])

def op_list(df: pd.DataFrame, what: str, params: dict) -> dict:
    with OPERATION_DURATION.labels(operation="list").time():
        logger.info("op_list.start", what=what, rows=len(df), params=params)

        try:
            result = _do_list(df, what, params)
            OPERATION_COUNT.labels(operation="list", status="success").inc()
            logger.info("op_list.success", result_count=len(result["rows"]))
            return result
        except Exception as e:
            OPERATION_COUNT.labels(operation="list", status="error").inc()
            logger.error("op_list.error", error=str(e), what=what)
            raise
```

### 6. Тесты как документация

```python
# Senior — тестирует happy path
def test_get_user():
    user = get_user("123")
    assert user.name == "John"

# Staff — тестирует контракт
class TestGetUser:
    """User retrieval contract."""

    def test_returns_user_for_valid_id(self):
        """Valid ID returns user object."""

    def test_returns_none_for_nonexistent_id(self):
        """Non-existent ID returns None, not exception."""

    def test_raises_on_invalid_id_format(self):
        """Malformed ID raises ValueError with details."""

    def test_raises_on_database_error(self):
        """Database errors wrapped in UserFetchError."""

    def test_logs_warning_on_invalid_format(self):
        """Invalid format logged for monitoring."""

    def test_handles_concurrent_access(self):
        """Thread-safe under concurrent load."""
```

### 7. Принцип "Не доверяй никому"

```python
# Senior — доверяет внутренним вызовам
def process(data: dict) -> Result:
    user_id = data["user_id"]  # KeyError если нет
    return do_something(user_id)

# Staff — валидирует на каждой границе
def process(data: dict) -> Result:
    # Граница: входные данные
    if not isinstance(data, dict):
        raise InvalidInputError("Expected dict")

    user_id = data.get("user_id")
    if not user_id:
        raise InvalidInputError("user_id required")

    if not isinstance(user_id, str) or len(user_id) > 36:
        raise InvalidInputError("user_id must be string <= 36 chars")

    # Теперь безопасно
    return do_something(user_id)
```

### 8. Memory и Resource Management

```python
# Senior
class Cache:
    def __init__(self):
        self.data = {}

    def set(self, key, value):
        self.data[key] = value  # Растёт бесконечно

# Staff
from collections import OrderedDict
from threading import Lock

class BoundedCache:
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._data: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = Lock()

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            # Evict oldest if full
            while len(self._data) >= self._max_size:
                self._data.popitem(last=False)

            self._data[key] = {
                "value": value,
                "expires_at": time.time() + self._ttl
            }

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            if time.time() > item["expires_at"]:
                del self._data[key]
                return None
            return item["value"]
```

---

## Конкретные изменения для этого проекта

### Сейчас → Staff Level

| Файл | Сейчас | Staff Level |
|------|--------|-------------|
| `modules/sql.py` | `except Exception: return None` | Typed `DatabaseError`, logging, metrics |
| `graph.py` | Global `_graph` без lock | Thread-safe singleton с lazy init |
| `operations/*.py` | `{"error": "..."}` | `Result[OperationResult, OperationError]` |
| `date_resolver.py` | Нет валидации | `raise ValueError` на невалидный input |
| `memory/conversation.py` | `asyncio.create_task()` | Background task с error handling |
| Все файлы | Mix of `print`/`logger` | `structlog` везде, structured data |

### Новые файлы для Staff Level

```
agent/
├── errors.py          # Error taxonomy
├── result.py          # Result[T, E] pattern
├── observability.py   # Logging + metrics setup
└── validation.py      # Input validators
```

### Пример errors.py

```python
"""Typed error hierarchy for the agent."""

from dataclasses import dataclass, field
from typing import Any

@dataclass
class AgentError(Exception):
    """Base error for all agent errors."""
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

@dataclass
class ValidationError(AgentError):
    """Input validation failed."""
    code: str = "VALIDATION_ERROR"

@dataclass
class DatabaseError(AgentError):
    """Database operation failed."""
    code: str = "DATABASE_ERROR"

@dataclass
class LLMError(AgentError):
    """LLM call failed."""
    code: str = "LLM_ERROR"

@dataclass
class OperationError(AgentError):
    """Data operation failed."""
    code: str = "OPERATION_ERROR"
```

---

## Итого: Gap Analysis

| Критерий | Вес | Текущий | Staff | Gap |
|----------|-----|---------|-------|-----|
| Error Handling | 20% | 50% | 95% | -45% |
| Thread Safety | 15% | 30% | 95% | -65% |
| Type Safety | 15% | 75% | 95% | -20% |
| Test Coverage | 15% | 60% | 85% | -25% |
| Observability | 15% | 40% | 90% | -50% |
| Input Validation | 10% | 50% | 95% | -45% |
| Documentation | 10% | 60% | 85% | -25% |

**Weighted Score: 72/100 → Target: 92/100**

Основной gap: **Error Handling + Thread Safety + Observability**

Это три области где Senior → Staff происходит скачок.
