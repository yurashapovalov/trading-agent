# Refactoring Plan

## Принципы

1. **Single Source of Truth** — каждый факт живёт в одном месте
2. **Явные контракты** — типизация между слоями
3. **Fail loud** — ошибки видны сразу
4. **Derive, don't duplicate** — производные данные вычисляются

---

## Активная работа

### 17. Intent в Parser — routing ДО Composer

**Статус:** ✅ DONE (2026-01-19)

**Сделано:**
- Добавлен `intent: "data" | "chitchat" | "concept"` в ParsedQuery
- Добавлена функция `after_parser()` в graph.py для routing по intent
- chitchat/concept → сразу в Responder (минуя Composer)
- Убраны `chitchat_keywords` и хардкоды из Composer
- Добавлены chitchat subtypes в Responder: greeting, thanks, goodbye, feedback, insult
- Исправлен conversation_test: передаёт chat_history как graph.py
- Добавлена валидация для chitchat/concept в тестах

---

### 19. Gemini Context Caching — оптимизация стоимости

**Статус:** PLANNED

**Проблема:** System prompt (правила, схема, примеры) повторяется в каждом запросе. Это ~3000 токенов на каждый вызов Parser/Responder.

**Текущая ситуация:**
```python
# config.py
CHAT_HISTORY_LIMIT = 10  # Только 10 сообщений в контекст LLM

# Gemini автоматически кэширует, но мы не создаём кэш явно
cached_tokens = response.usage_metadata.cached_content_token_count  # Tracking only
```

**Решение — Explicit Context Caching:**

```python
from google import genai
from google.genai import types

# 1. Создать кэш при старте приложения
cache = client.caches.create(
    model="gemini-2.5-flash-lite",
    contents=[system_prompt],  # Parser system prompt + examples
    config=types.CreateCachedContentConfig(
        display_name="parser_system_prompt",
        ttl="3600s",  # 1 hour
    ),
)

# 2. Использовать кэш в запросах
response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents=user_prompt,
    config=types.GenerateContentConfig(
        cached_content=cache.name,  # Использовать кэш
    ),
)
```

**Выгода:**
- Input tokens с кэша стоят в 4x дешевле
- Parser system prompt ~3000 токенов × 4x = экономия ~75% на input

**Что нужно:**
1. Создать кэш для Parser system prompt при старте
2. Создать кэш для Responder system prompt при старте
3. Хранить cache.name в памяти/config
4. Обновлять кэш при изменении промптов (TTL или manual)

**Связанное:**
- Увеличить `CHAT_HISTORY_LIMIT` с 10 до 20 (Gemini справится, история важна для follow-up)

---

### 18. Убрать хардкоды из Composer — Parser возвращает больше структуры

