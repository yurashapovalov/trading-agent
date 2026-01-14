# Multi-Agent System v2 — Концепция

## Проблема текущей версии

### Пример провала

**Вопрос**: "какое время чаще всего становится high/low дня за 2020-2025"

**Что сделал Understander**:
```json
{
    "type": "data",
    "granularity": "hourly",
    "search_condition": "most frequent time for High and Low within 06:00-16:00"
}
```

**Что сделал SQL Agent**:
```sql
SELECT time_of_day, COUNT(*) as count_high
FROM minute_data
GROUP BY time_of_day
```

**Что нужно было**:
```sql
WITH daily_highs AS (
    SELECT date, time, ROW_NUMBER() OVER (PARTITION BY date ORDER BY high DESC) as rn
    FROM ohlcv_1min
),
high_events AS (
    SELECT time FROM daily_highs WHERE rn = 1
)
SELECT time, COUNT(*) as frequency FROM high_events GROUP BY time ORDER BY frequency DESC
```

### Корневые причины

1. **Understander** передаёт `search_condition` — одну строку. SQL Agent должен сам догадаться что делать.

2. **SQL Agent** использует pattern matching — ищет похожий пример в промпте. Когда примера нет — пишет что-то похожее, но неправильное.

3. **Нет понимания уровней агрегации** — система не различает:
   - Простая агрегация (GROUP BY date)
   - Поиск события (PARTITION BY date, ROW_NUMBER)
   - Распределение событий (вложенная агрегация)

---

## Новая архитектура: Разделение ролей

### Принцип

```
┌─────────────────────────────────────────────────────────────────┐
│                      UNDERSTANDER                                │
│                 "Умный Product Manager"                          │
│                                                                  │
│  Модель: gemini-3-flash + thinking                              │
│                                                                  │
│  Задачи:                                                        │
│  - Глубоко понять вопрос пользователя                           │
│  - Задать уточняющие вопросы (human-in-the-loop)                │
│  - Знать домен OHLCV и типичные паттерны анализа                │
│  - Сформулировать ПОДРОБНОЕ ТЗ для SQL Agent                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │  detailed_spec (подробное ТЗ)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SQL AGENT                                  │
│                 "Исполнитель-разработчик"                        │
│                                                                  │
│  Модель: gemini-3-flash + thinking                              │
│                                                                  │
│  Задачи:                                                        │
│  - Получить чёткое ТЗ от Understander                           │
│  - Знать SQL паттерны и DuckDB синтаксис                        │
│  - Написать оптимальный SQL по ТЗ                               │
└─────────────────────────────────────────────────────────────────┘
```

### Разделение ответственности

| Аспект | Understander | SQL Agent |
|--------|--------------|-----------|
| **Роль** | Product Manager | Developer |
| **Думает о** | Что нужно пользователю | Как написать код |
| **Модель** | Умная с thinking | Умная с thinking |
| **Human-in-loop** | Да, задаёт вопросы | Нет |
| **Знает** | Домен, бизнес-логика | SQL, DuckDB, паттерны |

---

## Understander v2

### Что должен знать

**Статичное (домен OHLCV):**
- Структура данных: timestamp, open, high, low, close, volume
- Что такое свеча, бар, торговый день
- Сессии: RTH, ETH, Overnight, азиатская/европейская/американская
- Гэпы, волатильность, range, изменение цены
- Типичные вопросы трейдеров и как их решать
- Уровни агрегации (см. ниже)

**Динамическое (capabilities):**
- Какие инструменты доступны (NQ, ES, AAPL, BTC...)
- Какой период данных есть для каждого
- Особенности инструмента (торговые часы, тик, etc.)

### Уровни агрегации

Understander должен понимать и объяснять уровни:

