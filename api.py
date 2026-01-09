"""FastAPI server for Trading Agent"""

import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Optional

from data import get_data_info, init_database
import config

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


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response with SSE events."""
    import asyncio

    async def generate():
        try:
            agent = TradingAgent()  # Fresh agent each request
            for event in agent.chat_stream(request.message):
                yield f"data: {json.dumps(event, default=str)}\n\n"
                await asyncio.sleep(0)  # Force flush
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