**Статус:** FUTURE (после #17)

**Проблема:** Composer содержит много хардкодов для интерпретации `what`:

```python
# _determine_grouping() — fallback когда modifiers.group_by не указан
if "statistic" in what_lower: return TOTAL
if "time" in what_lower: return HOUR

# _determine_metrics() — fallback когда метрики не указаны
if "statistic" in what_lower: return [AVG, STDDEV, COUNT]
if "correlation" in what_lower: return [AVG_GAP, AVG_RANGE]

# _determine_special_op() — fallback когда modifiers не указаны
if "volati" in what_lower: order_by = "volatility"
if "when" in what_lower: return EVENT_TIME
```

**Анализ хардкодов:**

| Функция | Хардкод | Зачем | Решение |
|---------|---------|-------|---------|
| `_determine_grouping()` | "statistic" → TOTAL | Fallback когда group_by null | Parser явно возвращает grouping |
| `_determine_grouping()` | "time", "when" → HOUR | Угадывание | Parser понимает контекст |
| `_determine_metrics()` | "statistic" → [AVG, STDDEV] | Fallback | Parser возвращает metric_type |
| `_determine_metrics()` | "correlation" → [GAP, RANGE] | Специфика | Parser возвращает metric_type |
| `_determine_special_op()` | "volati" → order_by: volatility | Угадывание order_by | Parser возвращает order_by |
| `_determine_special_op()` | "when" → EVENT_TIME | Угадывание op | Parser возвращает special_op hint |
| `_check_not_supported()` | "next day", "streak" | Business rules | Оставить в Composer |
| `_needs_prev_day()` | "gap" in what | Определение source | Parser возвращает needs_gap: true |

**Предлагаемые изменения в Parser output:**

```python
{
    "intent": "data",
    "what": "volatility statistics",

    # NEW — hints для Composer
    "hints": {
        "grouping": "hour" | "total" | null,      # Явная группировка
        "metric_type": "statistics" | "ohlc" | "count" | null,
        "order_by": "volatility" | "range" | "volume" | null,
        "needs_gap": true | false,                 # Для gap анализа
        "special_op": "event_time" | "top_n" | "compare" | null,
    },

    "period": {...},
    "filters": {...},
    "modifiers": {...},
    "unclear": [...],
}
```

**Или расширить modifiers:**

```python
{
    "modifiers": {
        "group_by": "hour",
        "top_n": 10,
        "compare": ["RTH", "ETH"],
        "find": "max",
        # NEW
        "order_by": "volatility",    # Для TOP_N
        "metric_type": "statistics", # AVG, STDDEV, COUNT
    }
}
```

**Что останется в Composer:**
- `_check_not_supported()` — business rules (chain queries, streaks)
- `_build_filters()` — структурирование фильтров
- `_determine_source()` — выбор DAILY/MINUTES (зависит от grouping, session, dates)
- Валидация QuerySpec

**Что уйдёт из Composer:**
- Угадывание grouping по словам в what
- Угадывание metrics по словам в what
- Угадывание order_by по словам в what
- Угадывание special_op по словам в what

**Порядок выполнения:**
1. **#17** — Intent в Parser (chitchat, concept, data)
2. **#18** — Расширить modifiers (order_by, metric_type)
3. Постепенно убирать fallbacks из Composer

**Риски:**
- Сложнее промпт Parser
- Больше полей = больше шансов ошибки LLM
- Нужно много тестов

**Преимущества:**
- Composer становится чистой бизнес-логикой без угадывания
- Легче дебажить (видно что Parser извлёк)
- Меньше magic strings

---

### 16. Разделить Barb node на Parser + Composer nodes

**Статус:** ✅ DONE (2026-01-19)

**Проблема:** В REFACTORING_PLAN отмечено `[x] Разделить Barb на Parser (node) и Composer (node)`, но фактически в коде это НЕ сделано:
- `barb.py` содержит класс `Barb` который внутри вызывает и Parser (LLM) и Composer (code)
- `graph.py` имеет один node `barb` который вызывает `barb.ask()`
- SSE events показывают только `barb` как agent name
- В Supabase traces логируется только `barb`, нельзя отдельно дебажить Parser vs Composer

**Текущий flow в коде:**
```
START → barb (Parser+Composer внутри) → responder → ...
```

**Целевой flow:**
```
START → parser → composer → responder → ...
```

**Задачи:**
- [ ] Создать `agent/agents/parser.py` — отдельный агент с LLM вызовом
- [ ] Создать `agent/agents/composer.py` — отдельный агент (code only, no LLM)
- [ ] В `graph.py` добавить два отдельных node: `parser` и `composer`
- [ ] SSE events будут показывать `step_start/step_end` для каждого отдельно
- [ ] Supabase traces будет логировать Parser и Composer отдельно
- [ ] Удалить `barb.py` после миграции (или deprecate)

**Важно:**
- НЕ трогать Responder
- Parser → Composer — sequential flow (Composer зависит от Parser output)
- Сохранить все существующие типы: query, clarification, concept, greeting, not_supported
- Сохранить holiday_info, event_info проверки (можно перенести в Composer или отдельный node)

**State между nodes:**
```python
# После parser node:
state["parsed_query"] = ParsedQuery(...)  # Typed entities from LLM
state["parser_usage"] = {...}  # Tokens, cost

# После composer node:
state["intent"] = {...}  # type, query_spec, etc.
state["query_spec_obj"] = QuerySpec(...)  # For query_builder
```

**SSE events после изменения:**
```javascript
{type: "step_start", agent: "parser", message: "Understanding question..."}
{type: "step_end", agent: "parser", result: {what: "stats", period: {...}}}

{type: "step_start", agent: "composer", message: "Building query..."}
{type: "step_end", agent: "composer", result: {type: "query", source: "DAILY"}}

{type: "step_start", agent: "responder", message: "Preparing response..."}
...
```

---

### 15. Streaming structured outputs

**Статус:** ✅ DONE (2026-01-19)

**Сделано:**
- Добавлен `ResponderOutput` Pydantic model в responder.py
- Parser использует `response_schema=ParsedQuery`
- Responder использует `response_schema=ResponderOutput` (batch и streaming)
- Gemini теперь гарантированно возвращает валидный JSON по схеме

---

### 14. Responder-centric flow

**Статус:** ✅ Backend готов (2026-01-18), ожидаем frontend

**Проблема:** Сейчас Parser отвечает пользователю шаблонно ("Got it!"), потом тишина, потом Analyst. Две точки коммуникации, разрыв в UX, роботизированное общение.

**Текущий flow:**
```
User: "Волатильность по часам"
         ↓
Parser: "Понял! Покажу..." (шаблонно, быстро)
         ↓
      [тишина 10-15 сек]
         ↓
Analyst: [полный ответ с анализом]
```

**Новый flow:**
```
User: "Волатильность по часам"
         ↓
Parser: извлекает сущности (молча)
         ↓
Responder: [стримит сразу, с экспертизой]
           "Почасовая волатильность NQ обычно показывает
            чёткие паттерны — пики на открытии в 9:30
            и перед закрытием. Смотрю данные с 2008..."
         ↓
      [данные пришли]
         ↓
UI:      📊 4800 дней [открыть →]
         [Проанализировать]
         ↓
      [user click]
         ↓
Analyst: [глубокий анализ данных]
```

**Новая архитектура агентов:**

```
                 User Question
                      ↓
                   Parser ─────────► parsed entities
                      ↓
                  Composer ────────► type + QuerySpec (if query)
                      ↓
              ┌───────┴───────┐
              ↓               ↓
          Responder        Context
        (streaming)      (events, holidays)
              ↓               ↓
              └───────┬───────┘
                      ↓
           [if type == query]
                      ↓
                QueryBuilder
                      ↓
                DataFetcher ─────► UI: data card + button
                      ↓
               [user click]
                      ↓
                  Analyst ───────► deep analysis
```

**Роли агентов (Single Responsibility):**

| Агент | Задача | LLM | Input |
|-------|--------|-----|-------|
| Parser | Извлечь сущности из вопроса | Gemini Lite | question, instrument context |
| Composer | Бизнес-логика: определить тип (query/greeting/concept/clarification), source, special_op | Code (no LLM) | parsed entities |
| Responder | Общаться с пользователем, давать экспертный контекст | Gemini Lite | question, parsed entities, **composer result**, events, holidays |
| Analyst | Глубокий анализ данных | Gemini Pro | question, data, instrument |

**Composer определяет ТИП, Responder определяет КАК отвечать:**

| Composer result | Responder action |
|-----------------|------------------|
| `greeting` | Приветствует, предлагает помощь |
| `concept` | Объясняет концепт (gap, volatility, etc.) |
| `clarification` | Спрашивает уточнение + кнопки |
| `not_supported` | Объясняет почему запрос не поддерживается |
| `query` | Expert preview ("NQ обычно...") → ждём данные |

**Responder — ключевые принципы:**
1. **В домене** — знает инструмент, события, праздники (как Parser и Analyst)
2. **Экспертиза** — даёт контекст ДО данных ("обычно пики в 9:30", "это день OPEX")
3. **Живое общение** — не шаблоны, а осмысленные фразы
4. **Быстрый** — на Gemini Lite, стримит сразу
5. **Генерит title** — на основе QuerySpec, для карточки данных в UI

**Сценарии:**

1. **Простой запрос:**
   ```
   User: "Волатильность по часам"

   Responder: "Почасовая волатильность NQ обычно показывает
              чёткие паттерны — пики на открытии и перед
              закрытием. Смотрю данные с 2008..."

   [данные готовы]

   UI: 📊 4800 дней [открыть →]
       [Проанализировать]
   ```

2. **Запрос с событием:**
   ```
   User: "Что было 19 апреля 2024?"

   Responder: "19 апреля 2024 — пятница, день экспирации
              опционов (OPEX). Обычно повышенная волатильность.
              Достаю данные..."

   UI: 📊 1 день [открыть →]
       [Проанализировать]
   ```

3. **Запрос с праздником:**
   ```
   User: "Что было 4 июля 2024?"

   Responder: "4 июля 2024 — Independence Day, биржа закрыта.
              Данных за этот день нет."

   [без кнопки данных]
   ```

4. **Кларификация:**
   ```
   User: "Что было 16 мая?"

   Responder: "16 мая какого года? 2024, 2023, или показать все?"
              [2024] [2023] [Все года]

   User: [клик 2024]

   Responder: "16 мая 2024 — четверг, обычный торговый день.
              Смотрю данные..."
   ```

5. **Явный запрос анализа:**
   ```
   User: "Проанализируй волатильность за 2024"

   Responder: "2024 был насыщенным годом для NQ. Сейчас
              посмотрю данные и сделаю полный анализ..."

   [данные готовы → сразу вызывается Analyst]

   Analyst: [полный анализ без кнопки]
   ```

6. **Концепт (без данных):**
   ```
   User: "Что такое гэп?"

   Responder: "Гэп — это разрыв между ценой закрытия
              и открытия следующего дня..."

   [без кнопки данных, Analyst не нужен]
   ```

**Изменения в Parser:**
- Убрать генерацию `summary` для пользователя
- Только structured output: `what`, `period`, `filters`, `modifiers`, `unclear`
- Промпт становится проще и короче

**Требования к фронтенду:**
- [ ] Правая панель для данных (таблицы, графики)
- [ ] Кнопка "📊 N дней [открыть]" — открывает панель
- [ ] Кнопка "[Проанализировать]" — вызывает Analyst
- [ ] Кнопка анализа исчезает после нового сообщения
- [ ] Кнопки кларификации (интерактивные chips)
- [ ] **BUG:** Два ответа склеиваются (preview + summary) — нужно показывать только финальный
- [ ] **BUG:** Markdown таблицы не рендерятся — нужен markdown renderer

**Требования к бэкенду:**
- [x] Разделить Barb на Parser (node) и Composer (node) — см. **#16** ✅
- [x] Новый агент Responder между Barb и QueryBuilder
- [x] Responder получает: question, parsed entities, instrument context, events, holidays
- [x] Parser убрать summary из output
- [ ] Analyst вызывается только по trigger (кнопка или слово "проанализируй")
- [x] Новый SSE event type для interactive elements

**LangGraph реализация:**
```python
# Nodes
graph.add_node("parser", parse_question)      # LLM: extract entities
graph.add_node("composer", compose_query)     # Code: business logic, determines type
graph.add_node("responder", respond_to_user)  # LLM: expert preview, streaming
graph.add_node("query_builder", build_sql)    # Code: SQL generation
graph.add_node("data_fetcher", fetch_data)    # Code: execute SQL
graph.add_node("analyst", analyze_data)       # LLM: deep analysis

# Flow
START → parser → composer → responder → [routing by type]
                                ↓
                    ┌───────────┴───────────┐
                    ↓                       ↓
              [type: query]          [type: other]
                    ↓                       ↓
              query_builder               END
                    ↓
              data_fetcher → END
                    ↓
            [user trigger]
                    ↓
                analyst → END
```

**Routing после Responder (preview):**
- `greeting` → END (Responder уже ответил)
- `concept` → END (Responder объяснил концепт)
- `clarification` → END (ждём ответ пользователя)
- `not_supported` → END (Responder объяснил почему)
- `query` → query_builder → data_fetcher → **[решение]**

**Решение после DataFetcher:**

| Условие | Действие |
|---------|----------|
| row_count = 0 | Responder: "Нет данных" → END |
| row_count ≤ 5 | Responder сам даёт summary → END |
| row_count > 5, обычный запрос | UI: кнопка "Проанализировать" → END |
| row_count > 5, `wants_analysis=true` | Responder: "Готовлю анализ..." → Analyst → END |

**Когда Analyst нужен:**
- Много данных (статистика, паттерны, тренды)
- Сравнения (RTH vs ETH, месяцы)
- Явный запрос "проанализируй", "analyze"

**Когда Responder справляется сам:**
- 1-5 строк данных — озвучить факты (OHLC, range, change)
- Концепты, greeting, clarification, not_supported
- Простые вопросы "что было X числа"

**SSE events (новые):**
```javascript
// ✅ Responder генерит title для карточки
{type: "data_title", title: "Почасовая волатильность NQ"}

// ✅ Responder стримит expert preview
{type: "text_delta", content: "Обычно пики на открытии..."}

// ✅ DataFetcher закончил
{type: "data_ready", row_count: 4800, request_id: "xxx"}

// ✅ Предлагает анализ (для >5 rows)
{type: "offer_analysis", data: true}

// TODO: Кнопки кларификации (ждём frontend)
{type: "clarification", field: "year", options: ["2024", "2023", "Все года"]}
```

**Открытые вопросы:**
- [ ] Как передать trigger от UI к Analyst? (новый endpoint `/api/analyze`? продолжить thread?)
- [ ] Как определить что Analyst нужен сразу? (Parser добавляет `wants_analysis: true` если "проанализируй"?)

---

### 11. Multi-instrument support

**Статус:** FUTURE (когда докупим данные)

**Проблема:** Сейчас один инструмент (NQ). Когда будет много — нельзя добавить 1000 инструментов в промпт.

**Решение:**
- [ ] Двухэтапный парсинг: сначала символ, потом с контекстом
- [ ] Session-level symbol: определяется в начале сессии
- [ ] "Покажи ES" → symbol=ES для всей сессии
- [ ] Кларификация если символ неясен и их много

---

## Выполнено

<details>
<summary>Completed items (2026-01-18)</summary>

### instruments.py — единый источник правды
- SQL-хелперы в `source/common.py`
- `build_trading_day_timestamp_filter()` — единый источник
- SESSION CASE строится динамически из `get_session_times()`
- `data_start`, `data_end` в конфиге инструмента
- Все агенты получают диапазон данных из instruments.py

### Parser → Composer типизация
- `ParsedQuery`, `ParsedPeriod`, `ParsedFilters`, `ParsedModifiers` (Pydantic)
- `dict_to_parsed_query()` с validation и fallback
- Явные ошибки вместо `try/except: pass`

### ClarificationState
- Детерминированный merge между раундами
- `ParsedQuery.merge_with()` — не зависит от LLM
- `BarbResult.state` передаётся между раундами

### Trading day логика централизована
- `build_trading_day_timestamp_filter()` в `source/common.py`
- Удалено дублирование из minutes.py, find_extremum.py, event_time.py, compare.py

### Filters refactoring
- Разбит на PeriodFilter, CalendarFilter, TimeFilter, HolidaysConfig
- Backward compatibility properties

### Source selection
- `_determine_source()` с документированной Decision Table
- Time-based grouping (HOUR, MINUTE_*) использует MINUTES source

### Events integration
- `market/events.py` — calculable events (OPEX, NFP, Quad Witching, VIX Exp)
- `event_filter` в Parser → `specific_dates` в Composer
- Graceful error для non-calculable events

### Deploy improvements
- Health check после docker compose up
- fuser для orphan processes

</details>

---

## История

- 2026-01-18: Создан документ
- 2026-01-18: Parser typing, ClarificationState, Filters refactoring
- 2026-01-18: Trading day centralization, Events integration
- 2026-01-18: instruments.py как единый источник (data_start/data_end)
- 2026-01-18: **#14 Responder-centric flow** — новая архитектура с Responder агентом
- 2026-01-18: **#14 Backend готов** — Parser→Composer→Responder flow, data_title, offer_analysis, data_summary, 100% tests (36/36)
- 2026-01-19: **#15 Streaming structured outputs** — добавлена задача для response_json_schema
- 2026-01-19: **#16 Разделить Barb на Parser + Composer nodes** — задача для отдельного логирования (исправлен ложный checkbox)
- 2026-01-19: **#16 DONE** — Созданы `parser.py`, `composer_agent.py`, обновлен `graph.py` (START → parser → composer → responder), SSE events для отдельного логирования
- 2026-01-19: **#17 Intent в Parser** — добавлена задача для явного intent_type в Parser output
- 2026-01-19: **#18 Убрать хардкоды из Composer** — анализ всех хардкодов, план расширения Parser output
- 2026-01-19: **#17 DONE** — intent routing, chitchat subtypes, тесты с chat_history
- 2026-01-19: **#19 Context Caching** — добавлена задача, увеличен CHAT_HISTORY_LIMIT до 20
- 2026-01-19: **#15 DONE** — response_schema для Parser и Responder (гарантированный валидный JSON)
