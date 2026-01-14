# Как добавить новый кубик (Special Operation)

Этот гайд описывает процесс добавления нового кубика в систему QueryBuilder.

## Архитектура

```
Вопрос → Understander → QuerySpec → QueryBuilder → SQL → Data
                ↓
         special_op: "your_op"
         your_op_spec: {...}
```

**Single Source of Truth**: Все типы определены в `types.py`. JSON Schema для LLM генерируется автоматически.

## Пошаговая инструкция

### Шаг 1: Добавить enum в SpecialOp

**Файл:** `agent/query_builder/types.py`

```python
class SpecialOp(Enum):
    # ... существующие

    YOUR_OP = "your_op"
    """
    Краткое описание что делает операция.

    Пример: "найди корреляцию между инструментами"

    Логика:
    1. Описание SQL логики
    2. Что возвращает

    Требует: YourOpSpec с параметрами ...
    """
```

### Шаг 2: Создать Spec dataclass

**Файл:** `agent/query_builder/types.py` (там же)

```python
@dataclass
class YourOpSpec:
    """
    Параметры для операции YOUR_OP.

    Attributes:
        param1: Описание параметра
        param2: Описание параметра
    """

    param1: str
    param2: Literal["option1", "option2"] = "option1"
```

### Шаг 3: Добавить поле в QuerySpec

**Файл:** `agent/query_builder/types.py`

```python
@dataclass
class QuerySpec:
    # ... существующие поля

    your_op_spec: YourOpSpec | None = None
```

### Шаг 4: Зарегистрировать в schema.py

**Файл:** `agent/query_builder/schema.py`

```python
from .types import (
    # ... существующие
    YourOpSpec,
)

SPECIAL_OP_SPECS = {
    # ... существующие
    SpecialOp.YOUR_OP: YourOpSpec,
}
```

> **Важно:** После этого шага JSON Schema генерируется автоматически! Не нужно ничего менять в understander.py.

### Шаг 5: Создать Builder

**Файл:** `agent/query_builder/special_ops/your_op.py`

```python
"""
YOUR_OP — описание операции.
"""

from ..types import QuerySpec, SpecialOp
from .base import SpecialOpBuilder, SpecialOpRegistry


@SpecialOpRegistry.register
class YourOpBuilder(SpecialOpBuilder):
    """Builder для операции YOUR_OP."""

    op_type = SpecialOp.YOUR_OP

    def build_query(self, spec: QuerySpec, extra_filters_sql: str = "") -> str:
        """
        Строит SQL для YOUR_OP.

        Args:
            spec: QuerySpec с your_op_spec
            extra_filters_sql: Дополнительные фильтры

        Returns:
            SQL запрос
        """
        your_spec = spec.your_op_spec

        # Получить фильтры из spec
        symbol = spec.symbol
        period_start = spec.filters.period_start
        period_end = spec.filters.period_end

        sql = f"""
        WITH filtered AS (
            SELECT *
            FROM ohlcv_1min
            WHERE symbol = '{symbol}'
              AND timestamp >= '{period_start}'
              AND timestamp < '{period_end}'
              {extra_filters_sql}
        )
        SELECT
            -- ваша логика
        FROM filtered
        """

        return sql
```

### Шаг 6: Зарегистрировать Builder

**Файл:** `agent/query_builder/special_ops/__init__.py`

```python
from .your_op import YourOpBuilder

__all__ = [
    # ... существующие
    "YourOpBuilder",
]
```

### Шаг 7: Добавить парсинг в Understander

**Файл:** `agent/agents/understander.py`

В функции `_parse_query_spec()`:

```python
# Your Op Spec
your_op_spec = None
if special_op == SpecialOp.YOUR_OP:
    yos = query_spec.get("your_op_spec", {})
    your_op_spec = YourOpSpec(
        param1=yos.get("param1", "default"),
        param2=yos.get("param2", "option1"),
    )

return QuerySpec(
    # ... существующие
    your_op_spec=your_op_spec,
)
```

### Шаг 8: Обновить prompt

**Файл:** `agent/prompts/understander.py`

Добавить в секцию `special_op`:
- Описание когда использовать
- Пример вопроса
- Пример JSON output

```python
## special_op: "your_op"

Используй когда: [условие]

Пример вопроса: "..."

Пример output:
{
  "source": "minutes",
  "special_op": "your_op",
  "your_op_spec": {
    "param1": "value",
    "param2": "option1"
  }
}
```

### Шаг 9: Добавить тест в golden dataset

**Файл:** `agent/tests/test_integration.py`

```python
GoldenTestCase(
    name="your_op_test_case",
    question="вопрос на естественном языке",
    expected_special_op="your_op",
    expected_data={
        "some_field": "expected_value",
    },
),
```

Добавить pytest функцию:

```python
def test_your_op_test_case(run_test):
    """Test YOUR_OP - описание."""
    test_case = GOLDEN_DATASET[N]  # индекс в массиве
    passed, errors = run_test(test_case)
    assert passed, f"Failed: {errors}"
```

### Шаг 10: Запустить тесты

```bash
# Unit тесты
python -m pytest agent/query_builder/tests/ -v

# Интеграционные тесты
python agent/tests/test_integration.py
```

## Чеклист

- [ ] Enum добавлен в `SpecialOp`
- [ ] Создан `YourOpSpec` dataclass
- [ ] Поле добавлено в `QuerySpec`
- [ ] Зарегистрирован в `schema.py` → `SPECIAL_OP_SPECS`
- [ ] Создан `YourOpBuilder` с декоратором `@SpecialOpRegistry.register`
- [ ] Builder импортирован в `special_ops/__init__.py`
- [ ] Парсинг добавлен в `understander.py`
- [ ] Prompt обновлён с примерами
- [ ] Добавлен тест в golden dataset
- [ ] Все тесты проходят

## Файлы для изменения

| Файл | Что добавить |
|------|--------------|
| `types.py` | Enum + Spec dataclass + поле в QuerySpec |
| `schema.py` | Регистрация в SPECIAL_OP_SPECS |
| `special_ops/your_op.py` | Builder (новый файл) |
| `special_ops/__init__.py` | Import builder |
| `understander.py` | Парсинг spec |
| `prompts/understander.py` | Примеры для LLM |
| `tests/test_integration.py` | Golden dataset тест |

## Пример: FIND_EXTREMUM

Полный пример добавления кубика FIND_EXTREMUM:

1. **types.py**: `SpecialOp.FIND_EXTREMUM`, `FindExtremumSpec`, поле в QuerySpec
2. **schema.py**: `SpecialOp.FIND_EXTREMUM: FindExtremumSpec`
3. **special_ops/find_extremum.py**: `FindExtremumOpBuilder`
4. **understander.py**: парсинг `find_extremum_spec`
5. **prompt**: примеры "во сколько был хай..."

Время добавления: ~20-30 минут.
