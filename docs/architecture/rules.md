# Система правил

Single Source of Truth: config → rules → validation.

## Зачем

LLM делает ошибки. Правила исправляют их автоматически.

```
LLM: operation="formation", filter="doji"
      ↓
Pydantic: doji требует min 1H, formation требует 1m → конфликт!
      ↓
Auto-fix: operation="list", timeframe="1H"
```

## Структура

```
agent/rules/
├── operations.py   # 9 операций, их параметры и ограничения
├── filters.py      # 5 типов фильтров, парсинг, нормализация
├── metrics.py      # Метрики и их колонки
└── semantics.py    # Матрица operation × filter → semantic
```

## Operations

`rules/operations.py` — определения операций.

| Операция | Atoms | Required TF | Params |
|----------|-------|-------------|--------|
| `list` | 1-2 | — | n, sort |
| `count` | 1-2 | — | — |
| `compare` | 2 | — | — |
| `correlation` | 1 | — | — |
| `around` | 1 | — | offset, unit |
| `streak` | 1 | — | color, min_length |
| `distribution` | 1 | — | bins |
| `probability` | 1 | — | outcome |
| `formation` | 1 | **1m** | event, group_by |

## Filters

`rules/filters.py` — 5 типов фильтров.

| Тип | Пример | Парсинг |
|-----|--------|---------|
| `categorical` | monday, session=RTH | weekday/session |
| `comparison` | change > 0, gap < -1% | metric, op, value |
| `consecutive` | consecutive red >= 2 | color, length |
| `time` | time >= 09:30 | op, value |
| `pattern` | doji, inside_bar | pattern name |

**Pattern aliases:**
```python
PATTERN_ALIASES = {
    "inside_day": "inside_bar",
    "outside_day": "outside_bar",
}
```

Нормализуются автоматически: `inside_day` → `inside_bar`.

## Metrics

`rules/metrics.py` — метрики и колонки.

| Metric | Column | Daily only? |
|--------|--------|-------------|
| change | change | — |
| range | range | — |
| volume | volume | — |
| gap | gap | **да** |
| volatility | range | — |
| high | high | — |
| low | low | — |

`gap` требует daily data — нельзя использовать с session filter.

## Semantics

`rules/semantics.py` — как интерпретировать filter для operation.

```
           │ categorical │ comparison │ consecutive │ time  │ pattern │
───────────┼─────────────┼────────────┼─────────────┼───────┼─────────┤
list       │ where       │ where      │ where       │ where │ where   │
count      │ where       │ where      │ where       │ where │ where   │
probability│ where       │ condition  │ event       │ where │ condition│
around     │ where       │ event      │ event       │ where │ event   │
streak     │ where       │ condition  │ invalid     │ where │ condition│
```

- **where** — pre-filter (SQL WHERE)
- **condition** — condition для probability
- **event** — event для around
- **invalid** — запрещённая комбинация

## Pydantic Validators

`types.py` — автофиксы ошибок LLM.

**В Atom:**

| Validator | Что делает |
|-----------|------------|
| `normalize_pattern_aliases` | inside_day → inside_bar |
| `fix_invalid_metric` | unknown → change |
| `fix_timeframe_for_intraday_filter` | session → 1H |
| `validate_gap_vs_intraday` | gap + session = error |
| `fix_timeframe_for_pattern_filter` | doji → min 1H |

**В Step:**

| Validator | Что делает |
|-----------|------------|
| `fix_timeframe_for_operation` | formation → 1m |
| `fix_operation_filter_timeframe_conflict` | formation + doji → list |
| `validate_atoms_count` | compare требует 2 atoms |
| `validate_filter_combinations` | streak + consecutive = invalid |
| `set_default_params` | around → offset: 1 |

## Пример auto-fix

```python
# LLM выдал невозможную комбинацию
Step(
    operation="formation",  # требует 1m
    atoms=[Atom(filter="doji")]  # требует min 1H
)

# После Pydantic validators:
Step(
    operation="list",  # исправлено!
    atoms=[Atom(filter="doji", timeframe="1H")]
)
```