| Уровень | Описание | SQL паттерн | Пример задачи |
|---------|----------|-------------|---------------|
| 0 | Raw data | SELECT * FROM ohlcv_1min | "Покажи минутки за час" |
| 1 | Агрегация по периоду | GROUP BY date/hour/week | "Средняя волатильность по дням" |
| 2 | Событие внутри группы | PARTITION BY + ROW_NUMBER | "Время формирования high дня" |
| 3 | Статистика событий | Вложенная агрегация | "Распределение времени high" |

### Output: detailed_spec

Вместо короткого `search_condition`, Understander генерирует подробное ТЗ:

```python
{
    "type": "data",
    "symbol": "NQ",
    "period_start": "2020-01-01",
    "period_end": "2025-01-01",

    # Подробное ТЗ для SQL Agent
    "detailed_spec": """
    ## Задача
    Найти распределение времени формирования дневного максимума (high).

    ## Контекст
    Пользователь хочет понять в какое время дня чаще всего формируется
    максимальная цена. Это поможет в планировании торговли.

    ## Логика решения
    1. Для каждого торгового дня найти минуту, где high = MAX(high) этого дня
       - Использовать PARTITION BY date ORDER BY high DESC
       - ROW_NUMBER() для выбора первой строки
    2. Извлечь время (timestamp::time) этой минуты
    3. Сгруппировать результаты по времени
    4. Посчитать частоту каждого времени
    5. Отсортировать по частоте DESC, взять TOP-20

    ## Фильтры
    - Период: 2020-01-01 — 2025-01-01
    - Время дня: 06:00 — 16:00 (пользователь указал)

    ## Ожидаемый результат
    - Количество строк: ~20 (TOP-20 времён)
    - Колонки: time, frequency
    - Сумма frequency ≈ количество торговых дней (~1250)

    ## SQL паттерн
    Уровень 2 (событие) + Уровень 3 (статистика событий)
    Использовать CTE с PARTITION BY + ROW_NUMBER, затем GROUP BY
    """
}
```

### Human-in-the-loop

Understander задаёт вопросы когда:

1. **Неясна цель** — "Что вы хотите узнать о high/low?"
2. **Множество интерпретаций** — "Вас интересует время или цена?"
3. **Не хватает параметров** — "За какой период? Какие часы?"
4. **Сложная задача** — "Правильно ли я понял: вы хотите..."

```
Пользователь: "покажи high low"

Understander (thinking):
  "Неясно что именно нужно:
   - Показать значения high/low за период?
   - Найти когда были экстремумы?
   - Статистика по high/low?"

Understander → Clarification:
  "Что именно вас интересует про high/low?

   Варианты:
   • Показать дневные high/low за период
   • Найти дни с максимальным range (high-low)
   • Узнать в какое время формируется high/low дня"
```

---

## SQL Agent v2

### Что должен знать

**SQL и DuckDB:**
- Синтаксис DuckDB (FIRST, LAST, ::date, ::time)
- Window functions (PARTITION BY, ROW_NUMBER, LAG, LEAD)
- CTEs для многоуровневых запросов
- Агрегатные функции (AVG, STDDEV, CORR, PERCENTILE)
- Оптимизация запросов

**Паттерны для уровней:**

```sql
-- Уровень 1: Простая агрегация
WITH daily AS (
    SELECT timestamp::date as date, MAX(high) as high, MIN(low) as low
    FROM ohlcv_1min
    GROUP BY date
)
SELECT * FROM daily

-- Уровень 2: Событие внутри дня
WITH ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY timestamp::date ORDER BY high DESC) as rn
    FROM ohlcv_1min
)
SELECT * FROM ranked WHERE rn = 1

-- Уровень 3: Статистика событий
WITH ranked AS (...),
events AS (SELECT * FROM ranked WHERE rn = 1)
SELECT time, COUNT(*) FROM events GROUP BY time
```

### Input

SQL Agent получает `detailed_spec` от Understander и пишет SQL строго по ТЗ.

### Thinking

SQL Agent с thinking рассуждает:

