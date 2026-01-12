"""
Test script for v2 multi-agent architecture.
Run: python test_v2.py
"""

import sys
from datetime import datetime

# Initialize database first
from data import init_database
import config
init_database(config.DATABASE_PATH)


def test_sql_module():
    """Test 1: SQL module with granularity."""
    print("\n" + "="*60)
    print("TEST 1: SQL Module")
    print("="*60)

    from agent.modules import sql

    # Get data range
    data_range = sql.get_data_range("NQ")
    print(f"\nData range: {data_range}")

    if not data_range:
        print("ERROR: No data available")
        return False

    # Test period granularity
    print("\n--- Period granularity (aggregated) ---")
    result = sql.fetch(
        symbol="NQ",
        period_start="2024-01-01",
        period_end="2024-01-31",
        granularity="period"
    )
    print(f"Rows: {result.get('row_count')}")
    if result.get('rows'):
        print(f"First row: {result['rows'][0]}")

    # Test daily granularity
    print("\n--- Daily granularity ---")
    result = sql.fetch(
        symbol="NQ",
        period_start="2024-01-01",
        period_end="2024-01-10",
        granularity="daily"
    )
    print(f"Rows: {result.get('row_count')}")
    if result.get('rows'):
        print(f"Sample: {result['rows'][0]}")

    print("\nSQL module: OK")
    return True


def test_patterns_module():
    """Test 2: Patterns module."""
    print("\n" + "="*60)
    print("TEST 2: Patterns Module")
    print("="*60)

    from agent.modules import patterns

    # Test consecutive days pattern
    print("\n--- Consecutive up days ---")
    result = patterns.search(
        symbol="NQ",
        period_start="2024-01-01",
        period_end="2024-06-30",
        pattern_name="consecutive_days",
        params={"direction": "up", "min_days": 3}
    )
    print(f"Matches: {result.get('matches_count', 0)}")
    if result.get('matches'):
        print(f"Sample: {result['matches'][0]}")

    # Test big move pattern
    print("\n--- Big moves (>2%) ---")
    result = patterns.search(
        symbol="NQ",
        period_start="2024-01-01",
        period_end="2024-06-30",
        pattern_name="big_move",
        params={"threshold_pct": 2.0}
    )
    print(f"Matches: {result.get('matches_count', 0)}")

    print("\nPatterns module: OK")
    return True


def test_understander():
    """Test 3: Understander agent."""
    print("\n" + "="*60)
    print("TEST 3: Understander Agent")
    print("="*60)

    from agent.agents import Understander

    understander = Understander()

    test_questions = [
        "Как NQ вел себя в январе 2024?",
        "Покажи дни когда NQ вырос больше чем на 2%",
        "Что такое MACD?",
        "How did NQ perform last month?",
    ]

    for q in test_questions:
        print(f"\n--- Question: {q[:50]}... ---")
        result = understander({"question": q})
        intent = result.get("intent", {})
        print(f"Type: {intent.get('type')}")
        print(f"Symbol: {intent.get('symbol')}")
        print(f"Period: {intent.get('period_start')} - {intent.get('period_end')}")
        if intent.get('pattern'):
            print(f"Pattern: {intent.get('pattern')}")
        if intent.get('granularity'):
            print(f"Granularity: {intent.get('granularity')}")

    print("\nUnderstander: OK")
    return True


def test_data_fetcher():
    """Test 4: DataFetcher agent."""
    print("\n" + "="*60)
    print("TEST 4: DataFetcher Agent")
    print("="*60)

    from agent.agents import DataFetcher

    fetcher = DataFetcher()

    # Test data intent
    print("\n--- Data intent ---")
    state = {
        "intent": {
            "type": "data",
            "symbol": "NQ",
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "granularity": "period"
        }
    }
    result = fetcher(state)
    data = result.get("data", {})
    print(f"Row count: {data.get('row_count')}")

    # Test pattern intent
    print("\n--- Pattern intent ---")
    state = {
        "intent": {
            "type": "pattern",
            "symbol": "NQ",
            "period_start": "2024-01-01",
            "period_end": "2024-06-30",
            "pattern": {
                "name": "big_move",
                "params": {"threshold_pct": 2.0}
            }
        }
    }
    result = fetcher(state)
    data = result.get("data", {})
    print(f"Pattern: {data.get('pattern')}")
    print(f"Matches: {data.get('matches_count')}")

    # Test concept intent
    print("\n--- Concept intent ---")
    state = {
        "intent": {
            "type": "concept",
            "concept": "MACD"
        }
    }
    result = fetcher(state)
    data = result.get("data", {})
    print(f"Type: {data.get('type')}")

    print("\nDataFetcher: OK")
    return True


