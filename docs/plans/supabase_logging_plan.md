# Supabase Logging Plan

Полная документация по логированию в Supabase для trading assistant.

**Версия:** 2026-01-26 v18
**Статус:** ✅ Complete. All phases implemented.

---

## 1. Схема базы данных

### 1.1 chat_sessions — сессии чатов

Контейнер для разговора. Один chat = много сообщений.

```sql
create table public.chat_sessions (
  id uuid not null default gen_random_uuid(),
  user_id uuid null,
  title text null,
  status text null default 'active'::text,
  stats jsonb null default '{"cost_usd": 0, "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cached_tokens": 0, "message_count": 0}'::jsonb,
  created_at timestamp with time zone null default now(),
  updated_at timestamp with time zone null default now(),
  memory jsonb null default '{"key_facts": [], "summaries": []}'::jsonb,

  constraint chat_sessions_pkey primary key (id),
  constraint chat_sessions_user_id_fkey foreign key (user_id) references auth.users (id) on delete cascade
);
```

**Поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK, генерируется автоматически |
| user_id | uuid | FK → auth.users |
| title | text | Генерируется Understander при первом сообщении (2-3 слова) |
| status | text | `'active'` или `'deleted'` (soft delete) |
| stats | jsonb | Агрегированная статистика всей сессии (через RPC) |
| memory | jsonb | Conversation memory для LLM контекста |
| created_at | timestamptz | Время создания сессии |
| updated_at | timestamptz | Обновляется при каждом сообщении и действии |

**stats структура:**
```json
{
  "message_count": 15,
  "input_tokens": 12500,
  "output_tokens": 3200,
  "thinking_tokens": 1800,
  "cached_tokens": 8500,
  "cost_usd": 0.0045
}
```

**Примечание:** `message_count` учитывает все chat_logs включая clarifier (каждый вопрос/ответ = +1).
Агрегация через RPC `increment_chat_stats` для атомарности.

**memory структура:**
```json
{
  "summaries": [
    {
      "content": "Обсуждали волатильность NQ за 2024, пользователь интересовался топ днями по range",
      "up_to_id": 123
    }
  ],
  "key_facts": [
    "Пользователь торгует NQ futures",
    "Интересует только RTH сессия",
    "Предпочитает ответы на русском"
  ]
}
```

**memory детали:**
- `summaries` — LLM-сжатие старых сообщений (когда recent > limit)
  - `up_to_id` — chat_logs.id до которого сжато (для инкрементальной загрузки)
- `key_facts` — важные факты о пользователе/предпочтениях
  - Извлекаются LLM или добавляются явно
  - Используются Clarifier чтобы не спрашивать известное
- Модуль: `agent/memory/conversation.py` (ConversationMemory)
- **Статус:** написан, но не интегрирован в граф (Phase 3)

**Экономия токенов (tiered memory):**
```
┌────────────────────────────────────────────────┐
│ key_facts (5 max)      │ ~50 токенов           │
├────────────────────────────────────────────────┤
│ summaries (3 max)      │ ~150 токенов          │
│ LLM-сжатие, 1-2 предл. │ GEMINI_LITE_MODEL     │
├────────────────────────────────────────────────┤
│ recent (10 msg = 5 пар)│ ~500-1000 токенов     │
└────────────────────────────────────────────────┘
Итого: ~700-1200 токенов вместо полной истории
```

Config: `MEMORY_RECENT_LIMIT=10`, `MEMORY_SUMMARY_CHUNK_SIZE=6`, `MEMORY_MAX_SUMMARIES=3`

**Предупреждение о лимите контекста (реализовано):**
Когда память сжата (есть summaries), LLM сам добавляет предупреждение в ответ:
- Параметр `context_compacted: bool` в методе `present()` — передается в промпт
- Флаг `context_compacted` в TradingState — заполняется при загрузке памяти
- В промптах (SUMMARY_PROMPT, SHORT_SUMMARY_PROMPT, SUMMARY_ANSWER_PROMPT):
  ```
  <memory_state>
  context_compacted: {context_compacted}
  </memory_state>
  ```
- LLM генерирует предупреждение на языке пользователя (аналогично флагам holidays/events)
- Flow: memory module → state.context_compacted → present() → prompt → LLM response
- TODO: интегрировать с memory module (проверять `len(memory.summaries) > 0`)

**Индексы:**
```sql
idx_chat_sessions_user_id (user_id)
idx_chat_sessions_updated_at (updated_at DESC)
idx_chat_sessions_status (status) WHERE status = 'active'  -- partial
```

---

### 1.2 chat_logs — запросы и ответы

Каждая строка = одно сообщение пользователя + ответ системы.

```sql
create table public.chat_logs (
  id bigserial not null,
  request_id uuid null default gen_random_uuid(),
  user_id uuid null,
  chat_id uuid null,

  question text not null,
  response text null,

  route text null,
  agents_used text[] null default '{}'::text[],

  duration_ms integer null,
  usage jsonb null,

  feedback jsonb null,
  created_at timestamp with time zone null default now(),

  constraint chat_logs_pkey primary key (id),
  constraint chat_logs_request_id_key unique (request_id),
  constraint chat_logs_chat_id_fkey foreign key (chat_id) references chat_sessions (id) on delete cascade,
  constraint chat_logs_user_id_fkey foreign key (user_id) references auth.users (id) on delete cascade
);
```

**Поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| id | bigserial | PK, автоинкремент |
| request_id | uuid | Unique ID запроса, FK для request_traces |
| user_id | uuid | FK → auth.users |
| chat_id | uuid | FK → chat_sessions |
| question | text | Сообщение пользователя |
| response | text | Ответ системы (null пока обработка) |
| route | text | Тип обработки: `'data'`, `'clarify'`, `'chitchat'`, `'concept'` |
| agents_used | text[] | Список агентов: `['intent', 'understander', ...]` |
| duration_ms | integer | Общее время от получения вопроса до отправки ответа |
| usage | jsonb | Токены и стоимость по агентам (см. ниже) |
| feedback | jsonb | Отзыв пользователя `{rating, comment}` |
| created_at | timestamptz | Время запроса |

