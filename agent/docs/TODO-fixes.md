# Technical Debt & Fixes

Issues identified during code review. Prioritized by severity.

## Completed

- [x] **JWT signature verification** - Now verifies with SUPABASE_JWT_SECRET
- [x] **CORS configuration** - Now uses ALLOWED_ORIGINS from env

---

## High Priority

### 1. Add timeouts to LLM calls

**Problem:** LLM calls can hang indefinitely if the API is slow or unresponsive.

**Files:**
- `agent/agents/understander.py:101-134`
- `agent/agents/sql_agent.py` (similar location)
- `agent/agents/analyst.py:59-86`

**Fix:**
```python
# Add timeout to Gemini client config
response = self.client.models.generate_content(
    model=self.model,
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0,
        # Add timeout
    ),
    request_options={"timeout": 30}  # 30 seconds
)
```

---

### 2. Thread-safe usage tracking

**Problem:** `_last_usage` is instance state in singleton agents. Race condition in concurrent requests.

**Files:**
- `agent/agents/understander.py:42-47`
- `agent/agents/analyst.py:34-39`
- `agent/agents/sql_agent.py` (similar)

**Current (problematic):**
```python
class Understander:
    def __init__(self):
        self._last_usage = UsageStats(...)  # Mutable instance state

    def __call__(self, state):
        # ... LLM call ...
        self._last_usage = UsageStats(...)  # Race condition!
        return {"usage": self._last_usage}
```

**Fix options:**

A. Return usage directly (no instance state):
```python
def __call__(self, state):
    # ... LLM call ...
    usage = UsageStats(
        input_tokens=response.usage_metadata.prompt_token_count,
        output_tokens=response.usage_metadata.candidates_token_count,
        ...
    )
    return {"usage": usage}  # Return directly, no instance state
```

B. Use threading.local():
```python
import threading

class Understander:
    def __init__(self):
        self._local = threading.local()

    @property
    def _last_usage(self):
        return getattr(self._local, 'usage', None)

    @_last_usage.setter
    def _last_usage(self, value):
        self._local.usage = value
```

**Recommendation:** Option A is simpler and more functional.

---

### 3. Fix uninitialized variable in exception handler

**Problem:** `response_obj` may not exist when exception is caught.

**File:** `agent/agents/analyst.py:88-90`

**Current:**
```python
try:
    response_obj = self.client.models.generate_content(...)
    response_text = response_obj.text
except json.JSONDecodeError:
    response_text = response_obj.text if response_obj else ""  # NameError if response_obj not assigned!
```

**Fix:**
```python
response_obj = None  # Initialize before try
try:
    response_obj = self.client.models.generate_content(...)
    ...
```

---

## Medium Priority

### 0. Clarification message shows usage/steps artifact

**Problem:** When clarification is shown and user clicks a button, the old message with "2 steps" and token count remains as an artifact.

**Screenshot:** User asks unclear question → sees "2 steps" + "3,177 / 123 · $0.0004" → then their follow-up answer → then actual response with "8 steps".

**Root cause:**
1. `done` event adds message to `messages` with `agent_steps` and `usage`
2. `clarification` event shows ClarificationMessage with buttons
3. User clicks → ClarificationMessage disappears
4. But the old message artifact remains

**File:** `frontend/src/hooks/useChat.ts`

**Fix options:**

A. Don't add usage/steps for clarification messages:
```typescript
} else if (event.type === "done") {
  const isClarification = /* check if clarification was shown */;
  setMessages((prev) => [
    ...prev,
    {
      role: "assistant",
      content: stripSuggestions(finalText),
      agent_steps: isClarification ? undefined : [...stepsCollected],
      usage: isClarification ? undefined : usageData,
    },
  ]);
}
```

B. Track `isClarification` flag when `clarification` event received, use it in `done` handler.

C. Don't add message at all for clarification (ClarificationMessage handles display).

**Recommendation:** Option B - set flag when clarification event comes, check it in done handler.

---

### 4. Extract duplicated SSE parsing logic

**Problem:** Nearly identical SSE parsing in two places.

**Files:**
- `frontend/src/hooks/useChat.ts:169-309` (sendMessage)
- `frontend/src/hooks/useChat.ts:390-474` (respondToClarification)

