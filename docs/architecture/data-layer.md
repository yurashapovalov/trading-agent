# Data Layer

Как обрабатываются запросы к данным.

## Executor Pipeline

```
ParsedQuery
     │
     ▼
┌─────────────┐
│ resolve     │ "2024" → "2024-01-01" : "2024-12-31"
│ period      │ "yesterday" → "2025-01-14"
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ get_bars    │ загружаем данные из DuckDB
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ enrich      │ добавляем weekday, month, is_green, gap_pct...
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ filter      │ weekday=Friday, condition="gap > 0"
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ operation   │ stats, top_n, compare, seasonality...
└──────┬──────┘
       │
       ▼
   Result
```

## Операции

| Операция | Что делает | Пример |
|----------|------------|--------|
| **stats** | Базовая статистика | avg, median, green_pct |
| **top_n** | Топ N записей | "топ 5 волатильных дней" |
| **compare** | Сравнение групп | "понедельники vs пятницы" |
| **seasonality** | Сезонность | "лучший месяц" |
| **streak** | Серии | "максимальная серия зелёных" |
| **distribution** | Распределение | "гистограмма доходности" |

## Date Resolver

Преобразует человеческие периоды в даты:

| Input | Output |
|-------|--------|
| `year: 2024` | 2024-01-01 : 2024-12-31 |
| `month: 2024-06` | 2024-06-01 : 2024-06-30 |
| `quarter: Q2 2024` | 2024-04-01 : 2024-06-30 |
| `yesterday` | предыдущий торговый день |
| `last_week` | пн-пт прошлой недели |
| `last_n_days: 5` | 5 торговых дней назад |

Учитывает:
- Выходные (суббота, воскресенье)
- Праздники (market holidays)

## Данные

Источник: **DuckDB** с минутными барами NQ futures.

После загрузки данные обогащаются:

| Поле | Описание |
|------|----------|
| `change_pct` | (close - open) / open * 100 |
| `range` | high - low |
| `range_pct` | range / open * 100 |
| `gap_pct` | gap от предыдущего close |
| `is_green` | close > open |
| `weekday` | 0=Mon ... 4=Fri |
| `month` | 1-12 |
| `quarter` | 1-4 |

## Конфиги

**Паттерны** (`agent/config/patterns/`):
- Свечные: hammer, doji, engulfing, morning star...
- Ценовые: gap, trend, inside bar...

**События** (`agent/config/market/events.py`):
- OPEX (monthly options expiration)
- Quad Witching
- NFP (non-farm payrolls)
- FOMC

**Праздники** (`agent/config/market/holidays.py`):
- US market holidays
- Early close days
