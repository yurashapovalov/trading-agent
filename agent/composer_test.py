"""
Test Parser → Composer flow with saved output.

Run: python -m agent.composer_test
"""

import json
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types

import config
from agent.prompts.parser import get_parser_prompt
from agent.composer import compose


TEST_QUESTIONS = [
    # Basic queries
    "Statistics for Fridays 2020-2025 where close - low >= 200",
    "What happened on May 16, 2024?",
    "Top 10 volatile days in 2024",
    "RTH vs ETH range",
    "Volatility by month for 2024",
    "When is high usually formed?",

    # Concept / greeting
    "What is gap?",
    "Hello",

    # Not supported
    "What happens the day after a gap up > 1%?",
    "Win rate for gap down strategy",
    "Days after 3+ days of growth in a row",

    # Russian
    "Статистика по пятницам 2020-2025 где close - low >= 200",
    "Что было 16 мая 2024?",
    "Топ 10 волатильных дней за 2024",
    "Сравни RTH и ETH по range",
]


def test_parser_composer(runs_per_question: int = 2):
    """Test Parser → Composer flow and save results."""
    client = genai.Client(api_key=config.GOOGLE_API_KEY)

    print(f"\n{'='*70}")
    print("Parser → Composer Test")
    print(f"Model: {config.GEMINI_LITE_MODEL}")
    print(f"Runs per question: {runs_per_question}")
    print(f"{'='*70}\n")

    all_results = []

    for q in TEST_QUESTIONS:
        print(f"Q: {q[:60]}...")
        question_runs = []

        for run_num in range(runs_per_question):
            # Step 1: Parser
            today = datetime.now().strftime("%Y-%m-%d")
            system, user = get_parser_prompt(q, today=today)
            full_prompt = f"{system}\n\n{user}"

            start = datetime.now()
            response = client.models.generate_content(
                model=config.GEMINI_LITE_MODEL,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
            parser_time = (datetime.now() - start).total_seconds() * 1000

            # Parse JSON
            try:
                parsed = json.loads(response.text)
                parser_ok = True
            except Exception as e:
                parsed = {"error": str(e), "raw": response.text[:200]}
                parser_ok = False

            # Step 2: Composer
            if parser_ok:
                start = datetime.now()
                result = compose(parsed)
                composer_time = (datetime.now() - start).total_seconds() * 1000

                composer_output = {
                    "type": result.type,
                    "summary": result.summary,
                }

                if result.type == "query":
                    spec = result.spec
                    composer_output["source"] = spec.source.value
                    composer_output["grouping"] = spec.grouping.value
                    composer_output["special_op"] = spec.special_op.value
                    composer_output["filters"] = {
                        "period_start": spec.filters.period_start,
                        "period_end": spec.filters.period_end,
                        "weekdays": spec.filters.weekdays,
                        "session": spec.filters.session,
                        "conditions": [c.to_sql() for c in spec.filters.conditions] if spec.filters.conditions else None,
                    }
                    composer_output["metrics"] = [
                        {"metric": m.metric.value, "column": m.column, "alias": m.alias}
                        for m in spec.metrics
                    ]
                elif result.type == "clarification":
                    composer_output["field"] = result.field
                    composer_output["options"] = result.options
                elif result.type == "concept":
                    composer_output["concept"] = result.concept
                elif result.type == "not_supported":
                    composer_output["reason"] = result.reason
            else:
                composer_output = {"error": "Parser failed"}
                composer_time = 0

            run_result = {
                "run": run_num + 1,
                "parser": {
                    "time_ms": int(parser_time),
                    "ok": parser_ok,
                    "what": parsed.get("what"),
                    "unclear": parsed.get("unclear"),
                    "summary": parsed.get("summary"),
                    "full": parsed,
                },
                "composer": {
                    "time_ms": int(composer_time),
                    **composer_output,
                }
            }
            question_runs.append(run_result)

            # Print summary
            print(f"   Run {run_num + 1}: Parser {int(parser_time)}ms → Composer {result.type}")

        all_results.append({
            "question": q,
            "runs": question_runs,
        })
        print()

    # Save to file
    log_dir = Path(__file__).parent / "docs" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"parser_composer_{runs_per_question}x_{timestamp}.json"

    output = {
        "meta": {
            "model": config.GEMINI_LITE_MODEL,
            "runs_per_question": runs_per_question,
            "total_questions": len(TEST_QUESTIONS),
            "timestamp": datetime.now().isoformat(),
        },
        "results": all_results,
    }

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"{'='*70}")
    print(f"Results saved to: {log_file}")
    print(f"{'='*70}\n")

    return output


if __name__ == "__main__":
    import sys
    runs = 2
    for arg in sys.argv:
        if arg.startswith("--runs="):
            runs = int(arg.split("=")[1])
    test_parser_composer(runs_per_question=runs)
