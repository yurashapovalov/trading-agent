"""
Integration test — full graph flow with Supabase logging capture.

Runs the REAL TradingGraph.stream_sse() and captures all data
that would be logged to Supabase (without actually writing).

Usage:
    python -m agent.tests.full_flow_test              # show usage
    python -m agent.tests.full_flow_test <category>   # run category
    python -m agent.tests.full_flow_test all          # run all
    python -m agent.tests.full_flow_test "question"   # run single
    python -m agent.tests.full_flow_test -i           # interactive mode
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import patch, AsyncMock
from uuid import uuid4


# =============================================================================
# Supabase Logging Capture
# =============================================================================

@dataclass
class CapturedLog:
    """Captured Supabase logging data."""
    # chat_logs (init)
    init_chat_log: dict | None = None

    # request_traces (per-agent steps)
    trace_steps: list[dict] = field(default_factory=list)

    # chat_logs (complete)
    complete_chat_log: dict | None = None


def create_logging_mocks(captured: CapturedLog):
    """Create mock functions that capture logging data."""

    def mock_init_chat_log_sync(
        request_id: str,
        user_id: str,
        chat_id: str | None,
        question: str,
    ):
        captured.init_chat_log = {
            "request_id": request_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "question": question,
        }

    def mock_log_trace_step_sync(
        request_id: str,
        user_id: str,
        step_number: int,
        agent_name: str,
        input_data: dict | None = None,
        output_data: dict | None = None,
        usage: dict | None = None,
        duration_ms: int = 0,
    ):
        captured.trace_steps.append({
            "request_id": request_id,
            "user_id": user_id,
            "step_number": step_number,
            "agent_name": agent_name,
            "input_data": input_data,
            "output_data": output_data,
            "usage": usage,
            "duration_ms": duration_ms,
        })

    def mock_complete_chat_log_sync(
        request_id: str,
        chat_id: str | None = None,
        response: str = "",
        route: str = "",
        agents_used: list[str] | None = None,
        duration_ms: int = 0,
        usage: dict | None = None,
        title: str | None = None,
    ):
        if response and len(response) > 500:
            response = response[:500] + "..."
        captured.complete_chat_log = {
            "request_id": request_id,
            "chat_id": chat_id,
            "response": response,
            "route": route,
            "agents_used": agents_used or [],
            "duration_ms": duration_ms,
            "usage": usage,
            "title": title,
        }

    return mock_init_chat_log_sync, mock_log_trace_step_sync, mock_complete_chat_log_sync


# =============================================================================
# Display Functions
# =============================================================================

def print_separator(char="=", width=80):
    print(char * width)


def print_header(title: str):
    print_separator()
    print(f"  {title}")
    print_separator()


def print_section(title: str):
    print(f"\n{'─'*40}")
    print(f"  {title}")
    print(f"{'─'*40}")


def format_usage(usage: dict | None) -> str:
    """Format usage dict for display."""
    if not usage:
        return "—"
    return (
        f"in={usage.get('input_tokens', 0):,} "
        f"out={usage.get('output_tokens', 0):,} "
        f"think={usage.get('thinking_tokens', 0):,} "
        f"cache={usage.get('cached_tokens', 0):,}"
    )


def display_captured_logs(captured: CapturedLog, show_full: bool = False):
    """Display captured Supabase logging data."""

    # Init chat log
    print_section("chat_logs (INIT)")
    if captured.init_chat_log:
        init = captured.init_chat_log
        print(f"  request_id: {init.get('request_id', '—')}")
        print(f"  user_id:    {init.get('user_id', '—')}")
        print(f"  chat_id:    {init.get('chat_id', '—')}")
        question = init.get('question', '')
        print(f"  question:   {question[:100]}{'...' if len(question) > 100 else ''}")
    else:
        print("  (not captured)")

    # Trace steps
    print_section("request_traces (STEPS)")
    if captured.trace_steps:
        for step in captured.trace_steps:
            agent = step["agent_name"]
            step_num = step["step_number"]
            duration = step["duration_ms"]
            usage = format_usage(step.get("usage"))

            print(f"\n  [{step_num}] {agent} ({duration}ms)")
            print(f"      usage: {usage}")

            # Input summary
            input_data = step.get("input_data") or {}
            if input_data:
                print(f"      input:")
                for k, v in input_data.items():
                    if v is not None:
                        v_str = str(v)[:80] + "..." if len(str(v)) > 80 else str(v)
                        print(f"        {k}: {v_str}")

            # Output summary
            output_data = step.get("output_data") or {}
            if output_data and show_full:
                print(f"      output:")
                for k, v in output_data.items():
                    if v is not None and k not in ("usage", "messages"):
                        v_str = str(v)[:80] + "..." if len(str(v)) > 80 else str(v)
                        print(f"        {k}: {v_str}")
    else:
        print("  (no steps captured)")

    # Complete chat log
    print_section("chat_logs (COMPLETE)")
    if captured.complete_chat_log:
        comp = captured.complete_chat_log
        print(f"  request_id:  {comp.get('request_id', '—')}")
        print(f"  chat_id:     {comp.get('chat_id', '—')}")
        print(f"  route:       {comp.get('route', '—')}")
        print(f"  agents_used: {comp.get('agents_used', [])}")
        print(f"  duration_ms: {comp.get('duration_ms', 0)}")

        # Usage by agent
        usage = comp.get("usage") or {}
        if usage:
            print(f"  usage:")
            for agent_name, agent_usage in usage.items():
                if agent_name != "total" and isinstance(agent_usage, dict):
                    print(f"    {agent_name}: {format_usage(agent_usage)}")
            if "total" in usage:
                total = usage["total"]
                cost = total.get("cost_usd", 0)
                print(f"    ───────────")
                print(f"    TOTAL: {format_usage(total)} (${cost:.4f})")

        # Response preview
        response = comp.get("response", "")
        if response:
            print(f"\n  response:")
            for line in response.split("\n")[:10]:
                print(f"    {line[:100]}")
            if len(response.split("\n")) > 10:
                print(f"    ... ({len(response)} chars total)")
    else:
        print("  (not captured)")


def display_sse_events(events: list[dict]):
    """Display SSE events summary."""
    print_section("SSE Events")

    for event in events:
        etype = event.get("type")

        if etype == "step_start":
            agent = event.get("agent")
            step = event.get("step")
            print(f"  step_start: [{step}] {agent}")

        elif etype == "step_end":
            agent = event.get("agent")
            step = event.get("step")
            duration = event.get("duration_ms")
            print(f"  step_end:   [{step}] {agent} ({duration}ms)")

        elif etype == "text_delta":
            content = event.get("content", "")[:50]
            agent = event.get("agent")
            print(f"  text_delta: ({agent}) {content}...")

        elif etype == "usage":
            total = event.get("total", {})
            cost = event.get("cost", 0)
            print(f"  usage:      {format_usage(total)} (${cost:.4f})")

        elif etype == "done":
            duration = event.get("total_duration_ms")
            agents = event.get("agents_used", [])
            print(f"  done:       {duration}ms, agents={agents}")


# =============================================================================
# Test Runner
# =============================================================================

def run_question(
    question: str,
    user_id: str = "test-user",
    show_events: bool = False,
    awaiting_clarification: bool = False,
    original_question: str | None = None,
    clarification_history: list[dict] | None = None,
) -> dict:
    """
    Run question through real TradingGraph with Supabase logging capture.

    Returns dict with captured logs and SSE events.
    """
    from agent.trading_graph import TradingGraph

    # Create fresh graph instance
    graph = TradingGraph()

    # Capture logging calls
    captured = CapturedLog()
    mock_init, mock_trace, mock_complete = create_logging_mocks(captured)

    # Collect SSE events
    events = []

    session_id = str(uuid4())
    chat_id = str(uuid4())

    with patch("agent.trading_graph.init_chat_log_sync", mock_init), \
         patch("agent.trading_graph.complete_chat_log_sync", mock_complete), \
         patch("agent.graph.log_trace_step_sync", mock_trace):

        for event in graph.stream_sse(
            question=question,
            user_id=user_id,
            session_id=session_id,
            chat_id=chat_id,
            needs_title=True,
            awaiting_clarification=awaiting_clarification,
            original_question=original_question,
            clarification_history=clarification_history,
        ):
            events.append(event)

    # Display results
    header = f"Question: {question}"
    if awaiting_clarification:
        header += f" (continuing from: {original_question})"
    print_header(header)

    if show_events:
        display_sse_events(events)

    display_captured_logs(captured, show_full=True)

    return {
        "question": question,
        "awaiting_clarification": awaiting_clarification,
        "original_question": original_question,
        "clarification_history": clarification_history,
        "captured": {
            "init_chat_log": captured.init_chat_log,
            "trace_steps": captured.trace_steps,
            "complete_chat_log": captured.complete_chat_log,
        },
        "events": events,
    }


def run_batch(questions: list[str], label: str = "batch") -> list[dict]:
    """Run multiple questions, save results to JSON."""
    results = []

    for i, q in enumerate(questions, 1):
        print(f"\n\n{'#'*80}")
        print(f"#  [{i}/{len(questions)}] {q}")
        print(f"{'#'*80}")

        try:
            result = run_question(q)
            results.append(result)
        except Exception as e:
            print(f"\n  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({"question": q, "error": str(e)})

    # Save results
    os.makedirs("agent/tests/results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"agent/tests/results/flow_{label}_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n\n{'='*80}")
    print(f"Saved {len(results)} results to: {output_file}")

    return results


def run_clarification_scenarios() -> list[dict]:
    """Run all clarification flow scenarios and save to JSON."""
    results = []

    # Common history for clarification tests
    history = [{"role": "assistant", "content": "Смысл — это про вероятность или доходность?"}]
    original = "есть смысл держать позицию в RTH?"

    scenarios = [
        # 1. First question triggers clarification
        {
            "name": "1_initial_unclear",
            "question": "есть смысл держать позицию в RTH?",
        },
        # 2. User answers clarification
        {
            "name": "2_clarification_answered",
            "question": "вероятность",
            "awaiting_clarification": True,
            "original_question": original,
            "clarification_history": history,
        },
        # 3. User changes topic to clear question
        {
            "name": "3_topic_change_clear",
            "question": "покажи топ 5 дней по объёму",
            "awaiting_clarification": True,
            "original_question": original,
            "clarification_history": history,
        },
        # 4. User changes topic to unclear question
        {
            "name": "4_topic_change_unclear",
            "question": "покажи топ 5 волатильных дней",
            "awaiting_clarification": True,
            "original_question": original,
            "clarification_history": history,
        },
        # 5. User cancels
        {
            "name": "5_cancel",
            "question": "забей",
            "awaiting_clarification": True,
            "original_question": original,
            "clarification_history": history,
        },
        # 6. Chitchat without clarification
        {
            "name": "6_chitchat",
            "question": "привет",
        },
        # 7. Clear question from start
        {
            "name": "7_clear_from_start",
            "question": "топ 10 самых больших падений в 2024",
        },
    ]

    for i, scenario in enumerate(scenarios, 1):
        name = scenario.pop("name")
        question = scenario["question"]

        print(f"\n\n{'#'*80}")
        print(f"#  [{i}/{len(scenarios)}] {name}: {question}")
        print(f"{'#'*80}")

        try:
            result = run_question(**scenario)
            result["scenario_name"] = name
            results.append(result)
        except Exception as e:
            print(f"\n  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({"scenario_name": name, "question": question, "error": str(e)})

    # Save results
    os.makedirs("agent/tests/results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"agent/tests/results/clarification_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n\n{'='*80}")
    print(f"Saved {len(results)} clarification scenarios to: {output_file}")

    return results


def interactive_mode():
    """Interactive question testing."""
    print_header("Interactive Mode")
    print("Type questions to test. Commands: 'quit', 'exit', 'q'\n")

    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            break

        try:
            run_question(question, show_events=True)
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\nBye!")


# =============================================================================
# Test Categories
# =============================================================================

QUESTIONS_BY_CATEGORY = {
    "list": [
        "top 10 biggest drops in 2024",
        "топ 5 дней по объёму в январе",
        "show all days with gap > 2% in 2024",
        "покажи красные пятницы в 2024",
    ],
    "count": [
        "how many gap ups in 2024",
        "сколько дней с range > 300 пунктов в 2024",
        "how many green mondays in Q1 2024",
        "сколько раз gap закрылся в тот же день",
    ],
    "compare": [
        "compare monday vs friday performance in 2024",
        "сравни волатильность Q1 и Q4 2024",
        "compare morning vs afternoon range",
        "сравни 2023 и 2024 по среднему change",
    ],
    "probability": [
        "probability of green day after gap up",
        "вероятность роста после 2+ красных дней подряд",
        "chance of gap fill on gap down days",
        "какой процент пятниц закрывается в плюс",
    ],
    "streak": [
        "how many times were there 3+ red days in a row in 2024",
        "сколько раз было 4+ зелёных дня подряд",
        "longest losing streak in 2024",
        "максимальная серия дней с gap up",
    ],
    "around": [
        "what happens after big drops (> 2%)",
        "что было после gap up > 1% в 2024",
        "performance day after high volume days",
        "как закрывались дни после 3 красных подряд",
    ],
    "formation": [
        "when is daily high usually formed",
        "в какое время обычно формируется лоу дня",
        "what hour does gap usually fill",
        "когда чаще достигается 50% дневного диапазона",
    ],
    "distribution": [
        "distribution of daily changes in 2024",
        "распределение gap по размеру в 2024",
        "how is volume distributed across weekdays",
    ],
    "correlation": [
        "correlation between gap size and daily change",
        "корреляция объёма и волатильности",
        "relationship between overnight range and RTH range",
    ],
    "patterns": [
        "show me all doji candles in 2024",
        "сколько было молотов за последний год",
        "probability of reversal after evening star",
        "когда появлялись inside day в 2024",
        "what happens next day after bullish engulfing",
        "покажи топ 10 дней с hammer pattern",
        "how often does morning star predict growth",
        "найди все bearish engulfing в Q4 2024",
    ],
    "holidays": [
        "how does market behave before thanksgiving",
        "какая волатильность в black friday",
        "compare performance before vs after christmas",
        "average gap on days after memorial day",
        "probability of green day before labor day",
        "show range on independence day eve",
        "что было в день после нового года в 2024",
        "performance around fomc days in 2024",
    ],
    "quick": [
        "how many trading days in 2024",
        "average daily range",
    ],
}


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == "-i":
            interactive_mode()
        elif arg == "clarification":
            print_header("Running CLARIFICATION scenarios (7 tests)")
            run_clarification_scenarios()
        elif arg in QUESTIONS_BY_CATEGORY:
            questions = QUESTIONS_BY_CATEGORY[arg]
            print_header(f"Running {arg.upper()} ({len(questions)} questions)")
            run_batch(questions, arg)
        elif arg == "all":
            for category, questions in QUESTIONS_BY_CATEGORY.items():
                print_header(f"Category: {category.upper()} ({len(questions)} questions)")
                run_batch(questions, category)
        else:
            # Single question
            question = " ".join(sys.argv[1:])
            result = run_question(question, show_events=True)

            # Save to file
            os.makedirs("agent/tests/results", exist_ok=True)
            with open("agent/tests/results/flow_single.json", "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n\nSaved to: agent/tests/results/flow_single.json")
    else:
        print("Usage:")
        print("  python -m agent.tests.full_flow_test <category>     # run category")
        print("  python -m agent.tests.full_flow_test clarification  # run clarification scenarios")
        print("  python -m agent.tests.full_flow_test all            # run all")
        print('  python -m agent.tests.full_flow_test "question"     # run single')
        print("  python -m agent.tests.full_flow_test -i             # interactive")
        print()
        print("Categories:", ", ".join(QUESTIONS_BY_CATEGORY.keys()))
