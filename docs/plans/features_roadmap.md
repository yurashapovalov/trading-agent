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

## Priority 6: Advanced (future)

### 6.1 GAP_CLOSE event
"Когда закрываются гэпы?"

### 6.2 Conditional sequences
"Если понедельник красный, какой вторник?"

### 6.3 Backtesting
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