```
Читаю ТЗ...

Задача: распределение времени high дня.

Уровень: 2 (событие) + 3 (статистика)

План:
1. CTE ranked: PARTITION BY date ORDER BY high DESC, ROW_NUMBER
2. CTE events: WHERE rn = 1
3. Final: GROUP BY time, COUNT, ORDER BY frequency DESC LIMIT 20

Проверка:
- ~1250 дней в периоде
- ~20 строк в результате
- Сумма frequency ≈ 1250 ✓

Пишу SQL...
```

---

## Изменения в коде

### 1. State (agent/state.py)

```python
class Intent(TypedDict, total=False):
    type: Literal["data", "concept", "chitchat", "out_of_scope"]
    symbol: str | None
    period_start: str | None
    period_end: str | None

    # DEPRECATED: оставить для совместимости
    granularity: str | None
    search_condition: str | None

    # NEW: подробное ТЗ
    detailed_spec: str | None

    # Clarification
    needs_clarification: bool
    clarification_question: str | None
    suggestions: list[str]
```

### 2. Understander

- Модель: `config.GEMINI_MODEL` (gemini-3-flash)
- Включить thinking: `ThinkingConfig(include_thoughts=True)`
- Промпт: добавить описание домена OHLCV и уровней агрегации
- Output: генерировать `detailed_spec`

### 3. SQL Agent

- Модель: `config.GEMINI_MODEL` (gemini-3-flash) ✓ (уже сделано)
- Thinking: включен ✓ (уже сделано)
- Промпт: читать `detailed_spec`, убрать примеры SQL
- Фокус на понимании ТЗ, а не pattern matching

### 4. Capabilities (agent/capabilities.py)

Расширить для масштабирования:

```python
def get_available_instruments() -> list[dict]:
    """Динамически получить список доступных инструментов."""
    return [
        {"symbol": "NQ", "name": "Nasdaq 100 E-mini", "type": "futures", "sessions": ["RTH", "ETH"]},
        {"symbol": "ES", "name": "S&P 500 E-mini", "type": "futures", "sessions": ["RTH", "ETH"]},
        {"symbol": "AAPL", "name": "Apple Inc", "type": "stock", "sessions": ["RTH"]},
        {"symbol": "BTC", "name": "Bitcoin", "type": "crypto", "sessions": ["24/7"]},
    ]
```

---

## Масштабирование

### Текущее состояние
- 1 инструмент (NQ)
- Минутные данные

### Будущее
- Сотни инструментов (акции, фьючерсы, крипта)
- Всё на минутных данных
- Разные торговые сессии

### Как система масштабируется

1. **Домен OHLCV универсален** — свечи одинаковы для всех инструментов
2. **Understander знает домен** — не зависит от конкретного инструмента
3. **Инструменты динамические** — подгружаются из capabilities
4. **SQL Agent пишет универсальный SQL** — только symbol меняется

---

## План внедрения

### Фаза 1: Understander v2
1. Переключить на умную модель с thinking
2. Добавить описание домена OHLCV в промпт
3. Добавить описание уровней агрегации
4. Генерировать `detailed_spec` вместо `search_condition`
5. Улучшить human-in-the-loop

### Фаза 2: SQL Agent v2
1. ✅ Переключить на умную модель
2. ✅ Включить thinking
3. Изменить промпт — читать `detailed_spec`
4. Убрать жёсткие примеры SQL
5. Добавить паттерны для уровней агрегации

### Фаза 3: Тестирование
1. Протестировать на сложных вопросах:
   - "время high/low дня"
   - "корреляция утреннего объёма и дневного движения"
   - "распределение гэпов по дням недели"
2. Сравнить качество ответов v1 vs v2
3. Измерить стоимость (thinking дороже)

---

## Метрики успеха

1. **Запрос "время high/low дня"** возвращает распределение, а не 2 строки
2. **SQL использует правильные паттерны** — PARTITION BY для событий
3. **Количество строк соответствует логике** — ~20 для TOP-20, ~1250 для дней
4. **Human-in-the-loop работает** — уточняет неясные вопросы
5. **Масштабируется** — работает для любого инструмента
