# Features Roadmap

План реализации по приоритету (от простого к сложному).

## Статус текущих возможностей

| Возможность | Статус | Пример |
|-------------|--------|--------|
| Базовая аналитика | ✅ | "средняя волатильность по часам" |
| Группировка | ✅ | hour, weekday, month, year |
| Фильтры | ✅ | session=RTH, period 2024 |
| Virtual fields | ✅ | weekday='Friday' |
| Event time | ⚠️ частично | "когда формируется high" |
| Cross-symbol | ⚠️ частично | "correlation NQ/ES" |
| Паттерны свечей | ⚠️ частично | doji, hammer |

---

## Priority 1: Быстрые победы (1-2 дня)

### 1.1 CORR aggregate для одного символа
**Вопрос:** "Корреляция между объёмом и изменением цены"

**Сейчас:** CORR только в cross (между символами)
**Нужно:** Добавить CORR в AggregateFunc

```python
# atoms/data.py
class AggregateFunc:
    CORR = "corr"  # CORR(field1, field2)

# Специальный синтаксис для двух полей
Aggregate(func="corr", field="volume", field2="change_pct")
```

**Файлы:** atoms/data.py, builders/aggregate.py

---

### 1.2 Сезонность (уже работает?)
**Вопросы:**
- "В какой месяц года NQ растёт лучше всего?"
- "Есть ли сезонность в волатильности по месяцам?"

**Проверить:** analytics + group=["month"] + metrics=[avg(change_pct)]

---

### 1.3 Day-of-week (уже работает?)
**Вопросы:**
- "Какой день недели самый волатильный?"
- "Понедельники vs пятницы"

**Проверить:** analytics + group=["weekday"] или compare

---

## Priority 2: LAG-based features (3-5 дней)

### 2.1 Prev-day conditions
**Вопрос:** "Дни когда NQ упал >2% после роста >1% в предыдущий день"

**Требует:**
1. LAG(change_pct) AS prev_change_pct
2. Filter: change_pct < -2 AND prev_change_pct > 1

**Реализация:**
- Детектировать `prev_*` в filter
- Автоматически добавлять LAG stage

```python
# virtual_fields.py
PREV_FIELDS = {
    "prev_close": "LAG(close) OVER (ORDER BY timestamp)",
    "prev_change_pct": "LAG(change_pct) OVER (ORDER BY timestamp)",
    "prev_range": "LAG(range) OVER (ORDER BY timestamp)",
}
```

---

### 2.2 Gap fields
**Вопросы:**
- "Days with gap up > 1%"
- "Понедельники vs пятницы — где больше гэпов?"

**Требует:** prev_close + computed gap_pct

```python
gap_pct = (open - prev_close) / prev_close * 100
```

---

### 2.3 Streak detection
**Вопрос:** "Сколько раз было 3+ красных дня подряд?"

**Подход A:** Window function для подсчёта streak
```sql
SUM(CASE WHEN change_pct < 0 THEN 1 ELSE 0 END)
OVER (ORDER BY date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
```

**Подход B:** Sequence pattern в patterns molecule
```python
sequence: [
    {field: "change_pct", op: "<", value: 0},
    {field: "change_pct", op: "<", value: 0},
    {field: "change_pct", op: "<", value: 0},
]
```

---

## Priority 3: Compare enhancements (3-5 дней)

### 3.1 Period comparison
**Вопрос:** "Как NQ вёл себя в декабре за последние 3 года?"

**Сейчас:** compare для 2 срезов
**Нужно:** compare_multiple с автогенерацией периодов

```python
compare_multiple:
  dimension: "year"
  values: [2022, 2023, 2024]
  filter: {month: 12}
  metrics: [...]
```

---

### 3.2 Quarter comparison
**Вопрос:** "Если Q1 был красным, какой обычно Q2?"

**Требует:**
1. Группировка по year + quarter
2. Условная фильтрация (Q1 < 0)
3. Статистика по Q2 для этих лет

**Сложность:** Subquery или CTE

---

## Priority 4: Subqueries (5-7 дней)

### 4.1 Top-N then aggregate
**Вопрос:** "Топ-5 дней с максимальным объёмом, средний change_pct для них"

**Подход:**
```sql
WITH top_days AS (
    SELECT date FROM ... ORDER BY volume DESC LIMIT 5
)
SELECT AVG(change_pct) FROM ... WHERE date IN (SELECT date FROM top_days)
```

**Реализация:** Новый тип query composition

---

## Priority 5: Context/Memory (5-7 дней)

### 5.1 Follow-up questions
**Цепочка:**
1. "Статистика за март 2024"
2. "А теперь сравни с апрелем"
3. "Какой месяц лучше для лонгов?"

**Требует:**
- Сохранение контекста (период, фильтры)
- Распознавание references ("с апрелем" = с апрелем 2024)
- Merge/diff предыдущих результатов

