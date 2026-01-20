# Stock Trading Assistant

AI-ассистент для анализа торговых данных. Сейчас работает с NQ futures, будет расширяться на другие инструменты.

## Ключевой принцип

**Code for Facts, LLM for Text**

- Код вычисляет факты детерминированно (паттерны, события, статистика)
- LLM только форматирует готовый контекст в человеческий текст
- LLM не видит сырые данные — не может галлюцинировать цифры

## Архитектура

```
User Question → Parser → Executor → DataResponder → Response
                  ↓          ↓            ↓
              ParsedQuery   SQL/DB    Context → LLM
```

### Pipeline

1. **Parser** (`agent/prompts/parser.py`) — разбирает вопрос в структурированный ParsedQuery (intent, what, period, filters)
2. **Executor** (`agent/executor.py`) — строит и выполняет SQL запрос
3. **DataResponder** (`agent/agents/responders/data.py`) — собирает контекст из данных и генерирует ответ

### Контекст для LLM

DataResponder собирает контекст из:
- **Флаги паттернов** — is_hammer, is_doji и т.д. (из SQL)
- **События** — OPEX, NFP, VIX expiration (проверка дат по конфигу)
- **Праздники** — market holidays, early close (из конфига)

LLM получает готовый контекст типа `3× red, 1× Quad Witching` и пишет человеческий текст.

## Структура

```
agent/
├── prompts/           # Промпты для LLM (parser, responder, analyst)
├── agents/
│   └── responders/    # DataResponder и другие
├── executor.py        # SQL генерация и выполнение
├── patterns/
│   └── scanner.py     # Numpy-детекция паттернов
├── config/
│   ├── patterns/      # Свечные и ценовые паттерны
│   │   ├── candle.py  # hammer, doji, engulfing...
│   │   └── price.py   # gap, trend...
│   ├── market/
│   │   ├── events.py  # OPEX, NFP, Quad Witching
│   │   └── holidays.py
│   └── instruments/   # (будет) настройки инструментов
└── tests/             # Тесты

docs/
├── architecture/      # Описание архитектуры
├── plans/             # Roadmap, идеи фич
├── gemini/            # Гайды по Gemini API
├── claude/            # Prompt engineering гайды
└── code-guides/       # Стиль кода, комментирование
```

## Конфиги паттернов

Каждый паттерн в `agent/config/patterns/candle.py`:

```python
"hammer": {
    "name": "Hammer",
    "category": "reversal",      # reversal, continuation, neutral
    "signal": "bullish",         # bullish, bearish, neutral
    "importance": "medium",      # high, medium, low — для фильтрации
    "description": "...",        # для LLM контекста
    "detection": {...},          # параметры детекции
    "related": [...],            # связанные паттерны
}
```

`importance` определяет что показывать:
- **high** — всегда упоминаем (engulfing, morning/evening star)
- **medium** — упоминаем если немного паттернов или встречается часто
- **low** — только если совсем мало паттернов

## Тестирование

```bash
source .venv/bin/activate

python -m agent.tests.test_graph_v2 -s    # single questions
python -m agent.tests.test_graph_v2 -c    # conversations
python -m agent.tests.test_graph_v2 -i    # interactive
```

## Стек

- Python 3.11+
- DuckDB — аналитическая БД
- Google Gemini — LLM
- Pydantic — типизация
- Supabase — (скоро) персистенция переписок и трейсов

## Code Quality (Senior+ уровень)

### Типизация
```python
# ДА — полная типизация
def calculate_stats(rows: list[dict], metric: str) -> StatsResult:
    ...

# НЕТ — без типов
def calculate_stats(rows, metric):
    ...
```

### Функции
```python
# ДА — маленькие, одна задача, понятное имя
def extract_dates_from_rows(rows: list[dict]) -> list[str]:
    """Extract unique date strings from data rows."""
    ...

def check_dates_for_holidays(dates: list[str]) -> dict:
    """Check which dates are holidays."""
    ...

# НЕТ — большая функция делает всё
def process_data(rows):
    # 100 строк которые делают 5 разных вещей
    ...
```

### Именование
```python
# ДА — глагол для действий, существительное для данных
def build_context() -> str: ...
def get_pattern_info(name: str) -> dict: ...
flag_counts: dict[str, int] = {}
pattern_names: list[str] = []

# НЕТ — непонятные сокращения
def proc() -> str: ...
def get_pi(n: str) -> dict: ...
fc = {}
pn = []
```

### Ранний выход
```python
# ДА — guard clauses, fail fast
def get_pattern(name: str) -> dict | None:
    if not name:
        return None
    if name not in PATTERNS:
        return None
    return PATTERNS[name]

# НЕТ — вложенные if
def get_pattern(name: str) -> dict | None:
    if name:
        if name in PATTERNS:
            return PATTERNS[name]
    return None
```

### Обработка ошибок
```python
# ДА — явная обработка, логирование
try:
    result = client.query(sql)
except QueryError as e:
    logger.error(f"Query failed: {e}", extra={"sql": sql})
    raise ExecutorError(f"Failed to execute query") from e

# НЕТ — глотаем ошибки
try:
    result = client.query(sql)
except:
    pass
```

### Комментарии
```python
# ДА — объясняем ПОЧЕМУ, не ЧТО
# Skip low importance patterns when there are many — avoid cluttering the response
if importance == "low" and total_flags > 3:
    continue

# НЕТ — очевидные комментарии
# increment counter by 1
counter += 1
```

### Структура модуля
```python
"""
Module docstring — одно предложение что делает модуль.

Подробнее если нужно.
"""

from __future__ import annotations

# stdlib
import json
from datetime import date

# third-party
import pandas as pd
from pydantic import BaseModel

# local
from agent.config import get_pattern


# Constants
DEFAULT_THRESHOLD = 0.5


# Public API
def main_function() -> Result:
    """Public function with docstring."""
    ...


# Private helpers
def _helper() -> str:
    ...
```

### Принципы
- **Explicit > Implicit** — никакой магии, всё явно
- **Flat > Nested** — максимум 2 уровня вложенности
- **Pure > Stateful** — предпочитаем чистые функции
- **Composition > Inheritance** — композиция вместо наследования
- **Data > Objects** — dataclass/dict вместо сложных классов

### Чего избегать
- `**kwargs` без необходимости — теряем типизацию
- Глобальные переменные — кроме констант
- Классы ради классов — если хватит функции, используй функцию
- Комментарии для плохого кода — лучше перепиши код
- `Any` тип — если не знаешь тип, разберись

## TODO

- [ ] Чистка старых артефактов
- [ ] Подключение к фронту
- [ ] Supabase для переписок и трейсов
- [ ] Anomaly Finder модуль (docs/plans/anomaly_finder.md)
- [ ] Больше инструментов (ES, CL, GC)
- [ ] Индикаторы