**route значения:**
- `'data'` — запрос данных → intent → understander → parser → planner → executor → presenter
- `'clarify'` — нужна кларификация → intent → understander → clarifier
- `'chitchat'` — приветствие/благодарность → intent → responder
- `'concept'` — объяснение термина → intent → responder

**usage структура:**
```json
{
  "intent": {
    "input_tokens": 150,
    "output_tokens": 30,
    "thinking_tokens": 0,
    "cached_tokens": 100,
    "cost_usd": 0.0001
  },
  "understander": {
    "input_tokens": 800,
    "output_tokens": 100,
    "thinking_tokens": 50,
    "cached_tokens": 500,
    "cost_usd": 0.0008
  },
  "clarifier": null,
  "parser": {
    "input_tokens": 400,
    "output_tokens": 80,
    "thinking_tokens": 0,
    "cached_tokens": 300,
    "cost_usd": 0.0003
  },
  "presenter": {
    "input_tokens": 500,
    "output_tokens": 200,
    "thinking_tokens": 0,
    "cached_tokens": 300,
    "cost_usd": 0.0005
  },
  "responder": null,
  "total": {
    "input_tokens": 1850,
    "output_tokens": 410,
    "thinking_tokens": 50,
    "cached_tokens": 1200,
    "cost_usd": 0.0017
  }
}
```

**LLM агенты (6 штук):**
| Агент | Модель | Когда вызывается |
|-------|--------|------------------|
| intent | GEMINI_LITE | Всегда |
| understander | GEMINI_MODEL (flash) | Для data и clarify |
| clarifier | GEMINI_LITE | Когда understood=false |
| parser | GEMINI_LITE | Для data flow |
| presenter | GEMINI_LITE | Для data flow |
| responder | GEMINI_LITE | Для chitchat/concept |

---

### 1.3 request_traces — шаги выполнения

Детальный trace каждого агента. Главная таблица для дебага.

```sql
create table public.request_traces (
  id bigserial not null,
  request_id uuid null,
  user_id uuid null,
  step_number integer not null,
  agent_name text not null,
  input_data jsonb null,
  output_data jsonb null,
  usage jsonb null,
  duration_ms integer null,
  created_at timestamp with time zone null default now(),

  constraint request_traces_pkey primary key (id),
  constraint request_traces_request_id_fkey foreign key (request_id) references chat_logs (request_id) on delete cascade,
  constraint request_traces_user_id_fkey foreign key (user_id) references auth.users (id) on delete cascade
);
```

**Поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| id | bigserial | PK |
| request_id | uuid | FK → chat_logs.request_id (CASCADE) |
| user_id | uuid | FK → auth.users |
| step_number | integer | Порядок: 1, 2, 3... (sequential, без разрывов) |
| agent_name | text | Имя агента |
| input_data | jsonb | Что пришло в агент (agent-specific) |
| output_data | jsonb | Что вышло из агента (agent-specific) |
| usage | jsonb | Токены: `{input_tokens, output_tokens, thinking_tokens, cached_tokens}` |
| duration_ms | integer | Время выполнения этого шага |
| created_at | timestamptz | Время шага |

**agent_name значения:**
- `'intent'` — классификация намерения + язык + перевод
- `'understander'` — понимание вопроса, expansion, acknowledge
- `'clarifier'` — формулировка уточняющего вопроса
- `'parser'` — парсинг в структуру steps
- `'planner'` — создание execution plans (не LLM)
- `'executor'` — выполнение SQL запросов (не LLM)
- `'presenter'` — форматирование ответа
- `'responder'` — ответ на chitchat/concept

---

## 2. Структура input_data / output_data по агентам

### 2.1 intent

**Что делает:** Классифицирует намерение, определяет язык, переводит на английский.

**input_data:**
```json
{
  "question": "топ 5 самых волатильных дней 2024"
}
```
- `question` — оригинальное сообщение пользователя (как есть, без обработки)

**output_data:**
```json
{
  "intent": "data",
  "lang": "ru",
  "internal_query": "top 5 most volatile days of 2024"
}
```
- `intent` — классификация: `data` | `chitchat` | `concept`
- `lang` — язык пользователя (ISO 639-1: ru, en, de, es...)
- `internal_query` — перевод на английский для inter-agent communication

**usage:**
```json
{
  "input_tokens": 150,
  "output_tokens": 30,
  "thinking_tokens": 0,
  "cached_tokens": 100
}
```
- Единая структура для всех агентов (отдельная колонка в request_traces)

---

### 2.2 understander

**Что делает:** Понимает вопрос, расширяет для Parser, генерирует acknowledge, при первом сообщении — title.

**input_data:**
```json
{
  "internal_query": "top 5 most volatile days of 2024",
  "lang": "ru",
  "needs_title": true,
  "memory_context": "User prefers RTH session"
}
```
- `internal_query` — вопрос на английском (от intent)
- `lang` — язык для acknowledge/title
- `needs_title` — нужно ли генерировать название чата
- `memory_context` — контекст из памяти (опционально)

**output_data (understood=true):**
```json
{
  "intent": "data",
  "goal": "find extreme days",
  "understood": true,
  "topic_changed": false,
  "expanded_query": "list top 5 days by range descending in 2024 during RTH",
  "acknowledge": "Понял, смотрим топ-5 самых волатильных дней за 2024...",
  "suggested_title": "Волатильность 2024"
}
```
- `intent` — `data` | `chitchat` | `concept` (повторно классифицируется, но обычно совпадает с Intent)
- `goal` — зачем пользователю эти данные
- `understood` — понял ли запрос полностью
- `topic_changed` — `false` для обычного flow, `true` только при продолжении кларификации
- `expanded_query` — расширенный запрос для Parser (на английском)
- `acknowledge` — подтверждение на языке пользователя
- `suggested_title` — название чата (только при `needs_title=true`)

