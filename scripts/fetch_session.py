#!/usr/bin/env python3
"""
Fetch all chat logs and traces for a session.

Usage:
    python scripts/fetch_session.py <chat_id>
    python scripts/fetch_session.py <chat_id> --output results/session_abc.json
"""

import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from supabase import create_client


def fetch_session(chat_id: str) -> dict:
    """Fetch all data for a chat session."""
    supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)

    # Get chat session info
    session = supabase.table("chat_sessions") \
        .select("*") \
        .eq("id", chat_id) \
        .execute()

    # Get all chat logs for this session
    logs = supabase.table("chat_logs") \
        .select("*") \
        .eq("chat_id", chat_id) \
        .order("created_at") \
        .execute()

    # Get all request_ids
    request_ids = [log["request_id"] for log in (logs.data or []) if log.get("request_id")]

    # Get all traces for these requests
    traces = []
    if request_ids:
        traces_result = supabase.table("request_traces") \
            .select("*") \
            .in_("request_id", request_ids) \
            .order("created_at") \
            .execute()
        traces = traces_result.data or []

    # Group traces by request_id
    traces_by_request = {}
    for trace in traces:
        req_id = trace["request_id"]
        if req_id not in traces_by_request:
            traces_by_request[req_id] = []
        traces_by_request[req_id].append(trace)

    # Build result
    result = {
        "chat_id": chat_id,
        "session": session.data[0] if session.data else None,
        "messages": []
    }

    for log in (logs.data or []):
        req_id = log.get("request_id")
        message = {
            "request_id": req_id,
            "question": log.get("question"),
            "response": log.get("response"),
            "route": log.get("route"),
            "agents_used": log.get("agents_used"),
            "duration_ms": log.get("duration_ms"),
            "created_at": log.get("created_at"),
            "traces": traces_by_request.get(req_id, [])
        }
        result["messages"].append(message)

    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch session data for analysis")
    parser.add_argument("chat_id", help="Chat session ID")
    parser.add_argument("--output", "-o", help="Output file path (default: prints to stdout)")
    args = parser.parse_args()

    data = fetch_session(args.chat_id)

    output = json.dumps(data, ensure_ascii=False, indent=2, default=str)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output)
        print(f"Saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
