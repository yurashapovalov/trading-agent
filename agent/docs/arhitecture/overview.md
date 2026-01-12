# Trading Analytics Agent v2

Multi-agent system for trading data analysis using natural language.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Gemini 2.5 Flash (Lite for Understander) |
| **Framework** | LangGraph (state machine) |
| **Backend** | FastAPI + SSE streaming |
| **Frontend** | Next.js 15 + React |
| **Database** | DuckDB (trading data) + Supabase (auth, logs) |
| **Deploy** | Hetzner VPS (backend) + Vercel (frontend) |

## Core Principle

**LLM decides WHAT, Code decides HOW and VALIDATES**

| Agent | Type | Purpose |
|-------|------|---------|
| Understander | LLM (Gemini Lite) | Parses question → Intent |
| Responder | Code | Returns chitchat/clarification |
| SQL Agent | LLM | Intent → SQL query |
| SQL Validator | Code | Validates SQL |
| DataFetcher | Code | Executes SQL → data |
| Analyst | LLM (Gemini Flash) | Data → response + Stats |
| Validator | Code | Validates Stats |

## Architecture

```
                    ┌─ chitchat/out_of_scope/clarification ─► Responder ──► END
                    │
Question ─► Understander ─┼────────────────────────────────────────────────────────────┐
                    │                            ┌──────────────────────────────────────┤
                    │                            │ (rewrite loop)                       │
                    └─ data ─► SQL Agent ─► SQL Validator ─► DataFetcher ─► Analyst ─► Validator ─► END
                                   ↑_______________|                           ↑____________| (rewrite loop)
```

### Symmetry Pattern

```
┌─────────────┐     ┌─────────────────┐
│  SQL Agent  │ ←── │  SQL Validator  │
│   (LLM)     │ ──→ │     (Code)      │
└─────────────┘     └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   DataFetcher   │
                    │     (Code)      │
                    └────────┬────────┘
                             │
                             ▼
┌─────────────┐     ┌─────────────────┐
│   Analyst   │ ←── │    Validator    │
│   (LLM)     │ ──→ │     (Code)      │
└─────────────┘     └─────────────────┘
```

- SQL Agent generates SQL → SQL Validator checks before execution
- Analyst generates response → Validator checks stats against data

## Data Flow

### Standard Query (no search_condition)

```
User: "How did NQ perform in January 2024?"
     │
     ▼
Understander → Intent(type=data, daily, period=january)
     │
     ▼
DataFetcher → standard SQL template → 22 rows
     │
     ▼
Analyst ←─→ Validator (retry loop)
     │
     ▼
Response
```

### Search Query (with search_condition)

```
User: "Find days when NQ dropped >2%"
     │
     ▼
Understander → Intent(search_condition="days where change < -2%")
     │
     ▼
SQL Agent ←─→ SQL Validator (retry loop)
     │ valid SQL
     ▼
DataFetcher → executes SQL → 77 rows
     │
     ▼
Analyst ←─→ Validator (retry loop)
     │
     ▼
Response
```

## Human-in-the-Loop (Stateless)

When Understander cannot parse a question clearly, it returns `needs_clarification: true`.

### Why Stateless?

- Original approach used LangGraph `interrupt()`
- Doesn't work on serverless (Vercel) - MemorySaver doesn't persist between requests
- Stateless approach: clarification is just a normal response saved to chat_logs

### Flow

```
User: "Покажи данные"
         │
         ▼
    Understander
         │
    needs_clarification: true
    clarification_question: "Какой символ и период?"
    suggestions: ["NQ за последний месяц", "ES за 2024"]
         │
         ▼
    Responder
         │
    Formats question + suggestions as response
    Saves to chat_logs
         │
         ▼
    Frontend shows ClarificationMessage with buttons
         │
         ▼
User clicks: "NQ за последний месяц"
         │
         ▼
    New message sent (just like normal)
    Chat history includes clarification Q&A
         │
         ▼
    Understander (sees context, combines with previous)
         │
         ▼
    ... normal flow ...
```

