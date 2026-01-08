# Trading Analytics Agent

## Идея

Агент для анализа торговых данных на естественном языке. Вместо написания кода вручную — просто говоришь что нужно, агент сам генерирует запросы, выполняет их и возвращает результат.

## Примеры использования

```
User: "Найди оптимальное время для входа в SHORT на CL с RR 1:1.5, 
       стоп не больше 30 тиков и винрейтом от 65%"

Agent: [генерирует SQL/код] → [выполняет] → [возвращает таблицу результатов]
```

```
User: "Покажи статистику по NQ за последний месяц — 
       средний дневной range, объём, волатильность по часам"

Agent: [анализирует данные] → [возвращает статистику]
```

```
User: "Протестируй стратегию: вход в LONG на ES в 09:35, 
       стоп 10 пунктов, тейк 15 пунктов"

Agent: [бэктестит] → [возвращает результаты: винрейт, профит, просадка]
```

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INPUT                           │
│         "Найди лучшие входы на CL с винрейтом 70%+"        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      LLM AGENT (Claude)                     │
│                                                             │
│  1. Понимает запрос                                         │
│  2. Выбирает нужные функции                                 │
│  3. Генерирует параметры запроса                            │
│  4. Интерпретирует результаты                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         TOOLS                               │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  query_ohlcv    │  │ find_optimal_   │                  │
│  │                 │  │ entries         │                  │
│  │ SQL запросы к   │  │                 │                  │
│  │ данным OHLCV    │  │ Поиск лучших    │                  │
│  │                 │  │ точек входа     │                  │
│  └─────────────────┘  └─────────────────┘                  │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │  backtest_      │  │ get_statistics  │                  │
│  │  strategy       │  │                 │                  │
│  │                 │  │ Статистика по   │                  │
│  │ Тест стратегии  │  │ инструменту     │                  │
│  │ на истории      │  │                 │                  │
│  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                             │
│                                                             │
│  SQLite / PostgreSQL / DuckDB с таблицами:                 │
│                                                             │
│  - ohlcv_1min (timestamp, symbol, open, high, low,         │
│                close, volume)                               │
│  - symbols (symbol, tick_size, tick_value, description)    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Функции (Tools)

### 1. `query_ohlcv`

Выполняет SQL запрос к данным OHLCV.

```python
def query_ohlcv(sql: str) -> pd.DataFrame:
    """
    Выполняет SQL запрос к базе данных с OHLCV данными.
    
    Доступные таблицы:
    - ohlcv_1min: timestamp, symbol, open, high, low, close, volume
    
    Пример:
    SELECT * FROM ohlcv_1min 
    WHERE symbol = 'CL' 
    AND timestamp >= '2025-01-01'
    """
```

### 2. `find_optimal_entries`

Ищет оптимальные точки входа по заданным критериям.

```python
def find_optimal_entries(
    symbol: str,
    direction: str,           # 'long' | 'short' | 'both'
    risk_reward: float,       # например 1.5 для RR 1:1.5
    max_stop_loss: float,     # максимальный стоп в тиках
    min_winrate: float,       # минимальный винрейт (0-100)
    start_hour: int,          # начало диапазона часов
    end_hour: int,            # конец диапазона часов
    start_date: str = None,   # опционально: начало периода
    end_date: str = None      # опционально: конец периода
) -> pd.DataFrame:
    """
    Возвращает таблицу с оптимальными временами входа:
    - hour: час входа
    - minute: минута входа (опционально)
    - direction: long/short
    - stop_loss: оптимальный стоп
    - winrate: процент выигрышных сделок
    - avg_profit: средний профит на сделку
    - total_trades: количество сделок в выборке
    """
```

### 3. `backtest_strategy`

Тестирует конкретную стратегию на исторических данных.

```python
def backtest_strategy(
    symbol: str,
    entry_hour: int,
    entry_minute: int,
    direction: str,           # 'long' | 'short'
    stop_loss: float,         # стоп в тиках
    take_profit: float,       # тейк в тиках
    start_date: str = None,
    end_date: str = None
) -> dict:
    """
    Возвращает результаты бэктеста:
    - total_trades: общее количество сделок
    - wins: выигрышные сделки
    - losses: проигрышные сделки
    - winrate: винрейт
    - total_profit: общий профит в тиках
    - max_drawdown: максимальная просадка
    - profit_factor: profit factor
    - trades: список всех сделок
    """
```

