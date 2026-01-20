# Architecture v2: Simple Python Pipeline

## Проблема v1
- Слишком много абстракций (atoms, molecules, expander, builder)
- SQL строки сложно композировать
- Паттерны в двух местах (SQL + Python scanner)
- Сложно отлаживать

## Решение v2
- AI понимает вопрос → DomainSpec (JSON)
- Python код выполняет → pandas/DuckDB
- Никакого SQL в AI, никаких сложных абстракций

---

## Архитектура

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────────┐
│   Question  │ ──▶ │   Parser    │ ──▶ │  Executor   │ ──▶ │  Result  │
│  (natural)  │     │   (LLM)     │     │  (Python)   │     │  (data)  │
└─────────────┘     └─────────────┘     └─────────────┘     └──────────┘
                          │                   │
                          ▼                   ▼
                    DomainSpec           pandas/DuckDB
                      (JSON)            (deterministic)
```

**Parser (LLM):** Понимает вопрос, выдаёт DomainSpec
**Executor (Python):** Детерминированно выполняет spec, возвращает данные

---

## DomainSpec

8-10 операций покрывают 90% вопросов:

```python
class DomainSpec:
    op: str           # операция
    symbol: str       # инструмент (NQ, ES)
    period: str       # период (2024, 2020-2025, all)
    granularity: str  # daily, minutes
    params: dict      # параметры операции
```

### Операции

| op | Описание | Пример вопроса |
|----|----------|----------------|
| `stats` | Базовая статистика | "Статистика за 2024" |
| `compare` | Сравнить группы | "Понедельники vs пятницы" |
| `top_n` | Топ N + агрегат | "Топ-5 по объёму, их avg change" |
| `streak` | Consecutive дни | "3+ красных дня подряд" |
| `sequence` | После X было Y | "Упал после роста" |
| `distribution` | Распределение | "Когда формируется high" |
| `correlation` | Корреляция полей | "Корреляция объём/цена" |
| `seasonality` | По месяцам/кварталам | "Лучший месяц для роста" |
| `trend` | Динамика периода | "Как вёл себя в декабре" |

---

## Примеры DomainSpec

### "Сравни волатильность понедельников и пятниц в 2024"
```json
{
  "op": "compare",
  "symbol": "NQ",
  "period": "2024",
  "granularity": "daily",
  "params": {
    "group_by": "weekday",
    "groups": [1, 5],
    "metric": "range",
    "agg": "mean"
  }
}
```

### "Топ-5 дней по объёму, средний change_pct"
```json
{
  "op": "top_n",
  "symbol": "NQ",
  "period": "2024",
  "granularity": "daily",
  "params": {
    "n": 5,
    "by": "volume",
    "then": {"metric": "change_pct", "agg": "mean"}
  }
}
```

### "Сколько раз было 3+ красных дня подряд?"
```json
{
  "op": "streak",
  "symbol": "NQ",
  "period": "2024",
  "granularity": "daily",
  "params": {
    "condition": "red",
    "min_length": 3,
    "agg": "count"
  }
}
```

### "Когда NQ достигает дневного high?"
```json
{
  "op": "distribution",
  "symbol": "NQ",
  "period": "2020-2025",
  "granularity": "minutes",
  "params": {
    "event": "daily_high",
    "group_by": "hour",
    "hours_filter": [6, 16]
  }
}
```

---

## Executor: Python функции

### Базовые функции данных

```python
# data.py

from config.market import get_instrument, get_day_type
from config.patterns import CANDLE_PATTERNS

def get_daily(symbol: str, period: str, session: str = None) -> pd.DataFrame:
    """Daily OHLCV из DuckDB (агрегация минуток).

    Учитывает trading day из config (18:00 prev → 17:00 current для NQ).
    """
    instrument = get_instrument(symbol)
    trading_day = instrument["trading_day"]  # {"start": "18:00", "end": "17:00"}

    # SQL учитывает что trading day начинается в 18:00 предыдущего дня
    sql = f"""
        SELECT
            -- Trading day: если время >= 18:00, это следующий trading day
            CASE WHEN EXTRACT(HOUR FROM timestamp) >= 18
                 THEN timestamp::date + 1
                 ELSE timestamp::date
            END as date,
            FIRST(open ORDER BY timestamp) as open,
            MAX(high) as high,
            MIN(low) as low,
            LAST(close ORDER BY timestamp) as close,
            SUM(volume) as volume
        FROM ohlcv_1min
        WHERE symbol = '{symbol}'
          AND timestamp >= '{period_start}'
          AND timestamp < '{period_end}'
        GROUP BY 1
        ORDER BY 1
    """
    df = duckdb.query(sql).df()

    # Исключаем праздники
    df = df[df["date"].apply(lambda d: get_day_type(symbol, d) != "closed")]

    return enrich(df)


