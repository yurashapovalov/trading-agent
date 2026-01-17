# TODO: Реализовать COMPARE Operation

## Проблема

Запросы типа "Compare Monday and Friday volatility" или "RTH vs ETH range" падают с SQL Binder Error.

### Текущий SQL (неправильный):
```sql
SELECT
    date,  -- ← выбирается date
    AVG(range), STDDEV(change_pct), COUNT(*)
FROM daily
WHERE DAYNAME(date) IN ('Monday', 'Friday')
ORDER BY date
-- НЕТ GROUP BY!
```

### Нужный SQL:
```sql
SELECT
    DAYNAME(date) as weekday,  -- ← группировка по dimension
    AVG(range) as avg_range,
    STDDEV(change_pct) as volatility,
    COUNT(*) as count
FROM daily
WHERE DAYNAME(date) IN ('Monday', 'Friday')
GROUP BY DAYNAME(date)
```

## Причина

`CompareOpBuilder` не реализован — только пример в docstring `base.py`.

Файлы в `special_ops/`:
- ✅ top_n.py
- ✅ event_time.py
- ✅ find_extremum.py
- ❌ compare.py — НЕТ!

## Типы Compare

1. **Weekday compare**: "Monday vs Friday"
   - GROUP BY DAYNAME(date)
   - Filter: DAYNAME(date) IN ('Monday', 'Friday')

2. **Session compare**: "RTH vs ETH range"
   - Нужны два подзапроса для разных сессий
   - Или колонка session в данных

3. **Period compare**: "2023 vs 2024"
   - GROUP BY YEAR(date)
   - Filter: YEAR(date) IN (2023, 2024)

## Решение

### 1. Создать `agent/query_builder/special_ops/compare.py`

```python
@SpecialOpRegistry.register
class CompareOpBuilder(SpecialOpBuilder):
    op_type = SpecialOp.COMPARE

    def build_query(self, spec, extra_filters_sql=""):
        compare_spec = spec.compare_spec
        items = compare_spec.items  # ["Monday", "Friday"]

        # Определить dimension
        dimension = self._detect_dimension(items)
        # weekday, session, year, month

        # Построить SQL с GROUP BY dimension
        ...
```

### 2. Detect Dimension Logic

```python
def _detect_dimension(self, items: list[str]) -> str:
    weekdays = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}
    sessions = {"RTH", "ETH", "OVERNIGHT", "GLOBEX"}

    if all(i in weekdays for i in items):
        return "weekday"
    if all(i in sessions for i in items):
        return "session"
    if all(i.isdigit() and len(i) == 4 for i in items):
        return "year"
    ...
```

### 3. SQL Templates

**Weekday:**
```sql
SELECT
    DAYNAME(date) as weekday,
    AVG(range) as avg_range,
    AVG(change_pct) as avg_change,
    STDDEV(change_pct) as volatility,
    COUNT(*) as count
FROM {daily_cte}
WHERE DAYNAME(date) IN ({items})
GROUP BY DAYNAME(date)
ORDER BY CASE weekday
    WHEN 'Monday' THEN 1
    WHEN 'Friday' THEN 5
END
```

**Session (сложнее — нужны разные CTE):**
```sql
WITH rth AS (
    SELECT 'RTH' as session, AVG(range) as avg_range, ...
    FROM minutes WHERE time BETWEEN '09:30' AND '17:00'
),
eth AS (
    SELECT 'ETH' as session, AVG(range) as avg_range, ...
    FROM minutes WHERE time < '09:30' OR time >= '17:00'
)
SELECT * FROM rth
UNION ALL
SELECT * FROM eth
```

## Файлы для изменения

1. `agent/query_builder/special_ops/compare.py` — создать
2. `agent/query_builder/special_ops/__init__.py` — импортировать
3. `agent/composer.py` — проверить что compare_spec правильно создаётся

## Тестовые вопросы

- "Compare Monday and Friday volatility"
- "RTH vs ETH range"
- "Сравни RTH и ETH по range"
- "2023 vs 2024 performance"

## Приоритет

HIGH — часто используемый тип запросов