---

## Priority 5.3: Formation extended events (3-5 дней)

### 5.3.1 Проблема: formation знает только high/low

**Текущее поведение:**
- `what: high` → находит час максимальной цены ✅
- `what: low` → находит час минимальной цены ✅
- `what: gap_fill` → молча fallback на high ❌
- `what: range_50` → молча fallback на high ❌

**Нужные события:**

1. **gap_fill** — "в какой час обычно закрывается гэп"
   ```python
   # Алгоритм:
   # 1. Для каждого дня берём prev_close
   # 2. Ищем первую минуту где:
   #    - gap > 0 и low <= prev_close (gap up filled)
   #    - gap < 0 и high >= prev_close (gap down filled)
   # 3. Час этой минуты = gap_fill_hour
   ```

2. **range_50** — "когда достигается 50% дневного диапазона"
   ```python
   # Алгоритм:
   # 1. Для каждого дня вычисляем daily_range = high - low
   # 2. target = open ± (daily_range * 0.5)
   # 3. Ищем первую минуту где цена достигла target
   ```

**Файл:** `agent/operations/formation.py`

**Быстрый fix:** вернуть ошибку "event not supported" вместо молчаливого fallback.

---

## Priority 5.4: Parser intent improvements (промпты)

### 5.4.1 "distributed across X" → compare, not distribution
**Вопрос:** "how is volume distributed across weekdays"

**Проблема:** Parser выбрал `distribution` буквально (по слову), но семантика = группировка.

**Правильно:**
```
operation: compare
group_by: weekday
```

**Решение:** Добавить пример в промпт парсера.

---

### 5.4.2 "gap fill" в probability → outcome: gap_filled
**Вопрос:** "chance of gap fill on gap down days"

**Сейчас:**
```
filter: "gap < 0"
outcome: "> 0"  ← понял как "green day"
```

**Правильно:**
```
filter: "gap < 0"
outcome: "gap_filled"  ← или filter: "gap < 0, gap_filled"
```

**Решение:**
1. Добавить пример в промпт парсера: "gap fill" → outcome использует gap_filled
2. Или: probability должен понимать outcome: "gap_filled" (сейчас только >, <, = числа)

---

## Priority 5.5: Gap-filled metric (1 день)

### 5.5.1 Метрика gap_filled
**Вопрос:** "сколько раз gap закрылся в тот же день"

**Проблема:** Parser понял как `gap = 0` (нет гэпа), а нужно "был гэп, но цена вернулась".

**Файл:** `agent/data/enrich.py`

**Реализация:**
```python
# В enrich() добавить:
prev_close = df["close"].shift(1)

# Gap up filled: открылись выше, но low дошёл до prev_close
gap_up_filled = (df["gap"] > 0) & (df["low"] <= prev_close)

# Gap down filled: открылись ниже, но high дошёл до prev_close
gap_down_filled = (df["gap"] < 0) & (df["high"] >= prev_close)

df["gap_filled"] = gap_up_filled | gap_down_filled
```

**После этого:**
- Parser: `filter: "gap_filled = true"` или `filter: "gap_filled"`
- Добавить в `agent/rules/metrics.py` метрику `gap_filled`

---

## Priority 6: Session-specific metrics (3-5 дней)

### 6.1 Метрики по сессиям
**Вопрос:** "correlation between overnight range and RTH range"

**Проблема:** Сейчас метрики глобальные (gap, change, range). Нет разбивки по сессиям.

**Нужно:**
- `overnight_range` — range за ночную сессию
- `rth_range` — range за RTH
- `morning_range`, `afternoon_range`

**Реализация:**
```python
# В enrich() добавить session-specific поля:
# 1. Агрегировать minute data по дню + сессии
# 2. Добавить в daily df как колонки

session_metrics = {
    "overnight_range": "range WHERE session=OVERNIGHT",
    "rth_range": "range WHERE session=RTH",
    "morning_range": "range WHERE time 09:30-12:30",
    "afternoon_range": "range WHERE time 12:30-16:00",
}
```

**Сложность:** Требует join daily + intraday данных

---

## Priority 7: Advanced (future)

### 7.1 GAP_CLOSE event
"Когда закрываются гэпы?"

### 7.2 Conditional sequences
"Если понедельник красный, какой вторник?"

### 7.3 Backtesting
Entry/exit conditions, P&L calculation

---

## Порядок проверки

Перед реализацией — проверить что уже работает:

```bash
# 1. Сезонность
"В какой месяц NQ растёт лучше всего?"

# 2. Day-of-week
"Какой день недели самый волатильный?"

# 3. Compare
"Сравни понедельники и пятницы по волатильности"

# 4. Event time
"Когда формируется дневной high?"
```
