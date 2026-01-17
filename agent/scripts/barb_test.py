"""
Barb End-to-End Test.

Tests full flow: Barb → QueryBuilder → DataFetcher → Analyst
Handles clarifications automatically by selecting first option.

Run: python -m agent.scripts.barb_test
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Force USE_BARB=true and ANALYST_FAST_MODE=true for this test
os.environ["USE_BARB"] = "true"
os.environ["ANALYST_FAST_MODE"] = "true"

# Reload config to pick up the flag
import importlib
import config
importlib.reload(config)

from agent.graph import TradingGraph
from agent.state import create_initial_input


# =============================================================================
# Test Questions
# =============================================================================

TEST_QUESTIONS = [
    # === Basic statistics ===
    "Statistics for Fridays 2020-2025 where close - low >= 200",
    "Fridays where price closed 200+ points above the low",  # Natural phrasing
    "Statistics for 2024",
    "Average range by month for 2024",

    # === Specific date (triggers clarification) ===
    "may 16 2024",
    "what was jan 10",

    # === Holiday detection ===
    "What happened on December 25 те2024?",  # Christmas - should detect holiday

    # === Top N ===
    "When was the market craziest in 2023?",
    "Find me days with huge moves last year",

    # === Compare ===
    "RTH vs ETH range",
    "Compare Monday and Friday volatility",

    # === Time analysis ===
    "When is high usually formed?",
    "When is low usually formed?",

    # === Concept ===
    "What is gap?",
    "Explain RTH session",

    # === Greeting ===
    "Hello",
    "Hi there",

    # === Not supported ===
    "What happens the day after a gap up > 1%?",
    "Win rate for gap down strategy",
    "Days after 3+ days of growth in a row",

    # === Russian ===
    "Статистика по пятницам 2020-2025 где close - low >= 200",
    "Что было 16 мая 2024?",
    "Топ 10 волатильных дней за 2024",
    "Сравни RTH и ETH по range",
    "Привет",
    "Что такое гэп?",
]


# =============================================================================
# Clarification Auto-Responder
# =============================================================================

def get_clarification_response(suggestions: list[str]) -> str:
    """
    Auto-select response for clarification.

    Strategy: Pick first option (usually the most common/default).
    """
    if not suggestions:
        return "RTH"  # Default fallback

    first = suggestions[0]

    # Extract the key part (e.g., "RTH (09:30-17:00 ET)" → use full string as answer)
    return first


# =============================================================================
# Test Runner
# =============================================================================

def run_barb_test(max_clarification_rounds: int = 3, test_all_clarifications: bool = True):
    """
    Run full end-to-end test with Barb.

    Args:
        max_clarification_rounds: Max rounds per question
        test_all_clarifications: If True, test ALL clarification options, not just first
    """
    print(f"\n{'='*70}")
    print("Barb End-to-End Test")
    print(f"USE_BARB: {config.USE_BARB}")
    print(f"ANALYST_FAST_MODE: {config.ANALYST_FAST_MODE}")
    print(f"Questions: {len(TEST_QUESTIONS)}")
    print(f"Test all clarifications: {test_all_clarifications}")
    print(f"{'='*70}\n")

    graph = TradingGraph()
    results = []

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"[{i}/{len(TEST_QUESTIONS)}] Q: {question[:50]}...")

        result = run_single_question(
            graph,
            question,
            user_id="barb_test",
            session_id=f"test_{i}_{datetime.now().strftime('%H%M%S')}",
            max_rounds=max_clarification_rounds,
        )

        results.append(result)

        # Summary
        status = "✓" if result["success"] else "✗"
        print(f"    {status} {result['final_type']} | {result['total_time_ms']}ms | rounds: {result['rounds']}")
        if result.get("error"):
            print(f"    Error: {result['error']}")

        # If clarification with multiple options — test ALL options
        if test_all_clarifications and result.get("clarification_options"):
            options = result["clarification_options"]
            print(f"    Testing all {len(options)} clarification options...")

            for opt_idx, option in enumerate(options[1:], 2):  # Skip first (already tested)
                opt_result = run_single_question(
                    graph,
                    question,
                    user_id="barb_test",
                    session_id=f"test_{i}_opt{opt_idx}_{datetime.now().strftime('%H%M%S')}",
                    max_rounds=max_clarification_rounds,
                    force_clarification_choice=option,
                )

                opt_result["original_question"] = question
                opt_result["clarification_option_tested"] = option
                results.append(opt_result)

                opt_status = "✓" if opt_result["success"] else "✗"
                print(f"      [{opt_idx}/{len(options)}] {option[:30]}... → {opt_status} {opt_result['total_time_ms']}ms")

        print()

    # Save results
    save_results(results)

    # Print summary
    print_summary(results)

    return results


def run_single_question(
    graph: TradingGraph,
    question: str,
    user_id: str,
    session_id: str,
    max_rounds: int = 3,
    force_clarification_choice: str | None = None,
) -> dict:
    """
    Run a single question through the full flow.

    Handles clarification by auto-responding.

    Args:
        force_clarification_choice: If set, use this instead of auto-selecting first option
    """
    start_time = datetime.now()

    rounds = []
    current_question = question
    final_result = None
    success = False
    error = None
    clarification_options = None  # Store options from first clarification

    for round_num in range(max_rounds):
        round_start = datetime.now()

        try:
            # Run through graph
            result = graph.invoke(
                current_question,
                user_id=user_id,
                session_id=session_id,
            )

            round_time = int((datetime.now() - round_start).total_seconds() * 1000)

            intent = result.get("intent", {})
            intent_type = intent.get("type", "unknown")

            round_data = {
                "round": round_num + 1,
                "question": current_question,
                "intent_type": intent_type,
                "time_ms": round_time,
            }

            # Check if clarification needed
            if intent_type == "clarification":
                suggestions = intent.get("suggestions", [])
                response_text = intent.get("response_text", "")

                round_data["clarification"] = {
                    "text": response_text,
                    "suggestions": suggestions,
                }

                # Store options from first clarification for testing all options later
                if round_num == 0 and suggestions:
                    clarification_options = suggestions

                if suggestions:
                    # Use forced choice or auto-select first option
                    if force_clarification_choice and round_num == 0:
                        selected = force_clarification_choice
                    else:
                        selected = get_clarification_response(suggestions)
                    round_data["selected"] = selected
                    # Combine original question with clarification choice
                    current_question = f"{question}: {selected}"
                    rounds.append(round_data)
                    continue
                else:
                    # No suggestions, can't continue
                    round_data["error"] = "No suggestions provided"
                    rounds.append(round_data)
                    error = "Clarification without suggestions"
                    break

            # Not clarification — we have final result
            rounds.append(round_data)
            final_result = {
                "intent": intent,
                "response": result.get("response", ""),
                "data": result.get("data"),
                "sql_query": result.get("sql_query"),
                "usage": result.get("usage"),
            }

            # Check if we got actual data response
            if intent_type == "data" and result.get("response"):
                success = True
            elif intent_type in ("chitchat", "concept", "out_of_scope"):
                success = True  # These are valid end states

            break

        except Exception as e:
            error = str(e)
            rounds.append({
                "round": round_num + 1,
                "question": current_question,
                "error": error,
            })
            break

    total_time = int((datetime.now() - start_time).total_seconds() * 1000)

    return {
        "original_question": question,
        "rounds": len(rounds),
        "round_details": rounds,
        "final_type": rounds[-1].get("intent_type", "error") if rounds else "error",
        "final_result": final_result,
        "success": success,
        "error": error,
        "total_time_ms": total_time,
        "clarification_options": clarification_options,  # For testing all options
    }


# =============================================================================
# Results Saving
# =============================================================================

def save_results(results: list[dict]):
    """Save results to JSON file in agent/docs/logs/."""
    log_dir = Path(__file__).parent.parent / "docs" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"barb_e2e_{timestamp}.json"

    # Prepare output
    output = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "total_questions": len(results),
            "successful": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "use_barb": config.USE_BARB,
            "analyst_fast_mode": config.ANALYST_FAST_MODE,
        },
        "results": results,
    }

    # Clean up non-serializable data
    def clean_for_json(obj):
        if isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_for_json(v) for v in obj]
        elif hasattr(obj, '__dict__'):
            return str(obj)
        else:
            return obj

    output = clean_for_json(output)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'='*70}")
    print(f"Results saved to: {log_file}")
    print(f"{'='*70}\n")


def print_summary(results: list[dict]):
    """Print test summary."""
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    # Count by type
    by_type = {}
    for r in results:
        t = r["final_type"]
        by_type[t] = by_type.get(t, 0) + 1

    print(f"\nBy final type:")
    for t, count in sorted(by_type.items()):
        print(f"  {t}: {count}")

    # Success rate
    success = sum(1 for r in results if r["success"])
    total = len(results)
    print(f"\nSuccess rate: {success}/{total} ({success/total*100:.1f}%)")

    # Average time
    avg_time = sum(r["total_time_ms"] for r in results) / total
    print(f"Average time: {avg_time:.0f}ms")

    # Clarification rounds
    multi_round = [r for r in results if r["rounds"] > 1]
    if multi_round:
        print(f"\nQuestions with clarification: {len(multi_round)}")
        for r in multi_round:
            print(f"  - {r['original_question'][:40]}... ({r['rounds']} rounds)")

    # Errors
    errors = [r for r in results if r.get("error")]
    if errors:
        print(f"\nErrors: {len(errors)}")
        for r in errors:
            print(f"  - {r['original_question'][:40]}...")
            print(f"    {r['error']}")

    print(f"\n{'='*70}\n")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import sys

    max_rounds = 3
    for arg in sys.argv:
        if arg.startswith("--max-rounds="):
            max_rounds = int(arg.split("=")[1])

    run_barb_test(max_clarification_rounds=max_rounds)
