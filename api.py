"""FastAPI server for Trading Agent"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional

from agent.llm import TradingAgent
from data import get_data_info, init_database
import config

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
)

# Store agents per session (simple in-memory, for production use Redis)
agents: dict[str, TradingAgent] = {}


def get_agent(session_id: str = "default") -> TradingAgent:
    """Get or create agent for session."""
    if session_id not in agents:
        agents[session_id] = TradingAgent()
    return agents[session_id]


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
        agent = get_agent(request.session_id)
        result = agent.chat(request.message)
        return ChatResponse(
            response=result["response"],
            session_id=request.session_id,
            tools_used=result.get("tools_used", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset")
def reset(session_id: str = "default"):
    """Reset conversation history."""
    if session_id in agents:
        agents[session_id].reset()
    return {"status": "ok", "message": "Conversation reset"}


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
