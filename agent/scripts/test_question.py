#!/usr/bin/env python3
"""
Test runner for agent questions — determinism checker.

Tests that the same question produces identical SQL and data across multiple runs.

Usage:
    python agent/scripts/test_question.py "your question here"
    python agent/scripts/test_question.py "your question" --runs 10
    python agent/scripts/test_question.py --file questions.txt
    python agent/scripts/test_question.py "question" --runs 5 --output results.json
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.graph import TradingGraph


def hash_data(rows: list) -> str:
    """Create hash of data rows for comparison."""
    if not rows:
        return "empty"
    # Sort rows by all keys for consistent comparison
    try:
        sorted_rows = sorted(rows, key=lambda x: json.dumps(x, sort_keys=True, default=str))
        return hashlib.md5(json.dumps(sorted_rows, sort_keys=True, default=str).encode()).hexdigest()[:12]
    except Exception:
        return "unhashable"


def run_question(question: str, run_id: int = 1) -> dict:
    """Run a single question through the TradingGraph system."""
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
            session_id=f"test_{run_id}_{int(time.time())}",
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


def extract_run_data(run: dict) -> dict:
    """Extract key data from a run for comparison."""
    extracted = {
        "sql": None,
        "row_count": None,
        "data_hash": None,
        "query_spec": None,
    }

    for step in run.get("steps", []):
        # SQL from query_builder
        if step["agent"] == "query_builder":
            output = step.get("output", {})
            extracted["sql"] = output.get("sql_query")

        # Data from data_fetcher
        if step["agent"] == "data_fetcher":
            output = step.get("output", {})
            extracted["row_count"] = output.get("row_count")
            rows = output.get("rows", [])
            extracted["data_hash"] = hash_data(rows)

        # Query spec from understander
        if step["agent"] == "understander":
            output = step.get("output", {})
            intent = output.get("intent", {})
            extracted["query_spec"] = intent.get("query_spec")

    return extracted


def compare_runs(runs: list[dict]) -> dict:
    """Compare multiple runs and find differences."""
    if len(runs) < 2:
        return {"identical": True, "num_runs": len(runs)}

    comparison = {
        "num_runs": len(runs),
        "query_spec_identical": True,
        "sql_identical": True,
        "data_identical": True,
        "all_identical": True,
        "query_specs": [],
        "sqls": [],
        "row_counts": [],
        "data_hashes": [],
        "durations": [],
        "costs": [],
    }

    for run in runs:
        extracted = extract_run_data(run)

        comparison["query_specs"].append(
            json.dumps(extracted["query_spec"], sort_keys=True) if extracted["query_spec"] else None
        )
        comparison["sqls"].append(extracted["sql"])
        comparison["row_counts"].append(extracted["row_count"])
        comparison["data_hashes"].append(extracted["data_hash"])
        comparison["durations"].append(run.get("total_duration_ms", 0))
        comparison["costs"].append(run.get("usage", {}).get("cost", 0))

    # Check if query_specs are identical
    unique_specs = set(s for s in comparison["query_specs"] if s)
    comparison["query_spec_identical"] = len(unique_specs) <= 1

    # Check if SQLs are identical
    unique_sqls = set(s for s in comparison["sqls"] if s)
    comparison["sql_identical"] = len(unique_sqls) <= 1

    # Check if data hashes are identical (actual data comparison)
    unique_hashes = set(h for h in comparison["data_hashes"] if h)
    comparison["data_identical"] = len(unique_hashes) <= 1

    # Overall check
    comparison["all_identical"] = (
        comparison["query_spec_identical"]
        and comparison["sql_identical"]
        and comparison["data_identical"]
    )

    return comparison


def print_query_spec(qs: dict, indent: str = "  "):
    """Pretty print query_spec."""
    if not qs:
        print(f"{indent}(empty)")
        return

    filters = qs.get("filters", {})
    print(f"{indent}source: {qs.get('source')}")
    print(f"{indent}period: {filters.get('period_start')} — {filters.get('period_end')}")
    if filters.get("session"):
        print(f"{indent}session: {filters.get('session')}")
    if filters.get("conditions"):
        print(f"{indent}conditions: {filters.get('conditions')}")
    print(f"{indent}grouping: {qs.get('grouping')}")

    metrics = qs.get("metrics", [])
    if metrics:
        metric_strs = []
        for m in metrics:
            if m.get("column"):
                metric_strs.append(f"{m.get('metric')}({m.get('column')})")
            else:
                metric_strs.append(m.get('metric'))
        print(f"{indent}metrics: {', '.join(metric_strs)}")

    if qs.get("special_op") and qs.get("special_op") != "none":
        print(f"{indent}special_op: {qs.get('special_op')}")
        if qs.get("event_time_spec"):
            print(f"{indent}event_time: find={qs['event_time_spec'].get('find')}")
        if qs.get("top_n_spec"):
            tns = qs["top_n_spec"]
            print(f"{indent}top_n: n={tns.get('n')}, order_by={tns.get('order_by')}")


def print_comparison(comparison: dict, runs: list = None):
    """Print comparison results."""
    print(f"\n{'='*60}")
    print("DETERMINISM CHECK RESULTS")
    print(f"{'='*60}")

    # Show query_specs from each run
    if runs:
        print("\n--- Query Specs per run ---")
        for i, run in enumerate(runs):
            print(f"\nRun {i+1}:")
            for step in run.get("steps", []):
                if step["agent"] == "understander":
                    qs = step.get("output", {}).get("intent", {}).get("query_spec")
                    print_query_spec(qs)
                    break

    print(f"\n{'='*60}")

    # Query spec check
    spec_status = "✓ PASS" if comparison["query_spec_identical"] else "✗ FAIL"
    print(f"Query Spec identical: {spec_status}")
    if not comparison["query_spec_identical"]:
        print(f"  Unique specs: {len(set(comparison['query_specs']))}")

    # SQL check
    sql_status = "✓ PASS" if comparison["sql_identical"] else "✗ FAIL"
    print(f"SQL identical:        {sql_status}")
    if not comparison["sql_identical"]:
        print(f"  Unique SQLs: {len(set(comparison['sqls']))}")

    # Data check
    data_status = "✓ PASS" if comparison["data_identical"] else "✗ FAIL"
    print(f"Data identical:       {data_status}")
    print(f"  Row counts: {comparison['row_counts']}")
    print(f"  Data hashes: {comparison['data_hashes']}")

    # Overall
    print(f"\n{'='*50}")
    overall = "✓ ALL IDENTICAL" if comparison["all_identical"] else "✗ NON-DETERMINISTIC"
    print(f"OVERALL: {overall}")
    print(f"{'='*50}")

    # Stats
    durations = comparison["durations"]
    costs = comparison["costs"]
    if durations:
        print(f"\nDuration: min={min(durations)}ms, max={max(durations)}ms, avg={sum(durations)//len(durations)}ms")
    if costs:
        print(f"Cost: total=${sum(costs):.4f}, avg=${sum(costs)/len(costs):.4f}")


def get_default_output_path() -> Path:
    """Generate default output path with timestamp."""
    logs_dir = Path(__file__).parent.parent / "docs" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return logs_dir / f"test_{timestamp}.json"


def main():
    parser = argparse.ArgumentParser(
        description="Test agent questions for determinism",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run once (quick check)
    python agent/scripts/test_question.py "Покажи статистику за 2024"

    # Run 10 times (determinism check)
    python agent/scripts/test_question.py "В какое время формируется high?" --runs 10

    # Results are auto-saved to agent/docs/logs/test_YYYY-MM-DD_HH-MM-SS.json
        """
    )
    parser.add_argument("question", nargs="?", help="Question to test")
    parser.add_argument("--runs", "-r", type=int, default=1, help="Number of runs (default: 1)")
    parser.add_argument("--output", "-o", help="Output file (default: auto-generated in agent/docs/logs/)")
    parser.add_argument("--file", "-f", help="File with questions (one per line)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Less verbose output")
    parser.add_argument("--no-save", action="store_true", help="Don't save results to file")

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
        print(f"\n{'#'*60}")
        print(f"# Question: {question[:50]}...")
        print(f"# Runs: {args.runs}")
        print(f"{'#'*60}")

        runs = []
        for i in range(args.runs):
            print(f"\n--- Run {i+1}/{args.runs} ---")
            result = run_question(question, run_id=i+1)
            runs.append(result)

            # Print summary (always show key stats)
            usage = result.get("usage", {})
            duration = result.get("total_duration_ms", 0)
            tokens_in = usage.get("input_tokens", 0)
            tokens_out = usage.get("output_tokens", 0)
            cost = usage.get("cost", 0)
            print(f"  → {duration/1000:.1f}s | {tokens_in + tokens_out:,} tokens | ${cost:.4f}")

            if result.get("error"):
                print(f"  ERROR: {result['error']}")

        # Compare runs
        comparison = compare_runs(runs)

        if args.runs > 1:
            print_comparison(comparison, runs)

        all_results.append({
            "question": question,
            "runs": runs,
            "comparison": comparison,
        })

    # Save results (auto-save by default)
    if not args.no_save:
        output_path = Path(args.output) if args.output else get_default_output_path()
        with open(output_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str, ensure_ascii=False)
        print(f"\nResults saved to {output_path}")

    # Final summary
    if len(questions) > 1:
        print(f"\n{'='*60}")
        print("FINAL SUMMARY")
        print(f"{'='*60}")
        passed = sum(1 for r in all_results if r["comparison"].get("all_identical", True))
        print(f"Questions tested: {len(questions)}")
        print(f"Passed: {passed}/{len(questions)}")


if __name__ == "__main__":
    main()
