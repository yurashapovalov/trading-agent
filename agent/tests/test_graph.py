"""
Test graph flow.

Run: python -m agent.tests.test_graph
"""

import json
import re
from datetime import date, datetime
from pathlib import Path
from dataclasses import dataclass, field

from agent.types import ParsedQuery, ClarificationOutput
from agent.agents import Parser, Clarifier, present
from agent.executor import execute


def validate_parsed(question: str, parsed: ParsedQuery) -> ParsedQuery:
    """Post-validate: если года нет в вопросе — уточняем период."""
    has_year = bool(re.search(r'\b20[0-2]\d\b', question))

    if not has_year and parsed.intent == "data":
        unclear = list(parsed.unclear or [])
        if "year" not in unclear and "period" not in unclear:
            unclear.append("year")
        parsed.unclear = unclear

    return parsed


# =============================================================================
# Conversation State
# =============================================================================

@dataclass
class ConversationState:
    """Tracks multi-turn conversation."""
    messages: list[dict] = field(default_factory=list)  # [{role, content}, ...]
    last_parsed: dict | None = None  # Last parser output
    waiting_for: str | None = None  # What we're waiting for: "metric", "year", etc.
    original_question: str | None = None  # Original question before clarification

    def add_user(self, text: str):
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, text: str):
        self.messages.append({"role": "assistant", "content": text})

    def get_history_str(self) -> str:
        """Format history for prompts."""
        lines = []
        for m in self.messages[-6:]:  # Last 6 messages
            role = "User" if m["role"] == "user" else "Assistant"
            lines.append(f"{role}: {m['content']}")
        return "\n".join(lines)

    def clear(self):
        self.messages = []
        self.last_parsed = None
        self.waiting_for = None
        self.original_question = None


# =============================================================================
# Agents
# =============================================================================

def run_parser(question: str) -> ParsedQuery:
    """Run Parser agent."""
    parser = Parser()
    result = parser.parse(question, today=date.today())

    # Post-validate: если года нет — уточняем
    parsed = validate_parsed(question, result.query)

    return parsed


def run_clarification(question: str, parsed: dict, previous_context: str = "", mode: str = "asking", debug: bool = False) -> ClarificationOutput:
    """Run Clarifier agent."""
    if debug:
        print(f"\n  [DEBUG Clarifier]")
        print(f"  question: {question}")
        print(f"  parsed.period: {parsed.get('period')}")
        print(f"  parsed.unclear: {parsed.get('unclear')}")
        print(f"  parsed.what: {parsed.get('what')}")
        print(f"  previous_context: {previous_context}")

    clarifier = Clarifier()
    result = clarifier.clarify(
        question=question,
        parsed=parsed,
        previous_context=previous_context,
    )

    if debug:
        print(f"  → response: {result.response}")
        print(f"  → clarified_query: {result.clarified_query}")

    return result


def run_executor(parsed: ParsedQuery) -> dict:
    """Run Executor."""
    return execute(parsed, symbol="NQ", today=date.today())


# =============================================================================
# Flow
# =============================================================================