### 4. `get_statistics`

Возвращает статистику по инструменту.

```python
def get_statistics(
    symbol: str,
    start_date: str = None,
    end_date: str = None,
    group_by: str = 'hour'    # 'hour' | 'day' | 'week' | 'month'
) -> dict:
    """
    Возвращает статистику:
    - avg_daily_range: средний дневной диапазон
    - avg_volume: средний объём
    - volatility_by_hour: волатильность по часам
    - trend_stats: статистика трендов
    """
```

## Структура базы данных

```sql
-- Основная таблица с минутными данными
CREATE TABLE ohlcv_1min (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open DECIMAL(10,4) NOT NULL,
    high DECIMAL(10,4) NOT NULL,
    low DECIMAL(10,4) NOT NULL,
    close DECIMAL(10,4) NOT NULL,
    volume INTEGER NOT NULL,
    
    UNIQUE(timestamp, symbol)
);

CREATE INDEX idx_ohlcv_symbol_time ON ohlcv_1min(symbol, timestamp);

-- Справочник инструментов
CREATE TABLE symbols (
    symbol VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100),
    tick_size DECIMAL(10,6),    -- размер тика (0.01 для CL)
    tick_value DECIMAL(10,2),   -- стоимость тика ($10 для CL)
    exchange VARCHAR(20),
    trading_hours VARCHAR(50)   -- "18:00-17:00" для CL
);
```

## Пример диалога

```
User: Загрузи данные из файла CL_1min_sample.csv

Agent: ✓ Загружено 14,841 баров для CL
       Период: 2025-11-30 — 2025-12-15
       
User: Найди лучшие точки входа в шорт с RR 1:1.5, 
      стоп до 25 тиков, винрейт от 70%

Agent: [вызывает find_optimal_entries(...)]

       Найдено 3 оптимальных входа:
       
       | Время | SL    | Winrate | Avg Profit | Сделок |
       |-------|-------|---------|------------|--------|
       | 09:00 | 20    | 80.0%   | +20.0      | 10     |
       | 09:00 | 25    | 75.0%   | +21.9      | 8      |
       | 11:00 | 15    | 70.0%   | +11.3      | 10     |
       
       Лучший вариант: SHORT в 09:00 со стопом 20 тиков

User: Протестируй 09:00 SHORT, стоп 20, тейк 30

Agent: [вызывает backtest_strategy(...)]

       Результаты бэктеста:
       - Сделок: 10
       - Винрейт: 80%
       - Общий профит: +200 тиков ($2,000)
       - Max Drawdown: -40 тиков
       - Profit Factor: 4.0
```

## Стек технологий

- **Python 3.11+**
- **Claude API** — для понимания запросов и генерации ответов
- **DuckDB** или **SQLite** — для хранения и запросов данных
- **Pandas** — для обработки данных
- **Click** или **Typer** — для CLI интерфейса

## Структура проекта

```
trading-agent/
├── agent/
│   ├── __init__.py
│   ├── main.py           # Точка входа, CLI
│   ├── llm.py            # Работа с Claude API
│   └── tools/
│       ├── __init__.py
│       ├── query.py      # query_ohlcv
│       ├── entries.py    # find_optimal_entries
│       ├── backtest.py   # backtest_strategy
│       └── stats.py      # get_statistics
├── data/
│   ├── database.py       # Работа с базой данных
│   └── loader.py         # Загрузка CSV/Parquet
├── config.py
├── requirements.txt
└── README.md
```

## MVP — минимальная версия

Для начала можно сделать упрощённую версию:

1. **Один инструмент** — только CL
2. **Две функции** — `find_optimal_entries` и `backtest_strategy`
3. **SQLite** — для простоты
4. **CLI интерфейс** — запуск через терминал

Потом расширять: больше инструментов, больше функций, веб-интерфейс.

## Следующие шаги

1. Создать базовую структуру проекта
2. Реализовать загрузку данных в SQLite/DuckDB
3. Написать функции-инструменты
4. Настроить Claude API с tool use
5. Сделать простой CLI для взаимодействия
6. Тестировать и итерировать