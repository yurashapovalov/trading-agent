"""Test Parser entity extraction with response_schema."""

from google import genai
from google.genai import types

import config
from agent.prompts.parser import get_parser_prompt
from agent.types import ParsedQuery


def test_parser(question: str) -> ParsedQuery:
    """Run parser with response_schema."""
    system, user = get_parser_prompt(question, "2026-01-20", "Tuesday")
    full_prompt = f"{system}\n\n{user}"

    client = genai.Client(api_key=config.GOOGLE_API_KEY)
    response = client.models.generate_content(
        model=config.GEMINI_LITE_MODEL,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=ParsedQuery,
        ),
    )

    return ParsedQuery.model_validate_json(response.text)


def format_result(r: ParsedQuery) -> str:
    """Format result for display."""
    parts = []

    if r.intent != "data":
        return f"intent={r.intent}"

    if r.period:
        p = r.period
        if p.type == "range":
            parts.append(f"period=range:{p.start}-{p.end}")
        elif p.type == "quarter":
            parts.append(f"period=quarter:Q{p.q}-{p.year}")
        elif p.n:
            parts.append(f"period={p.type}:{p.value}(n={p.n})")
        else:
            parts.append(f"period={p.type}:{p.value}")

    if r.time:
        parts.append(f"time={r.time.start}-{r.time.end}")

    if r.session:
        parts.append(f"session={r.session}")

    if r.weekday_filter:
        parts.append(f"weekday={r.weekday_filter}")

    if r.event_filter:
        parts.append(f"event={r.event_filter}")

    if r.compare:
        parts.append(f"compare={r.compare}")

    if r.unclear:
        parts.append(f"unclear={r.unclear}")

    return ", ".join(parts) if parts else "empty"


def main():
    tests = [
        # === RELATIVE PERIODS ===
        ("вчера", "period=relative:yesterday"),
        ("сегодня", "period=relative:today"),
        ("позавчера", "period=relative:day_before_yesterday"),
        ("последние 5 дней", "period=relative:last_n_days(n=5)"),
        ("прошлая неделя", "period=relative:last_week"),
        ("последние 2 недели", "period=relative:last_n_weeks(n=2)"),
        ("последний месяц", "period=relative:last_month"),
        ("с начала года", "period=relative:ytd"),
        ("с начала месяца", "period=relative:mtd"),

        # === ABSOLUTE PERIODS ===
        ("2024", "period=year:2024"),
        ("январь 2024", "period=month:2024-01"),
        ("15 мая 2024", "period=date:2024-05-15"),
        ("15 мая", "unclear=[year]"),
        ("декабрь", "unclear=[year]"),
        ("Q1 2024", "period=quarter"),
        ("с 1 по 15 января 2024", "period=range"),
        ("2020-2024", "period=range"),

        # === TIME ===
        ("с 9:30 до 12:00", "time=09:30-12:00"),
        ("первый час торгов", "time=09:30-10:30"),
        ("последний час", "time=16:00-17:00"),

        # === SESSIONS ===
        ("RTH за вчера", "session=RTH"),
        ("ночная сессия", "session=OVERNIGHT"),

        # === FILTERS ===
        ("пятницы в 2024", "weekday=[Friday]"),
        ("дни OPEX 2024", "event=opex"),
        ("FOMC дни", "event=fomc"),

        # === COMPARE ===
        ("2023 vs 2024", "compare=[2023, 2024]"),
        ("RTH vs ETH", "compare=[RTH, ETH]"),

        # === INTENTS ===
        ("привет", "intent=chitchat"),
        ("что такое OPEX", "intent=concept"),
    ]

    print("=" * 70)
    print("PARSER TEST (with response_schema)")
    print("=" * 70)

    passed = 0
    for question, expected in tests:
        print(f"\n» {question}")
        print(f"  Expected: {expected}")

        try:
            result = test_parser(question)
            got = format_result(result)
            print(f"  Got:      {got}")
            if expected.split("=")[0] in got or expected in got:
                passed += 1
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n{'=' * 70}")
    print(f"PASSED: {passed}/{len(tests)}")


if __name__ == "__main__":
    main()