def test_analyst():
    """Test 5: Analyst agent."""
    print("\n" + "="*60)
    print("TEST 5: Analyst Agent")
    print("="*60)

    from agent.agents import Analyst
    from agent.modules import sql

    analyst = Analyst()

    # Fetch some data first
    data = sql.fetch(
        symbol="NQ",
        period_start="2024-01-01",
        period_end="2024-01-31",
        granularity="period"
    )

    state = {
        "question": "Как NQ вел себя в январе 2024?",
        "data": data,
        "intent": {"type": "data"}
    }

    result = analyst(state)

    print(f"\n--- Response (first 500 chars) ---")
    response = result.get("response", "")[:500]
    print(response)

    print(f"\n--- Stats ---")
    stats = result.get("stats")
    print(stats)

    usage = analyst.get_usage()
    print(f"\n--- Usage ---")
    print(f"Input: {usage['input_tokens']}, Output: {usage['output_tokens']}")
    print(f"Cost: ${usage['cost_usd']:.4f}")

    print("\nAnalyst: OK")
    return True


def test_validator():
    """Test 6: Validator agent."""
    print("\n" + "="*60)
    print("TEST 6: Validator Agent")
    print("="*60)

    from agent.agents import Validator

    validator = Validator()

    # Test with correct stats
    print("\n--- Correct stats ---")
    state = {
        "intent": {"type": "data"},
        "data": {
            "rows": [{
                "open": 100,
                "close": 110,
                "high": 115,
                "low": 95,
                "volume": 1000,
                "date": "2024-01-01"
            }]
        },
        "stats": {
            "open_price": 100,
            "close_price": 110,
            "max_price": 115,
            "min_price": 95
        }
    }
    result = validator(state)
    validation = result.get("validation", {})
    print(f"Status: {validation.get('status')}")
    print(f"Issues: {validation.get('issues')}")

    # Test with wrong stats
    print("\n--- Wrong stats ---")
    state["stats"]["close_price"] = 999  # Wrong!
    result = validator(state)
    validation = result.get("validation", {})
    print(f"Status: {validation.get('status')}")
    print(f"Issues: {validation.get('issues')}")

    print("\nValidator: OK")
    return True


def test_full_pipeline():
    """Test 7: Full pipeline through graph."""
    print("\n" + "="*60)
    print("TEST 7: Full Pipeline (Graph)")
    print("="*60)

    from agent.graph import TradingGraph

    graph = TradingGraph()

    question = "Как NQ вел себя в январе 2024?"
    print(f"\nQuestion: {question}")

    # Use stream_sse to see all events
    print("\n--- Events ---")
    for event in graph.stream_sse(
        question=question,
        user_id="test_user",
        session_id="test_session"
    ):
        event_type = event.get("type")
        if event_type == "step_start":
            print(f"→ {event.get('agent')}: {event.get('message')}")
        elif event_type == "step_end":
            print(f"  ✓ {event.get('agent')} done: {event.get('result')}")
        elif event_type == "validation":
            print(f"  Validation: {event.get('status')}")
        elif event_type == "usage":
            print(f"  Tokens: {event.get('input_tokens')}→{event.get('output_tokens')}")
        elif event_type == "done":
            print(f"\nDone in {event.get('total_duration_ms')}ms")

    print("\nFull pipeline: OK")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("V2 MULTI-AGENT ARCHITECTURE TESTS")
    print(f"Started: {datetime.now()}")
    print("="*60)

    tests = [
        ("SQL Module", test_sql_module),
        ("Patterns Module", test_patterns_module),
        ("Understander", test_understander),
        ("DataFetcher", test_data_fetcher),
        ("Analyst", test_analyst),
        ("Validator", test_validator),
        ("Full Pipeline", test_full_pipeline),
    ]

    results = []

    for name, test_fn in tests:
        try:
            success = test_fn()
            results.append((name, success))
        except Exception as e:
            print(f"\nERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")

    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\nTotal: {passed}/{total} passed")

    return all(s for _, s in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