**output_data (understood=false):**
```json
{
  "intent": "data",
  "goal": null,
  "understood": false,
  "topic_changed": false,
  "expanded_query": null,
  "acknowledge": null,
  "need_clarification": {
    "required": [
      {
        "field": "goal",
        "reason": "The phrase 'makes sense' is subjective",
        "options": ["probability of profit", "average return", "risk"]
      }
    ],
    "optional": [],
    "context": "User asking about holding position in RTH"
  }
}
```
- `intent` — обычно "data" (иначе бы не дошли до understander)
- `topic_changed` — `false` для первого вопроса, `true` если user сменил тему в clarification flow
- `need_clarification.required` — обязательные уточнения (без них нельзя ответить)
- `need_clarification.optional` — опциональные (есть defaults)
- `need_clarification.context` — контекст для Clarifier (что уже поняли)

**usage:** (отдельная колонка)
```json
{
  "input_tokens": 800,
  "output_tokens": 100,
  "thinking_tokens": 50,
  "cached_tokens": 500
}
```

---

### 2.3 clarifier

**Что делает:** Формулирует уточняющий вопрос из структурированных tezises от Understander.

**Когда вызывается:** После Understander когда `understood=false` и есть `need_clarification`.

**input_data:**
```json
{
  "required": [
    {"field": "goal", "reason": "The phrase 'makes sense' is subjective", "options": ["probability of profit", "average return", "risk"]}
  ],
  "optional": [],
  "context": "User asking about holding position in RTH",
  "question": "есть смысл держать позицию в RTH?",
  "lang": "ru",
  "memory_context": null
}
```
- `required` — обязательные уточнения (из need_clarification)
- `optional` — опциональные уточнения
- `context` — что Understander уже понял
- `question` — оригинальный вопрос пользователя
- `lang` — язык для ответа
- `memory_context` — известные факты из памяти (null если нет)

**output_data:**
```json
{
  "response": "Понял, RTH сессия. Смысл держать — это про вероятность зелёного дня, среднюю доходность или про риск?"
}
```
- `response` — сформулированный вопрос на языке пользователя (сохраняется в `clarifier_question`)

**Graph state после clarifier:**
```json
{
  "response": "Понял, RTH сессия. Смысл держать — ...",
  "awaiting_clarification": true,
  "original_question": "есть смысл держать позицию в RTH?",
  "clarification_history": [{"role": "assistant", "content": "Понял, RTH сессия..."}],
  "clarifier_question": "Понял, RTH сессия..."
}
```

**usage:** (отдельная колонка)
```json
{
  "input_tokens": 200,
  "output_tokens": 40,
  "thinking_tokens": 0,
  "cached_tokens": 100
}
```

---

### 2.4 clarify_continue

**Что делает:** Обрабатывает ответ пользователя на уточняющий вопрос. Собирает контекст (original question + history) и повторно вызывает Understander.

**Когда вызывается:** После Intent когда `awaiting_clarification=true` — пользователь ответил на вопрос от Clarifier.

**input_data:**
```json
{
  "original_question": "есть смысл держать позицию в RTH?",
  "user_answer": "вероятность профита",
  "clarification_history": [
    {"role": "assistant", "content": "Понял, RTH сессия. Смысл держать — ..."}
  ],
  "lang": "ru"
}
```
- `original_question` — первый вопрос пользователя (до кларификации)
- `user_answer` — текущий ответ пользователя (из messages)
- `clarification_history` — история диалога (добавляется user_answer)
- `lang` — язык пользователя

**Внутренний flow:**
1. Добавляет user_answer в history
2. Строит context для Understander: original + history
3. Вызывает Understander с контекстом
4. Анализирует результат и решает routing

**output_data — 4 сценария:**

**1. Ответ по теме (understood=true, topic_changed=false):**
```json
{
  "goal": "evaluate position holding",
  "understood": true,
  "topic_changed": false,
  "expanded_query": "probability of green day when holding position during RTH session",
  "acknowledge": "Понял, считаем вероятность закрытия RTH в плюс...",
  "awaiting_clarification": false
}
```
→ Граф идёт в `parser`

**2. Смена темы на новый запрос (understood=true, topic_changed=true):**
```json
{
  "goal": "check pattern",
  "understood": true,
  "topic_changed": true,
  "expanded_query": "list top 5 days by range descending during RTH",
  "acknowledge": "Понял, смотрим топ-5 самых волатильных дней...",
  "awaiting_clarification": false,
  "clarification_history": null,
  "original_question": null
}
```
→ Граф идёт в `parser` с НОВЫМ запросом

**3. Отмена/chitchat (understood=false, topic_changed=true):**
```json
{
  "intent": "chitchat",
  "understood": false,
  "topic_changed": true,
  "awaiting_clarification": false,
  "clarification_history": null,
  "original_question": null
}
```
→ Граф идёт в `responder`, который генерирует ответ ("Окей, без проблем..." или redirect к домену)

**4. Всё ещё не понял (understood=false, topic_changed=false):**
```json
{
  "goal": "partially understood",
  "understood": false,
  "topic_changed": false,
  "need_clarification": {
    "required": [{"field": "timeframe", "reason": "...", "options": [...]}],
    "optional": [],
    "context": "..."
  },
  "clarification_history": [...]
}
```
→ Граф идёт в `clarify` для следующего вопроса

**Safety net:** Максимум 3 раунда кларификации (6 сообщений в history), потом сдаёмся:
```json
{
  "response": "Не получается понять. Попробуй сформулировать вопрос по-другому?",
  "awaiting_clarification": false,
  "topic_changed": true
}
```

