"""FastAPI server for Trading Analytics Agent.

v2.2.4 - Fix request_id passing for feedback

Provides REST API and SSE streaming endpoints for the multi-agent trading
analysis system. Handles authentication via Supabase JWT, chat history,
and request logging.

Endpoints:
    GET  /           - Health check
    POST /chat/stream - SSE streaming chat with agents
    GET  /chat/history - Get user's chat history with traces
    GET  /data        - Get available trading data info

Run:
    uvicorn api:app --reload
"""

import json
import math
import jwt
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from supabase import create_client

from data import get_data_info, init_database
import config


def clean_for_json(obj):
    """Recursively replace NaN/Infinity with None for valid JSON."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


# Initialize Supabase client
supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY) if config.SUPABASE_URL else None

# Initialize database on startup
init_database(config.DATABASE_PATH)

app = FastAPI(
    title="Trading Analytics Agent",
    description="AI-powered trading data analysis with multi-agent architecture",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
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
        # Verify JWT signature with Supabase secret
        if config.SUPABASE_JWT_SECRET:
            payload = jwt.decode(
                token,
                config.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated"
            )
        else:
            # Fallback for local development without JWT secret (NOT for production!)
            print("WARNING: JWT signature verification disabled - set SUPABASE_JWT_SECRET!")
            payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
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
    chat_id: Optional[str] = None  # If None, creates new chat session
    session_id: Optional[str] = None  # Deprecated, use chat_id


class ChatSessionCreate(BaseModel):
    title: Optional[str] = None


class ChatSessionUpdate(BaseModel):
    title: str


class ChatSessionStats(BaseModel):
    message_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cost_usd: float = 0.0


class ChatSession(BaseModel):
    id: str
    title: Optional[str]
    stats: ChatSessionStats = ChatSessionStats()
    created_at: str
    updated_at: str


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


# =============================================================================
# Chat Sessions API
# =============================================================================

@app.get("/chats", response_model=list[ChatSession])
async def list_chats(user_id: str = Depends(require_auth)):
    """Get all active chat sessions for the authenticated user."""
    if not supabase:
        return []

    try:
        result = supabase.table("chat_sessions") \
            .select("id, title, stats, created_at, updated_at") \
            .eq("user_id", user_id) \
            .eq("status", "active") \
            .order("updated_at", desc=True) \
            .execute()

        if not result.data:
            return []

        return [
            ChatSession(
                id=chat["id"],
                title=chat["title"],
                stats=ChatSessionStats(**(chat.get("stats") or {})),
                created_at=chat["created_at"],
                updated_at=chat["updated_at"],
            )
            for chat in result.data
        ]
    except Exception as e:
        print(f"Failed to list chats: {e}")
        return []


@app.post("/chats", response_model=ChatSession)
async def create_chat(
    request: ChatSessionCreate = ChatSessionCreate(),
    user_id: str = Depends(require_auth)
):
    """Create a new chat session."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        result = supabase.table("chat_sessions").insert({
            "user_id": user_id,
            "title": request.title,
        }).execute()

        chat = result.data[0]
        return ChatSession(
            id=chat["id"],
            title=chat["title"],
            stats=ChatSessionStats(**(chat.get("stats") or {})),
            created_at=chat["created_at"],
            updated_at=chat["updated_at"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/chats/{chat_id}", response_model=ChatSession)
async def update_chat(
    chat_id: str,
    request: ChatSessionUpdate,
    user_id: str = Depends(require_auth)
):
    """Update chat session title."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        result = supabase.table("chat_sessions") \
            .update({"title": request.title, "updated_at": "now()"}) \
            .eq("id", chat_id) \
            .eq("user_id", user_id) \
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Chat not found")

        chat = result.data[0]
        return ChatSession(
            id=chat["id"],
            title=chat["title"],
            stats=ChatSessionStats(**(chat.get("stats") or {})),
            created_at=chat["created_at"],
            updated_at=chat["updated_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, user_id: str = Depends(require_auth)):
    """Soft delete a chat session (keeps data for analytics, hides from UI)."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        # Soft delete: set status='deleted' instead of actual DELETE
        # Data stays in Supabase for analytics bots
        result = supabase.table("chat_sessions") \
            .update({"status": "deleted", "updated_at": "now()"}) \
            .eq("id", chat_id) \
            .eq("user_id", user_id) \
            .eq("status", "active") \
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Chat not found")

        # Clear memory for this chat session
        from agent.memory import get_memory_manager
        get_memory_manager().delete(chat_id)

        return {"status": "ok", "deleted": chat_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chats/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    user_id: str = Depends(require_auth),
    limit: int = 100
):
    """Get messages for a specific chat session with traces."""
    if not supabase:
        return []

    try:
        # Verify chat belongs to user and is active
        chat_result = supabase.table("chat_sessions") \
            .select("id") \
            .eq("id", chat_id) \
            .eq("user_id", user_id) \
            .eq("status", "active") \
            .execute()

        if not chat_result.data:
            raise HTTPException(status_code=404, detail="Chat not found")

        # Get messages for this chat
        result = supabase.table("chat_logs") \
            .select("id, request_id, question, response, route, agents_used, feedback, created_at, usage, duration_ms") \
            .eq("chat_id", chat_id) \
            .order("created_at") \
            .limit(limit) \
            .execute()

        print(f"[API] get_chat_messages: chat_id={chat_id}, found={len(result.data) if result.data else 0} messages")

        if not result.data:
            return []

        # Extract token usage from JSONB 'usage' column for frontend compatibility
        logs = []
        for row in result.data:
            usage = row.get("usage") or {}
            total = usage.get("total", {})
            logs.append({
                **row,
                "input_tokens": total.get("input_tokens", 0),
                "output_tokens": total.get("output_tokens", 0),
                "thinking_tokens": total.get("thinking_tokens", 0),
                "cost_usd": total.get("cost_usd", 0),
            })

        # Get traces for all messages
        request_ids = [log["request_id"] for log in logs if log.get("request_id")]

        if request_ids:
            traces_result = supabase.table("request_traces") \
                .select("request_id, step_number, agent_name, input_data, output_data, duration_ms") \
                .in_("request_id", request_ids) \
                .order("step_number") \
                .execute()

            traces_by_request = {}
            for trace in (traces_result.data or []):
                req_id = trace["request_id"]
                if req_id not in traces_by_request:
                    traces_by_request[req_id] = []
                traces_by_request[req_id].append(trace)

            for log in logs:
                req_id = log.get("request_id")
                log["traces"] = traces_by_request.get(req_id, [])

        return logs
    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get chat messages: {e}")
        return []


@app.get("/chat/data/{request_id}")
async def get_request_data(
    request_id: str,
    user_id: str = Depends(require_auth),
):
    """Get full data for a specific request from executor trace."""
    if not supabase:
        raise HTTPException(status_code=500, detail="Database not available")

    try:
        # Verify request belongs to user
        log_result = supabase.table("chat_logs") \
            .select("id") \
            .eq("request_id", request_id) \
            .eq("user_id", user_id) \
            .execute()

        if not log_result.data:
            raise HTTPException(status_code=404, detail="Request not found")

        # Try executor (current) or data_fetcher (legacy)
        trace_result = supabase.table("request_traces") \
            .select("output_data, agent_name") \
            .eq("request_id", request_id) \
            .in_("agent_name", ["executor", "data_fetcher"]) \
            .execute()

        if not trace_result.data:
            return {"rows": [], "columns": [], "row_count": 0}

        output_data = trace_result.data[0].get("output_data") or {}
        agent_name = trace_result.data[0].get("agent_name")

        if agent_name == "executor":
            # Current architecture: data is array of results
            data = output_data.get("data", [])
            all_rows = []
            for result in data:
                all_rows.extend(result.get("rows", []))
            return {
                "rows": all_rows,
                "columns": list(all_rows[0].keys()) if all_rows else [],
                "row_count": len(all_rows),
                "title": "",
            }
        else:
            # Legacy: data_fetcher with full_data
            full_data = output_data.get("full_data") or {}
            return {
                "rows": full_data.get("rows", []),
                "columns": full_data.get("columns", []),
                "row_count": full_data.get("row_count", 0),
                "title": full_data.get("title", ""),
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get request data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FeedbackUpdate(BaseModel):
    positive_feedback: Optional[str] = None
    negative_feedback: Optional[str] = None


@app.patch("/messages/{request_id}/feedback")
async def update_message_feedback(
    request_id: str,
    feedback: FeedbackUpdate,
    user_id: str = Depends(require_auth),
):
    """Update feedback for a message."""
    if not supabase:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Get current feedback
        current = supabase.table("chat_logs") \
            .select("feedback") \
            .eq("request_id", request_id) \
            .eq("user_id", user_id) \
            .execute()

        if not current.data:
            raise HTTPException(status_code=404, detail="Message not found")

        # Merge with existing feedback
        existing = current.data[0].get("feedback") or {}
        if feedback.positive_feedback is not None:
            existing["positive_feedback"] = feedback.positive_feedback
        if feedback.negative_feedback is not None:
            existing["negative_feedback"] = feedback.negative_feedback

        # Update
        result = supabase.table("chat_logs") \
            .update({"feedback": existing if existing else None}) \
            .eq("request_id", request_id) \
            .eq("user_id", user_id) \
            .execute()

        return {"status": "ok", "feedback": existing}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to update feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def get_or_create_chat_session(user_id: str, chat_id: str | None) -> str:
    """
    Get existing chat session or create new one.

    Logic:
    - If chat_id provided and valid → use it
    - If chat_id not provided → create new session
    """
    if not supabase:
        return chat_id or "default"

    # If chat_id provided, verify and use it
    if chat_id:
        result = supabase.table("chat_sessions") \
            .select("id") \
            .eq("id", chat_id) \
            .eq("user_id", user_id) \
            .eq("status", "active") \
            .execute()

        if result.data:
            supabase.table("chat_sessions") \
                .update({"updated_at": "now()"}) \
                .eq("id", chat_id) \
                .execute()
            return chat_id

    # No chat_id provided → create new session
    result = supabase.table("chat_sessions").insert({
        "user_id": user_id,
        "title": None,
    }).execute()

    new_chat_id = result.data[0]["id"]
    print(f"[API] Created new chat session: {new_chat_id}")
    return new_chat_id


def check_needs_title(chat_id: str) -> bool:
    """Check if chat session needs a title (title is NULL)."""
    if not supabase:
        return False

    try:
        result = supabase.table("chat_sessions") \
            .select("title") \
            .eq("id", chat_id) \
            .execute()

        if not result.data:
            return False

        title = result.data[0].get("title")
        return title is None or title == ""
    except Exception as e:
        print(f"Failed to check title: {e}")
        return False


async def save_chat_title(chat_id: str, title: str) -> str | None:
    """Save suggested title to chat session. Returns title if saved."""
    if not supabase or not title:
        return None

    try:
        # Truncate to 40 chars
        title = title.strip()[:40]

        supabase.table("chat_sessions") \
            .update({"title": title}) \
            .eq("id", chat_id) \
            .execute()

        return title
    except Exception as e:
        print(f"Failed to save chat title: {e}")
        return None


def get_clarification_state(chat_id: str) -> dict | None:
    """
    Check if last message was a clarification request.

    Returns dict with clarification data if awaiting response, None otherwise.
    """
    if not supabase or not chat_id:
        return None

    try:
        # Get last chat_log for this chat
        result = supabase.table("chat_logs") \
            .select("request_id, route, question") \
            .eq("chat_id", chat_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        if not result.data:
            return None

        last_log = result.data[0]
        if last_log.get("route") != "clarify":
            return None

        # Get clarifier trace for original question and history
        request_id = last_log.get("request_id")
        if not request_id:
            return None

        trace_result = supabase.table("request_traces") \
            .select("input_data, output_data") \
            .eq("request_id", request_id) \
            .eq("agent_name", "clarifier") \
            .execute()

        if not trace_result.data:
            return None

        trace = trace_result.data[0]
        input_data = trace.get("input_data") or {}
        output_data = trace.get("output_data") or {}

        return {
            "awaiting_clarification": True,
            "original_question": input_data.get("question"),
            "clarification_history": [
                {"role": "assistant", "content": output_data.get("response", "")}
            ],
        }
    except Exception as e:
        print(f"Failed to get clarification state: {e}")
        return None


def get_recent_chat_history(user_id: str, limit: int = config.CHAT_HISTORY_LIMIT) -> list[dict]:
    """Fetch recent chat history from Supabase for context."""
    if not supabase:
        return []

    try:
        # Load by user_id only (no session filter until we implement multiple chats)
        result = supabase.table("chat_logs") \
            .select("question, response, session_id, created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

        if not result.data:
            return []

        # Convert to chat format and reverse to chronological order
        history = []
        for row in reversed(result.data):
            history.append({"role": "user", "content": row["question"]})
            if row.get("response"):
                history.append({"role": "assistant", "content": row["response"]})

        return history
    except Exception as e:
        print(f"Failed to fetch chat history: {e}")
        return []


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, user_id: str = Depends(require_auth)):
    """
    Stream chat response using multi-agent system.

    SSE event types:
    - step_start: agent starting work
    - step_end: agent finished
    - text_delta: streaming text
    - usage: token usage
    - done: completion (includes chat_id for frontend)

    Logging is handled by TradingGraph (init_chat_log, log_trace_step, complete_chat_log).
    """
    import asyncio
    from agent.trading_graph import trading_graph

    # Get or create chat session
    chat_id = get_or_create_chat_session(user_id, request.chat_id)
    print(f"[API] chat_stream: request.chat_id={request.chat_id}, resolved chat_id={chat_id}")

    # Check if chat needs a title (first message)
    needs_title = check_needs_title(chat_id)

    # Check if we're awaiting clarification response
    clarification_state = get_clarification_state(chat_id)

    async def generate():
        suggested_title = None

        try:
            for event in trading_graph.stream_sse(
                question=request.message,
                user_id=user_id,
                session_id=chat_id,
                chat_id=chat_id,
                needs_title=needs_title,
                awaiting_clarification=clarification_state.get("awaiting_clarification", False) if clarification_state else False,
                original_question=clarification_state.get("original_question") if clarification_state else None,
                clarification_history=clarification_state.get("clarification_history") if clarification_state else None,
            ):
                yield f"data: {json.dumps(clean_for_json(event), default=str)}\n\n"
                await asyncio.sleep(0)  # Force flush

                event_type = event.get("type")

                # Capture suggested_title from Understander for UI
                if event_type == "step_end":
                    output = event.get("output") or {}
                    if event.get("agent") == "understander" and output.get("suggested_title"):
                        suggested_title = output.get("suggested_title")

                elif event_type == "done":
                    # Save suggested title from Understander (first message only)
                    if suggested_title:
                        new_title = await save_chat_title(chat_id, suggested_title)
                        if new_title:
                            yield f"data: {json.dumps({'type': 'chat_title', 'chat_id': chat_id, 'title': new_title})}\n\n"

                    # Include chat_id in done event for frontend
                    yield f"data: {json.dumps({'type': 'chat_id', 'chat_id': chat_id})}\n\n"

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
                .select("request_id, step_number, agent_name, input_data, output_data, duration_ms") \
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
