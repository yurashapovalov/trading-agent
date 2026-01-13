# Validator Agent

**File:** `agent/agents/validator.py`

**Type:** Code (Python, без LLM)

## Purpose

Проверяет что Stats от Analyst соответствуют реальным данным.

## Principle

LLM (Analyst) написал ответ с числами.
Код (Validator) проверяет что числа правильные.

Это защита от галлюцинаций LLM.

## Input

```python
{
    "stats": Stats(
        change_pct=2.53,
        close_price=17449.5,
        ...
    ),
    "data": {
        "rows": [...],
        "granularity": "daily"
    },
    "intent": Intent(type="data")
}
```

## Output

```python
# Если все ок:
{
    "validation": ValidationResult(
        status="ok",
        issues=[],
        feedback=""
    )
}

# Если есть ошибки:
{
    "validation": ValidationResult(
        status="rewrite",
        issues=["close_price: reported 17500, actual 17449.5"],
        feedback="Validation errors:\n- close_price: ..."
    )
}
```

## Validation Flow

```
Stats от Analyst
       │
       ▼
┌──────────────────┐
│ type == concept? │──Yes──▶ OK (нечего проверять)
└────────┬─────────┘
         │ No
         ▼
┌──────────────────┐
│ attempts >= 3?   │──Yes──▶ OK (auto-approve)
└────────┬─────────┘
         │ No
         ▼
┌──────────────────┐
│ type == pattern? │──Yes──▶ _validate_pattern()
└────────┬─────────┘
         │ No
         ▼
    _validate_data()
         │
         ▼
    Issues found?
    /          \
   Yes          No
    │            │
    ▼            ▼
 REWRITE        OK
```

## Tolerance Values

```python
TOLERANCE_PCT = 0.5      # ±0.5% для процентов
TOLERANCE_PRICE = 0.01   # ±$0.01 для цен
```

## Field Mapping

```python
field_map = {
    "change_pct":    ("change_pct", TOLERANCE_PCT),
    "trading_days":  ("trading_days", 0),           # exact
    "open_price":    ("open_price", TOLERANCE_PRICE),
    "close_price":   ("close_price", TOLERANCE_PRICE),
    "max_price":     ("max_price", TOLERANCE_PRICE),
    "min_price":     ("min_price", TOLERANCE_PRICE),
    "total_volume":  ("total_volume", 0),           # exact
    "change_points": ("change_points", TOLERANCE_PRICE),
}
```

## Data Format Detection

Validator определяет формат данных автоматически:

```python
# 1. SQL-aggregated format (statistics queries)
# Когда SQL уже посчитал агрегаты (CORR, AVG, STDDEV)
{"trading_days": 5601, "corr_volume_change": -0.09, "avg_volume": 319342, ...}

# 2. Period format (aggregated by DataFetcher)
{"open_price": 17019, "close_price": 17449, ...}

# 3. Daily format (raw rows)
{"open": 17019, "close": 17007, "high": 17038, ...}
```

**Логика определения:**
```python
# SQL-aggregated: 1 строка + trading_days + prefixes (corr_, avg_, stddev_, etc.)
is_sql_aggregated = (
    "trading_days" in first_row and
    len(rows) == 1 and
    any(key.startswith(("corr_", "avg_", "stddev_", "total_")) for key in first_row)
)

# Period format: есть open_price
is_period_format = "open_price" in first_row

# Daily: всё остальное → агрегируем перед проверкой
```

## Aggregation Logic

Для daily/hourly данных:

```python
def _aggregate_rows(self, rows):
    sorted_rows = sorted(rows, key=lambda r: r["date"])
    return {
        "trading_days": len(rows),
        "open_price": sorted_rows[0]["open"],      # первый open
        "close_price": sorted_rows[-1]["close"],   # последний close
        "max_price": max(r["high"] for r in rows), # макс high
        "min_price": min(r["low"] for r in rows),  # мин low
        "total_volume": sum(r["volume"] for r in rows),
        "change_pct": self._calc_change_pct(sorted_rows)
    }
```

## Pattern Validation

Для паттернов проверяется только `matches_count`:

```python
def _validate_pattern(self, stats, data):
    if "matches_count" in stats:
        actual = data.get("matches_count", 0)
        if stats["matches_count"] != actual:
            return [f"matches_count: reported {stats['matches_count']}, actual {actual}"]
    return []
```

## Implementation

```python
class Validator:
    name = "validator"
    agent_type = "validation"
    max_attempts = 3

    def __call__(self, state: AgentState) -> dict:
        stats = state.get("stats") or {}
        data = state.get("data", {})
        intent = state.get("intent", {})
        attempts = state.get("validation_attempts", 0)

        # Auto-approve after 3 attempts
        if attempts >= self.max_attempts:
            return {"validation": ValidationResult(status="ok", ...)}

        # No stats or concept type
        if not stats or intent.get("type") == "concept":
            return {"validation": ValidationResult(status="ok", ...)}

        # Validate
        if intent.get("type") == "pattern":
            issues = self._validate_pattern(stats, data)
        else:
            issues = self._validate_data(stats, data)

        if issues:
            return {"validation": ValidationResult(
                status="rewrite",
                issues=issues,
                feedback=self._format_feedback(issues)
            )}

        return {"validation": ValidationResult(status="ok", ...)}
```

## Rewrite Loop

Если status="rewrite", граф возвращается к Analyst:

```
Analyst → Validator
           │
           ▼
      status="rewrite"?
      /            \
    Yes             No
     │               │
     ▼               ▼
  Analyst          END
  (again)
```

Максимум 3 попытки, потом auto-approve.

## Why No LLM?

1. **Скорость** - мгновенная проверка
2. **Точность** - нет галлюцинаций
3. **Стоимость** - бесплатно
4. **Предсказуемость** - детерминированный результат

Код проверяет лучше чем LLM проверял бы LLM.