**usage:** (отдельная колонка — это вызов Understander)
```json
{
  "input_tokens": 900,
  "output_tokens": 120,
  "thinking_tokens": 60,
  "cached_tokens": 600
}
```

**Примечание:** `clarify_continue` — это фактически повторный вызов Understander с расширенным контекстом. Логируется как отдельный шаг с `agent_name="clarify_continue"`.

---

### 2.5 parser

**Что делает:** Парсит expanded_query в структурированные steps. RAP выбирает релевантные примеры, LLM генерирует JSON, Pydantic валидирует и исправляет.

**input_data:**
```json
{
  "question": "list top 5 days by range descending in 2024 during RTH",
  "chunks_used": ["list", "count", "streak", "range_volume", "compare"]
}
```
- `question` — expanded_query от Understander (на английском)
- `chunks_used` — RAP chunks использованные для промпта

**output_data:**
```json
{
  "raw_output": {
    "steps": [
      {
        "id": "s1",
        "operation": "list",
        "atoms": [{"when": "2024", "what": "range", "filter": "session = RTH", "timeframe": "1D"}],
        "params": {"n": 5, "sort": "desc"}
      }
    ]
  },
  "parsed_query": [
    {
      "id": "s1",
      "operation": "list",
      "atoms": [{"when": "2024", "what": "range", "filter": "session = RTH", "timeframe": "1H"}],
      "params": {"n": 5, "sort": "desc"}
    }
  ],
  "thoughts": "User wants top volatile days during RTH session...",
  "validator_changes": [
    {
      "validator": "fix_timeframe_for_intraday_filter",
      "field": "timeframe",
      "path": "steps[0].atoms[0].timeframe",
      "old_value": "1D",
      "new_value": "1H",
      "reason": "filter 'session = RTH' requires intraday data"
    }
  ]
}
```
- `raw_output` — JSON от LLM до Pydantic валидации
- `parsed_query` — steps после валидации (идёт в planner)
- `thoughts` — LLM thinking (если есть)
- `validator_changes` — что исправили Pydantic validators

**Validators (7 с tracking):**

| Validator | Что меняет | Пример |
|-----------|------------|--------|
| `normalize_pattern_aliases` | filter | inside_day → inside_bar |
| `fix_invalid_metric` | what | formation → change |
| `fix_timeframe_for_intraday_filter` | timeframe | session + 1D → 1H |
| `fix_timeframe_for_pattern_filter` | timeframe | doji + 1m → 1H |
| `fix_timeframe_for_operation` | timeframe | formation → 1m |
| `fix_operation_filter_timeframe_conflict` | operation, timeframe | formation + doji → list |
| `set_default_params` | params.* | добавляет sort, n, etc. |

**Validators (3 только ошибки):**
- `validate_gap_vs_intraday` — gap + session = conflict
- `validate_atoms_count` — неверное количество atoms
- `validate_filter_combinations` — недопустимая комбинация

**usage:**
```json
{
  "input_tokens": 400,
  "output_tokens": 80,
  "thinking_tokens": 0,
  "cached_tokens": 300
}
```

---

### 2.6 planner (не LLM)

**Что делает:** Трансформирует parsed steps в execution plans. Резолвит даты и сессии. Не использует LLM.

**input_data:**
```json
{
  "parsed_query": [
    {
      "id": "s1",
      "operation": "list",
      "atoms": [{"when": "2024", "what": "range", "filter": "session = RTH", "timeframe": "1H"}],
      "params": {"n": 5, "sort": "desc"}
    }
  ]
}
```
- `parsed_query` — steps от parser (после валидации)

**output_data:**
```json
{
  "execution_plan": [
    {
      "step_id": "s1",
      "mode": "single",
      "operation": "list",
      "requests": [
        {
          "period": ["2024-01-01", "2024-12-31"],
          "timeframe": "1H",
          "filters": ["time >= 09:30, time < 17:00"],
          "label": "2024"
        }
      ],
      "params": {"n": 5, "sort": "desc"},
      "metrics": ["range"]
    }
  ],
  "plan_errors": null
}
```
- `execution_plan` — готовые планы для executor
- `plan_errors` — ошибки планирования (если есть)

**Трансформации:**

| Вход | Выход | Пример |
|------|-------|--------|
| `when: "2024"` | `period: ["2024-01-01", "2024-12-31"]` | date resolution |
| `when: "last week"` | `period: ["2024-01-19", "2024-01-25"]` | relative dates |
| `filter: "session = RTH"` | `filters: ["time >= 09:30, time < 17:00"]` | session → time |
| `filter: "session = ETH"` | `filters: ["time >= 18:00, time < 09:30"]` | overnight session |

**Режимы (mode):**

| Mode | Когда | Пример |
|------|-------|--------|
| `single` | 1 atom | "top 5 volatile days" |
| `multi_period` | разные `when` | "compare Q1 vs Q4" |
| `multi_filter` | разные `filter` | "monday vs friday" |
| `multi_metric` | разные `what` | "correlation change vs volume" |

**usage:** `null` (не LLM, нет токенов)

---

### 2.7 executor (не LLM)

**Что делает:** Выполняет execution plans против DuckDB. Загружает данные, обогащает (enrich), сканирует паттерны, применяет фильтры, выполняет операцию.

**input_data:**
```json
{
  "execution_plan": [
    {
      "step_id": "s1",
      "mode": "single",
      "operation": "list",
      "requests": [{"period": ["2024-01-01", "2024-12-31"], "timeframe": "1D", "filters": [...]}],
      "params": {"n": 5, "sort": "desc"},
      "metrics": ["change"]
    }
  ]
}
```
- `execution_plan` — планы от planner