def get_minutes(symbol: str, period: str, hours: tuple = None) -> pd.DataFrame:
    """Минутные данные из DuckDB."""
    ...


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет вычисляемые поля."""
    df["change_pct"] = (df["close"] - df["open"]) / df["open"] * 100
    df["range"] = df["high"] - df["low"]
    df["range_pct"] = df["range"] / df["low"] * 100
    df["weekday"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    df["quarter"] = df["date"].dt.quarter
    df["year"] = df["date"].dt.year
    df["is_red"] = df["close"] < df["open"]
    df["is_green"] = df["close"] > df["open"]
    df["gap_pct"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1) * 100
    df["prev_change"] = df["change_pct"].shift(1)
    return df
```

### Операции

```python
# operations.py

def op_compare(df: pd.DataFrame, params: dict) -> dict:
    """Сравнить группы."""
    group_by = params["group_by"]
    groups = params.get("groups")  # optional filter
    metric = params["metric"]
    agg = params.get("agg", "mean")

    result = df.groupby(group_by)[metric].agg(agg)

    if groups:
        result = result.loc[groups]

    return result.to_dict()


def op_top_n(df: pd.DataFrame, params: dict) -> dict:
    """Топ N, потом агрегация."""
    n = params["n"]
    by = params["by"]
    then = params.get("then")

    top = df.nlargest(n, by)

    if then:
        metric = then["metric"]
        agg = then.get("agg", "mean")
        return {f"{agg}_{metric}": top[metric].agg(agg), "rows": top.to_dict("records")}

    return {"rows": top.to_dict("records")}


def op_streak(df: pd.DataFrame, params: dict) -> dict:
    """Подсчёт consecutive дней."""
    condition = params["condition"]  # "red", "green", or custom
    min_length = params.get("min_length", 1)
    agg = params.get("agg", "count")

    if condition == "red":
        mask = df["is_red"]
    elif condition == "green":
        mask = df["is_green"]
    else:
        mask = df.eval(condition)

    # Streak calculation
    df["_streak_id"] = (mask != mask.shift()).cumsum()
    streaks = df[mask].groupby("_streak_id").size()

    valid_streaks = streaks[streaks >= min_length]

    if agg == "count":
        return {"count": len(valid_streaks)}
    elif agg == "max":
        return {"max_length": valid_streaks.max()}
    elif agg == "list":
        return {"streaks": valid_streaks.tolist()}


def op_sequence(df: pd.DataFrame, params: dict) -> dict:
    """После X было Y."""
    prev_condition = params["prev"]  # "change_pct > 1"
    curr_condition = params["curr"]  # "change_pct < -2"

    prev_mask = df.shift(1).eval(prev_condition)
    curr_mask = df.eval(curr_condition)

    matches = df[prev_mask & curr_mask]

    return {"count": len(matches), "rows": matches.to_dict("records")}


def op_distribution(df: pd.DataFrame, params: dict) -> dict:
    """Распределение события по времени."""
    event = params["event"]  # "daily_high", "daily_low"
    group_by = params["group_by"]  # "hour"

    if event == "daily_high":
        df["_daily_max"] = df.groupby(df["timestamp"].dt.date)["high"].transform("max")
        df["_is_event"] = df["high"] == df["_daily_max"]
    elif event == "daily_low":
        df["_daily_min"] = df.groupby(df["timestamp"].dt.date)["low"].transform("min")
        df["_is_event"] = df["low"] == df["_daily_min"]

    dist = df[df["_is_event"]].groupby(df["timestamp"].dt.hour).size()
    dist_pct = (dist / dist.sum() * 100).round(1)

    return {"distribution": dist_pct.to_dict()}


def op_correlation(df: pd.DataFrame, params: dict) -> dict:
    """Корреляция между полями."""
    field1 = params["field1"]
    field2 = params["field2"]

    corr = df[field1].corr(df[field2])

    return {"correlation": round(corr, 3)}


def op_seasonality(df: pd.DataFrame, params: dict) -> dict:
    """Сезонность по месяцам/кварталам."""
    group_by = params["group_by"]  # "month", "quarter"
    metric = params["metric"]
    agg = params.get("agg", "mean")

    result = df.groupby(group_by)[metric].agg(agg).sort_values(ascending=False)

    return {
        "best": int(result.idxmax()),
        "worst": int(result.idxmin()),
        "data": result.to_dict()
    }
```

### Главный Executor

```python
# executor.py

OPERATIONS = {
    "stats": op_stats,
    "compare": op_compare,
    "top_n": op_top_n,
    "streak": op_streak,
    "sequence": op_sequence,
    "distribution": op_distribution,
    "correlation": op_correlation,
    "seasonality": op_seasonality,
    "trend": op_trend,
}


def execute(spec: dict) -> dict:
    """Выполнить DomainSpec."""
    op = spec["op"]
    symbol = spec["symbol"]
    period = spec["period"]
    granularity = spec.get("granularity", "daily")
    params = spec.get("params", {})

    # Получить данные
    if granularity == "daily":
        df = get_daily(symbol, period)
    else:
        hours = params.get("hours_filter")
        df = get_minutes(symbol, period, hours)

    # Выполнить операцию
    if op not in OPERATIONS:
        return {"error": f"Unknown operation: {op}"}

    return OPERATIONS[op](df, params)
```

---

## Parser Prompt (LLM)

```
You are a parser for a trading data assistant.
Convert user questions to DomainSpec JSON.

Available operations:
- stats: basic statistics for a period
- compare: compare groups (weekdays, sessions, etc.)
- top_n: top N records, then optional aggregation
- streak: count consecutive days matching condition
- sequence: days where prev day was X and current day is Y
- distribution: when does event occur (by hour)
- correlation: correlation between two fields
- seasonality: best/worst month, quarter, etc.

Output ONLY valid JSON matching DomainSpec schema.
Do NOT include explanations.

Examples:
Q: "Волатильность по часам"
{"op": "compare", "symbol": "NQ", "period": "all", "granularity": "daily", "params": {"group_by": "hour", "metric": "range", "agg": "mean"}}

Q: "3 красных дня подряд в 2024"
{"op": "streak", "symbol": "NQ", "period": "2024", "granularity": "daily", "params": {"condition": "red", "min_length": 3, "agg": "count"}}
```

---

## Структура файлов

```
agent_v2/
├── parser.py          # LLM парсер → DomainSpec
├── executor.py        # Выполняет DomainSpec
├── operations/        # Операции
│   ├── __init__.py
│   ├── compare.py
│   ├── top_n.py
│   ├── streak.py
│   ├── sequence.py
│   ├── distribution.py
│   ├── correlation.py
│   └── seasonality.py
├── data/
│   ├── __init__.py
│   ├── daily.py       # get_daily()
│   ├── minutes.py     # get_minutes()
│   └── enrich.py      # enrich()
├── config/            # Domain knowledge (ОСТАЁТСЯ из v1)
│   ├── market/
│   │   ├── instruments.py  # NQ: sessions, trading_day, tick_size
│   │   ├── holidays.py     # Расчёт праздников, early close
│   │   └── events.py       # FOMC, NFP, OPEX даты
│   └── patterns/
│       └── candle.py       # Правила детекции паттернов
└── responder.py       # Форматирует ответ
```

---

## Config (переиспользуем из v1)

Config содержит domain knowledge — это не код, а данные.

### market/instruments.py
```python
INSTRUMENTS = {
    "NQ": {
        "name": "Nasdaq 100 E-mini",
        "sessions": {
            "RTH": ("09:30", "17:00"),
            "ETH": ("18:00", "17:00"),
            "OVERNIGHT": ("18:00", "09:30"),
        },
        "trading_day": {"start": "18:00", "end": "17:00"},
        "maintenance": ("17:00", "18:00"),
    }
}
```
**Используется:** фильтрация по сессиям, определение trading day

### market/holidays.py
```python
get_day_type("NQ", "2024-12-25")  # "closed"
get_day_type("NQ", "2024-12-24")  # "early_close"
get_close_time("NQ", "2024-12-24")  # "13:15"
```
**Используется:** исключение праздников, корректировка времени

### market/events.py
```python
MACRO_EVENTS = {
    "fomc": MarketEvent("fomc", "FOMC Rate Decision", impact=HIGH, schedule="8x/year"),
    "nfp": MarketEvent("nfp", "Non-Farm Payrolls", impact=HIGH, schedule="1st Friday"),
}
```
**Используется:** контекст для ответов ("это был день FOMC")

### patterns/candle.py
```python
CANDLE_PATTERNS = {
    "three_black_crows": {
        "candles": 3,
        "detection": {"all_red": True, "each_closes_lower": True},
    }
}
```
**Используется:** детекция паттернов в Python (не SQL)

---

## Производительность

| Операция | Время |
|----------|-------|
| DuckDB: 18M rows → daily | ~100-500ms |
| pandas: операции на 4K rows | <10ms |
| LLM: parse question | ~500-1000ms |
| **Total** | **~1-2 sec** |

---

## Сравнение v1 vs v2

| Аспект | v1 (atoms) | v2 (simple) |
|--------|------------|-------------|
| Слоёв | 5+ | 2 |
| Файлов | 50+ | ~15 |
| SQL | Сложный builder | 2 простых запроса |
| Паттерны | SQL + Python | Только Python |
| Отладка | Сложно | Просто |
| Расширение | Новый atom + builder | Новая функция |

---

## План реализации

1. **data/** — get_daily(), get_minutes(), enrich() — 1 день
2. **operations/** — 8 операций — 2 дня
3. **parser.py** — LLM prompt + schema — 1 день
4. **executor.py** — routing — 0.5 дня
5. **responder.py** — форматирование — 0.5 дня
6. **Тесты** — все вопросы — 1 день

**Итого: ~6 дней**
