# Query Builder Refactoring Plan

## Цель

Упростить архитектуру, убрать дублирование, сделать систему масштабируемой.

---

## Принципы

1. **Single Source of Truth** — каждый факт живёт в одном месте
2. **Явные контракты** — типизация между слоями, не надежда на LLM
3. **Fail loud** — ошибки видны сразу, не молчаливые падения
4. **Derive, don't duplicate** — производные данные вычисляются, не копируются

---

## Текущие проблемы

### 1. instruments.py недоиспользуется ✅ DONE

**Статус:** instruments.py — единый источник правды.

**Решение (2026-01-18):**
- [x] SQL-хелперы добавлены в `source/common.py`
- [x] `build_trading_day_timestamp_filter()` — единый источник для trading day SQL
- [x] `minutes.py`, `find_extremum.py`, `event_time.py` используют хелперы
- [x] `grouping/builders.py` — SESSION CASE строится динамически из `get_session_times()`

### 2. Parser → Composer: неявные контракты ✅ DONE

**Проблема:** Parser возвращает dict, Composer надеется на формат.

**Решение (2026-01-18):**
- [x] Типизировать Parser output → `ParsedQuery`, `ParsedPeriod`, `ParsedFilters`, `ParsedModifiers` (Pydantic)
- [x] `dict_to_parsed_query()` конвертирует LLM dict → typed model
- [x] Composer принимает `ParsedQuery`, не `dict`
- [x] Pydantic validation с fallback на ошибки (см. #13)
- [x] Явные ошибки вместо `try/except: pass` (см. #13)

### 3. History handling — LLM лотерея ✅ DONE

**Проблема:** Multi-turn clarification полагается на LLM для merge контекста.

**Решение (2026-01-18):**
- [x] `ClarificationState` в types.py — хранит resolved данные между раундами
- [x] `ParsedQuery.merge_with()` — детерминированный merge, не LLM
- [x] `BarbResult.state` — передаётся между раундами
- [x] chat_history + state работают вместе: history для LLM контекста, state как fallback

**Архитектура:**
```python
r1 = barb.ask("what was jan 10")  # state.resolved = {period.raw="jan 10"}
r2 = barb.ask("2024", state=r1.state)  # merge → dates=['2024-01-10']
r3 = barb.ask("RTH", state=r2.state)  # merge → dates + session
```

### 4. Дублирование trading day логики ✅ DONE

**Проблема:** 5+ мест строят одинаковый SQL для trading day boundaries.

**Решение (2026-01-18):**
- [x] `build_trading_day_timestamp_filter()` в `source/common.py` — единый хелпер
- [x] `get_trading_date_expression()` в `source/common.py` — SQL CASE для trading date
- [x] `minutes.py` использует централизованный хелпер
- [x] `find_extremum.py` использует централизованный хелпер (удалён `_get_trading_day_filter`)
- [x] `event_time.py` использует централизованный хелпер (удалён `_get_trading_day_filter`)
- [x] `compare.py` использует централизованный хелпер (см. #9)

### 5. TOP_N — непоследовательный паттерн ✅ INTENTIONAL

**Ситуация:** TOP_N использует `transform_spec()` вместо `build_query()`.

**Почему это правильно:**
- TOP_N не нужен свой SQL шаблон — просто добавляет ORDER BY + LIMIT
- `transform_spec()` модифицирует QuerySpec и переиспользует стандартный builder
- Избегает дублирования логики

**Документация в коде:**
```python
# top_n.py
"""
Note:
    TOP_N реализован через модификацию QuerySpec,
    а не как отдельный SQL шаблон. Это позволяет
    переиспользовать стандартный query builder.
"""
```

**Решение:** Оставить как есть — это осознанный дизайн, не баг.

### 6. Filters — монолитный dataclass ✅ DONE

**Ситуация:** 12 полей в одном классе → разбито на подклассы для масштабируемости.

**Решение (2026-01-18):**
- [x] `PeriodFilter` — start, end, specific_dates
- [x] `CalendarFilter` — years, months, weekdays
- [x] `TimeFilter` — session, start, end
- [x] `HolidaysConfig` — market_holidays, early_close_days
- [x] `Filters` использует подклассы + backward compatibility properties
- [x] `composer.py` обновлён для создания structured filters
- [x] Все 30 E2E тестов пройдены

**Архитектура:**
```python
class Filters(BaseModel):
    period: PeriodFilter
    calendar: CalendarFilter | None = None
    time: TimeFilter | None = None
    conditions: list[Condition] = Field(default_factory=list)
    holidays: HolidaysConfig = Field(default_factory=HolidaysConfig)

    # Backward compatibility properties
    @property
    def period_start(self) -> str: return self.period.start
    # ... etc
```

### 7. Source selection — implicit decision tree ✅ DONE

**Проблема:** Порядок условий в Composer критичен, но не документирован.

**Решение (2026-01-18):**
- [x] Вынесено в отдельную функцию `_determine_source()`
- [x] Документирована Decision Table в docstring
- [x] Комментарии объясняют "почему" для каждого правила

```
Decision Table:
┌─────────────────┬─────────┬────────────────┬───────────────┬─────────────────────┐
│ special_op      │ session │ specific_dates │ needs_prev    │ Source              │
├─────────────────┼─────────┼────────────────┼───────────────┼─────────────────────┤
│ EVENT_TIME      │ any     │ any            │ any           │ MINUTES             │
│ any             │ yes     │ yes            │ any           │ DAILY               │
│ TOP_N           │ yes     │ no             │ any           │ DAILY               │
│ any             │ yes     │ no             │ any           │ MINUTES             │
│ any             │ no      │ any            │ yes           │ DAILY_WITH_PREV     │
│ any             │ no      │ any            │ no            │ DAILY               │
└─────────────────┴─────────┴────────────────┴───────────────┴─────────────────────┘
```

### 8. "Calendar day" vs "Trading day" ✅ DONE

**Проблема:** Система не различала trading day vs calendar day.

**Решение (2026-01-18):**
- [x] Фикс в composer.py: period_end всегда +1 день (exclusive)
- [x] specific_dates корректно работает с MINUTES source
- [x] `build_trading_day_timestamp_filter()` обрабатывает оба случая:
  - `session=None` → trading day boundaries (18:00-17:00)
  - `session` указан → calendar day + session time filter
- [~] Явный enum DayType — не нужен, логика работает через session/time_start

### 9. compare.py дублирует trading day логику ✅ DONE

**Проблема:** `compare.py` дублировал trading day filter logic.

**Решение (2026-01-18):**
- [x] `_get_base_filter()` теперь использует `build_trading_day_timestamp_filter()`
- [x] Удалено ~15 строк дублирующего кода
- [~] daily_raw CTE оставлен как есть (упрощённая версия, не требует `build_daily_aggregation_sql()`)

### 10. Symbol hardcoded как "NQ" ⏳ DEFERRED

**Ситуация:** Default symbol "NQ" в 10+ местах.

**Почему это ок сейчас:**
- Один инструмент (NQ) — дефолты удобны
- Не вызывает багов

**Решение:**
- Оставить как есть до #11 (Multi-instrument)
- При добавлении инструментов → session-level symbol config

### 11. Multi-instrument support 🔮 FUTURE

**Проблема:** Сейчас инструмент один (NQ), но когда будет много:
- Парсер получает контекст одного инструмента в промпте
- Нельзя добавить 1000 инструментов в промпт

**Решение (когда докупим данные):**
- [ ] Двухэтапный парсинг: сначала извлечь символ, потом парсить с контекстом
- [ ] Session-level symbol state: определяется в начале, сохраняется до явной смены
- [ ] "Покажи ES" → symbol=ES для всей сессии
- [ ] "А что с NQ?" → переключение на NQ

```python
# Будущая архитектура
class SessionState:
    symbol: str | None  # Определяется из первого вопроса или явно

# Parser stage 1: extract symbol (if mentioned)
# Parser stage 2: parse with instrument context
```

---

## Архитектурные решения

### SQL helpers — централизация (source/common.py)

```python
# Текущий API instruments.py (сырые данные)
get_trading_day_boundaries(symbol)  # → ("18:00", "17:00")
get_session_times(symbol, session)  # → ("09:30", "17:00")

# SQL helpers (source/common.py) — DONE 2026-01-18
build_trading_day_timestamp_filter(symbol, start, end, session, time_start)  # → SQL WHERE clause
get_trading_date_expression(symbol)  # → SQL CASE expression для trading date

# TODO: возможные расширения
get_session_sql_filter(symbol, session)          # → SQL time filter
get_session_case_expression(symbol)              # → SQL CASE для grouping
```

### Parser output — типизация

```python
# TO DISCUSS: Pydantic vs dataclass vs TypedDict

class ParsedPeriod(BaseModel):
    raw: str | None
    start: date | None      # Всегда date, не str
    end: date | None        # Всегда inclusive
    dates: list[date] | None

class ParsedQuery(BaseModel):
    what: str
    period: ParsedPeriod | None
    filters: ParsedFilters | None
    modifiers: ParsedModifiers | None
    unclear: list[str]
    summary: str
```

### Clarification state — структурированный

```python
# TO DISCUSS: Как хранить состояние между раундами

@dataclass
class ClarificationState:
    original_question: str
    resolved_period: ParsedPeriod | None
    resolved_session: str | None
    pending_field: str | None  # "year", "session", etc.
```

---

## Порядок работ

1. **Phase 1: instruments.py** — централизация SQL generation
2. **Phase 2: Parser typing** — явные контракты
3. **Phase 3: Clarification flow** — надёжный multi-turn
4. **Phase 4: Cleanup** — удаление дублирования

---

## Открытые вопросы

- [x] ~~Нужен ли отдельный модуль `trading_calendar.py`?~~ → Нет, holidays.py достаточно
- [x] ~~Pydantic vs dataclass для Parser output?~~ → Pydantic (уже используем в FastAPI)
- [x] ~~Как тестировать multi-turn flows?~~ → barb_test.py + ClarificationState

---

## Backlog

### 12. Events интеграция (как holidays) ✅ DONE (calculable), ⏳ FUTURE (historical)

**Проблема:** В `instruments.py` есть `"events": ["macro", "options"]`, но они никак не используются. События должны работать как праздники — с возможностью query by event.

**Сделано (2026-01-18):**
- [x] `market/events.py` — Single Source of Truth для событий
- [x] `get_event_dates(event_id, start, end)` — вычисляет даты для calculable events
- [x] Calculable events: OPEX (3rd Fri), NFP (1st Fri), Quad Witching, VIX Exp
- [x] `get_events_for_date()` — возвращает события для конкретной даты
- [x] `check_dates_for_events()` — проверяет даты для Analyst context
- [x] `event_filter` в ParsedFilters — Parser извлекает intent
- [x] Parser prompt — примеры событий (opex, nfp, fomc, cpi и т.д.)
- [x] `_resolve_event_filter()` в composer.py — конвертирует event_filter → specific_dates
- [x] Graceful error для non-calculable: "Календарь FOMC пока не загружен"
- [x] `event_info` в BarbResult → Graph → Analyst
- [x] `<event_context>` в промптах Analyst
- [x] E2E тесты для events (4 вопроса: OPEX, NFP, FOMC, Russian)
- [x] `parser_output` сохраняется в логах тестов

**Архитектура (Single Source of Truth):**

```
┌─────────────────────────────────────────────────────────────────┐
│              market/events.py — источник правды                  │
├─────────────────────────────────────────────────────────────────┤
│  Calculable (алгоритм)        │  Historical (нет данных)        │
│  ✅ OPEX (3rd Friday)         │  ⏳ FOMC dates + outcomes        │
│  ✅ NFP (1st Friday)          │  ⏳ CPI dates + values           │
│  ✅ VIX Exp (Wed before OPEX) │  ⏳ GDP, PCE, etc.               │
│  ✅ Quad Witching             │                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Parser (LLM)                                │
├─────────────────────────────────────────────────────────────────┤
│  "volatility on expiration days" → event_filter: "opex"         │
│  "how does NQ behave on NFP?"    → event_filter: "nfp"          │
│  "FOMC days statistics"          → event_filter: "fomc"         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Composer (code)                              │
├─────────────────────────────────────────────────────────────────┤
│  _resolve_event_filter(event_filter, period)                     │
│    → calculable: specific_dates = get_event_dates(...)          │
│    → historical: NotSupportedResult("Календарь X не загружен")  │
└─────────────────────────────────────────────────────────────────┘
```

**Тесты (barb_test.py):**
- `"what's the volatility on expiration days?"` → data ✓
- `"how does NQ behave on NFP?"` → data ✓
- `"volatility on FOMC days"` → not_supported ✓
- `"статистика по дням экспирации"` → data ✓

**Future (historical events):**
- [ ] Файлы `data/events/fomc.json`, `cpi.json` с историческими датами
- [ ] Формат: `{"date": "2024-03-20", "outcome": "hold", "value": "5.25-5.50"}`
- [ ] Загрузка в `get_event_dates()` для non-calculable events

### 13. Composer validation ✅ DONE

**Из #2 — мелкие TODO:**
- [x] Pydantic validation на входе в Composer (2026-01-18)
  - `dict_to_parsed_query()` обёрнут в try/except ValidationError
  - Fallback: возвращает ParsedQuery с unclear=["question"]
- [x] Явные ошибки вместо `try/except: pass` (2026-01-18)
  - composer.py: логирует warning при ошибке парсинга даты
  - analyst.py: explicit exception types вместо bare `except:`

---

## История изменений

- 2026-01-18: Создан документ после аудита архитектуры
- 2026-01-18: **Parser → Composer типизация** — ParsedQuery (Pydantic), dict_to_parsed_query()
- 2026-01-18: **ClarificationState** — детерминированный merge между раундами
- 2026-01-18: **Calendar day fix** — period_end +1 день для MINUTES source
- 2026-01-18: **Parser prompt** — примеры для subjective terms и multi-round clarification
- 2026-01-18: **Trading day centralization** — `build_trading_day_timestamp_filter()` в common.py, удалено дублирование из minutes.py, find_extremum.py, event_time.py
- 2026-01-18: **Cleanup domain/** — удалён `agent/domain/` (мёртвый код), `get_trading_day_options()` перенесён в `market/instruments.py`
- 2026-01-18: **compare.py** — `_get_base_filter()` теперь использует централизованный хелпер
- 2026-01-18: **grouping/builders.py** — SESSION CASE теперь динамический из `instruments.py`
- 2026-01-18: **Source selection** — `_determine_source()` с документированной Decision Table
- 2026-01-18: **Final review** — #5, #6, #8, #10 закрыты (intentional/ok/done/deferred)
- 2026-01-18: **Filters refactoring** — разбит на PeriodFilter, CalendarFilter, TimeFilter, HolidaysConfig + backward compat
- 2026-01-18: **Error handling** — убран bare `except:`, добавлен logging для ошибок парсинга
- 2026-01-18: **Backlog** — добавлены #12 (Events), #13 (Composer validation)
- 2026-01-18: **Pydantic validation** — `dict_to_parsed_query()` теперь ловит ValidationError с fallback
- 2026-01-18: **Calendar day clarification fix** — добавлен `time_start/time_end` в ParsedFilters, исправлен `merge_with()`, приоритет time над session в composer
- 2026-01-18: **Events integration (Phase 1)** — `get_events_for_date()`, `check_dates_for_events()`, `event_info` в flow Barb → Graph → Analyst, `<event_context>` в промптах
- 2026-01-18: **Events integration (Phase 2)** — E2E тесты для events (4 вопроса), `parser_output` сохраняется в логах, #12 закрыт для calculable events
