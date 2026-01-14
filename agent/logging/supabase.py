"""Supabase logging for request traces and completions.

Logs to two tables:
- request_traces: Per-agent step data (input, output, duration)
- chat_logs: Complete request summary (question, response, usage)

Both async and sync versions provided for different contexts.
"""

import json
from datetime import datetime
from typing import Any
from supabase import create_client

import config


def make_json_serializable(obj: Any) -> Any:
    """Convert object to JSON-serializable format."""
    if obj is None:
        return None
    # Convert to JSON string and back to handle Timestamps, etc.
    try:
        return json.loads(json.dumps(obj, default=str))
    except (TypeError, ValueError):
        return str(obj)

# Initialize Supabase client
_supabase = None


def get_supabase():
    """Get or create Supabase client."""
    global _supabase
    if _supabase is None and config.SUPABASE_URL:
        _supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _supabase


async def log_trace_step(
    request_id: str,
    user_id: str,
    step_number: int,
    agent_name: str,
    input_data: dict | None = None,
    output_data: dict | None = None,
    duration_ms: int = 0,
):
    """
    Log a single agent step to request_traces.

    All agent-specific data (usage, validation, sql) goes into input_data/output_data JSONB.
    """
    supabase = get_supabase()
    if not supabase:
        return

    try:
        serializable_input = make_json_serializable(input_data)
        serializable_output = make_json_serializable(output_data)

        # Truncate large output to avoid storage issues
        output_str = json.dumps(serializable_output) if serializable_output else ""
        if len(output_str) > 50000:
            serializable_output = {"_truncated": True, "preview": output_str[:1000]}

        supabase.table("request_traces").insert({
            "request_id": request_id,
            "user_id": user_id,
            "step_number": step_number,
            "agent_name": agent_name,
            "input_data": serializable_input,
            "output_data": serializable_output,
            "duration_ms": duration_ms,
        }).execute()
    except Exception as e:
        print(f"Failed to log trace step: {e}")


async def log_completion(
    request_id: str,
    user_id: str,
    session_id: str,
    question: str,
    response: str,
    route: str | None = None,
    agents_used: list[str] | None = None,
    validation_attempts: int = 1,
    validation_passed: bool | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    cost_usd: float = 0.0,
    duration_ms: int = 0,
    model: str | None = None,
    provider: str = "gemini",
):
    """
    Log completed request to chat_logs.

    Called when the entire request is finished.
    """
    supabase = get_supabase()
    if not supabase:
        return

    try:
        # Truncate response if too long
        if len(response) > 10000:
            response = response[:10000] + "... [truncated]"

        supabase.table("chat_logs").insert({
            "request_id": request_id,
            "user_id": user_id,
            "session_id": session_id,
            "question": question,
            "response": response,
            "route": route,
            "agents_used": agents_used or [],
            "validation_attempts": validation_attempts,
            "validation_passed": validation_passed,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "cost_usd": cost_usd,
            "duration_ms": duration_ms,
            "model": model,
            "provider": provider,
        }).execute()
    except Exception as e:
        print(f"Failed to log completion: {e}")


def log_trace_step_sync(
    request_id: str,
    user_id: str,
    step_number: int,
    agent_name: str,
    **kwargs
):
    """Synchronous version of log_trace_step for non-async contexts."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(log_trace_step(
                request_id, user_id, step_number, agent_name, **kwargs
            ))
        else:
            loop.run_until_complete(log_trace_step(
                request_id, user_id, step_number, agent_name, **kwargs
            ))
    except RuntimeError:
        asyncio.run(log_trace_step(
            request_id, user_id, step_number, agent_name, **kwargs
        ))


def log_completion_sync(
    request_id: str,
    user_id: str,
    session_id: str,
    question: str,
    response: str,
    **kwargs
):
    """Synchronous version of log_completion for non-async contexts."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(log_completion(
                request_id, user_id, session_id, question, response, **kwargs
            ))
        else:
            loop.run_until_complete(log_completion(
                request_id, user_id, session_id, question, response, **kwargs
            ))
    except RuntimeError:
        asyncio.run(log_completion(
            request_id, user_id, session_id, question, response, **kwargs
        ))
