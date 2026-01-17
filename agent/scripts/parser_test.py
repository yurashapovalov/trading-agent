"""
Quick test for Parser prompt.

Run: python -m agent.prompts.parser_test
"""

import json
import time
from datetime import datetime

from google import genai
from google.genai import types

import config
from agent.prompts.parser import get_parser_prompt


TEST_QUESTIONS = [
    # Basic
    "Статистика по пятницам 2020-2025 где close - low >= 200",
    "What happened on May 16, 2024?",
    "When is high usually formed?",
    "Top 10 volatile days in 2024",
    "RTH vs ETH range",
    "Привет",
    "What is gap?",
    "Покажи волатильность по месяцам за 2024",
    "Дни когда упали больше 2%",

    # Strategy / Edge — can't see on chart
    "Что происходит на следующий день после gap up больше 1%?",
    "Какой средний range в понедельник после пятницы с range > 400?",
    "Как часто high формируется в первый час RTH?",
    "Статистика дней когда overnight high был пробит в RTH",
    "Сравни дни когда открылись выше prev close vs ниже",
    "В какое время чаще всего формируется low если день закрылся в плюс?",
    "Какой win rate у стратегии: вход на открытии если gap down > 0.5%, выход на close?",
    "Средний размер отката от high до close в трендовые дни (change > 1%)",
    "Дни когда range первого часа был больше 50% дневного range",
    "Корреляция между размером gap и дневным range",
    "Сколько раз за 2024 цена закрылась выше high предыдущего дня?",
    "Какой процент дней low формируется после 14:00?",
    "Статистика по дням после 3+ дней роста подряд",
    "RTH range в дни экспирации опционов vs обычные пятницы",
]


def test_parser_single(client: genai.Client, question: str, stream: bool = False) -> dict:
    """Test parser on a single question."""
    today = datetime.now().strftime("%Y-%m-%d")
    system, user = get_parser_prompt(question, today=today)

    # Combine system + user for Gemini (it uses single content)
    full_prompt = f"{system}\n\n{user}"

    start = time.time()

    if stream:
        # Streaming mode
        chunks = []
        first_chunk_time = None

        for chunk in client.models.generate_content_stream(
            model=config.GEMINI_LITE_MODEL,  # Fast model for parsing
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        ):
            if first_chunk_time is None:
                first_chunk_time = time.time() - start
            if chunk.text:
                chunks.append(chunk.text)

        response = "".join(chunks)
        total_time = time.time() - start

        return {
            "question": question,
            "first_chunk_ms": int(first_chunk_time * 1000) if first_chunk_time else None,
            "total_ms": int(total_time * 1000),
            "response": response,
        }
    else:
        # Non-streaming mode
        response = client.models.generate_content(
            model=config.GEMINI_LITE_MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )
        total_time = time.time() - start

        return {
            "question": question,
            "total_ms": int(total_time * 1000),
            "response": response.text,
            "input_tokens": response.usage_metadata.prompt_token_count if response.usage_metadata else 0,
            "output_tokens": response.usage_metadata.candidates_token_count if response.usage_metadata else 0,
        }


def test_all(stream: bool = False, save_log: bool = True):
    """Test parser on all questions."""
    client = genai.Client(api_key=config.GOOGLE_API_KEY)

    # Prepare log
    log_lines = []
    def log(text: str):
        print(text)
        log_lines.append(text)

    log(f"\n{'='*60}")
    log(f"Parser Test ({'streaming' if stream else 'non-streaming'})")
    log(f"Model: {config.GEMINI_LITE_MODEL}")
    log(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'='*60}\n")

    results = []
    for q in TEST_QUESTIONS:
        log(f"Q: {q}")
        result = test_parser_single(client, q, stream=stream)

        # Try to parse JSON
        try:
            response = result["response"]
            # Extract JSON from response (may have markdown)
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            parsed = json.loads(response.strip())
            result["parsed"] = parsed
            result["valid_json"] = True
        except Exception as e:
            result["valid_json"] = False
            result["error"] = str(e)

        # Log result
        line = f"   Total: {result['total_ms']}ms"
        if stream and result.get('first_chunk_ms'):
            line = f"   First chunk: {result['first_chunk_ms']}ms | " + line[3:]
        if not stream:
            line += f" | tokens: {result.get('input_tokens', 0)}/{result.get('output_tokens', 0)}"
        log(line)
        log(f"   Valid JSON: {result['valid_json']}")
        if result["valid_json"]:
            p = result["parsed"]
            log(f"   what: {p.get('what', 'N/A')}")
            if p.get("summary"):
                log(f"   summary: {p.get('summary')}")
            if p.get("unclear"):
                log(f"   unclear: {p.get('unclear')}")
            # Log full parsed JSON
            log(f"   parsed: {json.dumps(p, ensure_ascii=False)}")
        else:
            log(f"   Error: {result.get('error', 'unknown')}")
            log(f"   Raw: {result['response'][:200]}...")
        log("")

        results.append(result)

    # Summary
    valid = sum(1 for r in results if r["valid_json"])
    avg_time = sum(r["total_ms"] for r in results) / len(results)
    total_input = sum(r.get("input_tokens", 0) for r in results)
    total_output = sum(r.get("output_tokens", 0) for r in results)

    log(f"{'='*60}")
    log(f"Summary: {valid}/{len(results)} valid JSON")
    log(f"Average time: {int(avg_time)}ms")
    if not stream:
        log(f"Total tokens: {total_input} input / {total_output} output")
    if stream:
        first_chunks = [r["first_chunk_ms"] for r in results if r.get("first_chunk_ms")]
        if first_chunks:
            log(f"Average first chunk: {int(sum(first_chunks)/len(first_chunks))}ms")
    log(f"{'='*60}\n")

    # Save log to file
    if save_log:
        from pathlib import Path
        log_dir = Path(__file__).parent.parent / "docs" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode = "stream" if stream else "batch"
        log_file = log_dir / f"parser_test_{mode}_{timestamp}.txt"

        with open(log_file, "w") as f:
            f.write("\n".join(log_lines))

        print(f"Log saved to: {log_file}")

    return results


