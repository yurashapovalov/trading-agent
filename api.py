"""FastAPI server for Trading Agent - Multi-Agent Architecture"""

import json
import jwt
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from supabase import create_client

from data import get_data_info, init_database
from agent.logging.supabase import log_completion, log_trace_step
import config

# Initialize Supabase client
supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY) if config.SUPABASE_URL else None

# Initialize database on startup
init_database(config.DATABASE_PATH)

app = FastAPI(
    title="Trading Analytics Agent",
    description="AI-powered trading data analysis with multi-agent architecture",
    version="2.0.0"
)

# Allow frontend to connect from any origin (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: ["https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def get_user_id(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """Extract user_id from JWT token. Returns None if no auth."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("sub")
    except jwt.DecodeError:
        return None


def require_auth(authorization: Optional[str] = Header(None)) -> str:
    """Require valid authentication. Raises 401 if not authenticated."""
    user_id = get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


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
    return {"status": "ok", "service": "Trading Analytics Agent", "version": "2.0"}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, user_id: str = Depends(require_auth)):
    """
    Stream chat response using multi-agent system.

    SSE event types:
    - step_start: agent starting work
    - step_end: agent finished
    - sql_executed: SQL query result
    - text_delta: streaming text
    - validation: validation result
    - usage: token usage
    - done: completion
    """
    import asyncio
    import uuid
    from agent.graph import trading_graph

    print(f"[CHAT] Processing: {request.message[:50]}... for user {user_id[:8]}...")

    async def generate():
        final_text = ""
        usage_data = {}
        request_id = str(uuid.uuid4())
        route = None
        agents_used = []
        sql_queries_count = 0
        total_rows = 0
        validation_attempts = 0
        validation_passed = None
        step_number = 0

        try:
            for event in trading_graph.stream_sse(
                question=request.message,
                user_id=user_id,
                session_id=request.session_id or "default"
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
                await asyncio.sleep(0)  # Force flush

                # Collect data for logging
                event_type = event.get("type")

                if event_type == "step_start":
                    agents_used.append(event.get("agent"))

                elif event_type == "step_end":
                    agent_name = event.get("agent")
                    step_number += 1
                    duration_ms = event.get("duration_ms", 0)

                    # Get route from understander
                    if agent_name == "understander":
                        route = event.get("result", {}).get("type")

                    # Log trace step
                    await log_trace_step(
                        request_id=request_id,
                        user_id=user_id,
                        step_number=step_number,
                        agent_name=agent_name,
                        agent_type=event.get("result", {}).get("type", "unknown"),
                        output_data=event.get("result"),
                        duration_ms=duration_ms,
                    )

                elif event_type == "sql_executed":
                    sql_queries_count += 1
                    total_rows += event.get("rows_found", 0)

                elif event_type == "text_delta":
                    final_text += event.get("content", "")

                elif event_type == "validation":
                    validation_attempts += 1
                    validation_passed = event.get("status") == "ok"

                elif event_type == "usage":
                    usage_data = event

                elif event_type == "done":
                    duration_ms = event.get("total_duration_ms", 0)

                    # Log to Supabase
                    await log_completion(
                        request_id=request_id,
                        user_id=user_id,
                        session_id=request.session_id or "default",
                        question=request.message,
                        response=final_text[:10000],
                        route=route,
                        agents_used=list(set(agents_used)),
                        total_sql_queries=sql_queries_count,
                        total_rows_returned=total_rows,
                        validation_attempts=validation_attempts,
                        validation_passed=validation_passed,
                        input_tokens=usage_data.get("input_tokens", 0),
                        output_tokens=usage_data.get("output_tokens", 0),
                        thinking_tokens=usage_data.get("thinking_tokens", 0),
                        cost_usd=usage_data.get("cost", 0),
                        duration_ms=duration_ms,
                        model=config.GEMINI_MODEL,
                        provider="gemini"
                    )

        except Exception as e:
            print(f"[CHAT] Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# Keep v2 endpoint as alias for backward compatibility during transition
@app.post("/chat/v2/stream")
async def chat_stream_v2(request: ChatRequest, user_id: str = Depends(require_auth)):
    """Alias for /chat/stream (backward compatibility)."""
    return await chat_stream(request, user_id)


@app.get("/chat/history")
async def chat_history(user_id: str = Depends(require_auth), limit: int = 50):
    """Get chat history for the authenticated user with agent traces."""
    if not supabase:
        return []

    try:
        # Get chat logs
        result = supabase.table("chat_logs") \
            .select("id, request_id, question, response, route, agents_used, validation_passed, input_tokens, output_tokens, thinking_tokens, cost_usd, created_at, session_id") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

        if not result.data:
            return []

        logs = list(reversed(result.data))

        # Get request_ids to fetch traces
        request_ids = [log["request_id"] for log in logs if log.get("request_id")]

        if request_ids:
            # Fetch all traces for these requests in one query
            traces_result = supabase.table("request_traces") \
                .select("request_id, step_number, agent_name, agent_type, input_data, output_data, sql_query, sql_result, sql_rows_returned, validation_status, duration_ms") \
                .in_("request_id", request_ids) \
                .order("step_number") \
                .execute()

            # Group traces by request_id
            traces_by_request = {}
            for trace in (traces_result.data or []):
                req_id = trace["request_id"]
                if req_id not in traces_by_request:
                    traces_by_request[req_id] = []
                traces_by_request[req_id].append(trace)

            # Attach traces to logs
            for log in logs:
                req_id = log.get("request_id")
                if req_id and req_id in traces_by_request:
                    log["traces"] = traces_by_request[req_id]
                else:
                    log["traces"] = []

        return logs
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
