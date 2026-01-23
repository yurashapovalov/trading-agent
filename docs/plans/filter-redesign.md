# Filter System Redesign

## Проблема

Текущая система использует единое поле `filter` в Atom для всех операций:

```python
class Atom(BaseModel):
    when: str      # период
    what: str      # метрика
    filter: str    # ← одно поле для всего
```

Но семантика filter различается по операциям:

| Вопрос | Ожидание | Текущее поведение |
|--------|----------|-------------------|
| "3+ red days in a row in 2024" | Найти серии из 3+ красных подряд | filter=`change<0` отфильтровывает только красные → streak видит 111 дней без разрывов → не может найти серии |
| "probability of green after 2+ red" | P(green) на день ПОСЛЕ серии | filter=`consecutive red>=2` оставляет дни внутри серий → проверяем change>0 на этих же днях (которые все красные) → 0% |

**Корень проблемы**: для одних операций filter = WHERE, для других filter = EVENT/CONDITION.

---

## Анализ операций

### Группа A: filter = WHERE (отбор строк)

| Операция | Что делает | filter семантика |
|----------|------------|------------------|
| **list** | top N по метрике | отфильтровать строки для сортировки |
| **count** | количество + статистика | посчитать отфильтрованные строки |
| **distribution** | гистограмма значений | распределение отфильтрованных |
| **correlation** | корреляция двух метрик | корреляция на отфильтрованных |

Пример: "top 10 red days" → filter=`change<0`, отсортировать, взять 10.

### Группа B: filter = EVENT (определение события)

| Операция | Что делает | filter семантика |
|----------|------------|------------------|
| **around** | что было до/после события | filter определяет EVENT, смотрим prev/next |
| **probability** | P(outcome \| condition) | filter определяет CONDITION, outcome проверяем на тех же или следующих днях |
| **streak** | серии N подряд | filter определяет CONDITION серии, нужны ВСЕ данные для поиска |

Пример: "what happens after big drops" → filter=`change<-2%` это EVENT, смотрим next_change.

### Группа C: особые случаи

| Операция | Что делает | filter семантика |
|----------|------------|------------------|
| **compare** | сравнение групп | multi-filter: каждый filter определяет группу |
| **formation** | когда формируется high/low | filter как WHERE (опционально) |

---

## Типы фильтров

### 1. Categorical (всегда WHERE)
```
monday, friday, tuesday, wednesday, thursday
session = RTH, session = OVERNIGHT
event = fomc, event = opex
```

### 2. Comparison (контекстно-зависимый)
```
change > 0, change < -2%
gap > 0, gap < -1%
range > 300, volume > 1000000
```

Для list/count/distribution → WHERE
Для around/streak → EVENT/CONDITION

### 3. Consecutive (всегда EVENT)
```
consecutive red >= 2
consecutive green >= 3
```

Не имеет смысла как WHERE (отфильтровать только дни внутри серий).
Имеет смысл как EVENT (найти серии, анализировать что после).

### 4. Time (всегда WHERE)
```
time >= 09:30, time < 12:00
```

### 5. Pattern (контекстно-зависимый)
```
inside_day, outside_day, doji, gap_fill
```

---

## Предлагаемая архитектура

### Вариант 1: Типизированные фильтры в схеме

```python
class CategoricalFilter(BaseModel):
    type: Literal["categorical"] = "categorical"
    weekday: Literal["monday", "tuesday", ...] | None = None
    session: str | None = None
    event: str | None = None

class ComparisonFilter(BaseModel):
    type: Literal["comparison"] = "comparison"
    metric: str  # change, gap, range, volume
    op: Literal[">", "<", ">=", "<=", "="]
    value: float

class ConsecutiveFilter(BaseModel):
    type: Literal["consecutive"] = "consecutive"
    color: Literal["red", "green"]
    op: Literal[">=", ">", "="]
    length: int

class TimeFilter(BaseModel):
    type: Literal["time"] = "time"
    op: Literal[">=", "<"]
    value: str  # "09:30"

class PatternFilter(BaseModel):
    type: Literal["pattern"] = "pattern"
    pattern: Literal["inside_day", "outside_day", "doji", "gap_fill", ...]

Filter = CategoricalFilter | ComparisonFilter | ConsecutiveFilter | TimeFilter | PatternFilter
```