def test_stability(runs: int = 10):
    """Run each question multiple times to test consistency."""
    client = genai.Client(api_key=config.GOOGLE_API_KEY)

    print(f"\n{'='*60}")
    print(f"Parser Stability Test")
    print(f"Model: {config.GEMINI_LITE_MODEL}")
    print(f"Runs per question: {runs}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    all_results = {}

    for q in TEST_QUESTIONS:
        print(f"Q: {q[:50]}...")
        question_results = []

        for i in range(runs):
            result = test_parser_single(client, q, stream=False)

            # Parse JSON
            try:
                response = result["response"]
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0]
                parsed = json.loads(response.strip())
                result["parsed"] = parsed
                result["valid_json"] = True
            except Exception as e:
                result["parsed"] = None
                result["valid_json"] = False
                result["error"] = str(e)

            question_results.append({
                "run": i + 1,
                "time_ms": result["total_ms"],
                "valid": result["valid_json"],
                "what": result.get("parsed", {}).get("what") if result["valid_json"] else None,
                "summary": result.get("parsed", {}).get("summary") if result["valid_json"] else None,
                "unclear": result.get("parsed", {}).get("unclear") if result["valid_json"] else None,
                "parsed": result.get("parsed"),
            })
            print(f"   Run {i+1}: {result['total_ms']}ms", end="")
            if result["valid_json"]:
                print(f" | what: {result['parsed'].get('what', 'N/A')[:20]}")
            else:
                print(" | INVALID JSON")

        all_results[q] = {
            "runs": question_results,
            "stats": {
                "valid_count": sum(1 for r in question_results if r["valid"]),
                "avg_time_ms": int(sum(r["time_ms"] for r in question_results) / len(question_results)),
                "unique_what": list(set(r["what"] for r in question_results if r["what"])),
                "unique_unclear": list(set(str(r["unclear"]) for r in question_results if r["unclear"] is not None)),
            }
        }
        print(f"   Stats: {all_results[q]['stats']['valid_count']}/{runs} valid, "
              f"avg {all_results[q]['stats']['avg_time_ms']}ms, "
              f"unique 'what': {len(all_results[q]['stats']['unique_what'])}")
        print()

    # Save to JSON
    from pathlib import Path
    log_dir = Path(__file__).parent.parent / "docs" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"parser_stability_{runs}x_{timestamp}.json"

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "model": config.GEMINI_LITE_MODEL,
                "runs_per_question": runs,
                "total_questions": len(TEST_QUESTIONS),
                "timestamp": datetime.now().isoformat(),
            },
            "results": all_results,
        }, f, ensure_ascii=False, indent=2)

    print(f"{'='*60}")
    print(f"Results saved to: {log_file}")
    print(f"{'='*60}\n")

    return all_results


def main():
    """Run tests."""
    import sys

    if "--stability" in sys.argv:
        runs = 10
        for arg in sys.argv:
            if arg.startswith("--runs="):
                runs = int(arg.split("=")[1])
        test_stability(runs=runs)
    else:
        stream = "--stream" in sys.argv
        test_all(stream=stream)


if __name__ == "__main__":
    main()
