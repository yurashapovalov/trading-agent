"""FastAPI server for Trading Agent"""

import json
import jwt
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Optional
from supabase import create_client

from data import get_data_info, init_database
import config

# Initialize Supabase client
supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY) if config.SUPABASE_URL else None

# Import agent based on provider
if config.LLM_PROVIDER == "gemini":
    from agent.llm_gemini import GeminiAgent as TradingAgent
else:
    from agent.llm import TradingAgent

# Initialize database on startup
init_database(config.DATABASE_PATH)

app = FastAPI(
    title="Trading Analytics Agent",
    description="AI-powered trading data analysis",
    version="1.0.0"
)

# Allow frontend to connect from any origin (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: ["https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Required for streaming
)


def get_user_id(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract user_id from JWT token. Returns None if no auth."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ")[1]
    try:
        # Decode without verification - Supabase tokens are self-signed
        # We trust the token since it comes from our Supabase instance
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("sub")  # user_id is in 'sub' claim
    except jwt.DecodeError:
        return None


def require_auth(authorization: Optional[str] = Header(None)) -> str:
    """Require valid authentication. Raises 401 if not authenticated."""
    user_id = get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


async def log_chat(
    user_id: str,
    question: str,
    response: str,
    tools_used: list,
    input_tokens: int,
    output_tokens: int,
    thinking_tokens: int,
    cost_usd: float,
    model: str,
    provider: str,
    duration_ms: int,
    session_id: str
):
    """Log chat interaction to Supabase."""
    if not supabase:
        return

    try:
        supabase.table("chat_logs").insert({
            "user_id": user_id,
            "question": question,
            "response": response,
            "tools_used": tools_used,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "cost_usd": cost_usd,
            "model": model,
            "provider": provider,
            "duration_ms": duration_ms,
            "session_id": session_id
        }).execute()
    except Exception as e:
        print(f"Failed to log chat: {e}")



# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ToolUsage(BaseModel):
    name: str
    input: dict
    result: Any
    duration_ms: float


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tools_used: list[ToolUsage] = []


class DataInfo(BaseModel):
    symbol: str
    bars: int
    start_date: str
    end_date: str
    trading_days: int


# Endpoints
@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "Trading Analytics Agent"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Send a message to the trading agent."""
    try:
        agent = TradingAgent()  # Fresh agent each request
        result = agent.chat(request.message)
        return ChatResponse(
            response=result["response"],
            session_id=request.session_id or "none",
            tools_used=result.get("tools_used", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_recent_history(user_id: str, limit: int = 10) -> list:
    """Fetch recent chat history for context."""
    if not supabase:
        return []
    try:
        result = supabase.table("chat_logs") \
            .select("question, response") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return list(reversed(result.data)) if result.data else []
    except Exception as e:
        print(f"Failed to fetch history for context: {e}")
        return []


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, user_id: str = Depends(require_auth)):
    """Stream chat response with SSE events."""
    import asyncio
    import time

    # Fetch recent history for context
    history = get_recent_history(user_id, limit=10)

    async def generate():
        start_time = time.time()
        tools_collected = []
        final_text = ""
        usage_data = {}

        try:
            agent = TradingAgent(history=history)  # Agent with conversation context
            for event in agent.chat_stream(request.message):
                yield f"data: {json.dumps(event, default=str)}\n\n"
                await asyncio.sleep(0)  # Force flush

                # Collect data for logging
                if event.get("type") == "tool_end":
                    tools_collected.append({
                        "name": event.get("name"),
                        "input": event.get("input"),
                        "result": str(event.get("result", ""))[:1000],  # Truncate
                        "duration_ms": event.get("duration_ms")
                    })
                elif event.get("type") == "text_delta":
                    final_text += event.get("content", "")
                elif event.get("type") == "usage":
                    usage_data = event
                elif event.get("type") == "done":
                    # Log to Supabase
                    duration_ms = int((time.time() - start_time) * 1000)
                    await log_chat(
                        user_id=user_id,
                        question=request.message,
                        response=final_text[:10000],  # Truncate long responses
                        tools_used=tools_collected,
                        input_tokens=usage_data.get("input_tokens", 0),
                        output_tokens=usage_data.get("output_tokens", 0),
                        thinking_tokens=usage_data.get("thinking_tokens", 0),
                        cost_usd=usage_data.get("cost", 0),
                        model=config.GEMINI_MODEL if config.LLM_PROVIDER == "gemini" else config.CLAUDE_MODEL,
                        provider=config.LLM_PROVIDER,
                        duration_ms=duration_ms,
                        session_id=request.session_id or "default"
                    )
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.post("/reset")
def reset():
    """Reset endpoint (no-op, agents are fresh each request)."""
    return {"status": "ok", "message": "Agents are fresh each request, no reset needed"}


@app.get("/chat/history")
async def chat_history(user_id: str = Depends(require_auth), limit: int = 50):
    """Get chat history for the authenticated user."""
    if not supabase:
        return []

    try:
        result = supabase.table("chat_logs") \
            .select("id, question, response, tools_used, input_tokens, output_tokens, thinking_tokens, cost_usd, created_at, session_id") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

        # Reverse to get chronological order
        return list(reversed(result.data)) if result.data else []
    except Exception as e:
        print(f"Failed to fetch chat history: {e}")
        return []


@app.get("/data", response_model=list[DataInfo])
def data_info():
    """Get information about loaded data."""
    try:
        df = get_data_info()
        if df.empty:
            return []

        return [
            DataInfo(
                symbol=row['symbol'],
                bars=int(row['bars']),
                start_date=str(row['start_date'])[:10],
                end_date=str(row['end_date'])[:10],
                trading_days=int(row['trading_days'])
            )
            for _, row in df.iterrows()
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