**output_data:**
```json
{
  "rows": [
    {"date": "2024-03-15", "change": 3.21, "volume": 180000, "is_hammer": 0, "is_doji": 0},
    {"date": "2024-01-22", "change": 2.95, "volume": 165000, "is_hammer": 1, "is_doji": 0},
    {"date": "2024-07-08", "change": 2.87, "volume": 142000, "is_hammer": 0, "is_doji": 1}
  ],
  "summary": {"count": 5, "total": 252, "by": "change", "sort": "desc"}
}
```
- `rows` — полные данные с `is_*` флагами (для UI таблицы и Presenter)
- `summary` — агрегированный результат операции

**Примеры output по операциям:**

| Operation | rows | summary |
|-----------|------|---------|
| `list` | записи с датами и `is_*` флагами | `{count, total, by, sort}` |
| `count` | `[]` | `{count, avg, min, max}` |
| `distribution` | бины гистограммы | `{count, mean, std, p50}` |
| `probability` | `[]` | `{probability, matches, total}` |
| `streak` | `[{start, end, length}]` | `{count, max_length, avg_length}` |
| `correlation` | `[]` | `{correlation, strength, direction}` |
| `formation` | `[{hour, count, pct}]` | `{peak_hour, peak_pct}` |

**Паттерн:** rows может быть пустым (count, probability, correlation) — тогда ответ в summary. Presenter использует оба поля.

**usage:** `null` (не LLM)

**duration_ms:** время выполнения (DuckDB + enrich + pattern scan)

---

### 2.8 presenter

**Что делает:** Форматирует результаты запроса для пользователя. Генерирует acknowledge, title (для DataCard), summary. Делает несколько LLM вызовов.

**Ключевая особенность:** Для больших таблиц (>5 rows) presenter **НЕ видит сами данные** — только `summary` и `row_count`. Таблица показывается в UI отдельно из executor лога.

**input_data (rows ≤ 5):**
```json
{
  "rows": [
    {"date": "2024-03-15", "change": 3.21, "is_hammer": 0},
    {"date": "2024-01-22", "change": 2.95, "is_hammer": 1}
  ],
  "summary": {"count": 2, "total": 252, "by": "change"},
  "row_count": 2,
  "question": "top volatile days of 2024",
  "lang": "ru",
  "context_compacted": false
}
```

**input_data (rows > 5):**
```json
{
  "rows": [],
  "summary": {"count": 21, "total": 252, "by": "change", "sort": "desc"},
  "row_count": 21,
  "question": "volatile days of 2024",
  "lang": "ru",
  "context_compacted": false
}
```
- `rows` — данные (пустой если >5, таблица в UI из executor)
- `summary` — агрегат от executor (presenter использует для текста)
- `row_count` — **критично**: presenter пишет "Вот 21 день..." не видя данных
- `question` — `internal_query` (на английском)
- `lang` — язык пользователя
- `context_compacted` — если `true`, presenter предупреждает что старые сообщения сжаты

**Что presenter извлекает из rows (когда они есть):**
- `is_*` флаги → считает, строит контекст для LLM
- даты → проверяет holidays/events через config

**output_data (large_data, >5 rows):**
```json
{
  "acknowledge": "Понял, смотрим волатильные дни за 2024...",
  "title": "Волатильность NQ 2024",
  "summary": "Вот 21 день с высокой волатильностью. Среди них 3 hammer паттерна.",
  "type": "large_data",
  "row_count": 21
}
```

**output_data (inline, 2-5 rows):**
```json
{
  "acknowledge": "Понял, смотрим топ дни...",
  "title": null,
  "summary": "Вот 3 самых волатильных дня:\n\n| date | change | volume |\n|---|---|---|\n| 2024-03-15 | 3.21 | 180000 |\n| 2024-01-22 | 2.95 | 165000 |\n| 2024-07-08 | 2.87 | 142000 |",
  "type": "inline",
  "row_count": 3
}
```

**output_data (single, 1 row):**
```json
{
  "acknowledge": "Понял, смотрим этот день...",
  "title": null,
  "summary": "15 марта 2024 — самый волатильный день, change 3.21%. Был hammer паттерн.",
  "type": "single",
  "row_count": 1
}
```

- `acknowledge` — "Понял, получаю..." (показывается сразу)
- `title` — заголовок DataCard (`null` если ≤5 rows)
- `summary` — основной текст (для inline включает markdown таблицу)
- `type` — тип ответа
- `row_count` — количество строк

**type values и что видит presenter:**

| Type | Rows | Presenter видит | summary содержит |
|------|------|-----------------|------------------|
| `no_data` | 0 | ничего | "Ничего не нашлось" |
| `single` | 1 | 1 row с флагами | текст про эту запись |
| `inline` | 2-5 | rows с флагами | текст + markdown таблица |
| `large_data` | >5 | **только row_count + summary** | только текст, таблица в UI |

**LLM вызовы:**

| Метод | Когда | max_tokens |
|-------|-------|------------|
| `_generate_acknowledge` | всегда | 50 |
| `_generate_title` | rows > 5 | 30 |
| `_generate_summary` | rows > 5 с контекстом | 150 |
| `_generate_summary_short` | rows 1-5 с контекстом | 80 |
| `_generate_summary_answer` | есть summary от executor | 100 |
| `_generate_no_data` | rows = 0 | 60 |

**usage:**
```json
{
  "input_tokens": 500,
  "output_tokens": 200,
  "thinking_tokens": 0,
  "cached_tokens": 300
}
```

**context_compacted:** Когда старые сообщения в conversation memory были сжаты (summarized), presenter добавляет предупреждение типа "Я могу не помнить детали нашего предыдущего разговора..."

**TODO в коде:**
1. Передавать `context_compacted` из state в presenter
2. Сохранять `row_count` в state

---

### 2.9 responder (для non-data запросов)