### Context Preservation

Clarification response is saved to `chat_logs.response` so subsequent questions see:
```
User: Отдели RTH от ETH
Assistant: Что вы хотите сделать с данными RTH и ETH?
Варианты:
• Сравнить волатильность RTH и ETH
• Сравнить объёмы по сессиям
User: Сравнить волатильность RTH и ETH
```

### Guidelines for Understander

1. **Use context before clarifying** - if previous conversation was about RTH vs ETH, assume follow-up questions are about the same
2. **Combine follow-ups** - when user answers clarification, combine with original question
3. **Max 3 clarification attempts** - after that, use defaults

## Intent Types

| Type | Description | Example |
|------|-------------|---------|
| `data` | Data queries + search | "Как NQ в январе?", "Найди падения >2%" |
| `concept` | Explain concepts | "Что такое MACD?" |
| `chitchat` | Small talk | "Привет!" |
| `out_of_scope` | Non-trading questions | "Какая погода?" |

## Granularity

| Value | Returns | Use Case |
|-------|---------|----------|
| `period` | 1 aggregated row | "За месяц вырос на X%" |
| `daily` | 1 row per day | "По дням", поиск паттернов |
| `hourly` | 1 row per hour | "Какой час самый волатильный" |
| `weekday` | 1 row per weekday | "Понедельник vs пятница" |
| `monthly` | 1 row per month | "По месяцам за год" |

## Validation Loops

### SQL Validation Loop

```
SQL Agent generates SQL
         │
         ▼
SQL Validator checks syntax, safety
         │
     ┌───┴───┐
     │       │
    OK     Rewrite
     │       │
     ▼       ▼
DataFetcher  SQL Agent (fix errors)
                 │
                 ▼
            SQL Validator (again)
                 │
            Max 3 attempts
```

### Response Validation Loop

```
Analyst generates response with Stats
         │
         ▼
Validator checks Stats vs actual data
         │
     ┌───┴───┐
     │       │
    OK     Rewrite
     │       │
     ▼       ▼
   END    Analyst (fix errors)
              │
              ▼
          Validator (again)
              │
          Max 3 attempts
```

## SSE Events

| Type | Description |
|------|-------------|
| `step_start` | Agent starting work |
| `step_end` | Agent finished (includes input/output for traces) |
| `text_delta` | Response chunk (streaming) |
| `clarification` | Need user input (shows buttons) |
| `validation` | Response validation result |
| `usage` | Token usage and cost |
| `done` | Complete |

### clarification Event

```json
{
  "type": "clarification",
  "question": "Какой символ вас интересует?",
  "suggestions": ["NQ", "ES", "RTH vs ETH"]
}
```

Frontend shows `ClarificationMessage` component with question and suggestion buttons.

## Project Structure

```
trading-agent/
├── api.py                    # FastAPI backend
├── config.py                 # Environment config
├── agent/
│   ├── state.py              # AgentState, Intent, Stats types
│   ├── graph.py              # LangGraph pipeline + TradingGraph wrapper
│   ├── capabilities.py       # System capabilities description
│   ├── pricing.py            # Token cost calculation
│   ├── checkpointer.py       # LangGraph memory (MemorySaver)
│   ├── agents/
│   │   ├── understander.py   # LLM - parses question → Intent
│   │   ├── sql_agent.py      # LLM - generates SQL from search_condition
│   │   ├── sql_validator.py  # Code - validates SQL before execution
│   │   ├── data_fetcher.py   # Code - executes SQL, fetches data
│   │   ├── analyst.py        # LLM - analyzes data, writes response
│   │   └── validator.py      # Code - validates stats against data
│   ├── prompts/
│   │   ├── understander.py   # Structured prompts with examples
│   │   ├── sql_agent.py
│   │   └── analyst.py
│   ├── modules/
│   │   ├── sql.py            # DuckDB query templates + helpers
│   │   └── patterns.py       # Pattern detection (consecutive days, etc.)
│   └── logging/
│       └── supabase.py       # Request traces logging
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js pages
│   │   ├── components/
│   │   │   ├── ai/           # Chat components (message, prompt-input, etc.)
│   │   │   ├── ui/           # shadcn/ui components
│   │   │   └── auth-provider.tsx
│   │   ├── hooks/
│   │   │   └── useChat.ts    # Chat state, SSE handling
│   │   └── types/
│   │       └── chat.ts       # ChatMessage, SSEEvent types
│   └── ...
└── data/
    └── NQ_1min.parquet       # Trading data (NQ futures)
```

