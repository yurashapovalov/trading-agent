"""Supabase logging for request traces and completions.

Logs to two tables:
- request_traces: Per-agent step data (input, output, duration)
- chat_logs: Complete request summary (question, response, usage)

Both async and sync versions provided for different contexts.
"""

import json
import logging
from datetime import datetime
from typing import Any
from supabase import create_client

import config

logger = logging.getLogger(__name__)


def make_json_serializable(obj: Any) -> Any:
    """Convert object to JSON-serializable format."""
    if obj is None:
        return None
    # Convert to JSON string and back to handle Timestamps, etc.
    try:
        return json.loads(json.dumps(obj, default=str))
    except (TypeError, ValueError):
        return str(obj)

# Initialize Supabase client (thread-safe)
import threading

_supabase = None
_supabase_lock = threading.Lock()


def get_supabase():
    """Get or create Supabase client (thread-safe)."""
    global _supabase
    if _supabase is None and config.SUPABASE_URL:
        with _supabase_lock:
            if _supabase is None and config.SUPABASE_URL:
                _supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _supabase


async def init_chat_log(
    request_id: str,
    user_id: str,
    chat_id: str | None,
    question: str,
):
    """
    Create initial chat_log entry at the START of request.

    This allows request_traces to reference the request_id via FK.
    Response and stats will be updated at the end via complete_chat_log.
    """
    supabase = get_supabase()
    if not supabase:
        return

    try:
        supabase.table("chat_logs").insert({
            "request_id": request_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "question": question,
            "response": None,  # Will be updated at completion
        }).execute()
    except Exception as e:
        print(f"Failed to init chat log: {e}")


async def log_trace_step(
    request_id: str,
    user_id: str,
    step_number: int,
    agent_name: str,
    input_data: dict | None = None,
    output_data: dict | None = None,
    usage: dict | None = None,
    duration_ms: int = 0,
):
    """
    Log a single agent step to request_traces.

    Args:
        input_data: Agent-specific input (question, expanded_query, etc.)
        output_data: Agent-specific output (intent, steps, response, etc.)
        usage: Token usage dict {input_tokens, output_tokens, thinking_tokens, cached_tokens}
        duration_ms: Step execution time
    """
    supabase = get_supabase()
    if not supabase:
        return

    try:
        serializable_input = make_json_serializable(input_data)
        serializable_output = make_json_serializable(output_data)
        serializable_usage = make_json_serializable(usage)

        supabase.table("request_traces").insert({
            "request_id": request_id,
            "user_id": user_id,
            "step_number": step_number,
            "agent_name": agent_name,
            "input_data": serializable_input,
            "output_data": serializable_output,
            "usage": serializable_usage,
            "duration_ms": duration_ms,
        }).execute()
    except Exception as e:
        print(f"Failed to log trace step: {e}")


async def complete_chat_log(
    request_id: str,
    chat_id: str | None = None,
    response: str = "",
    route: str | None = None,
    agents_used: list[str] | None = None,
    duration_ms: int = 0,
    usage: dict | None = None,
):
    """
    Complete chat_log entry at the END of request.

    Updates the row created by init_chat_log with response and stats.
    Also updates chat_sessions stats if chat_id provided.

    Args:
        usage: Token usage dict with structure:
            {
                "intent": {...}, "understander": {...}, ...
                "total": {"input_tokens", "output_tokens", "thinking_tokens", "cached_tokens", "cost_usd"}
            }
    """
    supabase = get_supabase()
    if not supabase:
        return

    try:
        # Truncate response if too long
        if response and len(response) > 10000:
            response = response[:10000] + "... [truncated]"

        supabase.table("chat_logs").update({
            "response": response,
            "route": route,
            "agents_used": agents_used or [],
            "duration_ms": duration_ms,
            "usage": usage,
        }).eq("request_id", request_id).execute()

        # Update chat_sessions stats if chat_id provided
        if chat_id and usage:
            total = usage.get("total", {})
            await update_chat_session_stats(
                chat_id=chat_id,
                input_tokens=total.get("input_tokens", 0),
                output_tokens=total.get("output_tokens", 0),
                thinking_tokens=total.get("thinking_tokens", 0),
                cached_tokens=total.get("cached_tokens", 0),
                cost_usd=total.get("cost_usd", 0),
            )

    except Exception as e:
        print(f"Failed to complete chat log: {e}")


async def update_chat_session_stats(
    chat_id: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    cached_tokens: int = 0,
    cost_usd: float = 0.0,
):
    """Increment chat_sessions stats JSONB field."""
    supabase = get_supabase()
    if not supabase:
        return

    try:
        # Use raw SQL to increment JSONB values atomically
        supabase.rpc("increment_chat_stats", {
            "p_chat_id": chat_id,
            "p_input_tokens": input_tokens,
            "p_output_tokens": output_tokens,
            "p_thinking_tokens": thinking_tokens,
            "p_cached_tokens": cached_tokens,
            "p_cost_usd": cost_usd,
        }).execute()
    except Exception as e:
        # Fallback: read-modify-write (less safe but works without RPC)
        try:
            result = supabase.table("chat_sessions") \
                .select("stats") \
                .eq("id", chat_id) \
                .execute()

            if result.data:
                stats = result.data[0].get("stats") or {}
                stats["message_count"] = (stats.get("message_count") or 0) + 1
                stats["input_tokens"] = (stats.get("input_tokens") or 0) + input_tokens
                stats["output_tokens"] = (stats.get("output_tokens") or 0) + output_tokens
                stats["thinking_tokens"] = (stats.get("thinking_tokens") or 0) + thinking_tokens
                stats["cached_tokens"] = (stats.get("cached_tokens") or 0) + cached_tokens
                stats["cost_usd"] = (stats.get("cost_usd") or 0) + cost_usd

                supabase.table("chat_sessions") \
                    .update({"stats": stats, "updated_at": "now()"}) \
                    .eq("id", chat_id) \
                    .execute()
        except Exception as e2:
            print(f"Failed to update chat stats (fallback): {e2}")


