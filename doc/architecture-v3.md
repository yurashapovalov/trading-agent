# Architecture v3: Model + Users + Logging

## Priorities

| # | Task | Why |
|---|------|-----|
| 1 | Switch to Gemini 3 Flash | 30% cheaper, need to test quality |
| 2 | Add users (Supabase Auth) | Know who uses the system |
| 3 | Add logging (Supabase) | Track usage, costs, debug |
| 4 | Fix tools | After infrastructure is ready |

---

## Phase 1: Switch to Gemini 3 Flash

### Why Gemini?

| | Claude Haiku | Gemini 3 Flash |
|---|-------------|----------------|
| Input | $1.00/1M | $0.10/1M |
| Output | $5.00/1M | $0.40/1M |
| Speed | Fast | Fast |
| Tool use | Good | Good (need to test) |

**~80% cheaper!** (not 30% as initially thought)

### Changes Required

```
agent/
├── llm.py           # Add GeminiAgent class
├── llm_gemini.py    # NEW: Gemini implementation
└── llm_claude.py    # Rename current llm.py (keep as fallback)

api.py               # Switch agent based on config
config.py            # Add GEMINI_API_KEY, LLM_PROVIDER
```

### config.py additions

```python
# LLM Provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # "gemini" or "claude"

# Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Claude (fallback)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
```

### Tool Format Comparison

**Claude:**
```python
{
    "name": "analyze_data",
    "description": "...",
    "input_schema": {
        "type": "object",
        "properties": {...},
        "required": [...]
    }
}
```

**Gemini:**
```python
{
    "name": "analyze_data",
    "description": "...",
    "parameters": {
        "type": "object",
        "properties": {...},
        "required": [...]
    }
}
```

Only difference: `input_schema` → `parameters`

### Implementation Steps

1. Install google-generativeai: `pip install google-generativeai`
2. Create `agent/llm_gemini.py` with GeminiAgent class
3. Update `api.py` to use provider from config
4. Test with same prompts
5. Compare quality

---

## Phase 2: Add Users (Supabase Auth)

### Flow

```
User opens app
    │
    ▼
[Not logged in?] → Show login modal
    │
    ▼
Supabase Auth (email/password or magic link)
    │
    ▼
Frontend gets JWT + user_id
    │
    ▼
JWT sent with every /chat request
    │
    ▼
API validates JWT, extracts user_id
```

### Supabase Setup

1. Create project at supabase.com
2. Enable Email auth
3. Get keys:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY` (frontend)
   - `SUPABASE_SERVICE_KEY` (backend)

### Frontend Changes

```tsx
// lib/supabase.ts
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
```

```tsx
// components/auth-provider.tsx
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user)
      setLoading(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_, session) => {
      setUser(session?.user ?? null)
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  if (loading) return <Loading />
  if (!user) return <LoginModal />
  return children
}
```

### API Changes

```python
# api.py
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def get_current_user(authorization: str = Header(None)):
    """Validate JWT and return user_id"""
    if not authorization:
        raise HTTPException(401, "Missing authorization")

    token = authorization.replace("Bearer ", "")
    try:
        user = supabase.auth.get_user(token)
        return user.user.id
    except:
        raise HTTPException(401, "Invalid token")

@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    user_id: str = Depends(get_current_user)
):
    # user_id now available for logging
    ...
```

### Environment Variables

```bash
# Frontend (.env.local)
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...

# Backend (.env)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
```

---

## Phase 3: Add Logging (Supabase)

### Database Schema

```sql
-- Chat logs table
CREATE TABLE chat_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users NOT NULL,

    -- Request/Response
    question TEXT NOT NULL,
    response TEXT NOT NULL,

    -- Tools used
    tools_used JSONB DEFAULT '[]',

    -- Usage & Cost
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DECIMAL(10, 6),

    -- Metadata
    model VARCHAR(50),
    provider VARCHAR(20),  -- 'gemini' or 'claude'
    duration_ms INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_chat_logs_user ON chat_logs(user_id);
