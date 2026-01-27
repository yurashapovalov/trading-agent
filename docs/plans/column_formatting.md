# Column Formatting: df_to_rows() Enhancement

## Текущее состояние

После strip is_* в graph.py остаётся 16 колонок, но:
- Порядок рандомный (зависит от DataFrame)
- Нет приоритизации (date не первый)
- Нет фильтрации redundant колонок

## План

### Изменение: agent/operations/_utils.py

Расширить `df_to_rows()` — добавить ordering и возможность фильтрации.

```python
COLUMN_ORDER = [
    # 1. Время — всегда первое
    "date", "timestamp",

    # 2. Ключевые метрики
    "change", "gap", "range",

    # 3. OHLCV
    "open", "high", "low", "close", "volume",

    # 4. Флаги
    "is_green", "gap_filled",

    # 5. Время (часто redundant)
    "weekday", "month", "year",

    # 6. Соседи (редко нужны)
    "prev_change", "next_change",
]

def df_to_rows(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to list of dicts with ordered columns."""
    if df.empty:
        return []

    # Order columns by priority
    df = _order_columns(df)

    # Convert to rows (existing logic)
    rows = []
    for _, row in df.iterrows():
        record = {}
        for col, val in row.items():
            if pd.isna(val):
                continue
            elif hasattr(val, "isoformat"):
                record[col] = val.isoformat()
            elif isinstance(val, float):
                record[col] = round(val, 3)
            elif hasattr(val, "item"):
                record[col] = val.item()
            else:
                record[col] = val
        rows.append(record)
    return rows


def _order_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Reorder DataFrame columns by priority."""
    cols = list(df.columns)

    # Sort: known columns first (by priority), then unknown
    def priority(col):
        try:
            return COLUMN_ORDER.index(col)
        except ValueError:
            return len(COLUMN_ORDER)  # Unknown columns last

    ordered = sorted(cols, key=priority)
    return df[ordered]
```

### Миграция strip is_* из graph.py

Перенести логику strip is_* в df_to_rows():

```python
def df_to_rows(df: pd.DataFrame, strip_patterns: bool = True) -> list[dict]:
    if strip_patterns:
        # Remove is_* pattern columns (keep is_green)
        pattern_cols = [c for c in df.columns if c.startswith("is_") and c != "is_green"]
        df = df.drop(columns=pattern_cols, errors='ignore')

    df = _order_columns(df)
    # ... rest
```

Тогда в graph.py можно убрать `_strip_pattern_columns()`.

## Будущие расширения

- [ ] Убирать redundant колонки (weekday=4 для всех пятниц)
- [ ] Параметр `columns` для явного списка
- [ ] Разные приоритеты для разных операций

## Файлы для изменения

1. `agent/operations/_utils.py` — основные изменения
2. `agent/graph.py` — убрать `_strip_pattern_columns()` (опционально)
3. `agent/tests/test_operations.py` — тесты на ordering
