"""Supabase logging for request traces and completions."""

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
    agent_type: str,
    input_data: dict | None = None,
    output_data: dict | None = None,
    duration_ms: int = 0,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    sql_query: str | None = None,
    sql_result: Any | None = None,
    sql_rows_returned: int | None = None,
    sql_error: str | None = None,
    validation_status: str | None = None,
    validation_issues: list[str] | None = None,
    validation_feedback: str | None = None,
    prompt_template: str | None = None,
    model_used: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    cost_usd: float = 0.0,
):
    """
    Log a single agent step to request_traces.

    Called after each agent completes its work.
    """
    supabase = get_supabase()
    if not supabase:
        return

    try:
        # Convert all data to JSON-serializable format
        serializable_sql_result = make_json_serializable(sql_result)
        serializable_input = make_json_serializable(input_data)
        serializable_output = make_json_serializable(output_data)

        # Truncate large fields to avoid storage issues
        if serializable_sql_result and len(str(serializable_sql_result)) > 10000:
            serializable_sql_result = str(serializable_sql_result)[:10000] + "... [truncated]"

        supabase.table("request_traces").insert({
            "request_id": request_id,
            "user_id": user_id,
            "step_number": step_number,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "input_data": serializable_input,
            "output_data": serializable_output,
            "duration_ms": duration_ms,
            "started_at": started_at.isoformat() if started_at else None,
            "finished_at": finished_at.isoformat() if finished_at else None,
            "sql_query": sql_query,
            "sql_result": serializable_sql_result,
            "sql_rows_returned": sql_rows_returned,
            "sql_error": sql_error,
            "validation_status": validation_status,
            "validation_issues": validation_issues,
            "validation_feedback": validation_feedback,
            "prompt_template": prompt_template,
            "model_used": model_used,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thinking_tokens": thinking_tokens,
            "cost_usd": cost_usd,
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
    total_sql_queries: int = 0,
    total_rows_returned: int = 0,
    validation_attempts: int = 1,
    validation_passed: bool | None = None,
    was_interrupted: bool = False,
    interrupt_reason: str | None = None,
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
            "total_sql_queries": total_sql_queries,
            "total_rows_returned": total_rows_returned,
            "validation_attempts": validation_attempts,
            "validation_passed": validation_passed,
            "was_interrupted": was_interrupted,
            "interrupt_reason": interrupt_reason,
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
    agent_type: str,
    **kwargs
):
    """Synchronous version of log_trace_step for non-async contexts."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, create task
            asyncio.create_task(log_trace_step(
                request_id, user_id, step_number, agent_name, agent_type, **kwargs
            ))
        else:
            loop.run_until_complete(log_trace_step(
                request_id, user_id, step_number, agent_name, agent_type, **kwargs
            ))
    except RuntimeError:
        # No event loop, run synchronously
        asyncio.run(log_trace_step(
            request_id, user_id, step_number, agent_name, agent_type, **kwargs
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
