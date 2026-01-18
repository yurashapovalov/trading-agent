
"""Export chat session with all logs and traces to markdown file."""

import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import config
from supabase import create_client

OUTPUT_FILE = Path(__file__).parent.parent.parent / "docs" / "logs" / "session.md"


def export_session(chat_id: str):
    """Export all logs and traces for a chat session."""

    supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)

    # Get all logs for this chat session
    logs = supabase.table("chat_logs").select("*").eq("chat_id", chat_id).order("created_at").execute()

    if not logs.data:
        print(f"No logs found for chat_id={chat_id}")
        return

    lines = []
    lines.append(f"# Chat Session: {chat_id}")
    lines.append(f"Total messages: {len(logs.data)}")
    lines.append("")

    for i, log_data in enumerate(logs.data):
        request_id = log_data["request_id"]

        lines.append(f"---")
        lines.append(f"## Message {i + 1}")
        lines.append(f"**Question:** {log_data['question']}")
        lines.append(f"**Route:** {log_data.get('route', 'N/A')}")
        lines.append(f"**Input tokens:** {log_data.get('input_tokens', 0)}")
        lines.append(f"**Output tokens:** {log_data.get('output_tokens', 0)}")
        lines.append("")

        # Get traces for this request
        traces = supabase.table("request_traces").select("*").eq("request_id", request_id).order("step_number").execute()

        if traces.data:
            lines.append("### Traces")
            for trace in traces.data:
                agent = trace.get("agent_name", "unknown")
                duration = trace.get("duration_ms", 0)
                lines.append(f"- **{agent}**: {duration}ms")

                # Show input/output data
                input_data = trace.get("input_data")
                output_data = trace.get("output_data")

                if input_data:
                    lines.append(f"  - Input: ```json")
                    lines.append(f"  {json.dumps(input_data, ensure_ascii=False, default=str)[:500]}")
                    lines.append(f"  ```")

                if output_data:
                    lines.append(f"  - Output: ```json")
                    lines.append(f"  {json.dumps(output_data, ensure_ascii=False, default=str)[:1000]}")
                    lines.append(f"  ```")
            lines.append("")

        # Response
        response = log_data.get("response", "")
        if response:
            lines.append("### Response")
            lines.append(response[:2000])
            lines.append("")

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Exported {len(logs.data)} messages to {OUTPUT_FILE}")


def export_log(log_id: int):
    """Export single chat_log by ID (legacy)."""

    supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)

    chat_log = supabase.table("chat_logs").select("*").eq("id", log_id).single().execute()

    if not chat_log.data:
        print(f"Log with id={log_id} not found")
        return

    # Use chat_id to export full session
    export_session(chat_log.data["chat_id"])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python export_log.py <chat_id or log_id>")
        sys.exit(1)

    arg = sys.argv[1]

    # Detect if it's UUID (chat_id) or integer (log_id)
    if "-" in arg:
        export_session(arg)
    else:
        export_log(int(arg))