Atom:
```python
class Atom(BaseModel):
    when: str
    what: str
    filters: list[Filter] = []  # типизированный список
    group: str | None = None
    timeframe: str = "1D"
```

### Вариант 2: Два поля — filter и event

```python
class Atom(BaseModel):
    when: str
    what: str
    filter: str | None = None   # WHERE условия (categorical, time)
    event: str | None = None    # EVENT условия (для around, streak, probability)
    group: str | None = None
    timeframe: str = "1D"
```

Parser решает куда класть:
- monday, session=RTH → filter
- change < -2%, consecutive red >= 2 → event (для around/streak/probability)

### Вариант 3: Семантика определяется операцией (минимальные изменения)

Схема не меняется. Executor для разных операций обрабатывает filter по-разному:

```python
# В executor
if operation in ("list", "count", "distribution", "correlation"):
    df = apply_filters(df, filters)  # WHERE
    result = OPERATIONS[operation](df, what, params)

elif operation == "streak":
    # НЕ применяем filter как WHERE
    # Передаём filter в params как condition
    params["condition"] = filters
    result = op_streak(df, what, params)

elif operation == "around":
    df = apply_filters(df, filters)  # WHERE для event selection
    # around использует prev/next_change которые уже в df
    result = op_around(df, what, params)
```

---

## Сравнение вариантов

| Критерий | Вариант 1 (типизация) | Вариант 2 (два поля) | Вариант 3 (executor) |
|----------|----------------------|---------------------|---------------------|
| Изменения схемы | Большие | Средние | Нет |
| Ясность архитектуры | Высокая | Средняя | Низкая (магия) |
| Валидация Pydantic | Полная | Частичная | Нет |
| Риск ошибок LLM | Выше (сложнее схема) | Средний | Ниже |
| Расширяемость | Отличная | Хорошая | Плохая |

---

## Рекомендация

**Вариант 1 (типизированные фильтры)** — лучший для долгосрочной архитектуры:

1. Pydantic валидирует каждый тип фильтра
2. Executor точно знает семантику (по type)
3. Можно добавить правила: `ConsecutiveFilter + streak → не применять как WHERE`
4. Самодокументируемо

### Правила применения по операции:

```python
FILTER_SEMANTICS = {
    # operation → какие типы фильтров как обрабатывать
    "list": {
        "categorical": "where",
        "comparison": "where",
        "consecutive": "where",  # отфильтровать дни внутри серий
        "time": "where",
        "pattern": "where",
    },
    "streak": {
        "categorical": "where",      # streak среди понедельников
        "comparison": "condition",   # условие серии
        "consecutive": "invalid",    # не имеет смысла
        "time": "where",
        "pattern": "condition",
    },
    "around": {
        "categorical": "where",      # события среди понедельников
        "comparison": "event",       # определяет событие
        "consecutive": "event",      # "после 3 красных"
        "time": "where",
        "pattern": "event",
    },
    "probability": {
        "categorical": "where",
        "comparison": "condition",   # P(outcome | condition)
        "consecutive": "condition",  # P(green | after 2+ red)
        "time": "where",
        "pattern": "condition",
    },
}
```

---

## Следующие шаги

1. [ ] Обсудить выбор варианта
2. [ ] Обновить types.py с новыми моделями Filter
3. [ ] Обновить промпты парсера с примерами
4. [ ] Обновить executor с логикой по типам
5. [ ] Обновить streak/around/probability операции
6. [ ] Протестировать на проблемных кейсах
7. [ ] Обновить архитектурную документацию
