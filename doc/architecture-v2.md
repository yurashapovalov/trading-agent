# Architecture v2: Users, Sessions, Logging

## Current State (костыли)

```
┌─────────────┐     ┌─────────────┐     ┌────────────┐
│   Vercel    │────▶│   Hetzner   │────▶│   DuckDB   │
│  Frontend   │     │  FastAPI    │     │  Trading   │
└─────────────┘     └─────────────┘     └────────────┘
```

**Проблемы:**
- Агенты кешируются в памяти по session_id → memory leak
- Нет авторизации
- Нет логирования
- Контекст теряется при refresh
- Нельзя сохранить важные ответы

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ┌─────────────┐      ┌─────────────┐      ┌────────────┐     │
│   │   Vercel    │─────▶│   Hetzner   │─────▶│   DuckDB   │     │
│   │  Frontend   │      │  FastAPI    │      │  (trading) │     │
│   └─────────────┘      └─────────────┘      └────────────┘     │
│          │                    │                                 │
│          │ Auth               │ Logging                         │
│          ▼                    ▼                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                      SUPABASE                            │  │
│   │                                                          │  │
│   │  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │  │
│   │  │  users   │  │ saved_chats  │  │    chat_logs      │  │  │
│   │  │  (auth)  │  │  (favorites) │  │  (full history)   │  │  │
│   │  └──────────┘  └──────────────┘  └───────────────────┘  │  │
│   │                                                          │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Authentication
```
User opens app
    │
    ▼
Supabase Auth (magic link / password)
    │
    ▼
Frontend gets user_id + JWT
    │
    ▼
JWT sent with every API request
```

### 2. Chat Request
```
User sends message
    │
    ▼
Frontend → POST /chat/stream
           { message, user_id }
    │
    ▼
API creates TradingAgent (fresh each request, no caching)
    │
    ▼
Claude processes → streams response
    │
    ▼
API logs to Supabase (async):
    - user_id
    - question
    - response
    - tools_used
    - tokens, cost
    │
    ▼
Response streamed to frontend
```

### 3. Save Favorite
```
User clicks ⭐ on response
    │
    ▼
Frontend → Supabase direct (RLS by user_id)
           INSERT INTO saved_chats
```

---

## Database Schema (Supabase)

### users (built-in Supabase Auth)
```sql
-- Supabase creates this automatically
-- We just need profiles if extra data needed
CREATE TABLE profiles (
    id UUID REFERENCES auth.users PRIMARY KEY,
    display_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### chat_logs (full history for analytics)
```sql
CREATE TABLE chat_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users NOT NULL,

    -- Request/Response
    question TEXT NOT NULL,
    response TEXT NOT NULL,

    -- Tools
    tools_used JSONB DEFAULT '[]',
    -- Format: [{"name": "...", "input": {...}, "duration_ms": 123}]

    -- Usage & Cost
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost DECIMAL(10, 6),

    -- Metadata
    model VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chat_logs_user ON chat_logs(user_id);
CREATE INDEX idx_chat_logs_created ON chat_logs(created_at DESC);
```

### saved_chats (user favorites)
```sql
CREATE TABLE saved_chats (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users NOT NULL,
    chat_log_id BIGINT REFERENCES chat_logs(id),

    -- Or standalone save (copy of data)
    question TEXT,
    response TEXT,

    note VARCHAR(500),  -- user's note
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_saved_chats_user ON saved_chats(user_id);

-- RLS: users can only see their own
ALTER TABLE saved_chats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own saves" ON saved_chats
    FOR ALL USING (auth.uid() = user_id);
```

---

## API Changes

### Current
```python
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
```

### New
```python
class ChatRequest(BaseModel):
    message: str
    user_id: str  # from JWT

# Middleware to verify JWT
@app.middleware("http")
async def verify_jwt(request: Request, call_next):
    token = request.headers.get("Authorization")
    user = supabase.auth.get_user(token)
    request.state.user_id = user.id
    return await call_next(request)
```

### New Endpoint: Log Chat (async)
```python
async def log_chat(
    user_id: str,
    question: str,
    response: str,
    tools_used: list,
    usage: dict
):
    """Log chat to Supabase (non-blocking)"""
    await supabase.table("chat_logs").insert({
        "user_id": user_id,
        "question": question,
        "response": response,
        "tools_used": tools_used,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cost": usage.get("cost"),
        "model": config.MODEL_NAME
    }).execute()
```

---

## Frontend Changes

### Auth Flow
```tsx
// lib/supabase.ts
import { createClient } from '@supabase/supabase-js'
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

// components/auth-guard.tsx
export function AuthGuard({ children }) {
  const [user, setUser] = useState(null)

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      if (!data.user) {
        // Show login modal or redirect
      }
      setUser(data.user)
    })
  }, [])

  if (!user) return <LoginModal />
  return children
}
```

### Save Button
```tsx
const saveToFavorites = async (chatLogId: number) => {
  await supabase.from('saved_chats').insert({
    user_id: user.id,
    chat_log_id: chatLogId
  })
}
```

---

## Migration Plan

### Phase 1: Logging (без auth)
1. Добавить Supabase client в API
2. Создать таблицу chat_logs
3. Логировать все запросы с user_name (как сейчас планировали)
4. Для 20 тестеров - просто модалка с именем

### Phase 2: Auth
1. Включить Supabase Auth
2. Добавить login на фронте
3. Заменить user_name на user_id
4. JWT verification в API

### Phase 3: Features
1. Saved chats (favorites)
2. Chat history view
3. Usage dashboard

---

## Analytics Queries

```sql
-- Activity by user
SELECT
    p.display_name,
    COUNT(*) as questions,
    SUM(cost) as total_cost,
    AVG(input_tokens + output_tokens) as avg_tokens
FROM chat_logs cl
JOIN profiles p ON cl.user_id = p.id
GROUP BY p.display_name
ORDER BY questions DESC;

-- Popular tools
SELECT
    tool->>'name' as tool_name,
    COUNT(*) as usage_count,
    AVG((tool->>'duration_ms')::float) as avg_duration
FROM chat_logs,
     jsonb_array_elements(tools_used) as tool
GROUP BY tool_name
ORDER BY usage_count DESC;

-- Daily costs
SELECT
    DATE(created_at) as day,
    COUNT(*) as requests,
    SUM(cost) as daily_cost
FROM chat_logs
GROUP BY day
ORDER BY day DESC;

-- Most expensive queries
SELECT
    question,
    cost,
    input_tokens + output_tokens as total_tokens,
    created_at
FROM chat_logs
ORDER BY cost DESC
LIMIT 20;
```

---

## Decisions to Make

1. **Auth method**: Magic link vs Password vs OAuth?
2. **Context**: Fresh each time vs last N messages?
3. **Rate limiting**: Per user limits?
4. **Cost alerts**: Notify if user spends > $X?

---

## Environment Variables

```bash
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...  # for server-side operations

# Existing
ANTHROPIC_API_KEY=sk-ant-...
MODEL_NAME=claude-haiku-4-5-20251001
DATABASE_PATH=data/trading.duckdb
```