def process_question(question: str, state: ConversationState) -> dict:
    """
    Process single question through the flow with conversation state.

    Returns dict with all intermediate results.
    """
    result = {
        "question": question,
        "steps": [],
    }

    # Add user message to history
    state.add_user(question)

    # Check if we're in clarification flow (waiting for answer)
    if state.waiting_for:
        # User is answering a clarification question
        # Pass full conversation history so LLM can understand context
        clarification = run_clarification(
            question=question,
            parsed=state.last_parsed,
            previous_context=state.get_history_str(),
            mode="confirming",
            debug=True,
        )
        result["steps"].append("clarification_confirm")
        result["clarification"] = {
            "response": clarification.response,
            "clarified_query": clarification.clarified_query,
        }

        state.add_assistant(clarification.response)

        if clarification.clarified_query:
            # Got clarified query, now parse it
            result["route"] = "clarification → parser → executor"
            state.waiting_for = None

            parsed = run_parser(clarification.clarified_query)
            result["parsed"] = parsed.model_dump()
            result["steps"].append("parser")
            state.last_parsed = parsed.model_dump()

            # Continue to executor
            if not parsed.unclear:
                exec_result = run_executor(parsed)
                result["executor"] = {
                    "intent": exec_result.get("intent"),
                    "operation": exec_result.get("operation"),
                    "row_count": exec_result.get("row_count"),
                    "result": exec_result.get("result"),
                }
                result["steps"].append("executor")

                # Build data response using DataResponder
                data_response = present(
                    state.original_question or clarification.clarified_query,
                    exec_result,
                    symbol="NQ"
                )
                result["response"] = data_response
                state.add_assistant(data_response)
                state.original_question = None
                return result

        result["response"] = clarification.response
        return result

    # Fresh question - run parser
    parsed = run_parser(question)
    result["parsed"] = parsed.model_dump()
    result["steps"].append("parser")
    state.last_parsed = parsed.model_dump()

    intent = parsed.intent
    unclear = parsed.unclear or []

    # Route: Chitchat
    if intent == "chitchat":
        result["route"] = "chitchat"
        response = "Привет! Чем могу помочь с анализом NQ?"
        result["response"] = response
        state.add_assistant(response)
        return result

    # Route: Concept
    if intent == "concept":
        result["route"] = "concept"
        response = f"TODO: объяснить {parsed.what}"
        result["response"] = response
        state.add_assistant(response)
        return result

    # Route: Clarification needed
    if unclear:
        result["route"] = "clarification"
        state.original_question = question
        state.waiting_for = unclear[0]  # e.g., "metric"

        clarification = run_clarification(question, parsed.model_dump(), mode="asking")
        result["clarification"] = {
            "response": clarification.response,
            "clarified_query": clarification.clarified_query,
        }
        result["response"] = clarification.response
        result["steps"].append("clarification_ask")
        state.add_assistant(clarification.response)
        return result

    # Route: Executor
    result["route"] = "executor"
    exec_result = run_executor(parsed)
    result["executor"] = {
        "intent": exec_result.get("intent"),
        "operation": exec_result.get("operation"),
        "row_count": exec_result.get("row_count"),
        "result": exec_result.get("result"),
    }
    result["steps"].append("executor")

    # Build response using DataResponder
    response = present(question, exec_result, symbol="NQ")
    result["response"] = response
    state.add_assistant(response)
    return result


# =============================================================================
# Tests
# =============================================================================

# Single questions (each starts fresh)
SINGLE_TESTS = [
    "привет",
    "что такое OPEX",
    "волатильность за 2024",
    "топ 5 самых волатильных дней 2024",
]

# Conversation tests (multi-turn)
CONVERSATION_TESTS = [
    # Test 1: Basic clarification — metric
    [
        "статистика за 2024",  # → unclear: metric
        "доходность",          # → clarified, executor
    ],

    # Test 2: User asks what's available
    [
        "как прошёл год",      # → unclear: metric (assumes current year)
        "а что можно?",        # → list options
        "волатильность",       # → clarified, executor
    ],

    # Test 3: Win rate request
    [
        "покажи данные за 2023",  # → unclear: metric
        "win rate",               # → clarified, executor
    ],

    # Test 4: Comparison request
    [
        "сравни года",           # → unclear: which years
        "2023 и 2024",           # → clarified, executor
    ],

    # Test 5: Specific date — missing year
    [
        "что было 10 января",    # → unclear: year
        "2024",                  # → clarified, executor
    ],

    # Test 6: Top N query
    [
        "топ дней",              # → unclear: what metric, how many
        "5 самых волатильных",   # → clarified
        "за 2024",               # → executor
    ],

    # Test 7: Seasonality
    [
        "какой день недели лучший",  # → unclear: metric, period
        "по доходности",             # → still unclear: period
        "за последние 3 года",       # → clarified, executor
    ],

    # Test 8: Quick chitchat then data
    [
        "привет",                # → chitchat
        "волатильность 2024",    # → executor (no clarification needed)
    ],

    # Test 9: Concept then data
    [
        "что такое OPEX",        # → concept
        "покажи OPEX за 2024",   # → executor
    ],

    # Test 10: Vague "how was" questions
    [
        "как прошёл январь",     # → unclear: metric, year
        "2024",                  # → still unclear: metric
        "доходность",            # → clarified, executor
    ],

    # Test 11: Volume request
    [
        "объём торгов",          # → unclear: period
        "за прошлый месяц",      # → clarified, executor
    ],

    # Test 12: Multiple unclear fields
    [
        "покажи статистику",     # → unclear: metric, period
        "волатильность",         # → still unclear: period
        "2024",                  # → clarified, executor
    ],

    # Test 13: User changes mind
    [
        "статистика за 2024",    # → unclear: metric
        "хотя нет, лучше 2023",  # → still unclear: metric, new period
        "доходность",            # → clarified, executor
    ],

    # Test 14: English user
    [
        "show me stats",         # → unclear: metric, period
        "volatility",            # → still unclear: period
        "2024",                  # → clarified, executor
    ],
]