## Database Schema

### Trading Data (DuckDB)

```sql
-- Minute-level OHLCV data
CREATE TABLE nq_1min (
    timestamp TIMESTAMP,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume INTEGER
);
```

### Application Data (Supabase)

```sql
-- Chat logs with traces
CREATE TABLE chat_logs (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    request_id UUID,
    session_id TEXT,
    question TEXT,
    response TEXT,
    route TEXT,
    agents_used TEXT[],
    validation_attempts INT,
    validation_passed BOOLEAN,
    input_tokens INT,
    output_tokens INT,
    thinking_tokens INT,
    cost_usd DECIMAL,
    duration_ms INT,
    model TEXT,
    provider TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent traces for debugging
CREATE TABLE request_traces (
    id SERIAL PRIMARY KEY,
    request_id UUID,
    user_id UUID,
    step_number INT,
    agent_name TEXT,
    input_data JSONB,
    output_data JSONB,
    duration_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Quick Start

### Backend

```bash
cd /Users/yura/Development/stock
source venv/bin/activate
uvicorn api:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm run dev
```

### Using the Graph Directly

```python
from agent.graph import TradingGraph

graph = TradingGraph()

# Synchronous
result = graph.invoke(
    question="Найди дни падения >2%",
    user_id="user123",
    session_id="session1"
)
print(result["response"])

# Streaming (for SSE)
for event in graph.stream_sse(
    question="Как NQ в январе?",
    user_id="user123"
):
    print(event)
```

## Cost Tracking

All LLM calls track usage and cost:

```python
# Gemini 2.5 Flash
GEMINI_2_5_FLASH = {
    "input": 0.15 / 1_000_000,   # $0.15 per 1M tokens
    "output": 0.60 / 1_000_000,  # $0.60 per 1M tokens
    "thinking": 3.50 / 1_000_000 # $3.50 per 1M thinking tokens
}

# Gemini 2.5 Flash Lite (for Understander)
GEMINI_2_5_FLASH_LITE = {
    "input": 0.075 / 1_000_000,
    "output": 0.30 / 1_000_000,
    "thinking": 0
}
```

Usage is aggregated across all agents and returned in `usage` SSE event.

## Deployment

### GitHub Actions

On push to `main`:
1. SSH to Hetzner VPS
2. `git pull`
3. `docker-compose up -d --build`

### Environment Variables

```bash
# Backend (.env)
GOOGLE_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
DUCKDB_PATH=data/NQ_1min.parquet

# Frontend (.env.local)
NEXT_PUBLIC_API_URL=https://api.askbar.trade
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

## Future Extensions

### Technical Indicators

```
Understander
     │
     ├─── SQL Agent ────→ SQL Validator ───┐
     ├─── RSI Agent ────→ RSI Validator ───┼──→ DataFetcher
     ├─── MACD Agent ───→ MACD Validator ──┘
     └─── Pattern Agent → Pattern Validator
                                           │
                                           ▼
                                       Analyst
                                           │
                                           ▼
                                       Validator
```

Each LLM agent has its own Code validator.

### Multiple Symbols

Currently only NQ. Extend to ES, CL, GC, etc.

### Backtesting

Strategy definition and walk-forward analysis.
