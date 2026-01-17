#!/usr/bin/env python3
"""
Test conversation flow with session persistence.

Tests multi-turn conversations where the system asks for clarification
and user responds with one of the suggestions.

Usage:
    python agent/scripts/test_conversation.py
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.graph import TradingGraph


def run_conversation(messages: list[str], session_id: str = "conv_test") -> list[dict]:
    """
    Run a multi-turn conversation through TradingGraph.

    Args:
        messages: List of user messages in order
        session_id: Session ID to maintain conversation context

    Returns:
        List of results for each turn
    """
    graph = TradingGraph()
    results = []

    for i, message in enumerate(messages):
        print(f"\n{'='*60}")
        print(f"Turn {i+1}: {message}")
        print(f"{'='*60}")

        turn_result = {
            "turn": i + 1,
            "user_message": message,
            "steps": [],
            "response": None,
            "suggestions": None,
            "debug": None,
        }

        start_time = time.time()

        for event in graph.stream_sse(
            question=message,
            user_id="test_user",
            session_id=session_id,  # Same session for all turns
        ):
            event_type = event.get("type")

            if event_type == "step_start":
                agent = event.get("agent")
                print(f"  [{agent}] Starting...")
                turn_result["steps"].append({
                    "agent": agent,
                    "status": "running",
                })

            elif event_type == "step_end":
                agent = event.get("agent")
                output = event.get("output", {})
                print(f"  [{agent}] Done in {event.get('duration_ms', 0)}ms")

                # Update step
                for step in turn_result["steps"]:
                    if step["agent"] == agent and step["status"] == "running":
                        step["status"] = "completed"
                        step["output"] = output
                        break

                # Extract debug info from understander
                if agent == "understander":
                    intent = output.get("intent", {})
                    turn_result["debug"] = intent.get("_debug", {})
                    print(f"    [Debug] {turn_result['debug']}")

            elif event_type == "text_delta":
                content = event.get("content", "")
                if turn_result["response"] is None:
                    turn_result["response"] = ""
                turn_result["response"] += content

            elif event_type == "suggestions":
                turn_result["suggestions"] = event.get("suggestions", [])

        turn_result["duration_ms"] = int((time.time() - start_time) * 1000)

        print(f"\n  Response: {turn_result['response'][:100] if turn_result['response'] else 'N/A'}...")
        if turn_result["suggestions"]:
            print(f"  Suggestions: {turn_result['suggestions']}")

        results.append(turn_result)

    return results


def test_clarification_flow():
    """Test: Question triggers clarification → User selects option → System responds with data."""

    print("\n" + "#"*70)
    print("# TEST: Clarification → Follow-up Flow")
    print("#"*70)

    # Conversation:
    # 1. Question about specific day (ambiguous → clarification)
    # 2. User selects "RTH"

    messages = [
        "что было 16 мая 2023 в течении дня",  # Should trigger clarification
        "RTH",  # Follow-up selecting RTH session
    ]

    results = run_conversation(messages, session_id=f"clarification_test_{int(time.time())}")

    # Verify turn 1: Should be clarification
    turn1 = results[0]
    print(f"\n--- Turn 1 Analysis ---")

    understander_step = next((s for s in turn1["steps"] if s["agent"] == "understander"), None)
    if understander_step:
        intent = understander_step.get("output", {}).get("intent", {})
        intent_type = intent.get("type")
        print(f"  Intent type: {intent_type}")

        if intent_type == "clarification":
            print("  ✓ Turn 1: Clarification triggered correctly")
        else:
            print(f"  ✗ Turn 1: Expected 'clarification', got '{intent_type}'")

    if turn1["suggestions"]:
        print(f"  Suggestions: {turn1['suggestions']}")

    # Verify turn 2: Should have context and return data
    turn2 = results[1]
    print(f"\n--- Turn 2 Analysis ---")

    debug = turn2.get("debug", {})
    print(f"  has_history_context: {debug.get('has_history_context')}")
    print(f"  chat_history_length: {debug.get('chat_history_length')}")
    print(f"  messages_count: {debug.get('messages_count')}")

    if debug.get("has_history_context"):
        print("  ✓ Turn 2: History context preserved")
    else:
        print("  ✗ Turn 2: History context NOT preserved")

    understander_step2 = next((s for s in turn2["steps"] if s["agent"] == "understander"), None)
    if understander_step2:
        intent2 = understander_step2.get("output", {}).get("intent", {})
        intent_type2 = intent2.get("type")
        print(f"  Intent type: {intent_type2}")

        if intent_type2 == "data":
            query_spec = intent2.get("query_spec", {})
            filters = query_spec.get("filters", {})
            session = filters.get("session")
            print(f"  Session resolved: {session}")

            if session == "RTH":
                print("  ✓ Turn 2: RTH session correctly extracted from follow-up")
            else:
                print(f"  ✗ Turn 2: Expected session='RTH', got '{session}'")

    # Check if data was fetched (indicates full pipeline ran)
    data_step = next((s for s in turn2["steps"] if s["agent"] == "data_fetcher"), None)
    if data_step:
        output = data_step.get("output", {})
        summary = output.get("summary", {})
        row_count = summary.get("row_count", 0)
        print(f"  Data fetched: {row_count} rows")
        if row_count > 0:
            print("  ✓ Turn 2: Data pipeline completed successfully")

    return results


def test_all_clarification_options():
    """Test all three clarification options: RTH, ETH, Calendar day."""

    print("\n" + "#"*70)
    print("# TEST: All Clarification Options")
    print("#"*70)

    options = ["RTH", "ETH", "Calendar day"]

    for option in options:
        print(f"\n{'='*60}")
        print(f"Testing option: {option}")
        print(f"{'='*60}")

        messages = [
            "что было 29 ноября 2024",  # Black Friday - early close
            option,
        ]

        results = run_conversation(messages, session_id=f"option_test_{option}_{int(time.time())}")

        turn2 = results[1]
        understander_step = next((s for s in turn2["steps"] if s["agent"] == "understander"), None)

        if understander_step:
            intent = understander_step.get("output", {}).get("intent", {})
            query_spec = intent.get("query_spec", {})
            filters = query_spec.get("filters", {})

            print(f"  → Session: {filters.get('session')}")
            print(f"  → Period: {filters.get('period_start')} to {filters.get('period_end')}")

            # Check data fetched
            data_step = next((s for s in turn2["steps"] if s["agent"] == "data_fetcher"), None)
            if data_step:
                output = data_step.get("output", {})
                row_count = output.get("summary", {}).get("row_count", 0)
                print(f"  → Data rows: {row_count}")


if __name__ == "__main__":
    # Run tests
    test_clarification_flow()

    print("\n" + "="*70)
    print("Done!")