async def _safe_background(coro, name: str):
    """Run coroutine and log errors instead of losing them."""
    try:
        await coro
    except Exception as e:
        logger.error(f"Background task {name} failed: {e}")


def log_trace_step_sync(
    request_id: str,
    user_id: str,
    step_number: int,
    agent_name: str,
    input_data: dict | None = None,
    output_data: dict | None = None,
    usage: dict | None = None,
    duration_ms: int = 0,
):
    """Synchronous version of log_trace_step."""
    supabase = get_supabase()
    if not supabase:
        return

    try:
        serializable_input = make_json_serializable(input_data)
        serializable_output = make_json_serializable(output_data)
        serializable_usage = make_json_serializable(usage)

        supabase.table("request_traces").insert({
            "request_id": request_id,
            "user_id": user_id,
            "step_number": step_number,
            "agent_name": agent_name,
            "input_data": serializable_input,
            "output_data": serializable_output,
            "usage": serializable_usage,
            "duration_ms": duration_ms,
        }).execute()
    except Exception as e:
        print(f"Failed to log trace step: {e}")


def init_chat_log_sync(
    request_id: str,
    user_id: str,
    chat_id: str | None,
    question: str,
):
    """Synchronous version - create initial chat_log entry."""
    supabase = get_supabase()
    if not supabase:
        return

    try:
        print(f"[SUPABASE] init_chat_log: chat_id={chat_id}, request_id={request_id}")
        supabase.table("chat_logs").insert({
            "request_id": request_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "question": question,
            "response": None,
        }).execute()
    except Exception as e:
        print(f"Failed to init chat log: {e}")


def complete_chat_log_sync(
    request_id: str,
    chat_id: str | None = None,
    response: str = "",
    route: str | None = None,
    agents_used: list[str] | None = None,
    duration_ms: int = 0,
    usage: dict | None = None,
):
    """Synchronous version - complete chat_log entry."""
    supabase = get_supabase()
    if not supabase:
        return

    try:
        # Truncate response if too long
        if response and len(response) > 10000:
            response = response[:10000] + "... [truncated]"

        supabase.table("chat_logs").update({
            "response": response,
            "route": route,
            "agents_used": agents_used or [],
            "duration_ms": duration_ms,
            "usage": usage,
        }).eq("request_id", request_id).execute()

        # Update chat_sessions stats if chat_id provided
        if chat_id and usage:
            total = usage.get("total", {})
            _update_chat_session_stats_sync(
                chat_id=chat_id,
                input_tokens=total.get("input_tokens", 0),
                output_tokens=total.get("output_tokens", 0),
                thinking_tokens=total.get("thinking_tokens", 0),
                cached_tokens=total.get("cached_tokens", 0),
                cost_usd=total.get("cost_usd", 0),
            )

    except Exception as e:
        print(f"Failed to complete chat log: {e}")


def _update_chat_session_stats_sync(
    chat_id: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    cached_tokens: int = 0,
    cost_usd: float = 0.0,
):
    """Synchronous version - increment chat_sessions stats."""
    supabase = get_supabase()
    if not supabase:
        return

    try:
        supabase.rpc("increment_chat_stats", {
            "p_chat_id": chat_id,
            "p_input_tokens": input_tokens,
            "p_output_tokens": output_tokens,
            "p_thinking_tokens": thinking_tokens,
            "p_cached_tokens": cached_tokens,
            "p_cost_usd": cost_usd,
        }).execute()
    except Exception:
        # Fallback: read-modify-write
        try:
            result = supabase.table("chat_sessions") \
                .select("stats") \
                .eq("id", chat_id) \
                .execute()

            if result.data:
                stats = result.data[0].get("stats") or {}
                stats["message_count"] = (stats.get("message_count") or 0) + 1
                stats["input_tokens"] = (stats.get("input_tokens") or 0) + input_tokens
                stats["output_tokens"] = (stats.get("output_tokens") or 0) + output_tokens
                stats["thinking_tokens"] = (stats.get("thinking_tokens") or 0) + thinking_tokens
                stats["cached_tokens"] = (stats.get("cached_tokens") or 0) + cached_tokens
                stats["cost_usd"] = (stats.get("cost_usd") or 0) + cost_usd

                supabase.table("chat_sessions") \
                    .update({"stats": stats, "updated_at": "now()"}) \
                    .eq("id", chat_id) \
                    .execute()
        except Exception as e2:
            print(f"Failed to update chat stats (fallback): {e2}")


