"""Test full pipeline: Parser → Executor → Result."""

import json
from datetime import date
from google import genai
from google.genai import types

import config
from agent.prompts.parser import get_parser_prompt
from agent.types import ParsedQuery
from agent.executor import execute


def run_pipeline(question: str, today: date = date(2026, 1, 20)) -> dict:
    """Run full pipeline and return result."""
    weekday = today.strftime("%A")
    system, user = get_parser_prompt(question, today.isoformat(), weekday)

    client = genai.Client(api_key=config.GOOGLE_API_KEY)
    response = client.models.generate_content(
        model=config.GEMINI_LITE_MODEL,
        contents=f"{system}\n\n{user}",
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=ParsedQuery,
        ),
    )

    parsed = ParsedQuery.model_validate_json(response.text)
    result = execute(parsed, symbol="NQ", today=today)

    # Remove DataFrame from result (not JSON serializable)
    result_copy = {k: v for k, v in result.items() if k != "data"}

    return {
        "question": question,
        "parsed": parsed.model_dump(),
        "result": result_copy,
    }


def main():
    tests = [
        # Vague → should have unclear: ["metric"]
        "статистика за 2024",
        "как прошёл 2024 год",
        "данные за прошлый месяц",

        # Clear → should NOT have unclear
        "волатильность за 2024",
        "волатильность по дням недели за 2024",
        "топ 5 самых волатильных дней 2024",
        "сколько зеленых пятниц было в 2024",

        # Other intents
        "привет",
        "что такое OPEX",

        # Periods
        "вчера",
        "Q1 2024",
    ]

    results = []
    for q in tests:
        print(f"Testing: {q}")
        r = run_pipeline(q)
        results.append(r)

    # Save to file
    output_path = "agent/tests/pipeline_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
