#!/usr/bin/env python3
"""
Test runner for agent questions.

Usage:
    python agent/scripts/test_question.py "your question here"
    python agent/scripts/test_question.py "your question" --runs 3
    python agent/scripts/test_question.py --file questions.txt
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.graph import TradingGraph


def run_question(question: str, run_id: int = 1) -> dict:
    """Run a single question through the agent system."""
    graph = TradingGraph()

    start_time = time.time()
    results = {
        "run_id": run_id,
        "question": question,
        "timestamp": datetime.now().isoformat(),
        "steps": [],
        "final_response": None,
        "error": None,
    }

    try:
        for event in graph.stream_sse(
            question=question,
            user_id="test_user",
            session_id=f"test_{int(time.time())}",
            chat_history=[],
        ):
            event_type = event.get("type")

            if event_type == "step_start":
                results["steps"].append({
                    "agent": event.get("agent"),
                    "status": "running",
                    "start_time": time.time(),
                })
                print(f"  [{event.get('agent')}] Starting...")

            elif event_type == "step_end":
                agent = event.get("agent")
                # Find and update the step
                for step in results["steps"]:
                    if step["agent"] == agent and step["status"] == "running":
                        step["status"] = "completed"
                        step["duration_ms"] = event.get("duration_ms", 0)
                        step["result"] = event.get("result")
                        step["output"] = event.get("output")
                        break
                print(f"  [{agent}] Done in {event.get('duration_ms', 0)}ms")

            elif event_type == "text_delta":
                content = event.get("content", "")
                if results["final_response"] is None:
                    results["final_response"] = ""
                results["final_response"] += content

            elif event_type == "usage":
                results["usage"] = {
                    "input_tokens": event.get("input_tokens", 0),
                    "output_tokens": event.get("output_tokens", 0),
                    "thinking_tokens": event.get("thinking_tokens", 0),
                    "cost": event.get("cost", 0),
                }

            elif event_type == "done":
                results["total_duration_ms"] = event.get("total_duration_ms", 0)

            elif event_type == "error":
                results["error"] = event.get("message")

    except Exception as e:
        results["error"] = str(e)

    results["wall_time_ms"] = int((time.time() - start_time) * 1000)
    return results


def compare_runs(runs: list[dict]) -> dict:
    """Compare multiple runs and find differences."""
    if len(runs) < 2:
        return {"identical": True}

    comparison = {
        "num_runs": len(runs),
        "sql_identical": True,
        "data_identical": True,
        "response_lengths": [],
        "durations": [],
        "costs": [],
        "sqls": [],
        "row_counts": [],
    }

    for run in runs:
        # Extract SQL from data_fetcher step
        sql = None
        row_count = None
        for step in run.get("steps", []):
            if step["agent"] == "data_fetcher":
                output = step.get("output", {})
                sql = output.get("sql_query")
                row_count = output.get("row_count")
                break

        comparison["sqls"].append(sql)
        comparison["row_counts"].append(row_count)
        comparison["response_lengths"].append(len(run.get("final_response") or ""))
        comparison["durations"].append(run.get("total_duration_ms", 0))
        comparison["costs"].append(run.get("usage", {}).get("cost", 0))

    # Check if SQLs are identical
    unique_sqls = set(s for s in comparison["sqls"] if s)
    comparison["sql_identical"] = len(unique_sqls) <= 1

    # Check if row counts are identical
    unique_counts = set(c for c in comparison["row_counts"] if c is not None)
    comparison["data_identical"] = len(unique_counts) <= 1

    return comparison


def main():
    parser = argparse.ArgumentParser(description="Test agent questions")
    parser.add_argument("question", nargs="?", help="Question to test")
    parser.add_argument("--runs", type=int, default=1, help="Number of runs")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--file", "-f", help="File with questions (one per line)")

    args = parser.parse_args()

    questions = []
    if args.file:
        with open(args.file) as f:
            questions = [line.strip() for line in f if line.strip()]
    elif args.question:
        questions = [args.question]
    else:
        parser.print_help()
        return

    all_results = []

    for question in questions:
        print(f"\n{'='*60}")
        print(f"Question: {question[:50]}...")
        print(f"{'='*60}")

        runs = []
        for i in range(args.runs):
            print(f"\n--- Run {i+1}/{args.runs} ---")
            result = run_question(question, run_id=i+1)
            runs.append(result)

            # Print summary
            usage = result.get("usage", {})
            print(f"\n  Summary:")
            print(f"    Duration: {result.get('total_duration_ms', 0)}ms")
            print(f"    Tokens: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out")
            print(f"    Cost: ${usage.get('cost', 0):.4f}")

            if result.get("error"):
                print(f"    ERROR: {result['error']}")

        # Compare runs
        if args.runs > 1:
            comparison = compare_runs(runs)
            print(f"\n--- Comparison ---")
            print(f"  SQL identical: {'✓' if comparison['sql_identical'] else '✗'}")
            print(f"  Data identical: {'✓' if comparison['data_identical'] else '✗'}")
            print(f"  Row counts: {comparison['row_counts']}")
            print(f"  Durations: {comparison['durations']}")
            print(f"  Costs: {comparison['costs']}")

            all_results.append({
                "question": question,
                "runs": runs,
                "comparison": comparison,
            })
        else:
            all_results.append({
                "question": question,
                "runs": runs,
            })

    # Save results
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str, ensure_ascii=False)
        print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
