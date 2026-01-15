"""FastAPI server for Trading Analytics Agent.

v2.2.2 - Fix request_id passing for feedback

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
from agent.logging.supabase import init_chat_log, complete_chat_log, log_trace_step
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

        # Clear LangGraph checkpointer context for this chat
        from agent.checkpointer import clear_thread_checkpoint
        thread_id = f"{user_id}_{chat_id}"
        clear_thread_checkpoint(thread_id)

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
            .select("id, request_id, question, response, route, agents_used, validation_passed, input_tokens, output_tokens, thinking_tokens, cost_usd, feedback, created_at") \
            .eq("chat_id", chat_id) \
            .order("created_at") \
            .limit(limit) \
            .execute()

        if not result.data:
            return []

        logs = result.data

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
    Get existing active chat session or create new one.

    Logic:
    - If chat_id provided and valid → use it
    - If chat_id not provided → find user's most recent active chat
    - If no active chats → create new one

    This ensures page reload preserves context (uses last chat).
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

    # No chat_id provided → find most recent active chat
    result = supabase.table("chat_sessions") \
        .select("id") \
        .eq("user_id", user_id) \
        .eq("status", "active") \
        .order("updated_at", desc=True) \
        .limit(1) \
        .execute()

    if result.data:
        # Use existing chat → context preserved!
        existing_chat_id = result.data[0]["id"]
        supabase.table("chat_sessions") \
            .update({"updated_at": "now()"}) \
            .eq("id", existing_chat_id) \
            .execute()
        return existing_chat_id

    # No active chats → create new one
    result = supabase.table("chat_sessions").insert({
        "user_id": user_id,
        "title": None,  # Will be generated after 2-3 messages
    }).execute()

    return result.data[0]["id"]


async def maybe_generate_chat_title(chat_id: str) -> str | None:
    """Generate chat title if this is the 2nd or 3rd message and no title yet.
    Returns the new title if generated, None otherwise."""
    if not supabase:
        return None

    try:
        # Check if title already exists
        chat_result = supabase.table("chat_sessions") \
            .select("title") \
            .eq("id", chat_id) \
            .execute()

        current_title = chat_result.data[0].get("title") if chat_result.data else None
        # Skip if already has a real title (not "New Chat")
        if current_title and not current_title.startswith("New Chat"):
            return None  # Already has custom title

        # Count messages in this chat
        count_result = supabase.table("chat_logs") \
            .select("id", count="exact") \
            .eq("chat_id", chat_id) \
            .execute()

        message_count = count_result.count or 0

        # Generate title after 2-3 messages
        if message_count < 2:
            return None

        # Get first 3 messages for title generation
        messages_result = supabase.table("chat_logs") \
            .select("question, response") \
            .eq("chat_id", chat_id) \
            .order("created_at") \
            .limit(3) \
            .execute()

        if not messages_result.data:
            return None

        # Generate title using Gemini
        from google import genai
        client = genai.Client(api_key=config.GOOGLE_API_KEY)

        messages_text = "\n".join([
            f"User: {m['question']}\nAssistant: {m.get('response', '')[:200]}"
            for m in messages_result.data
        ])

        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",  # Fast model for simple task
            contents=f"""Generate a short title (3-5 words, max 40 chars) for this chat conversation.
The title should capture the main topic. Use the SAME LANGUAGE as the conversation.
Reply with ONLY the title, no quotes or explanation.

Conversation:
{messages_text}""",
        )

        title = response.text.strip()[:40]

        # Update chat session with title
        supabase.table("chat_sessions") \
            .update({"title": title}) \
            .eq("id", chat_id) \
            .execute()

        return title

    except Exception as e:
        print(f"Failed to generate chat title: {e}")
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
    - sql_executed: SQL query result
    - text_delta: streaming text
    - validation: validation result
    - suggestions: clarification options (quick-reply buttons)
    - usage: token usage
    - done: completion (includes chat_id for frontend)
    """
    import asyncio
    import uuid
    from agent.graph import trading_graph

    # Get or create chat session
    chat_id = get_or_create_chat_session(user_id, request.chat_id)

    # NOTE: chat_history is NOT loaded for LLM context anymore!
    # LangGraph checkpointer handles message accumulation automatically by thread_id.
    # Supabase is only used for UI history display and analytics.

    async def generate():
        final_text = ""
        usage_data = {}
        request_id = str(uuid.uuid4())
        route = None
        agents_used = []
        validation_attempts = 0
        validation_passed = None
        step_number = 0

        # Create chat_log entry FIRST so traces can reference it via FK
        await init_chat_log(
            request_id=request_id,
            user_id=user_id,
            chat_id=chat_id,
            session_id=chat_id,
            question=request.message,
        )

        try:
            for event in trading_graph.stream_sse(
                question=request.message,
                user_id=user_id,
                session_id=chat_id,  # Use chat_id as session_id for LangGraph checkpointer
                request_id=request_id,  # Pass request_id so frontend gets the same ID saved to DB
            ):
                yield f"data: {json.dumps(clean_for_json(event), default=str)}\n\n"
                await asyncio.sleep(0)  # Force flush

                # Collect data for logging
                event_type = event.get("type")

                if event_type == "step_start":
                    agent_name = event.get("agent")
                    agents_used.append(agent_name)

                elif event_type == "step_end":
                    agent_name = event.get("agent")
                    step_number += 1
                    duration_ms = event.get("duration_ms", 0)
                    result = event.get("result") or {}

                    # Get route from understander
                    if agent_name == "understander":
                        route = result.get("type")

                    # Log trace step (use 'output' for full data, fallback to 'result')
                    await log_trace_step(
                        request_id=request_id,
                        user_id=user_id,
                        step_number=step_number,
                        agent_name=agent_name,
                        input_data=event.get("input"),
                        output_data=event.get("output") or event.get("result"),
                        duration_ms=duration_ms,
                    )

                elif event_type == "text_delta":
                    final_text += event.get("content", "")

                elif event_type == "validation":
                    validation_attempts += 1
                    validation_passed = event.get("status") == "ok"
                    # Reset text on rewrite to avoid concatenating multiple attempts
                    if event.get("status") == "rewrite":
                        final_text = ""

                elif event_type == "usage":
                    usage_data = event

                elif event_type == "done":
                    duration_ms = event.get("total_duration_ms", 0)

                    # Complete chat_log with response and stats
                    await complete_chat_log(
                        request_id=request_id,
                        chat_id=chat_id,
                        response=final_text[:10000],
                        route=route,
                        agents_used=list(set(agents_used)),
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

                    # Generate chat title after 2-3 messages
                    new_title = await maybe_generate_chat_title(chat_id)
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
