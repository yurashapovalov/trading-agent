"""
Integration test — runs real questions through real graph.

Tests the actual production code path.
Saves results to file for analysis.

Usage:
    python -m agent.tests.full_flow_test
    python -m agent.tests.full_flow_test "custom question here"
"""

import json
import sys
import os
from datetime import datetime
from uuid import uuid4

from langchain_core.messages import HumanMessage

from agent.graph import build_graph


# Test cases with expected behavior
TEST_CASES = [
    # Data queries - should parse correctly and return data
    {
        "question": "волатильность за декабрь 2024",
        "expect": {"lang": "ru", "route": "executor", "period_type": "month"},
    },
    {
        "question": "volatility for December 2024",
        "expect": {"lang": "en", "route": "executor", "period_type": "month"},
    },
    {
        "question": "топ 5 волатильных дней 2024",
        "expect": {"lang": "ru", "route": "executor", "top_n": 5},
    },
    {
        "question": "top 3 volatile days in 2024",
        "expect": {"lang": "en", "route": "executor", "top_n": 3},
    },
    {
        "question": "волатильность за 2099",
        "expect": {"lang": "ru", "route": "executor", "row_count": 0},
    },

    # Chitchat - should route to responder
    {
        "question": "привет",
        "expect": {"lang": "ru", "intent": "chitchat"},
    },
    {
        "question": "hello",
        "expect": {"lang": "en", "intent": "chitchat"},
    },
]


def run_single_test(graph, question: str) -> dict:
    """Run single question through graph, return full state."""
    initial_state = {
        "messages": [HumanMessage(content=question)],
        "session_id": str(uuid4()),
        "user_id": "test-user",
        "agents_used": [],
        "step_number": 0,
    }

    result = graph.invoke(initial_state)

    return {
        "question": question,
        "intent": result.get("intent"),
        "lang": result.get("lang"),
        "question_en": result.get("question_en"),
        "agents_used": result.get("agents_used", []),
        "parsed_query": result.get("parsed_query"),
        "row_count": result.get("data", {}).get("row_count") if result.get("data") else None,
        "response": result.get("response"),
    }


def check_expectations(result: dict, expect: dict) -> list[str]:
    """Check if result matches expectations. Returns list of failures."""
    failures = []

    if "lang" in expect and result.get("lang") != expect["lang"]:
        failures.append(f"lang: expected {expect['lang']}, got {result.get('lang')}")

    if "intent" in expect and result.get("intent") != expect["intent"]:
        failures.append(f"intent: expected {expect['intent']}, got {result.get('intent')}")

    if "route" in expect:
        agents = result.get("agents_used", [])
        if expect["route"] == "executor" and "executor" not in agents:
            failures.append(f"route: expected executor, got {agents}")
        if expect["route"] == "clarifier" and "clarifier" not in agents:
            failures.append(f"route: expected clarifier, got {agents}")

    pq = result.get("parsed_query", {})

    if "period_type" in expect:
        period = pq.get("period")
        actual_type = period.get("type") if period else None
        if actual_type != expect["period_type"]:
            failures.append(f"period.type: expected {expect['period_type']}, got {actual_type}")

    if "top_n" in expect:
        if pq.get("top_n") != expect["top_n"]:
            failures.append(f"top_n: expected {expect['top_n']}, got {pq.get('top_n')}")

    if "row_count" in expect:
        if result.get("row_count") != expect["row_count"]:
            failures.append(f"row_count: expected {expect['row_count']}, got {result.get('row_count')}")

    return failures


def run_all_tests():
    """Run all test cases."""
    print("Building graph...")
    graph = build_graph().compile()

    results = []
    passed = 0
    failed = 0

    for i, test in enumerate(TEST_CASES, 1):
        question = test["question"]
        expect = test["expect"]

        print(f"\n{'='*60}")
        print(f"TEST {i}: {question}")
        print("="*60)

        try:
            result = run_single_test(graph, question)

            # Check expectations
            failures = check_expectations(result, expect)

            if failures:
                print(f"FAILED:")
                for f in failures:
                    print(f"   - {f}")
                failed += 1
            else:
                print(f"PASSED")
                passed += 1

            # Show details
            print(f"   Lang: {result['lang']}")
            print(f"   Intent: {result['intent']}")
            print(f"   Agents: {' → '.join(result['agents_used'])}")
            if result['parsed_query']:
                pq = result['parsed_query']
                print(f"   Period: {pq.get('period')}")
                print(f"   Metric: {pq.get('metric')}")
                print(f"   Top N: {pq.get('top_n')}")
            if result['row_count'] is not None:
                print(f"   Row count: {result['row_count']}")
            print(f"   Response: {result['response'][:100]}...")

            results.append({
                "test_number": i,
                "question": question,
                "expect": expect,
                "result": result,
                "failures": failures,
                "passed": len(failures) == 0,
            })

        except Exception as e:
            print(f"ERROR: {e}")
            failed += 1
            results.append({
                "test_number": i,
                "question": question,
                "error": str(e),
                "passed": False,
            })

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("="*60)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("agent/tests/results", exist_ok=True)
    output_file = f"agent/tests/results/integration_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "passed": passed,
            "failed": failed,
            "results": results,
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f"Results saved to: {output_file}")
    return passed, failed


def run_custom_question(question: str):
    """Run a single custom question for debugging."""
    print(f"Question: {question}")
    print("="*60)

    graph = build_graph().compile()
    result = run_single_test(graph, question)

    print(f"\nIntent: {result['intent']}")
    print(f"Lang: {result['lang']}")
    print(f"Question EN: {result['question_en']}")
    print(f"Agents: {' → '.join(result['agents_used'])}")

    if result['parsed_query']:
        print(f"\nParsed Query:")
        print(json.dumps(result['parsed_query'], ensure_ascii=False, indent=2))

    if result['row_count'] is not None:
        print(f"\nRow count: {result['row_count']}")

    print(f"\nResponse:\n{result['response']}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Custom question mode
        question = " ".join(sys.argv[1:])
        run_custom_question(question)
    else:
        # Run all tests
        run_all_tests()
