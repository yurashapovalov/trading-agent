# Operations: Unified Output Format

## Концепция уровней агрегации

```
Уровень 0: Сырые данные (pandas DataFrame, 4524 строки)
    ↓ агрегация
Уровень 1: Агрегированная таблица (rows) ← для UI
    ↓ агрегация
Уровень 2: Ответ (summary) ← для Presenter
```

**Пользователь видит:**
- Текст от Presenter (уровень 2)
- Таблица в UI (уровень 1) — подтверждение

## Единый контракт операций

Каждая операция возвращает:

```python
{
    "rows": [
        {"month": "Jan", "avg_change": 0.038},
        {"month": "Feb", "avg_change": 0.060},
        ...
    ],
    "summary": {
        "best": "Jul",
        "best_value": 0.199,
        "worst": "Sep",
        "worst_value": -0.041,
    }
}
```

## Операции по типам

### Тип A: Агрегация с ответом (seasonality, compare, streak, distribution, correlation)

| Операция | rows (уровень 1) | summary (уровень 2) |
|----------|------------------|---------------------|
| seasonality | 12 месяцев | best, worst |
| compare | N групп | best, worst |
| streak | список серий | count, max_length |
| distribution | часы с % | peak, peak_pct |
| sequence | дни-совпадения | count, probability |
| correlation | по периодам | value, interpretation |

### Тип B: Таблица = ответ (top_n, stats, list)

| Операция | rows | summary |
|----------|------|---------|
| top_n | 5-10 строк | {count: N} |
| stats | 1 строка метрик | {count: N} |
| list | N строк | {count: N, truncated: bool} |

Для типа B: Presenter говорит "Вот N строк" и показывает таблицу.

## Presenter логика

```python
def present(result, question, lang):
    rows = result.get("rows", [])
    summary = result.get("summary", {})

    # Формируем текст из summary
    text = generate_text(question, summary, lang)

    # Таблица для UI
    table = format_table(rows)

    return {
        "text": text,
        "table": table,
        "row_count": len(rows)
    }
```

## Миграция операций

- [ ] seasonality.py — grouped Series → rows + summary
- [ ] compare.py — grouped Series → rows + summary
- [ ] streak.py — details → rows + summary
- [ ] distribution.py — distribution dict → rows + summary
- [ ] sequence.py — sample → rows + summary
- [ ] correlation.py — добавить rows по периодам
- [ ] stats.py — метрики как одну строку в rows
- [ ] top_n.py — уже есть rows, добавить summary

## Формат rows

Всегда list of dicts, сериализуемый в JSON:

```python
[
    {"month": "Jan", "avg_change": 0.038, "count": 380},
    {"month": "Feb", "avg_change": 0.060, "count": 356},
    ...
]
```

- Ключи — snake_case
- Значения — примитивы (str, int, float, None)
- Даты — ISO string "2024-01-15"
