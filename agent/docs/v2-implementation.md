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

## План реализации (пошаговый)

### Шаг 1: Типы и State ✅ → 🔄
**Файл:** `agent/state.py`

Добавить новые типы:
```python
class Intent(TypedDict):
    type: Literal["data", "concept", "strategy", "mixed"]
    symbol: str | None
    period_start: str | None   # ISO date
    period_end: str | None     # ISO date
    analysis_types: list[str]  # ["stats", "extremes", "events"]
    strategy: StrategyDef | None
    concept: str | None
    needs_clarification: bool
    clarification_question: str | None

class Stats(TypedDict, total=False):
    period_start: str
    period_end: str
    trading_days: int
    open_price: float
    close_price: float
    change_pct: float
    max_price: float
    min_price: float
    total_volume: int
    avg_volume: float
```

Обновить `AgentState`:
- Добавить `intent: Intent | None`
- Добавить `stats: Stats | None`
- Добавить `missing_capabilities: list[str]`
- Убрать `route` (заменяется на `intent.type`)

---

### Шаг 2: CAPABILITIES
**Файл:** `agent/capabilities.py` (новый)

```python
CAPABILITIES = {
    # Данные
    "ohlcv": True,
    "stats": True,
    "extremes": True,
    "hourly": True,

    # Бэктест
    "backtest": False,  # пока выключен

    # Индикаторы
    "rsi": False,
    "macd": False,
}

# Описания для LLM
CAPABILITY_DESCRIPTIONS = {
    "stats": "Базовая статистика: open, close, high, low, volume за период",
    "extremes": "Экстремумы: максимумы, минимумы, аномалии",
    "hourly": "Почасовая разбивка статистики",
    # ...
}
```

---

### Шаг 3: SQL модуль
**Файл:** `agent/modules/sql.py` (новый)

```python
TEMPLATES = {
    "stats": '''
        SELECT
            MIN(timestamp)::date as period_start,
            MAX(timestamp)::date as period_end,
            COUNT(DISTINCT timestamp::date) as trading_days,
            (array_agg(open ORDER BY timestamp))[1] as open_price,
            (array_agg(close ORDER BY timestamp DESC))[1] as close_price,
            MAX(high) as max_price,
            MIN(low) as min_price,
            SUM(volume) as total_volume
        FROM ohlcv_1min
        WHERE symbol = $1
          AND timestamp >= $2 AND timestamp < $3
    ''',

    "daily": '''
        SELECT
            timestamp::date as day,
            (array_agg(open ORDER BY timestamp))[1] as open,
            MAX(high) as high,
            MIN(low) as low,
            (array_agg(close ORDER BY timestamp DESC))[1] as close,
            SUM(volume) as volume
        FROM ohlcv_1min
        WHERE symbol = $1
          AND timestamp >= $2 AND timestamp < $3
        GROUP BY day
        ORDER BY day
    ''',

    "hourly": '''...''',
    "extremes": '''...''',
}

def fetch(symbol: str, period_start: str, period_end: str, analysis_types: list[str]) -> dict:
    """Выполняет SQL запросы по шаблонам."""
    results = {}
    for analysis in analysis_types:
        template = TEMPLATES.get(analysis)
        if template:
            results[analysis] = execute_query(template, [symbol, period_start, period_end])
    return results
```

---

### Шаг 4: Understander (переписать Router)
**Файл:** `agent/agents/understander.py`

Заменяет текущий `router.py`. Ключевые изменения:
- Возвращает структурированный `Intent`, не просто строку
- Использует structured output (JSON mode)
- Читает CAPABILITIES для понимания что доступно
- Может запросить уточнение

```python
class Understander:
    def __call__(self, state: AgentState) -> dict:
        intent = self._parse_intent(state["question"])
        return {"intent": intent}

    def _parse_intent(self, question: str) -> Intent:
        # LLM с JSON mode возвращает структурированный Intent
        ...
```

---

### Шаг 5: DataFetcher (переписать DataAgent)
**Файл:** `agent/agents/data_fetcher.py`

Заменяет текущий `data_agent.py`. Ключевые изменения:
- **Без LLM** — чистый Python код
- Читает `intent` и вызывает соответствующий модуль
- Роутинг: `intent.type` → модуль