CREATE INDEX idx_chat_logs_created ON chat_logs(created_at DESC);

-- RLS
ALTER TABLE chat_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own logs" ON chat_logs
    FOR SELECT USING (auth.uid() = user_id);
```

### Logging Function

```python
# agent/logging.py
from supabase import create_client
import asyncio

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def log_chat(
    user_id: str,
    question: str,
    response: str,
    tools_used: list,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    model: str,
    provider: str,
    duration_ms: int
):
    """Log chat to Supabase (non-blocking)"""
    try:
        await asyncio.to_thread(
            lambda: supabase.table("chat_logs").insert({
                "user_id": user_id,
                "question": question,
                "response": response,
                "tools_used": tools_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "model": model,
                "provider": provider,
                "duration_ms": duration_ms
            }).execute()
        )
    except Exception as e:
        print(f"Logging error: {e}")  # Don't fail request on log error
```

### Usage in API

```python
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, user_id: str = Depends(get_current_user)):
    start_time = time.time()

    # ... stream response ...

    # Log after response complete (non-blocking)
    asyncio.create_task(log_chat(
        user_id=user_id,
        question=request.message,
        response=full_response,
        tools_used=tools_used,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        cost_usd=usage["cost"],
        model=config.GEMINI_MODEL,
        provider="gemini",
        duration_ms=int((time.time() - start_time) * 1000)
    ))
```

---

## Analytics Queries

```sql
-- Daily usage by user
SELECT
    DATE(created_at) as day,
    user_id,
    COUNT(*) as requests,
    SUM(cost_usd) as cost
FROM chat_logs
GROUP BY day, user_id
ORDER BY day DESC;

-- Popular tools
SELECT
    tool->>'name' as tool_name,
    COUNT(*) as usage_count
FROM chat_logs, jsonb_array_elements(tools_used) as tool
GROUP BY tool_name
ORDER BY usage_count DESC;

-- Total cost by provider
SELECT
    provider,
    COUNT(*) as requests,
    SUM(cost_usd) as total_cost,
    AVG(cost_usd) as avg_cost
FROM chat_logs
GROUP BY provider;
```

---

## Implementation Order

### Week 1: Gemini
- [ ] Install google-generativeai
- [ ] Create GeminiAgent class
- [ ] Convert tool format
- [ ] Test streaming
- [ ] Compare quality with Claude
- [ ] Deploy if good

### Week 2: Users
- [ ] Create Supabase project
- [ ] Add auth to frontend
- [ ] Add JWT validation to API
- [ ] Test login flow
- [ ] Deploy

### Week 3: Logging
- [ ] Create chat_logs table
- [ ] Add logging function
- [ ] Integrate with API
- [ ] Create analytics dashboard (optional)
- [ ] Deploy

### Week 4: Tools
- [ ] Fix tick_size bug
- [ ] Remove duplicate tools
- [ ] Simplify parameters
- [ ] Test everything

---

## Files to Create/Modify

```
Phase 1 (Gemini):
  agent/llm_gemini.py    # NEW
  agent/llm_claude.py    # Rename from llm.py
  agent/llm.py           # Factory function
  config.py              # Add Gemini config
  api.py                 # Use provider from config
  requirements.txt       # Add google-generativeai

Phase 2 (Users):
  frontend/lib/supabase.ts           # NEW
  frontend/components/auth-provider.tsx  # NEW
  frontend/components/login-modal.tsx    # NEW
  frontend/app/layout.tsx            # Wrap with AuthProvider
  api.py                             # Add auth middleware

Phase 3 (Logging):
  agent/logging.py       # NEW
  api.py                 # Add logging calls
  supabase/schema.sql    # NEW - database schema
```

---

## Environment Variables Summary

```bash
# .env (backend)
# LLM
LLM_PROVIDER=gemini
GOOGLE_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
ANTHROPIC_API_KEY=...  # fallback
CLAUDE_MODEL=claude-haiku-4-5-20251001

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Database
DATABASE_PATH=data/trading.duckdb
```

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=https://api.heybar.ai
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```