**Fix:** Extract to a shared function:
```typescript
async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  handlers: {
    onStepStart: (event: StepStartEvent) => void;
    onStepEnd: (event: StepEndEvent) => void;
    onTextDelta: (content: string) => void;
    onClarification: (event: ClarificationEvent) => void;
    onUsage: (event: UsageEvent) => void;
    onDone: () => void;
    onError: (message: string) => void;
  }
) {
  // ... shared parsing logic ...
}
```

---

### 5. Replace bare except with specific exceptions

**Problem:** Catches all exceptions including SystemExit, KeyboardInterrupt.

**File:** `agent/agents/analyst.py:197-198`

**Current:**
```python
except:
    pass
```

**Fix:**
```python
except (json.JSONDecodeError, KeyError, TypeError):
    pass
```

---

### 6. Use proper logging instead of print

**Problem:** Using print() for errors makes debugging in production difficult.

**Files:**
- `agent/logging/supabase.py:69-70`
- `agent/agents/understander.py:154`
- `api.py:56`

**Fix:**
```python
import logging

logger = logging.getLogger(__name__)

# Instead of:
print(f"Failed to log trace step: {e}")

# Use:
logger.error(f"Failed to log trace step: {e}", exc_info=True)
```

---

### 7. Async database operations

**Problem:** Synchronous DuckDB operations block the event loop.

**Files:**
- `agent/agents/data_fetcher.py:69-70`
- `api.py:145-150`

**Fix:**
```python
import asyncio

# In async endpoint:
result = await asyncio.to_thread(
    trading_graph.stream_sse,
    question=request.message,
    user_id=user_id,
    ...
)
```

---

## Low Priority

### 8. Extract shared `_convert_numpy_types` function

**Problem:** Same function duplicated in two files.

**Files:**
- `agent/modules/sql.py:15-29`
- `agent/modules/patterns.py:17-33`

**Fix:** Create `agent/utils.py`:
```python
def convert_numpy_types(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    ...
```

---

### 9. Define magic numbers as constants

**Files:**
- `agent/graph.py:143` - `step_number >= 6`
- `agent/graph.py:477-478` - `chunk_size = 50`
- `agent/logging/supabase.py:57` - `50000` character limit

**Fix:**
```python
# In config.py or at top of file
MAX_SQL_VALIDATION_ATTEMPTS = 3  # 6 steps = 3 cycles of agent + validator
SSE_CHUNK_SIZE = 50
MAX_LOG_CONTENT_LENGTH = 50000
```

---

### 10. Update `__all__` exports

**File:** `agent/agents/__init__.py`

**Current:**
```python
__all__ = ["Understander", "DataFetcher", "Analyst", "Validator"]
```

**Fix:**
```python
__all__ = [
    "Understander",
    "SQLAgent",
    "SQLValidator",
    "DataFetcher",
    "Analyst",
    "Validator"
]
```

---

### 11. Remove or complete dead code

**File:** `agent/agents/analyst.py:104-170`

**Problem:** `generate_stream` method exists but is never called.

**Options:**
1. Remove if not needed
2. Integrate into graph if streaming per-agent is desired

---

### 12. Thread-safe lazy initialization

**File:** `agent/graph.py:262-268`

**Current:**
```python
@property
def app(self):
    if self._app is None:  # Race condition
        self._app = compile_graph(...)
    return self._app
```

**Fix:**
```python
import threading

class TradingGraph:
    _lock = threading.Lock()

    @property
    def app(self):
        if self._app is None:
            with self._lock:
                if self._app is None:  # Double-check
                    self._app = compile_graph(...)
        return self._app
```

---

## Environment Variables Required

Add to `.env` on server:

```bash
# Required for JWT verification (get from Supabase Dashboard > Settings > API)
SUPABASE_JWT_SECRET=your-jwt-secret-here

# Required for CORS (comma-separated list)
ALLOWED_ORIGINS=https://askbar.trade,https://www.askbar.trade
```

---

## Testing Checklist

After fixes, verify:

- [ ] JWT tokens from Supabase are accepted
- [ ] Forged JWT tokens are rejected
- [ ] Frontend can connect from allowed origins
- [ ] Frontend cannot connect from disallowed origins
- [ ] LLM calls timeout after 30s if API hangs
- [ ] Concurrent requests don't have race conditions