```python
from agent.modules import sql

class DataFetcher:
    def __call__(self, state: AgentState) -> dict:
        intent = state["intent"]

        if intent["type"] == "concept":
            return {"data": {}}  # Данные не нужны

        data = sql.fetch(
            symbol=intent["symbol"],
            period_start=intent["period_start"],
            period_end=intent["period_end"],
            analysis_types=intent["analysis_types"]
        )

        return {"data": data}
```

---

### Шаг 6: Analyst (обновить)
**Файл:** `agent/agents/analyst.py`

Обновить текущий. Ключевые изменения:
- Возвращает `response` + `stats`
- Stats — структурированные данные для валидации
- Использует JSON mode для stats

```python
class Analyst:
    def __call__(self, state: AgentState) -> dict:
        result = self._generate(state)
        return {
            "response": result["response"],
            "stats": result["stats"],  # Новое!
        }
```

---

### Шаг 7: Validator (переписать)
**Файл:** `agent/agents/validator.py`

Ключевые изменения:
- **Без LLM** — чистый Python код
- Сравнивает `stats` с `data`
- Возвращает конкретные расхождения

```python
class Validator:
    def __call__(self, state: AgentState) -> dict:
        stats = state.get("stats", {})
        data = state.get("data", {})

        issues = self._validate(stats, data)

        if issues:
            return {"validation": {"status": "rewrite", "issues": issues}}
        return {"validation": {"status": "ok"}}

    def _validate(self, stats: Stats, data: dict) -> list[str]:
        issues = []

        if "change_pct" in stats and "stats" in data:
            actual = self._calc_change_pct(data["stats"])
            if abs(stats["change_pct"] - actual) > 0.5:
                issues.append(f"change_pct: LLM={stats['change_pct']}, actual={actual}")

        return issues
```

---

### Шаг 8: Граф (обновить)
**Файл:** `agent/graph.py`

- Заменить `router` → `understander`
- Заменить `data_agent` → `data_fetcher`
- Убрать `educator` (объединяется с analyst)
- Упростить роутинг (по `intent.type`)

---

### Шаг 9: Тесты
**Файл:** `tests/test_agents.py`

- Тест Understander: вопрос → правильный Intent
- Тест DataFetcher: Intent → правильные SQL
- Тест Validator: stats vs data → issues

---

## Порядок выполнения

| # | Задача | Файлы | Время |
|---|--------|-------|-------|
| 1 | Типы Intent, Stats | state.py | 15 мин |
| 2 | CAPABILITIES | capabilities.py | 10 мин |
| 3 | SQL модуль | modules/sql.py | 30 мин |
| 4 | Understander | agents/understander.py | 45 мин |
| 5 | DataFetcher | agents/data_fetcher.py | 20 мин |
| 6 | Analyst + Stats | agents/analyst.py | 30 мин |
| 7 | Validator | agents/validator.py | 20 мин |
| 8 | Граф | graph.py | 30 мин |
| 9 | Интеграция | api.py, тесты | 30 мин |

**Итого:** ~4 часа работы

---

## Текущий статус

- [x] Документ написан
- [x] Шаг 1: Типы Intent, Stats ✅
- [x] Шаг 2: CAPABILITIES ✅
- [x] Шаг 3: SQL модуль ✅
- [x] Шаг 4: Understander ✅
- [x] Шаг 5: DataFetcher ✅
- [x] Шаг 6: Analyst + Stats ✅
- [x] Шаг 7: Validator (no LLM) ✅
- [x] Шаг 8: Граф ✅
- [ ] Шаг 9: Тесты

### Дополнительно реализовано:
- [x] PatternDef для сложных запросов (type="pattern")
- [x] modules/patterns.py с 5 паттернами (consecutive_days, big_move, reversal, gap, range_breakout)
- [x] Промпты в отдельных файлах (agent/prompts/understander.py, analyst.py)

---

## Миграция

При переходе на v2:
1. Старые агенты остаются в `agents/` пока не заменим
2. Новые создаём параллельно
3. После тестов — удаляем старые
4. `educator.py` удаляется (логика в analyst)
