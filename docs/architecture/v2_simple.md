# Architecture: Simple Python Pipeline

## Ключевой принцип

**Code for Facts, LLM for Text**

- Код вычисляет факты детерминированно (паттерны, события, статистика)
- LLM только форматирует готовый контекст в человеческий текст
- LLM не видит сырые данные — не может галлюцинировать цифры

---

## Архитектура

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌───────────────┐
│   Question  │ ──▶ │   Parser    │ ──▶ │  Executor   │ ──▶ │ DataResponder │
│  (natural)  │     │   (LLM)     │     │  (Python)   │     │  (LLM+Code)   │
└─────────────┘     └─────────────┘     └─────────────┘     └───────────────┘
                          │                   │                     │
                          ▼                   ▼                     ▼
                    ParsedQuery          SQL/DuckDB            Context → Text
                      (JSON)           (deterministic)        (formatted)
```

**Parser (LLM):** Понимает вопрос → ParsedQuery (intent, what, period, filters)
**Executor (Python):** Детерминированно выполняет SQL, возвращает данные + флаги
**DataResponder (Code+LLM):** Собирает контекст из данных, LLM форматирует текст

---

## ParsedQuery

```python
class ParsedQuery(BaseModel):
    intent: str           # data, chitchat, concept, clarification
    what: str | None      # volatility, returns, volume, patterns...
    period: Period | None # year, date_range, relative
    filters: list[str]    # weekday:monday, session:rth, event:opex...
    group_by: str | None  # weekday, month, quarter...
    operation: str | None # list, stats, compare, top_n, streak...
    unclear: list[str]    # что нужно уточнить
```

### Intents

| Intent | Описание | Следующий шаг |
|--------|----------|---------------|
| `data` | Запрос данных | Executor → DataResponder |
| `chitchat` | Приветствие | Простой ответ |
| `concept` | Объяснение термина | ConceptResponder |
| `clarification` | Неясный запрос | Уточняющий вопрос |

### Operations

| Operation | Описание | Пример |
|-----------|----------|--------|
| `list` | Вывести строки | "Покажи январь 2024" |
| `filter` | Фильтрация | "Дни с gap > 1%" |
| `stats` | Статистика | "Средняя волатильность" |
| `compare` | Сравнить группы | "Понедельники vs пятницы" |
| `top_n` | Топ N записей | "Топ-5 по объёму" |
| `streak` | Подряд идущие | "3+ красных подряд" |
| `seasonality` | По периодам | "Лучший месяц" |

---

## Context Building

DataResponder собирает контекст из нескольких источников:

### 1. Флаги паттернов (из SQL)
```sql
SELECT *,
  CASE WHEN ... THEN 1 ELSE 0 END as is_hammer,
  CASE WHEN ... THEN 1 ELSE 0 END as is_doji
FROM daily
```

### 2. События (проверка дат по конфигу)
```python
# agent/config/market/events.py
events = check_dates_for_events(dates, symbol)
# → {"2024-12-20": ["Quad Witching", "OPEX"]}
```

### 3. Праздники (из конфига)
```python
# agent/config/market/holidays.py
holidays = check_dates_for_holidays(dates, symbol)
# → {"early_close_dates": ["2024-12-24"], "holiday_names": {...}}
```

### Результат для LLM
```
Context:
- 3× red
- 2× green
- 1× Quad Witching
- 1× VIX Expiration
```

LLM получает этот контекст и пишет:
> "Топ-5 включают три красных и два зелёных дня, затронули Quad Witching и VIX экспирацию."

---

## Pattern Config

Паттерны определены в `agent/config/patterns/candle.py`:

```python
"hammer": {
    "name": "Hammer",
    "category": "reversal",
    "signal": "bullish",
    "importance": "medium",  # high, medium, low
    "description": "Long lower shadow, small body at top...",
    "detection": {
        "body_ratio_max": 0.3,
        "lower_shadow_ratio_min": 0.6,
        "upper_shadow_ratio_max": 0.1,
    },
    "related": ["hanging_man", "inverted_hammer"],
    "opposite": "hanging_man",
    "confirms": ["morning_star", "bullish_engulfing"],
    "reliability": 0.60,
}
```

### Importance Filtering

| Level | Когда показывать |
|-------|------------------|
| `high` | Всегда (engulfing, morning/evening star) |
| `medium` | Если мало паттернов или встречается ≥2 раз |
| `low` | Только если ≤3 паттернов всего |

---

## Структура файлов

```
agent/
├── prompts/
│   ├── parser.py          # Промпт для Parser LLM
│   ├── responder.py       # Промпт для Responder LLM
│   └── clarification.py   # Уточняющие вопросы
├── agents/
│   └── responders/
│       └── data.py        # DataResponder (context → text)
├── executor.py            # SQL генерация и выполнение
├── operations/            # Операции (stats, compare, top_n...)
├── patterns/
│   └── scanner.py         # Numpy детекция паттернов
├── config/
│   ├── patterns/
│   │   ├── candle.py      # Свечные паттерны с метаданными
│   │   └── price.py       # Ценовые паттерны (gap, trend)
│   └── market/
│       ├── events.py      # OPEX, NFP, FOMC, Quad Witching
│       ├── holidays.py    # Праздники, early close
│       └── instruments.py # Настройки инструментов
├── types.py               # ParsedQuery, Period и другие типы
└── tests/
    └── test_graph_v2.py   # Тесты pipeline
```

---

## Пример полного flow

**Вопрос:** "топ 5 самых волатильных дней 2024"

### 1. Parser
```json
{
  "intent": "data",
  "what": "volatility",
  "period": {"type": "year", "year": 2024},
  "operation": "top_n",
  "top_n": 5
}
```

### 2. Executor
```sql
SELECT date, open, high, low, close, range, range_pct, is_red, is_green
FROM daily WHERE year = 2024
ORDER BY range_pct DESC LIMIT 5
```

### 3. Context Builder
```python
flag_counts = {"is_red": 3, "is_green": 2}
dates = ["2024-08-05", "2024-12-20", ...]
events = check_dates_for_events(dates)  # → Quad Witching, VIX exp
```

### 4. DataResponder
```
Context:
- 3× red
- 2× green
- 1× Quad Witching
- 1× VIX Expiration

LLM → "Топ-5 самых волатильных дней 2024 включают три красных
       и два зелёных дня, затронули Quad Witching и VIX экспирацию."
```

---

## Преимущества

| Аспект | Как решено |
|--------|------------|
| **Честность** | LLM не видит цифры — только готовый контекст |
| **Отладка** | Каждый шаг изолирован, легко тестировать |
| **Расширение** | Новый паттерн = запись в config |
| **Производительность** | DuckDB для SQL, numpy для паттернов |
| **Maintainability** | Чёткие границы между компонентами |
