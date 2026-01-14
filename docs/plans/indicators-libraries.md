# Технические индикаторы

**File:** `agent/modules/indicators.py` (планируется)

**Status:** В планах

## Философия

Индикаторы — **building blocks** для бэктестинга и поиска входов, не самостоятельная фича.

```
LLM decides WHAT → какой индикатор, параметры, условие
Code does HOW   → вычисляет формулу
```

## Реализация: pandas_ta

Используем готовую библиотеку [pandas_ta](https://github.com/twopirllc/pandas-ta) — 130+ индикаторов из коробки.

```python
import pandas_ta as ta

# RSI
df['rsi'] = ta.rsi(df['close'], length=14)

# MACD (возвращает 3 колонки)
macd = ta.macd(df['close'])

# EMA
df['ema20'] = ta.ema(df['close'], length=20)

# Bollinger Bands
bb = ta.bbands(df['close'], length=20)

# ATR
df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

# Stochastic
stoch = ta.stoch(df['high'], df['low'], df['close'])
```

## Альтернатива: ta-lib

```python
import talib

# Быстрее (написан на C), но сложнее в установке
rsi = talib.RSI(df['close'], timeperiod=14)
macd, signal, hist = talib.MACD(df['close'])
```

**Рекомендация:** Начать с pandas_ta (проще), перейти на ta-lib если нужна скорость.

## Интеграция в архитектуру

```
User: "Найди когда RSI был ниже 30"
              │
              ▼
┌─────────────────────────┐
│      Understander       │
│  → intent: RSI < 30     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│       SQL Agent         │
│  → SQL для базовых данных│
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│      DataFetcher        │
│  1. Выполняет SQL       │
│  2. Вызывает indicators │
│     → ta.rsi(close, 14) │
│  3. Фильтрует RSI < 30  │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│        Analyst          │
│  → Данные с RSI колонкой│
└─────────────────────────┘
```

## Планируемый модуль

```python
# agent/modules/indicators.py

import pandas as pd
import pandas_ta as ta

def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Добавляет RSI колонку."""
    df['rsi'] = ta.rsi(df['close'], length=period)
    return df

def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет MACD, signal, histogram."""
    macd = ta.macd(df['close'])
    df = pd.concat([df, macd], axis=1)
    return df

def add_ema(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """Добавляет EMA колонку."""
    df[f'ema{period}'] = ta.ema(df['close'], length=period)
    return df

def add_bollinger(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Добавляет Bollinger Bands."""
    bb = ta.bbands(df['close'], length=period)
    df = pd.concat([df, bb], axis=1)
    return df

def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Добавляет ATR колонку."""
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=period)
    return df
```

## Базовые индикаторы

| Индикатор | Функция pandas_ta | Параметры |
|-----------|-------------------|-----------|
| RSI | `ta.rsi()` | length=14 |
| MACD | `ta.macd()` | fast=12, slow=26, signal=9 |
| EMA | `ta.ema()` | length |
| SMA | `ta.sma()` | length |
| Bollinger | `ta.bbands()` | length=20, std=2 |
| ATR | `ta.atr()` | length=14 |
| Stochastic | `ta.stoch()` | k=14, d=3 |
| VWAP | `ta.vwap()` | — |
| OBV | `ta.obv()` | — |

## Комбинации

Сила агентного подхода — комбинации на natural language:

```
"RSI < 30 И цена выше EMA50"
"MACD пересёк signal снизу вверх"
"Bollinger squeeze + volume spike"
"RSI дивергенция с ценой"
```

SQL Agent или отдельный Indicator Agent будет генерировать логику для комбинаций.

## Добавление по мере надобности

Не реализуем все индикаторы заранее. Добавляем когда нужны:

```
User: "Протестируй стратегию на RSI"
→ Нужен RSI? Добавляем calculate_rsi()

User: "Добавь фильтр по MACD"
→ Нужен MACD? Добавляем calculate_macd()
```

## Зависимости

```bash
pip install pandas-ta
# или
pip install TA-Lib  # требует установки C библиотеки
```
