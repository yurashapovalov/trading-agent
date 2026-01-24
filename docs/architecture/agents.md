# Агенты

Каждый агент делает одну задачу хорошо.

**В графе (активные):**
- Intent → Parser → Planner → Executor

**Standalone (не в графе):**
- Clarifier, Presenter, Responder — есть код, но не подключены

## Intent

**Задача:** Классифицировать намерение пользователя.

```
"топ 5 волатильных дней"  → data
"привет"                   → chitchat
"что такое OPEX"           → concept
```

| Intent | Что делать |
|--------|------------|
| `data` | Parser → Planner → Executor |
| `chitchat` | end (пока не обрабатывается) |
| `concept` | end (пока не обрабатывается) |

## Parser

**Задача:** NL → структурированный запрос.

```
"когда появлялись inside day в 2024"
         ↓
{
  "steps": [{
    "operation": "list",
    "atoms": [{
      "when": "2024",
      "what": "change",
      "filter": "inside_bar",
      "timeframe": "1D"
    }],
    "params": {"n": 10, "sort": "desc"}
  }]
}
```

**Как работает:**

1. **RAP** (Retrieval-Augmented Prompting) — подбирает релевантные chunks
2. **Gemini** — генерирует JSON
3. **Pydantic** — валидирует и авто-фиксит ошибки LLM

**9 операций:**

| Операция | Что делает | Пример |
|----------|------------|--------|
| `list` | Показать данные | "топ 10 по объёму" |
| `count` | Агрегация | "сколько gap up в 2024" |
| `compare` | Сравнить | "понедельники vs пятницы" |
| `correlation` | Связь метрик | "корреляция объёма и волатильности" |
| `around` | До/после события | "что было после gap up" |
| `streak` | Серии | "сколько раз 3+ красных подряд" |
| `distribution` | Распределение | "гистограмма change" |
| `probability` | Вероятность | "шанс роста после doji" |
| `formation` | Время формирования | "когда формируется high дня" |

## Clarifier (standalone)

**Задача:** Уточнить недостающую информацию.

> Не подключен к графу. Код готов, но нужна интеграция.

```
User: "покажи статистику"
      ↓
Parser: unclear = ["period", "metric"]
      ↓
Clarifier: "За какой период? И что посчитать?"
      ↓
User: "волатильность за 2024"
      ↓
→ clarified_query → Parser (повторно)
```

## Planner

**Задача:** Построить план выполнения.

```
Step с двумя atoms
      ↓
Planner: "multi_period" или "multi_filter"
      ↓
Executor знает как обрабатывать
```

**Режимы:**

| Mode | Когда |
|------|-------|
| `single` | Один запрос |
| `multi_period` | Сравнение периодов |
| `multi_filter` | Сравнение фильтров |
| `multi_metric` | Корреляция метрик |

## Executor

**Задача:** Выполнить запрос к данным.

```
Plan
  │
  ▼
┌─────────────┐
│ get_bars    │  DuckDB → DataFrame
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ enrich      │  + change, gap, weekday, month...
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ scan_patterns│  + is_doji, is_hammer, is_inside_bar...
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ apply_filter│  WHERE change > 0, filter: doji...
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ operation   │  list, count, compare, around...
└──────┬──────┘
       │
       ▼
   Result
```

## Presenter (standalone)

**Задача:** Превратить данные в понятный текст.

> Не подключен к графу. Используется отдельно для форматирования.

```
Executor возвращает:
{
  rows: [...34 inside bars...],
  summary: { total: 34, avg_change: 0.45% }
}
      ↓
Presenter:
"В 2024 году было 34 дня с паттерном Inside Bar.
 Средний change в эти дни составил +0.45%."
```

Presenter знает про:
- Праздники (market holidays)
- События (OPEX, NFP, FOMC)
- Паттерны свечей (hammer, doji, engulfing)
- Контекст (что означает паттерн)

## Responder (standalone)

**Задача:** Отвечать без данных.

> Не подключен к графу. Код готов для chitchat/concept.

**chitchat:**
```
User: "привет"
→ "Привет! Чем могу помочь с анализом NQ?"
```

**concept:**
```
User: "что такое OPEX"
→ "OPEX — Monthly Options Expiration, третья пятница месяца.
   Часто повышенная волатильность из-за закрытия позиций."
```
