"""
Barb End-to-End Test.

Tests full flow: Barb → QueryBuilder → DataFetcher → Analyst
Handles clarifications automatically by selecting first option.

Run: python -m agent.scripts.barb_test
     python -m agent.scripts.barb_test --fast  # Skip Analyst (faster)
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Force ANALYST_FAST_MODE=true for this test
os.environ["ANALYST_FAST_MODE"] = "true"

# Reload config to pick up the flag
import importlib
import config
importlib.reload(config)

from agent.graph import TradingGraph
from agent.state import create_initial_input

# Fast mode components (skip Analyst)
from agent.agents.barb import Barb
from agent.query_builder import QueryBuilder
from agent.agents.data_fetcher import DataFetcher
from agent.agents.responder import Responder


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

    # === Hourly grouping (requires MINUTES source) ===
    "Volatility by hour",
    "Какая волатильность по часам?",

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

    # === Events ===
    "what's the volatility on expiration days?",  # OPEX — calculable
    "how does NQ behave on NFP?",                 # NFP — calculable
    "volatility on FOMC days",                    # FOMC — not supported (no calendar)
    "статистика по дням экспирации",              # Russian + OPEX

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
# Fast Mode (skip Analyst)
# =============================================================================

def run_fast_question(
    barb: Barb,
    query_builder: QueryBuilder,
    data_fetcher: DataFetcher,
    responder: Responder,
    question: str,
    max_rounds: int = 3,
    force_clarification_choice: str | None = None,
) -> dict:
    """
    Run question through Barb → Responder → QueryBuilder → DataFetcher (skip Analyst).

    Faster for testing — validates parsing, responder preview, and data fetching.
    """
    start_time = datetime.now()
    chat_history = ""
    current_question = question
    rounds = []
    clarification_options = None  # Store first clarification options
    clarification_state = None  # Track state between clarification rounds

    for round_num in range(max_rounds):
        round_start = datetime.now()

        try:
            # Step 1: Barb (Parser + Composer) — pass state for multi-round context
            barb_result = barb.ask(current_question, chat_history=chat_history, state=clarification_state)
            round_time = int((datetime.now() - round_start).total_seconds() * 1000)

            round_data = {
                "round": round_num + 1,
                "question": current_question,
                "barb_type": barb_result.type,
                "time_ms": round_time,
                "parser_output": barb_result.parser_output,
            }

            # Handle different result types
            if barb_result.type == "clarification":
                options = barb_result.options or []

                # Build state for Responder
                responder_state = {
                    "messages": [{"role": "user", "content": current_question}],
                    "intent": {
                        "type": "clarification",
                        "field": barb_result.field,
                        "suggestions": options,
                        "parser_output": barb_result.parser_output,
                        "symbol": "NQ",
                    },
                }

                # Call Responder for natural clarification text
                responder_result = responder(responder_state)
                responder_response = responder_result.get("response", barb_result.summary)

                round_data["clarification"] = {
                    "text": responder_response,
                    "suggestions": options,
                }
                round_data["responder_response"] = responder_response

                # Store options from first clarification
                if round_num == 0 and options:
                    clarification_options = options

                if options:
                    # Use forced choice or auto-select first
                    if force_clarification_choice and round_num == 0:
                        selected = force_clarification_choice
                    else:
                        selected = get_clarification_response(options)
                    round_data["selected"] = selected
                    chat_history = f"User: {current_question}\nAssistant: {responder_response}"
                    clarification_state = barb_result.state  # Preserve state for next round
                    current_question = selected
                    rounds.append(round_data)
                    continue
                elif "year" in responder_response.lower() or "год" in responder_response.lower():
                    # Year clarification without buttons — simulate typing year
                    selected = "2024"
                    round_data["selected"] = selected
                    chat_history = f"User: {current_question}\nAssistant: {responder_response}"
                    clarification_state = barb_result.state  # Preserve state for next round
                    current_question = selected
                    rounds.append(round_data)
                    continue
                else:
                    round_data["error"] = "Clarification without suggestions"
                    rounds.append(round_data)
                    break

            elif barb_result.type in ("greeting", "concept", "not_supported"):
                # Non-data types — call Responder for natural response
                intent_type = {"greeting": "chitchat", "concept": "concept", "not_supported": "out_of_scope"}[barb_result.type]

                # Build state for Responder
                responder_state = {
                    "messages": [{"role": "user", "content": current_question}],
                    "intent": {
                        "type": intent_type,
                        "parser_output": barb_result.parser_output,
                        "symbol": "NQ",
                        "concept": barb_result.concept if barb_result.type == "concept" else None,
                        "response_text": barb_result.reason if barb_result.type == "not_supported" else None,
                    },
                }

                # Call Responder
                responder_result = responder(responder_state)
                responder_response = responder_result.get("response", "")

                round_data["responder_response"] = responder_response
                rounds.append(round_data)

                return {
                    "original_question": question,
                    "rounds": len(rounds),
                    "round_details": rounds,
                    "final_type": intent_type,
                    "success": True,
                    "error": None,
                    "total_time_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                    "responder_response": responder_response,
                    "parser_output": barb_result.parser_output,
                    "clarification_options": clarification_options,
                }

            elif barb_result.type == "query":
                # Data query — call Responder for preview, then build SQL and fetch data
                spec = barb_result.spec

                # Build state for Responder (before data fetch)
                responder_state = {
                    "messages": [{"role": "user", "content": current_question}],
                    "intent": {
                        "type": "data",
                        "parser_output": barb_result.parser_output,
                        "symbol": spec.symbol if spec else "NQ",
                        "holiday_info": barb_result.holiday_info,
                        "event_info": barb_result.event_info,
                        "query_spec": {
                            "special_op": spec.special_op.value if spec else None,
                            "source": spec.source.value if spec else None,
                            "grouping": spec.grouping.value if spec else None,
                        },
                    },
                }

                # Call Responder for preview and title
                responder_result = responder(responder_state)
                responder_response = responder_result.get("response", "")
                data_title = responder_result.get("data_title")

                # Build SQL and fetch data
                sql = query_builder.build(spec)
                state = {
                    "sql_query": sql,
                    "intent": {"query_spec": {}},
                }
                fetch_result = data_fetcher(state)
                data = fetch_result.get("data", {})

                round_data["intent_type"] = "data"
                round_data["sql_preview"] = sql[:100] if sql else None
                round_data["responder_response"] = responder_response
                round_data["data_title"] = data_title
                rounds.append(round_data)

                total_time = int((datetime.now() - start_time).total_seconds() * 1000)

                return {
                    "original_question": question,
                    "rounds": len(rounds),
                    "round_details": rounds,
                    "final_type": "data",
                    "success": True,
                    "error": None,
                    "total_time_ms": total_time,
                    "row_count": data.get("row_count", 0),
                    "columns": data.get("columns", []),
                    "sql_query": sql,
                    "parser_output": barb_result.parser_output,
                    "responder_response": responder_response,
                    "data_title": data_title,
                    "clarification_options": clarification_options,
                }

        except Exception as e:
            rounds.append({
                "round": round_num + 1,
                "question": current_question,
                "error": str(e),
            })
            break

    total_time = int((datetime.now() - start_time).total_seconds() * 1000)

    return {
        "original_question": question,
        "rounds": len(rounds),
        "round_details": rounds,
        "final_type": rounds[-1].get("intent_type", "error") if rounds else "error",
        "success": False,
        "error": rounds[-1].get("error") if rounds else "Unknown error",
        "total_time_ms": total_time,
    }


# =============================================================================
# Test Runner
# =============================================================================

def run_barb_test(
    max_clarification_rounds: int = 3,
    test_all_clarifications: bool = True,
    fast_mode: bool = False,
):
    """
    Run full end-to-end test with Barb.

    Args:
        max_clarification_rounds: Max rounds per question
        test_all_clarifications: If True, test ALL clarification options, not just first
        fast_mode: If True, skip Analyst (Barb → QueryBuilder → DataFetcher only)
    """
    mode_str = "FAST (no Analyst)" if fast_mode else "FULL (with Analyst)"
    print(f"\n{'='*70}")
    print(f"Barb End-to-End Test — {mode_str}")
    print(f"USE_BARB: {config.USE_BARB}")
    print(f"Questions: {len(TEST_QUESTIONS)}")
    print(f"Test all clarifications: {test_all_clarifications}")
    print(f"{'='*70}\n")

    # Initialize components
    if fast_mode:
        barb = Barb()
        query_builder = QueryBuilder()
        data_fetcher = DataFetcher()
        responder = Responder()
        graph = None
    else:
        barb = None
        query_builder = None
        data_fetcher = None
        responder = None
        graph = TradingGraph()

    results = []

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"[{i}/{len(TEST_QUESTIONS)}] Q: {question[:50]}...")

        session_id = f"test_{i}_{datetime.now().strftime('%H%M%S')}"

        if fast_mode:
            result = run_fast_question(
                barb, query_builder, data_fetcher, responder,
                question,
                max_rounds=max_clarification_rounds,
            )
        else:
            result = run_single_question(
                graph,
                question,
                user_id="barb_test",
                session_id=session_id,
                max_rounds=max_clarification_rounds,
            )

        results.append(result)

        # Summary
        status = "✓" if result["success"] else "✗"
        rows_info = f", rows={result.get('row_count', '?')}" if result.get("row_count") else ""
        title_info = f", title=\"{result.get('data_title')}\"" if result.get("data_title") else ""
        print(f"    {status} {result['final_type']} | {result['total_time_ms']}ms{rows_info}{title_info}")

        # Show Responder preview (first 80 chars)
        responder_response = result.get("responder_response", "")
        if responder_response:
            preview = responder_response[:80].replace("\n", " ")
            print(f"    Responder: {preview}...")

        if result.get("error"):
            print(f"    Error: {result['error']}")

        # If clarification with multiple options — test ALL options
        if test_all_clarifications and result.get("clarification_options"):
            options = result["clarification_options"]
            print(f"    Testing all {len(options)} clarification options...")

            for opt_idx, option in enumerate(options[1:], 2):  # Skip first (already tested)
                if fast_mode:
                    opt_result = run_fast_question(
                        barb, query_builder, data_fetcher, responder,
                        question,
                        max_rounds=max_clarification_rounds,
                        force_clarification_choice=option,
                    )
                else:
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
                rows_info = f", rows={opt_result.get('row_count', '?')}" if opt_result.get("row_count") else ""
                print(f"      [{opt_idx}/{len(options)}] {option[:30]}... → {opt_status} {opt_result['total_time_ms']}ms{rows_info}")

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
                    # Send just the selection — checkpointer preserves history
                    current_question = selected
                    rounds.append(round_data)
                    continue
                else:
                    # No suggestions — check if it's a year/text clarification
                    # Simulate user typing a year
                    if "year" in response_text.lower() or "год" in response_text.lower():
                        selected = "2024"
                        round_data["selected"] = selected
                        current_question = selected
                        rounds.append(round_data)
                        continue
                    else:
                        # Unknown clarification without suggestions
                        round_data["error"] = "No suggestions provided"
                        rounds.append(round_data)
                        error = "Clarification without suggestions"
                        break

            # Not clarification — we have final result
            rounds.append(round_data)
            final_result = {
                "intent": intent,
                "response": result.get("response", ""),
                "data": result.get("full_data") or result.get("data"),  # Prefer full_data
                "sql_query": result.get("sql_query"),
                "usage": result.get("usage"),
                "data_title": result.get("data_title"),  # From responder node
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
    fast_mode = False

    for arg in sys.argv:
        if arg.startswith("--max-rounds="):
            max_rounds = int(arg.split("=")[1])
        elif arg == "--fast":
            fast_mode = True

    run_barb_test(max_clarification_rounds=max_rounds, fast_mode=fast_mode)