**Что делает:** Обрабатывает все non-data запросы. Всегда возвращает разговор к домену (NQ, трейдинг).

**Поведение:**
- Приветствия → отвечает, предлагает помощь с NQ
- Благодарности/прощания → отвечает, приглашает вернуться
- Торговые термины → объясняет кратко (concept)
- Отмена ("забей") → подтверждает, остаётся доступен
- Off-topic (погода, анекдоты) → вежливо отклоняет, перенаправляет к домену

**Когда вызывается:**
1. После `intent`, если `intent != "data"` (chitchat или concept)
2. После `clarify_continue`, если `topic_changed=true` и `understood=false`

**input_data:**
```json
{
  "question": "hello!",
  "lang": "ru"
}
```
- `question` — `internal_query` из state (переведённый на английский от Intent)
- `lang` — язык пользователя для ответа

**output_data:**
```json
{
  "response": "Привет! Могу помочь с анализом NQ — волатильность, паттерны, сессии. Что интересует?"
}
```
- `response` — ответ на языке пользователя

**Примеры (проверено):**

| Оригинал | internal_query | intent | Ответ |
|----------|----------------|--------|-------|
| привет! | hello! | chitchat | Привет! Могу помочь с анализом NQ — волатильность, паттерны, сессии. Что интересует? |
| что такое OPEX? | what is OPEX? | concept | OPEX — это ежемесячная экспирация опционов (третья пятница месяца). Часто вызывает повышенную волатильность. |
| расскажи анекдот | tell a joke | chitchat | Я специализируюсь на анализе NQ. Могу помочь с волатильностью, паттернами, сессиями — что интересует? |
| какая погода? | what's the weather? | chitchat | Я специализируюсь на анализе NQ. Могу помочь с волатильностью, паттернами... |

**usage:** (отдельная колонка)
```json
{
  "input_tokens": 1362,
  "output_tokens": 58,
  "thinking_tokens": 1,
  "cached_tokens": 658
}
```

**Принцип:** Один агент для всех non-data запросов. Не различает chitchat/concept — просто отвечает по контексту вопроса, всегда возвращая к домену.

---

## 3. Связи между таблицами

```
┌─────────────────────────────────────────────────────────┐
│                    chat_sessions                         │
│  id (PK), user_id, title, status, stats, memory          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      │ 1:N (chat_id → id)
                      │ ON DELETE CASCADE
                      ▼
┌─────────────────────────────────────────────────────────┐
│                      chat_logs                           │
│  id, request_id (UNIQUE), chat_id (FK),                  │
│  question, response, route, agents_used, usage           │
└─────────────────────┬───────────────────────────────────┘
                      │
                      │ 1:N (request_id → request_id)
                      │ ON DELETE CASCADE
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   request_traces                         │
│  id, request_id (FK), step_number, agent_name,           │
│  input_data, output_data, duration_ms                    │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow

### 4.1 Data Flow (успешный запрос данных)

```
User: "топ 5 самых волатильных дней 2024"

1. API получает запрос
   └─→ check_needs_title(chat_id) → needs_title=true (первое сообщение)
   └─→ init_chat_log(request_id, user_id, chat_id, question)
   └─→ INSERT INTO chat_logs (question only)

2. TradingGraph.stream_sse(needs_title=true) выполняет агентов:

   step 1: intent (LLM)
   └─→ log_trace_step(step=1, agent="intent", input, output)

   step 2: understander (LLM)
   └─→ understood=true, expanded_query="list top 5..."
   └─→ suggested_title="Волатильность 2024"  ← генерируется при needs_title=true
   └─→ log_trace_step(step=2, agent="understander", input, output)

   step 3: parser (LLM)
   └─→ log_trace_step(step=3, agent="parser", input, output)

   step 4: planner (не LLM)
   └─→ log_trace_step(step=4, agent="planner", input, output)

   step 5: executor (не LLM)
   └─→ log_trace_step(step=5, agent="executor", input, output)

   step 6: presenter (LLM)
   └─→ log_trace_step(step=6, agent="presenter", input, output)

3. Завершение
   └─→ complete_chat_log(request_id, response, route="data", agents_used, usage)
   └─→ UPDATE chat_logs SET response=?, route=?, usage=?
   └─→ save_chat_title(chat_id, suggested_title)  ← сохраняем title
   └─→ increment_chat_stats(chat_id)
```

### 4.2 Clarify Flow (нужна кларификация)

```
User: "есть смысл держать позицию в RTH?"

=== chat_log #1 ===

1. init_chat_log(...)

2. TradingGraph.stream_sse():

   step 1: intent (LLM)
   └─→ intent="data", lang="ru"

   step 2: understander (LLM)
   └─→ understood=false
   └─→ need_clarification={required: [{field: "goal", ...}]}

   step 3: clarifier (LLM)
   └─→ response="Что для тебя значит 'есть смысл'?"

3. complete_chat_log(
     response="Что для тебя значит...",
     route="clarify",
     agents_used=["intent", "understander", "clarifier"]
   )

=== chat_log #2 (пользователь ответил) ===

User: "вероятность профита"

1. init_chat_log(...)

2. TradingGraph.stream_sse():
   └─→ awaiting_clarification=true, переходит в clarify_continue

   step 1: intent
   step 2: clarify_continue (re-run understander with context)
   └─→ understood=true, expanded_query="probability of green day in RTH"

   step 3: parser
   step 4: planner
   step 5: executor
   step 6: presenter

3. complete_chat_log(
     response="Вероятность зелёного дня в RTH: 54%...",
     route="data",
     agents_used=["intent", "understander", "parser", "planner", "executor", "presenter"]
   )
```

### 4.3 Chitchat Flow

```
User: "привет"

1. init_chat_log(...)

2. TradingGraph.stream_sse():

   step 1: intent (LLM)
   └─→ intent="chitchat"

   step 2: responder (LLM)
   └─→ response="Привет! Чем могу помочь?"

