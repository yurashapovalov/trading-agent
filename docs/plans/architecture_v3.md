# Architecture v3: Production-Ready Setup

План настройки архитектуры перед подключением фронта.

## Цели

1. **Экономия токенов** — кэширование статического контекста
2. **Персистенция** — история и трейсы в Supabase
3. **Масштабируемость** — LangGraph для множества агентов
4. **Чистота** — удалить артефакты старой архитектуры

---

## 1. Supabase Schema

### Таблицы

```sql
-- Сессии пользователей
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);

-- Сообщения (история переписки)
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),

    -- Для компактификации истории
    is_summarized BOOLEAN DEFAULT false,
    summary_of UUID[] DEFAULT '{}',  -- IDs сообщений которые суммаризировали

    -- Метаданные
    metadata JSONB DEFAULT '{}'  -- parsed_query, intent, agents_used, etc.
);

-- Трейсы (для дебага и аналитики)
CREATE TABLE traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    agent TEXT NOT NULL,  -- parser, executor, responder, etc.
    input JSONB,
    output JSONB,
    duration_ms INT,
    tokens_in INT,
    tokens_out INT,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Кэш контекста (для отслеживания что закэшировано)
CREATE TABLE context_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT UNIQUE NOT NULL,  -- hash of content
    gemini_cache_name TEXT,  -- Gemini cache resource name
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Сохранённые стратегии пользователя
CREATE TABLE strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    conditions JSONB NOT NULL,  -- entry/exit rules
    backtest_results JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Индексы

```sql
CREATE INDEX idx_messages_session ON messages(session_id, created_at);
CREATE INDEX idx_traces_message ON traces(message_id);
CREATE INDEX idx_sessions_user ON sessions(user_id, created_at DESC);
```

### RLS (Row Level Security)

```sql
-- Пользователи видят только свои данные
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY sessions_user_policy ON sessions
    FOR ALL USING (user_id = auth.uid()::text);

CREATE POLICY messages_user_policy ON messages
    FOR ALL USING (
        session_id IN (SELECT id FROM sessions WHERE user_id = auth.uid()::text)
    );
```

---

## 2. История переписки

### Стратегия хранения

```
Сообщения 1-20:  Полные (последние)
Сообщения 21-50: Суммаризованные (1 summary на 10 сообщений)
Сообщения 50+:   Удалены или архивированы
```

### Компактификация

```python
async def compact_history(session_id: str):
    """Суммаризировать старые сообщения для экономии токенов."""
    messages = await get_messages(session_id, limit=50)

    if len(messages) < 30:
        return  # Не нужно компактить

    # Взять сообщения 21-30 для суммаризации
    to_summarize = messages[20:30]

    summary = await llm_summarize(to_summarize)

    # Сохранить summary как одно сообщение
    await save_message(
        session_id=session_id,
        role="system",
        content=f"[Summary of earlier conversation]: {summary}",
        is_summarized=True,
        summary_of=[m.id for m in to_summarize]
    )

    # Пометить оригиналы как суммаризированные
    await mark_summarized([m.id for m in to_summarize])
```

### Загрузка истории для LLM

```python
async def get_context_history(session_id: str, max_tokens: int = 2000) -> list[dict]:
    """Получить историю оптимизированную для LLM."""
    messages = await get_messages(session_id, limit=30)

    # Фильтруем суммаризированные оригиналы
    messages = [m for m in messages if not m.is_summarized or m.role == "system"]

    # Обрезаем если слишком много токенов
    history = []
    token_count = 0

    for msg in reversed(messages):
        msg_tokens = estimate_tokens(msg.content)
        if token_count + msg_tokens > max_tokens:
            break
        history.insert(0, {"role": msg.role, "content": msg.content})
        token_count += msg_tokens

    return history
```

---

## 3. Token Caching (Gemini)

### Что кэшируем

| Контент | Размер | TTL | Когда обновлять |
|---------|--------|-----|-----------------|
| Parser system prompt | ~1500 tokens | 1h | При деплое |
| Responder system prompt | ~1000 tokens | 1h | При деплое |
| Pattern definitions | ~2000 tokens | 24h | При изменении конфига |
| Event/holiday rules | ~500 tokens | 24h | При изменении конфига |

### Структура промптов

```python
# prompts/parser.py

PARSER_STATIC = """
You are a parser for trading data assistant.
[... длинные инструкции ...]
[... примеры ...]
[... pattern definitions ...]
"""  # ~1500 tokens, кэшируется

def get_parser_prompt(question: str, history: list[dict], today: str) -> tuple[str, str]:
    """Возвращает (cached_content, dynamic_content)."""

    dynamic = f"""
Today: {today}

Recent history:
{format_history(history[-5:])}

Question: {question}

Output ParsedQuery JSON:
"""  # ~200 tokens, каждый раз новое

    return PARSER_STATIC, dynamic
```

### Управление кэшем

```python
# cache/manager.py

class CacheManager:
    def __init__(self, client: genai.Client):
        self.client = client
        self.caches = {}  # key -> cache_name

    async def get_or_create(self, key: str, content: str, ttl: str = "1h") -> str:
        """Получить кэш или создать новый."""
        if key in self.caches:
            # Проверить что не истёк
            if not self._is_expired(key):
                return self.caches[key]

        cache = await self.client.caches.create(
            model="gemini-2.5-flash",
            contents=[content],
            ttl=ttl,
            display_name=key
        )

        self.caches[key] = cache.name
        await self._save_to_supabase(key, cache.name, ttl)

        return cache.name

    async def call_with_cache(
        self,
        cache_key: str,
        static_content: str,
        dynamic_content: str,
        **kwargs
    ) -> str:
        """Вызвать LLM с кэшированным контекстом."""
        cache_name = await self.get_or_create(cache_key, static_content)

        response = await self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[dynamic_content],
            cached_content=cache_name,
            **kwargs
        )

        return response.text
