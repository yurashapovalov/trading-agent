# AskBar v2 — Implementation Plan

## Принципы

1. **4 агента** — простой граф, не переусложнять
2. **Модули внутри** — логика в Python модулях, агенты координируют
3. **LLM решает ЧТО, код решает КАК**
4. **Stats validation** — проверяем числа кодом

---

## Архитектура

```
┌─────────────┐     ┌─────────────┐     ┌─────────┐     ┌───────────┐
│ Understander │ ──→ │ DataFetcher │ ──→ │ Analyst │ ◄──→│ Validator │
│    (LLM)     │     │   (код)     │     │  (LLM)  │     │   (код)   │
└─────────────┘     └─────────────┘     └─────────┘     └───────────┘
       │                   │                                   │
       │                   ▼                                   │
       │         ┌─────────────────┐                          │
       │         │     Модули      │                          │
       │         ├─────────────────┤                          │
       │         │ • sql           │                          │
       │         │ • backtest      │                          │
       │         │ • indicators    │                          │
       │         │ • ...           │                          │
       │         └─────────────────┘                          │
       │                                                      │
       └──── читает CAPABILITIES ─────────────────────────────┘
```

**LLM вызовы: 2** (Understander + Analyst)

---

## Граф LangGraph

```
START
  │
  ▼
┌─────────────┐
│ understander │
└─────────────┘
  │
  ├─── needs_clarification ──→ INTERRUPT ──→ resume ──┐
  │                                                    │
  │◄───────────────────────────────────────────────────┘
  │
  ▼
┌─────────────┐
│ data_fetcher │
└─────────────┘
  │
  ├─── no_data ──→ INTERRUPT ──→ resume ──→ understander
  │
  ▼
┌─────────────┐
│   analyst   │
└─────────────┘
  │
  ▼
┌─────────────┐
│  validator  │
└─────────────┘
  │
  ├─── rewrite ──→ analyst (max 3)
  │
  ▼
 END
```

---

## State

```python
class AgentState(TypedDict):
    # Input
    question: str
    user_id: str
    session_id: str
    request_id: str

    # Understander
    intent: Intent | None
    clarification_attempts: int

    # DataFetcher
    data: dict                    # результаты от модулей
    missing_capabilities: list[str]

    # Analyst
    stats: Stats | None
    response: str

    # Validator
    validation: Validation | None
    validation_attempts: int

    # Meta
    chat_history: list[dict]
    errors: list[str]
```

---

## Типы

```python
class Intent(TypedDict):
    type: Literal["data", "concept", "strategy", "mixed"]
    symbol: str | None
    period_start: str | None
    period_end: str | None
    analysis_types: list[str]     # ["stats", "extremes", "events", "backtest"]
    strategy: StrategyDef | None  # для type="strategy"
    concept: str | None           # для type="concept"

class StrategyDef(TypedDict):
    name: str                     # "consecutive_down", "breakout"
    params: dict                  # {"down_days": 3, "hold_days": 1}

class Stats(TypedDict, total=False):
    # Период
    period_start: str
    period_end: str
    trading_days: int

    # Цены
    open_price: float
    close_price: float
    change_pct: float
    max_price: float
    min_price: float

    # Объём
    total_volume: int
    avg_volume: float

    # Бэктест (если есть)
    total_return_pct: float
    trades_count: int
    win_rate: float
    max_drawdown_pct: float
```

---

## Агент 1: Understander (LLM)

Парсит вопрос → Intent.

```python
def understander(state: AgentState) -> dict:
    # Проверка лимита уточнений
    if state.get("clarification_attempts", 0) >= 3:
        return {"intent": default_intent(state)}

    # LLM парсит вопрос
    intent = llm_parse_intent(
        question=state["question"],
        capabilities=CAPABILITIES,
        chat_history=state.get("chat_history", [])
    )

    # Нужно уточнение?
    if intent.get("needs_clarification"):
        answer = interrupt({
            "message": intent["clarification_question"],
            "suggestions": intent.get("suggestions", [])
        })
        return {
            "question": f"{state['question']}. {answer}",
            "clarification_attempts": state.get("clarification_attempts", 0) + 1
        }

    return {"intent": intent}
```

---

## Агент 2: DataFetcher (код)

Координатор. Вызывает нужный модуль.

```python
from modules import sql, backtest, indicators

def data_fetcher(state: AgentState) -> dict:
    intent = state["intent"]
    intent_type = intent.get("type", "data")

    # Проверяем capabilities
    missing = check_capabilities(intent)

    # Роутинг по типу
    if intent_type == "concept":
        # Concept — данные не нужны
        return {"data": {}, "missing_capabilities": missing}

    elif intent_type == "strategy":
        # Бэктест
        data = backtest.run(
            symbol=intent["symbol"],
            period_start=intent["period_start"],
            period_end=intent["period_end"],
            strategy=intent["strategy"]
        )

    else:  # data, mixed
        # SQL запросы
        data = sql.fetch(
            symbol=intent["symbol"],
            period_start=intent["period_start"],
            period_end=intent["period_end"],
            analysis_types=intent["analysis_types"]
        )

    # Нет данных?
    if not data.get("rows"):
        answer = interrupt({
            "type": "no_data",
            "message": "Данных за этот период нет",
            "available_range": get_available_range()
        })
        return {"question": answer, "data": {}}

    return {"data": data, "missing_capabilities": missing}
```

