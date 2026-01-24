"""
Integration test — Intent → Understander → Parser → Executor.

Usage:
    python -m agent.tests.full_flow_test              # show usage
    python -m agent.tests.full_flow_test <category>   # run category
    python -m agent.tests.full_flow_test all          # run all
    python -m agent.tests.full_flow_test "question"   # run single
"""

import json
import os
import sys
from datetime import datetime
from uuid import uuid4

from langchain_core.messages import HumanMessage

from agent.graph import build_graph


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
}


def run_question(question: str, graph=None) -> dict:
    """Run question through graph: Intent → Parser → Executor."""
    if graph is None:
        graph = build_graph().compile()

    state = {
        "messages": [HumanMessage(content=question)],
        "session_id": str(uuid4()),
        "user_id": "test-user",
    }

    result = graph.invoke(state)

    return {
        "question": question,
        "intent": result.get("intent"),
        "lang": result.get("lang"),
        "question_en": result.get("question_en"),
        # Understander
        "goal": result.get("goal"),
        "understood": result.get("understood"),
        "expanded_query": result.get("expanded_query"),
        "need_clarification": result.get("need_clarification"),
        # Parser
        "steps": result.get("parsed_query", []),
        "plans": result.get("execution_plan", []),
        "thoughts": result.get("parser_thoughts"),
        "data": result.get("data"),
        "usage": result.get("usage"),
    }


def run_batch(questions: list[str], label: str = "batch") -> list[dict]:
    """Run multiple questions, save results to JSON."""
    graph = build_graph().compile()
    results = []

    for i, q in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] {q}")
        try:
            result = run_question(q, graph)
            results.append(result)

            # Understander
            understood = result.get("understood")
            goal = result.get("goal")
            expanded = result.get("expanded_query")
            clarification = result.get("need_clarification")

            if understood:
                print(f"  → Understander: ✓ goal={goal}")
                if expanded:
                    print(f"     expanded: {expanded[:80]}...")
            else:
                print(f"  → Understander: ✗ needs clarification")
                if clarification:
                    print(f"     question: {clarification.get('question', '?')}")

            steps = result.get("steps", [])
            if steps:
                ops = [s.get("operation", "?") for s in steps]
                print(f"  → Parser: {', '.join(ops)}")
            elif understood:
                print(f"  → Parser: no steps")

            plans = result.get("plans", [])
            if plans:
                modes = [p.get("mode", "?") for p in plans]
                print(f"  → Planner: {', '.join(modes)}")

            data = result.get("data", [])
            if data:
                for d in data:
                    summary = d.get("summary", {})
                    if "error" in summary:
                        print(f"  → Executor: ERROR {summary['error']}")
                    else:
                        print(f"  → Executor: {summary}")
        except Exception as e:
            print(f"  → ERROR: {e}")
            results.append({"question": q, "error": str(e)})

    os.makedirs("agent/tests/results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"agent/tests/results/test_{label}_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Saved {len(results)} results to: {output_file}")
    return results


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg in QUESTIONS_BY_CATEGORY:
            questions = QUESTIONS_BY_CATEGORY[arg]
            print("="*60)
            print(f"Running {arg.upper()} ({len(questions)} questions)")
            print("="*60)
            run_batch(questions, arg)
        elif arg == "all":
            for category, questions in QUESTIONS_BY_CATEGORY.items():
                print("\n" + "="*60)
                print(f"Running {category.upper()} ({len(questions)} questions)")
                print("="*60)
                run_batch(questions, category)
        else:
            question = " ".join(sys.argv[1:])
            result = run_question(question)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Usage:")
        print("  python -m agent.tests.full_flow_test <category>   # run category")
        print("  python -m agent.tests.full_flow_test all          # run all")
        print('  python -m agent.tests.full_flow_test "question"   # run single')
        print()
        print("Categories:", ", ".join(QUESTIONS_BY_CATEGORY.keys()))