```

---

## 4. LangGraph Architecture

### Не линейный граф

```
                                    ┌─────────────────┐
                                    │   Anomaly       │
                                    │   Scanner       │
                                    └────────┬────────┘
                                             │
┌──────────┐    ┌──────────┐    ┌───────────┴───────────┐    ┌──────────┐
│  START   │───►│  Parser  │───►│       Router          │───►│Responder │───► END
└──────────┘    └──────────┘    └───────────┬───────────┘    └──────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
            ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
            │   Executor   │       │  Clarifier   │       │   Concept    │
            │   (data)     │       │  (unclear)   │       │  (explain)   │
            └──────────────┘       └──────────────┘       └──────────────┘
                    │                      │                       │
                    │                      ▼                       │
                    │              ┌──────────────┐                │
                    │              │    Human     │                │
                    │              │   (input)    │                │
                    │              └──────────────┘                │
                    │                      │                       │
                    └──────────────────────┴───────────────────────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │  Responder   │
                                    └──────────────┘
```

### State (упрощённый)

```python
from typing import TypedDict, Annotated
from langgraph.graph import MessagesState

class TradingState(MessagesState):
    """Минимальный state для нового графа."""

    # Идентификация
    session_id: str
    user_id: str

    # Parser output
    parsed: dict | None
    intent: str | None

    # Execution
    data: dict | None
    context: str | None  # Для респондера

    # Response
    response: str | None

    # Tracking
    agents_used: list[str]

    # Для clarification loop
    waiting_for: str | None
    original_question: str | None
```

### Nodes

```python
# nodes/parser.py
async def parse(state: TradingState, cache_manager: CacheManager) -> dict:
    """Parse question using cached prompt."""
    question = get_current_question(state)
    history = await get_context_history(state["session_id"])

    static, dynamic = get_parser_prompt(question, history, today())

    result = await cache_manager.call_with_cache(
        cache_key="parser_v1",
        static_content=static,
        dynamic_content=dynamic,
        response_schema=ParsedQuery,
    )

    parsed = ParsedQuery.model_validate_json(result)

    return {
        "parsed": parsed.model_dump(),
        "intent": parsed.intent,
        "agents_used": ["parser"],
    }
```

### Conditional Routing

```python
def route_after_parser(state: TradingState) -> str:
    """Decide next node based on parser output."""
    intent = state.get("intent")
    parsed = state.get("parsed", {})

    if intent == "chitchat":
        return "responder"  # Сразу отвечаем

    if intent == "concept":
        return "concept"  # Объясняем термин

    if parsed.get("unclear"):
        return "clarifier"  # Уточняем

    if intent == "find_anomalies":
        return "anomaly_scanner"  # Новый агент

    if intent == "backtest":
        return "backtester"  # Новый агент

    return "executor"  # Default: получить данные
```

---

## 5. Чистка артефактов

### Удалить

```
agent/graph.py              # Старый LangGraph (1000+ строк)
agent/state.py              # Старый state (заменим новым)
agent/checkpointer.py       # Старый checkpointer
agent/agents/validator.py   # Не используется
agent/agents/analyst.py     # Переделаем позже
agent/agents/parser.py      # Старый parser
agent/agents/data_fetcher.py # Старый fetcher
agent/log_utils/            # Сломан
agent/parser/               # Пустая папка
venv/                       # Старый venv
```

### Оставить и обновить

```
agent/graph_v2.py           # База для нового графа
agent/executor.py           # Работает
agent/types.py              # Работает
agent/prompts/              # Разбить на static/dynamic
agent/agents/responders/    # Работает
agent/config/               # Работает
agent/patterns/             # Работает
agent/operations/           # Работает
agent/modules/sql.py        # Может пригодиться
agent/pricing.py            # Для трекинга costs
```

---

## 6. Порядок работы

### Phase 1: Cleanup (сегодня)
- [ ] Удалить артефакты
- [ ] Создать новый `agent/state.py` (минимальный)
- [ ] Проверить что graph_v2 работает

### Phase 2: Supabase (сегодня-завтра)
- [ ] Создать таблицы в Supabase
- [ ] Написать функции для работы с историей
- [ ] Интегрировать с graph_v2

### Phase 3: Caching (завтра)
- [ ] Разбить промпты на static/dynamic
- [ ] Создать CacheManager
- [ ] Протестировать экономию токенов

### Phase 4: LangGraph upgrade
- [ ] Добавить новые nodes (anomaly_scanner, backtester)
- [ ] Настроить conditional routing
- [ ] Добавить human-in-the-loop для clarification

### Phase 5: Frontend
- [ ] Подключить API к новому графу
- [ ] Тестирование e2e

---

## 7. Метрики успеха

| Метрика | Сейчас | Цель |
|---------|--------|------|
| Input tokens/request | ~2000 | ~300 (cached) |
| Response time | ~2s | ~1s |
| History storage | In-memory | Supabase (persistent) |
| Agents | 3 | 6+ |
| Code complexity | High (1000+ lines old) | Low (modular) |