---

## Агент 3: Analyst (LLM)

Пишет ответ + заполняет stats.

```python
def analyst(state: AgentState) -> dict:
    # Собираем контекст
    context = {
        "question": state["question"],
        "intent": state["intent"],
        "data": state["data"],
        "missing_capabilities": state.get("missing_capabilities", []),
        "validation_feedback": state.get("validation", {}).get("feedback"),
    }

    # LLM генерирует ответ + stats
    result = llm_analyze(context)

    return {
        "response": result["response"],
        "stats": result["stats"],
        "validation_attempts": state.get("validation_attempts", 0) + 1
    }
```

---

## Агент 4: Validator (код)

Проверяет stats против данных.

```python
def validator(state: AgentState) -> dict:
    stats = state.get("stats", {})
    data = state.get("data", {})

    if not stats or not data:
        return {"validation": {"status": "ok"}}

    issues = []

    # Проверяем каждое поле
    if "change_pct" in stats:
        actual = calculate_change_pct(data)
        if abs(stats["change_pct"] - actual) > 0.5:
            issues.append(f"change_pct: {stats['change_pct']} vs {actual:.2f}")

    if "max_price" in stats:
        actual = data["high"].max()
        if abs(stats["max_price"] - actual) > 0.01:
            issues.append(f"max_price: {stats['max_price']} vs {actual}")

    # ... остальные проверки

    if issues:
        return {"validation": {
            "status": "rewrite",
            "issues": issues,
            "feedback": "\n".join(issues)
        }}

    return {"validation": {"status": "ok"}}
```

---

## Модули

```
modules/
├── __init__.py
├── sql.py           # SQL шаблоны и выполнение
├── backtest.py      # Бэктест логика
├── indicators.py    # RSI, MACD (когда добавим)
└── ...
```

### modules/sql.py

```python
TEMPLATES = {
    "stats": """
        SELECT date_trunc('day', timestamp) as period,
               (array_agg(open ORDER BY timestamp))[1] as open,
               MAX(high) as high, MIN(low) as low,
               (array_agg(close ORDER BY timestamp DESC))[1] as close,
               SUM(volume) as volume
        FROM ohlcv_1min
        WHERE symbol = %(symbol)s
          AND timestamp >= %(start)s AND timestamp < %(end)s
        GROUP BY 1 ORDER BY 1
    """,
    "extremes": "...",
    "events": "...",
}

def fetch(symbol, period_start, period_end, analysis_types):
    results = {}
    for analysis in analysis_types:
        sql = TEMPLATES.get(analysis)
        if sql:
            results[analysis] = execute(sql, {...})
    return results
```

### modules/backtest.py

```python
STRATEGIES = {
    "consecutive_down": consecutive_down_strategy,
    "breakout": breakout_strategy,
}

def run(symbol, period_start, period_end, strategy):
    # Получаем данные
    data = sql.fetch(symbol, period_start, period_end, ["stats"])

    # Запускаем стратегию
    strategy_fn = STRATEGIES.get(strategy["name"])
    if not strategy_fn:
        return {"error": f"Unknown strategy: {strategy['name']}"}

    return strategy_fn(data, strategy["params"])
```

---

## Capabilities

```python
# config.py
CAPABILITIES = {
    # Данные
    "ohlcv": True,
    "stats": True,
    "extremes": True,
    "events": True,

    # Бэктест
    "backtest": True,
    "strategy_consecutive_down": True,
    "strategy_breakout": True,

    # Индикаторы (пока нет)
    "rsi": False,
    "macd": False,
}
```

---

## Feature Requests

```python
# В конце data_fetcher или отдельно
if missing_capabilities:
    for feature in missing_capabilities:
        log_feature_request(feature, user_id, question)
```

---

## Файловая структура

```
agent/
├── __init__.py
├── state.py              # AgentState, Intent, Stats
├── graph.py              # LangGraph сборка
├── agents/
│   ├── understander.py
│   ├── data_fetcher.py
│   ├── analyst.py
│   └── validator.py
└── modules/
    ├── sql.py
    ├── backtest.py
    └── indicators.py     # будущее
```

---

## Масштабирование

Добавить RSI:
1. `modules/indicators.py` — логика расчёта
2. `CAPABILITIES["rsi"] = True`
3. В `data_fetcher`: добавить вызов `indicators.calculate()`

Агенты не меняются. Модули растут.

---

## План реализации

### Фаза 1: Инфраструктура
- [ ] agent/state.py
- [ ] config.py (CAPABILITIES)
- [ ] modules/sql.py

### Фаза 2: Агенты
- [ ] understander
- [ ] data_fetcher
- [ ] analyst
- [ ] validator

### Фаза 3: Граф
- [ ] graph.py
- [ ] routing
- [ ] тесты

### Фаза 4: Бэктест
- [ ] modules/backtest.py
- [ ] стратегии