def run_single_tests(save_to_file: bool = True):
    """Run single question tests (no conversation)."""
    results = []

    print("=" * 70)
    print("SINGLE QUESTION TESTS")
    print("=" * 70)

    for q in SINGLE_TESTS:
        state = ConversationState()  # Fresh state each time
        print(f"\n» {q}")
        try:
            r = process_question(q, state)
            results.append(r)

            print(f"  Route: {r.get('route')}")
            print(f"  Steps: {r.get('steps')}")
            print(f"  Response: {r.get('response', '')[:80]}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"question": q, "error": str(e)})

    return results


def run_conversation_tests(save_to_file: bool = True):
    """Run multi-turn conversation tests."""
    all_results = []

    print("\n" + "=" * 70)
    print("CONVERSATION TESTS")
    print("=" * 70)

    for i, conversation in enumerate(CONVERSATION_TESTS):
        print(f"\n--- Conversation {i + 1} ---")
        state = ConversationState()  # One state per conversation
        conv_results = []

        for q in conversation:
            print(f"\nUser: {q}")
            try:
                r = process_question(q, state)
                conv_results.append(r)

                print(f"Assistant: {r.get('response', '')}")
                print(f"  [steps: {r.get('steps')}, waiting: {state.waiting_for}]")

            except Exception as e:
                print(f"  ERROR: {e}")
                conv_results.append({"question": q, "error": str(e)})

        all_results.append({"conversation": i + 1, "turns": conv_results})

    if save_to_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(__file__).parent / f"conv_{timestamp}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n\nResults saved to: {output_path}")

    return all_results


def run_tests(save_to_file: bool = True):
    """Run all tests."""
    single = run_single_tests(save_to_file=False)
    conversations = run_conversation_tests(save_to_file=False)

    results = {
        "single_tests": single,
        "conversation_tests": conversations,
    }

    if save_to_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(__file__).parent / f"results_{timestamp}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n\nResults saved to: {output_path}")

    return results


# =============================================================================
# Interactive mode
# =============================================================================

def interactive():
    """Interactive conversation mode."""
    print("=" * 70)
    print("INTERACTIVE MODE")
    print("Commands: 'exit' to quit, 'clear' to reset conversation")
    print("=" * 70)

    state = ConversationState()

    while True:
        try:
            # Show if we're waiting for something
            prompt = "» "
            if state.waiting_for:
                prompt = f"[waiting: {state.waiting_for}] » "

            q = input(f"\n{prompt}").strip()

            if q.lower() in ("exit", "quit", "q"):
                break
            if q.lower() == "clear":
                state.clear()
                print("Conversation cleared.")
                continue
            if not q:
                continue

            r = process_question(q, state)

            print(f"\nAssistant: {r.get('response')}")
            print(f"  [route: {r.get('route')}, steps: {r.get('steps')}]")

            if r.get("executor", {}).get("result"):
                res = r["executor"]["result"]
                if "count" in res:
                    print(f"  [count: {res['count']}, green: {res.get('green_pct')}%]")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import sys

    args = sys.argv[1:]

    if "-i" in args:
        interactive()
    elif "-c" in args or "--conv" in args:
        run_conversation_tests()
    elif "-s" in args or "--single" in args:
        run_single_tests()
    else:
        # Default: show help
        print("Usage:")
        print("  python -m agent.tests.test_graph -c    # conversation tests")
        print("  python -m agent.tests.test_graph -s    # single tests")
        print("  python -m agent.tests.test_graph -i    # interactive mode")
        print("  python -m agent.tests.test_graph -a    # all tests")
        print()
        if "-a" in args or "--all" in args:
            run_tests()
