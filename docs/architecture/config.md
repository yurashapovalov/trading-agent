# Конфигурация

Система знает про инструменты, паттерны, события и праздники через конфиги.

## Зачем

Агенты не гуглят "что такое OPEX" — они берут информацию из конфигов:

```
User: "что было в день OPEX?"
      ↓
Executor: проверяет config/market/events.py
      ↓
Presenter: "15 января был OPEX — monthly options expiration"
```

## Структура

```
agent/config/
├── market/
│   ├── instruments.py   # Инструменты и сессии
│   ├── holidays.py      # Праздники
│   └── events.py        # OPEX, NFP, FOMC...
├── patterns/
│   ├── candle.py        # Свечные паттерны
│   └── price.py         # Ценовые паттерны
└── backtest/            # (будущее)
```

## Инструменты

`market/instruments.py` — параметры торговых инструментов.

| Параметр | NQ |
|----------|-----|
| Биржа | CME |
| Данные | 2008 — 2026 |
| Торговый день | 18:00 prev → 17:00 current (ET) |
| Maintenance | 17:00 — 18:00 (нет данных) |

**Сессии:**

| Сессия | Время (ET) |
|--------|------------|
| RTH | 09:30 — 17:00 |
| ETH | 18:00 — 17:00 (full day) |
| OVERNIGHT | 18:00 — 09:30 |
| ASIAN | 18:00 — 03:00 |
| EUROPEAN | 03:00 — 09:30 |

## Праздники

`market/holidays.py` — когда рынок закрыт или закрывается раньше.

**Полностью закрыт:**
- New Year's Day, MLK Day, Presidents Day
- Good Friday, Memorial Day, Juneteenth
- Independence Day, Labor Day, Thanksgiving, Christmas

**Early close (13:00 ET):**
- Independence Day Eve, Black Friday
- Christmas Eve, New Year's Eve

Date Resolver автоматически пропускает праздники при расчёте "вчера", "прошлая неделя".

## Рыночные события

`market/events.py` — регулярные события, влияющие на волатильность.

| Событие | Что это | Когда |
|---------|---------|-------|
| **OPEX** | Monthly options expiration | 3-я пятница месяца |
| **Quad Witching** | 4 типа контрактов экспирятся | 3-я пятница Mar/Jun/Sep/Dec |
| **NFP** | Non-farm payrolls | 1-я пятница месяца |
| **FOMC** | Fed meeting | по расписанию |
| **VIX Expiration** | VIX settlement | среда за 30 дней до SPX expiry |

Presenter упоминает события когда они релевантны анализу.

## Свечные паттерны

`patterns/candle.py` — определения паттернов для детекции и объяснения.

**Reversal (разворотные):**
- hammer, inverted_hammer, hanging_man, shooting_star
- bullish_engulfing, bearish_engulfing
- morning_star, evening_star

**Continuation (продолжение):**
- three_white_soldiers, three_black_crows

**Neutral:**
- doji, dragonfly_doji, gravestone_doji
- spinning_top, marubozu

Каждый паттерн имеет: category, signal (bullish/bearish/neutral), importance, reliability.

## Ценовые паттерны

`patterns/price.py` — структурные паттерны на нескольких барах.

**Consolidation:**
- inside_bar — range внутри предыдущего бара
- narrow_range_4 (NR4) — минимальный range за 4 бара
- narrow_range_7 (NR7) — минимальный range за 7 баров

**Trend:**
- higher_high, higher_low — uptrend structure
- lower_low, lower_high — downtrend structure

**Breakout:**
- breakout_high, breakout_low — пробой уровня

## Backtest (будущее)

`backtest/` — наброски для будущего бэктестинга:

- Position sizing: fixed, percent, risk_based, kelly
- Execution: slippage, commission, initial_capital
- Output: 25+ метрик (win_rate, sharpe, drawdown...)

## Кто использует

| Компонент | Что берёт из конфигов |
|-----------|----------------------|
| **Date Resolver** | Праздники — пропускает при расчёте дат |
| **Executor** | Инструменты — сессии, торговые дни |
| **Presenter** | События, праздники, паттерны — контекст для ответа |
| **Scanner** | Паттерны — параметры детекции |