3. complete_chat_log(
     response="Привет!...",
     route="chitchat",
     agents_used=["intent", "responder"]
   )
```

---

## 5. Что сломано сейчас

### 5.1 TradingGraph не существует

```python
# api.py ожидает:
from agent.graph import trading_graph
for event in trading_graph.stream_sse(question, user_id, session_id):
    ...

# agent/graph.py имеет:
def build_graph() → StateGraph
def compile_graph()
def get_graph()  # singleton

# НЕТ: trading_graph, stream_sse()
```

**Результат:** `ImportError: cannot import name 'trading_graph'`

### 5.2 Memory не интегрирована

```python
# TradingState имеет:
memory_context: str | None  # НИКОГДА НЕ ЗАПОЛНЯЕТСЯ

# ConversationMemory работает, но не вызывается из графа
```

### 5.3 Validator changes не отслеживаются явно

Parser сохраняет raw_output, но diff не вычисляется.

---

## 6. План реализации

**Принцип:** Маленькие шаги, тесты после каждого, не ломаем существующий код.

### Phase 1: Инфраструктура логирования (минимальный риск)

**1.1 Создать `agent/logging/trace.py`**
```python
def log_trace_step(
    request_id: str,
    step_number: int,
    agent_name: str,
    input_data: dict,
    output_data: dict,
    usage: dict | None,
    duration_ms: int
) -> None:
    """Insert into request_traces."""
    pass  # TODO: implement
```

**1.2 Создать `agent/logging/chat.py`**
```python
def init_chat_log(request_id: str, user_id: str, chat_id: str, question: str) -> None:
    """INSERT INTO chat_logs (question only)."""
    pass

def complete_chat_log(request_id: str, response: str, route: str, agents_used: list, usage: dict) -> None:
    """UPDATE chat_logs SET response, route, usage."""
    pass
```

**Тест:** Unit tests для функций (mock Supabase)

---

### Phase 2: Добавить недостающие поля в state (минимальный риск)

**2.1 Добавить `row_count` в presenter output**
```python
# agent/graph.py, present_response()
return {
    ...
    "presenter_row_count": r.row_count,  # NEW
}
```

**2.2 Добавить `presenter_row_count` в state**
```python
# agent/state.py
presenter_row_count: int | None  # NEW
```

**2.3 Передать `context_compacted` в presenter**
```python
# agent/graph.py, present_response()
response = presenter.present(
    data=presenter_data,
    question=question,
    lang=lang,
    context_compacted=state.get("context_compacted", False),  # NEW
)
```

**Тест:** `pytest agent/tests/ -v` — все 64 теста должны пройти

---

### Phase 3: Логирование по агентам (минимальный риск)

Добавляем логирование в каждый node по одному. Не меняем логику — только добавляем вызовы `log_trace_step()`.

**Порядок:**
1. intent
2. understander
3. clarifier
4. clarify_continue
5. parser
6. planner
7. executor
8. presenter
9. responder

**После каждого агента:** запускаем тесты

---

### Phase 4: TradingGraph wrapper (средний риск)

**4.1 Создать `agent/trading_graph.py`**
```python
class TradingGraph:
    def __init__(self):
        self.graph = get_graph()

    def stream_sse(self, question: str, user_id: str, session_id: str):
        """Execute graph with logging, yield SSE events."""
        request_id = str(uuid4())
        init_chat_log(request_id, user_id, session_id, question)

        # Run graph...
        # Yield events...

        complete_chat_log(request_id, response, route, agents_used, usage)

trading_graph = TradingGraph()
```

**4.2 Обновить экспорт в `agent/graph.py`**
```python
from agent.trading_graph import trading_graph
```

**Тест:** Integration test с реальным запросом

---

### Phase 5: Memory Integration (средний риск)

**5.1 Загрузка memory в начале stream_sse()**
```python
memory = ConversationMemory(user_id, session_id)
memory_context = memory.get_context()
# Передать в initial state
```

**5.2 Сохранение memory после ответа**
```python
memory.add_message(question, response)
# Compaction если нужно
```

**5.3 Передать context_compacted из memory**
```python
context_compacted = len(memory.summaries) > 0
```

---

### Checklist

| Step | Описание | Статус |
|------|----------|--------|
| 1.1 | `agent/logging/supabase.py` (все функции) | ✅ (уже существует) |
| 2.1 | `presenter_row_count` в graph.py | ✅ |
| 2.2 | `presenter_row_count` в state.py | ✅ |
| 2.3 | `context_compacted` в presenter | ✅ |
| 3.1 | Логирование intent | ✅ |
| 3.2 | Логирование understander | ✅ |
| 3.3 | Логирование clarifier | ✅ |
| 3.4 | Логирование clarify_continue | ✅ |
| 3.5 | Логирование parser | ✅ |
| 3.6 | Логирование planner | ✅ |
| 3.7 | Логирование executor | ✅ |
| 3.8 | Логирование presenter | ✅ |
| 3.9 | Логирование responder | ✅ |
| 4.1 | TradingGraph: init_chat_log + complete_chat_log | ✅ |
| 4.2 | TradingGraph: request_id в state | ✅ |
| 5.1 | Memory загрузка | ✅ |
| 5.2 | Memory сохранение | ✅ |
| 5.3 | context_compacted из memory | ✅ |

---

## 7. SQL запросы для аналитики

### Стоимость по дням
```sql
SELECT
  DATE(created_at) as day,
  COUNT(*) as requests,
  SUM((usage->'total'->>'input_tokens')::int) as input_tokens,
  SUM((usage->'total'->>'cost_usd')::numeric) as total_cost
FROM chat_logs
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1 DESC;
```

### Среднее время по агентам
```sql
SELECT
  agent_name,
  COUNT(*) as calls,
  AVG(duration_ms) as avg_ms,
  MAX(duration_ms) as max_ms
