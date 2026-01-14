"""Export chat log and traces by ID to markdown file."""

import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import config
from supabase import create_client

OUTPUT_FILE = Path(__file__).parent.parent / "docs" / "logs" / "responce.md"


def export_log(log_id: int):
    """Export chat_log and all related traces to markdown file."""

    supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)

    # Get chat_log
    chat_log = supabase.table("chat_logs").select("*").eq("id", log_id).single().execute()

    if not chat_log.data:
        print(f"Log with id={log_id} not found")
        return

    log_data = chat_log.data
    request_id = log_data["request_id"]

    # Get all traces for this request
    traces = supabase.table("request_traces").select("*").eq("request_id", request_id).order("step_number").execute()

    # Write to file
    lines = []

    # Chat log as JSON
    lines.append(json.dumps(log_data, ensure_ascii=False, default=str))
    lines.append("")

    # Each trace as JSON
    for idx, trace in enumerate(traces.data or []):
        trace["idx"] = idx
        lines.append(json.dumps(trace, ensure_ascii=False, default=str))
        lines.append("")

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Exported log {log_id} with {len(traces.data or [])} traces to {OUTPUT_FILE}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python export_log.py <log_id>")
        sys.exit(1)

    log_id = int(sys.argv[1])
    export_log(log_id)
