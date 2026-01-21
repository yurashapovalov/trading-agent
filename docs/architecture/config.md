# Конфигурация

Система знает про паттерны, события и праздники через конфиги.

## Зачем

Агенты не гуглят "что такое OPEX" — они берут информацию из конфигов:

```
User: "что было в день OPEX?"
           ↓
Executor: проверяет config/market/events.py
           ↓
Presenter: "15 января был OPEX — monthly options expiration"
```

## Паттерны свечей

`agent/config/patterns/candle.py`

```python
"hammer": {
    "name": "Hammer",
    "category": "reversal",     # reversal, continuation, neutral
    "signal": "bullish",        # bullish, bearish, neutral  
    "importance": "medium",     # high, medium, low
    "description": "Молот — потенциальный разворот вверх"
}
```

**Importance** определяет когда упоминать:
- **high** — всегда (engulfing, morning star)
- **medium** — если паттернов немного
- **low** — только если совсем мало

Presenter смотрит на importance и решает что включить в ответ.

## Рыночные события

`agent/config/market/events.py`

| Событие | Что это | Как определяется |
|---------|---------|------------------|
| **OPEX** | Monthly options expiration | 3-я пятница месяца |
| **Quad Witching** | 4 типа контрактов экспирятся | 3-я пятница Mar/Jun/Sep/Dec |
| **NFP** | Non-farm payrolls | 1-я пятница месяца |
| **FOMC** | Fed meeting | по расписанию |

```python
# Проверка даты
events = check_dates_for_events(["2024-01-19"])
# → {"2024-01-19": ["OPEX"]}
```

## Праздники

`agent/config/market/holidays.py`

```python
# US Market Holidays
"2024-01-01": "New Year's Day"
"2024-01-15": "MLK Day"
"2024-02-19": "Presidents Day"
...

# Early Close (1:00 PM ET)
"2024-07-03": "Independence Day Eve"
"2024-11-29": "Black Friday"
```

```python
# Проверка
is_trading_day("NQ", date(2024, 12, 25))  # False (Christmas)
get_day_type("NQ", date(2024, 11, 29))    # "early_close"
```

## Как агенты используют конфиги

### Parser
Не использует конфиги напрямую — просто парсит вопрос.

### Executor
```python
# Date Resolver учитывает праздники
"yesterday" → пропускает выходные и праздники
```

### Presenter
```python
# Проверяет какие события были в данных
events = check_dates_for_events(dates)
holidays = check_dates_for_holidays(dates)
patterns = scan_patterns(rows)

# Формирует контекст
"3× OPEX days, 1× NFP, 5× hammer patterns"
```

## Добавление нового

**Новый паттерн:**
```python
# agent/config/patterns/candle.py
"new_pattern": {
    "name": "New Pattern",
    "category": "...",
    "signal": "...",
    "importance": "...",
    "description": "..."
}
```

**Новое событие:**
```python
# agent/config/market/events.py
def is_new_event(d: date) -> bool:
    # логика определения
    return True/False
```

**Новый праздник:**
```python
# agent/config/market/holidays.py
US_HOLIDAYS = {
    ...
    date(2025, 1, 1): "New Year's Day",
}
```

Конфиги — это knowledge base системы. LLM не нужно знать когда OPEX — система знает.