FROM request_traces
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY agent_name
ORDER BY avg_ms DESC;
```

### Запросы с кларификацией
```sql
SELECT
  cl.question,
  cl.response,
  rt.output_data->'need_clarification' as clarification
FROM chat_logs cl
JOIN request_traces rt ON rt.request_id = cl.request_id
WHERE rt.agent_name = 'understander'
  AND rt.output_data->>'understood' = 'false'
ORDER BY cl.created_at DESC
LIMIT 50;
```

### Usage по агентам за неделю
```sql
SELECT
  (usage->>'intent' IS NOT NULL)::int as has_intent,
  SUM((usage->'intent'->>'input_tokens')::int) as intent_input,
  SUM((usage->'understander'->>'input_tokens')::int) as understander_input,
  SUM((usage->'parser'->>'input_tokens')::int) as parser_input,
  SUM((usage->'presenter'->>'input_tokens')::int) as presenter_input
FROM chat_logs
WHERE created_at > NOW() - INTERVAL '7 days'
  AND usage IS NOT NULL;
```

---

## 8. Graph Routing (полная схема)

```
                            ┌─────────────────────────────────────────────────────────┐
                            │                       START                              │
                            └────────────────────────┬────────────────────────────────┘
                                                     │
                                                     ▼
                            ┌─────────────────────────────────────────────────────────┐
                            │                      INTENT                              │
                            │  • Классифицирует: data / chitchat / concept            │
                            │  • Определяет язык (ru, en, ...)                        │
                            │  • Переводит на английский (internal_query)             │
                            └────────────────────────┬────────────────────────────────┘
                                                     │
                          ┌──────────────────────────┼──────────────────────────┐
                          │                          │                          │
              awaiting_clarification?           intent=data              intent=chitchat/concept
                          │                          │                          │
                          ▼                          ▼                          ▼
            ┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
            │    CLARIFY_CONTINUE     │  │      UNDERSTANDER       │  │       RESPONDER         │
            │  • Берёт user answer    │  │  • Понимает вопрос      │  │  • Отвечает на любой    │
            │  • Вызывает Understander│  │  • Расширяет для Parser │  │    non-data запрос      │
            │    с контекстом         │  │  • Генерирует acknowledge│  │  • Всегда к домену      │
            └───────────┬─────────────┘  └───────────┬─────────────┘  └───────────┬─────────────┘
                        │                            │                            │
      ┌─────────────────┼─────────────────┐          │                            │
      │                 │                 │          │                            │
  topic_changed     understood=true   understood=false                            │
  +!understood          │                 │          │                            │
      │                 │                 │          │                            │
      ▼                 │                 ▼          │                            │
┌───────────┐           │         ┌─────────────┐    │                            │
│ RESPONDER │           │         │  CLARIFIER  │    │                            │
│ (cancel/  │           │         │ Формулирует │    │                            │
│  offtopic)│           │         │   вопрос    │    │                            │
└─────┬─────┘           │         └──────┬──────┘    │                            │
      │                 │                │           │                            │
      │                 │                ▼           │                            │
      │                 │           ┌─────────┐      │                            │
      │                 │           │   END   │      │                            │
      │                 │           │(await)  │      │                            │
      │                 │           └─────────┘      │                            │
      │                 │                            │                            │
      │                 └──────────┬─────────────────┘                            │
      │                            │                                              │
      │                    understood=true                                        │
      │                            │                                              │
      │                            ▼                                              │
      │             ┌─────────────────────────┐                                   │
      │             │         PARSER          │                                   │
      │             │  • Парсит в steps       │                                   │
      │             │  • Структурирует запрос │                                   │
      │             └───────────┬─────────────┘                                   │
      │                         │                                                 │
      │                         ▼                                                 │
      │             ┌─────────────────────────┐                                   │
      │             │        PLANNER          │                                   │
      │             │  • Создаёт SQL планы    │                                   │
      │             │  • Определяет periods   │                                   │
      │             └───────────┬─────────────┘                                   │
      │                         │                                                 │
      │                         ▼                                                 │
      │             ┌─────────────────────────┐                                   │
      │             │        EXECUTOR         │                                   │
      │             │  • Выполняет SQL        │                                   │
      │             │  • Возвращает rows      │                                   │
      │             └───────────┬─────────────┘                                   │
      │                         │                                                 │
      │                         ▼                                                 │
      │             ┌─────────────────────────┐                                   │
      │             │       PRESENTER         │                                   │
      │             │  • Форматирует ответ    │                                   │
      │             │  • Генерирует summary   │                                   │
      │             └───────────┬─────────────┘                                   │
      │                         │                                                 │
      │                         ▼                                                 │
      └────────────────────►┌─────────┐◄──────────────────────────────────────────┘
                            │   END   │
                            └─────────┘
```

**Route values для chat_logs:**
| Route | Flow | agents_used |
|-------|------|-------------|
| `data` | intent → understander → parser → planner → executor → presenter | `["intent", "understander", "parser", "planner", "executor", "presenter"]` |
| `clarify` | intent → understander → clarifier | `["intent", "understander", "clarifier"]` |
| `chitchat` | intent → responder | `["intent", "responder"]` |
| `concept` | intent → responder | `["intent", "responder"]` |

**Clarification continuation routes:**
| Сценарий | topic_changed | understood | Route | agents_used |
|----------|---------------|------------|-------|-------------|
| Ответ по теме | false | true | data | `["intent", "clarify_continue", "parser", ...]` |
| Новый data запрос | true | true | data | `["intent", "clarify_continue", "parser", ...]` |
| Отмена/chitchat | true | false | chitchat | `["intent", "clarify_continue", "responder"]` |
| Снова не понял | false | false | clarify | `["intent", "clarify_continue", "clarifier"]` |
