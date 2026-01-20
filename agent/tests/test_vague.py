"""
Test vague questions without unclear handling.

Just parse → execute → see what happens.

Run: python -m agent.tests.test_vague
"""

from datetime import date
from google import genai
from google.genai import types

import config
from agent.types import ParsedQuery
from agent.prompts.parser import get_parser_prompt
from agent.executor import execute


client = genai.Client(api_key=config.GOOGLE_API_KEY)


def parse(question: str) -> ParsedQuery:
    """Parse without post-validation."""
    today = date.today()
    system, user = get_parser_prompt(question, today.isoformat(), today.strftime("%A"))

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

    # IGNORE unclear - just execute
    parsed.unclear = None

    return parsed


def test_question(q: str):
    """Test single question."""
    print(f"\n{'='*60}")
    print(f"Q: {q}")
    print("="*60)

    parsed = parse(q)
    print(f"\nParsed:")
    print(f"  intent: {parsed.intent}")
    print(f"  period: {parsed.period}")
    print(f"  metric: {parsed.metric}")
    print(f"  operation: {parsed.operation}")
    print(f"  what: {parsed.what}")

    if parsed.intent != "data":
        print(f"\n→ Non-data intent: {parsed.intent}")
        return

    result = execute(parsed, symbol="NQ", today=date.today())

    print(f"\nResult:")
    print(f"  intent: {result.get('intent')}")
    print(f"  rows: {result.get('row_count', 0)}")
    print(f"  operation: {result.get('operation')}")
    print(f"  period: {result.get('period')}")

    if result.get("result"):
        res = result["result"]
        print(f"\n  Stats:")
        for k, v in list(res.items())[:8]:
            if isinstance(v, float):
                print(f"    {k}: {v:.2f}")
            else:
                print(f"    {k}: {v}")


VAGUE_QUESTIONS = [
    # Совсем тупые
    "статистика",
    "данные",
    "покажи",

    # Без периода
    "волатильность",
    "доходность",
    "объём",

    # Без метрики
    "за 2024",
    "прошлый месяц",
    "вторники",

    # Частично понятные
    "волатильность по вторникам",
    "топ дней",
    "сравни",

    # Нормальные
    "волатильность за 2024",
    "топ 5 дней по range за 2024",
    "доходность по вторникам за 2023",
]


if __name__ == "__main__":
    for q in VAGUE_QUESTIONS:
        test_question(q)
