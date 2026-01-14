# Python Code Commenting Guide

Гайд по комментированию кода в проекте. Основан на [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html), [PEP 8](https://peps.python.org/pep-0008/), и [PEP 257](https://peps.python.org/pep-0257/).

## Главный Принцип

> **Comments explain WHY, not WHAT.**
> Код показывает ЧТО делается. Комментарии объясняют ПОЧЕМУ.

```python
# BAD: What (очевидно из кода)
x = x + 1  # увеличиваем x на 1

# GOOD: Why (объясняет причину)
x = x + 1  # компенсируем off-by-one в API response
```

---

## Docstrings vs Comments

| Тип | Для чего | Формат |
|-----|----------|--------|
| **Docstring** | Документирует API (что делает, параметры, возврат) | `"""triple quotes"""` |
| **Comment** | Объясняет реализацию (почему так, контекст, допущения) | `# single line` |

---

## Docstrings (Google Style)

### Модули

```python
"""Краткое описание модуля в одну строку.

Более детальное описание если нужно. Объясняет назначение модуля,
основные классы/функции, и как их использовать.

Example:
    from module import MyClass
    obj = MyClass()
    result = obj.process(data)
"""
```

### Функции и Методы

```python
def calculate_cost(input_tokens: int, output_tokens: int, model: str = "default") -> float:
    """Рассчитывает стоимость запроса к LLM.

    Использует актуальные цены из конфига. Поддерживает разные модели
    с разной ценовой политикой.

    Args:
        input_tokens: Количество входных токенов.
        output_tokens: Количество выходных токенов.
        model: Идентификатор модели. По умолчанию "default".

    Returns:
        Стоимость в USD.

    Raises:
        ValueError: Если модель неизвестна.

    Example:
        >>> calculate_cost(1000, 500, "gpt-4")
        0.045
    """
```

### Классы

```python
class QueryBuilder:
    """Строит SQL запросы из структурированной спецификации.

    Принимает QuerySpec и генерирует валидный DuckDB SQL.
    Гарантирует детерминированность: один QuerySpec = один SQL.

    Attributes:
        symbol: Торговый инструмент (NQ, ES).
        source: Источник данных (minutes, daily).

    Example:
        builder = QueryBuilder()
        sql = builder.build(spec)
    """
```

### Короткие Docstrings (однострочные)

```python
def get_name(self) -> str:
    """Возвращает имя пользователя."""
    return self._name
```

---

## Inline Comments

### Когда использовать

```python
# GOOD: Объясняет неочевидное решение
# ETH = Extended Trading Hours = всё кроме RTH, поэтому NOT BETWEEN
if session == "ETH":
    return "timestamp::time NOT BETWEEN '09:30:00' AND '16:00:00'"

# GOOD: Предупреждает о подводных камнях
# ВАЖНО: порядок важен — сначала high DESC, потом timestamp ASC для стабильности
order_clause = "high DESC, timestamp ASC"

# GOOD: Объясняет бизнес-логику
# Премаркет начинается в 04:00 ET, но данные могут быть с 18:00 предыдущего дня
if crosses_midnight:
    ...
```

### Когда НЕ использовать

```python
# BAD: Очевидно из кода
total = price * quantity  # умножаем цену на количество

# BAD: Устаревший комментарий (код изменился)
# Возвращает список пользователей
def get_user(id: int) -> User:  # на самом деле возвращает одного
    ...

# BAD: Commented-out code без объяснения
# old_method()
# another_old_thing()
new_method()
```

---

## Section Comments

Для разделения логических блоков в длинных файлах:

```python
# =============================================================================
# CTE Builders — Common Table Expressions для разных источников данных
# =============================================================================

def _build_minutes_cte(self, spec: QuerySpec) -> str:
    ...

def _build_daily_cte(self, spec: QuerySpec) -> str:
    ...


# =============================================================================
# Filter Builders — SQL условия для фильтрации
# =============================================================================

def _build_time_filter(self, filters: Filters) -> str:
    ...
```

---

## TODO Comments

```python
# TODO: Добавить поддержку множественных периодов
# TODO(username): Оптимизировать для больших датасетов
# FIXME: Не работает с отрицательными значениями
# HACK: Временное решение до рефакторинга API
# NOTE: Это поведение согласовано с product owner
```

---

## SQL в Python

```python
sql = f"""
WITH filtered_data AS (
    -- Минутные данные с применёнными фильтрами
    SELECT
        timestamp,
        timestamp::date as date,
        high,
        low
    FROM ohlcv_1min
    WHERE symbol = '{symbol}'
      AND timestamp >= '{period_start}'
      AND timestamp < '{period_end}'
      {extra_filters}  -- Динамические фильтры (время, календарь)
),
daily_extremes AS (
    -- Для каждого дня находим момент экстремума (high или low)
    -- Используем FIRST с ORDER BY для детерминированности при равных значениях
    SELECT
        date,
        FIRST(timestamp ORDER BY {order_clause}) as event_ts
    FROM filtered_data
    GROUP BY date
)
SELECT * FROM daily_extremes
"""
```

---

## Type Hints как Документация

Type hints — это тоже документация. Используй их везде:

```python
# Вместо комментария
def process(data):  # data это список словарей
    ...

# Используй type hints
def process(data: list[dict[str, Any]]) -> ProcessedResult:
    ...
```

---

## Чеклист перед коммитом

- [ ] Все публичные функции/классы имеют docstrings
- [ ] Docstrings описывают Args, Returns, Raises
- [ ] Комментарии объясняют WHY, не WHAT
- [ ] Нет закомментированного кода без объяснения
- [ ] TODO имеют контекст (что сделать, почему)
- [ ] Type hints везде где возможно

---

## Источники

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [PEP 8 – Style Guide](https://peps.python.org/pep-0008/)
- [PEP 257 – Docstring Conventions](https://peps.python.org/pep-0257/)
- [Real Python: Documenting Python Code](https://realpython.com/documenting-python-code/)
