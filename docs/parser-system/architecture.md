# Core Architecture

## Почему Data Layer — фундамент

```
     Backtest    Scan    Anomaly    Positions
          \       |        |        /
           \      |        |       /
            ▼     ▼        ▼      ▼
       ┌────────────────────────────┐
       │        Data Layer          │
       │    (получить данные)       │
       └─────────────┬──────────────┘
                     │
                     ▼
                 ┌────────┐
                 │ DuckDB │
                 └────────┘
```

Любая задача начинается с данных:
- Бэктест → нужны данные
- Сканирование паттернов → нужны данные
- Поиск аномалий → нужны данные
- Анализ позиций → нужны данные

**Data Layer — самая важная часть системы.**

Данные могут отдаваться:
- **Человеку** → через Presenter в читаемом виде
- **Агенту** → напрямую для дальнейшей обработки

---

## Пайплайн

```
User → Intent → Parser → Planner → Executor → Result
```

**Intent** — определяет тип запроса, язык, переводит на английский

**Parser** — получает вопрос на английском, отвечает ЧТО хочет пользователь (LLM)

**Planner** — отвечает КАК посчитать (LLM)

**Executor** — выполняет (код)

---

## Атом

```
{когда} + {что} + [фильтр] + [группа]
```

- **когда** — период (обязательно)
- **что** — метрика (обязательно)
- **фильтр** — условие выборки
- **группа** — группировка результата

**Атом стабилен — не меняется. Расширение через операции.**

### Когда
минута, час, день, неделя, месяц, квартал, год, всё время, конкретное, относительное

### Что
- Сырые: open, high, low, close, volume
- Производные: change, range, gap, volatility

---

## Операции над атомами

```
operation(атом, [атом], [params])
```

1. **list** — показать (params: n, sort — опционально)
2. **count** — посчитать количество
3. **compare** — сравнить атомы
4. **correlation** — корреляция атомов
5. **around** — до/после события (params: offset)
6. **streak** — серии N подряд
7. **distribution** — распределение значений
8. **probability** — условная вероятность P(outcome | condition)
9. **formation** — когда формируется high/low

---

## Примеры

**"volatility for 2024"**
```json
{"operation": "list", "atoms": [{"when": "2024", "what": "volatility"}]}
```

**"how many red days in 2024"**
```json
{"operation": "count", "atoms": [{"when": "2024", "what": "change", "filter": "< 0"}]}
```

**"top 10 by volume for 2024"**
```json
{"operation": "list", "params": {"n": 10, "sort": "desc"}, "atoms": [{"when": "2024", "what": "volume"}]}
```

**"compare mondays and fridays in 2024"**
```json
{
  "operation": "compare",
  "atoms": [
    {"when": "2024", "what": "change", "filter": "monday"},
    {"when": "2024", "what": "change", "filter": "friday"}
  ]
}
```

**"correlation of volatility and volume for 2024"**
```json
{
  "operation": "correlation",
  "atoms": [
    {"when": "2024", "what": "volatility"},
    {"when": "2024", "what": "volume"}
  ]
}
```

**"what happened after red days in 2024"**
```json
{
  "operation": "around",
  "atoms": [{"when": "2024", "what": "change", "filter": "change < 0"}],
  "params": {"offset": 1, "unit": "1D"}
}
```

**"how many times were there 3+ red days in a row in 2024"**
```json
{
  "operation": "streak",
  "atoms": [{"when": "2024", "what": "count", "filter": "change < 0"}],
  "params": {"n": 3}
}
```

**"how is volatility distributed in 2024"**
```json
{
  "operation": "distribution",
  "atoms": [{"when": "2024", "what": "volatility"}]
}
```

**"at what hour does the daily high usually form in 2024"**
```json
{
  "operation": "formation",
  "atoms": [{"when": "2024", "what": "high", "group": "by hour"}]
}
```

**"what is the probability of growth after gap up in 2024"**
```json
{
  "operation": "probability",
  "atoms": [{"when": "2024", "what": "change", "filter": "gap > 0"}],
  "params": {"outcome": "> 0"}
}
```

**"top 10 drops in 2024, what happened the day before and how did they close the next day"** (цепочка зависимых шагов)
```json
{
  "steps": [
    {"id": "s1", "operation": "list", "params": {"n": 10, "sort": "asc"}, "atoms": [{"when": "2024", "what": "change"}]},
    {"id": "s2", "operation": "list", "from": "s1", "atoms": [{"when": "-1 day", "what": "change"}]},
    {"id": "s3", "operation": "list", "from": "s1", "atoms": [{"when": "+1 day", "what": "close"}]}
  ]
}
```
