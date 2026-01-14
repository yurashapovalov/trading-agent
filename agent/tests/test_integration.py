"""
Integration tests for QueryBuilder special operations.

Tests the full pipeline: Question -> Understander -> QuerySpec -> QueryBuilder -> SQL -> Data

Golden dataset with verified values from database.

Usage:
    python -m pytest agent/tests/test_integration.py -v
    python -m pytest agent/tests/test_integration.py -v -k "find_extremum"
    python agent/tests/test_integration.py  # Run directly
"""

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# =============================================================================
# Golden Dataset - verified values from database
# =============================================================================

@dataclass
class GoldenTestCase:
    """Single test case with expected results."""
    name: str
    question: str
    expected_special_op: str
    expected_data: dict  # Key values to verify in results
    tolerance: float = 0.01  # For numeric comparisons


GOLDEN_DATASET = [
    # ----- FIND_EXTREMUM -----
    GoldenTestCase(
        name="find_extremum_jan_10_2025",
        question="во сколько был хай и лоу на NQ 10 января 2025?",
        expected_special_op="find_extremum",
        expected_data={
            "high_time": "06:13:00",
            "high_value": 21372.5,
            "low_time": "10:11:00",
            "low_value": 20874.75,
        },
    ),
    GoldenTestCase(
        name="find_extremum_aug_5_2024",
        question="когда был максимум и минимум NQ 5 августа 2024?",
        expected_special_op="find_extremum",
        expected_data={
            "high_time": "21:13:00",
            "high_value": 18437.0,
            "low_time": "01:55:00",
            "low_value": 17351.0,
        },
    ),

    # ----- TOP_N -----
    GoldenTestCase(
        name="top_n_max_range_2024",
        question="какой день был самым волатильным в 2024 году на NQ?",
        expected_special_op="top_n",
        expected_data={
            "top_date": "2024-08-05",
            "top_range_approx": 1086.0,  # range may vary slightly
        },
    ),

    # ----- EVENT_TIME -----
    # Note: EVENT_TIME returns distribution, so we check top bucket
    GoldenTestCase(
        name="event_time_high_2024_rth",
        question="в какое время чаще всего формируется high на NQ за 2024 год в RTH?",
        expected_special_op="event_time",
        expected_data={
            "top_bucket_contains": "09:30",  # 09:30 is most common (49 days)
            "min_count": 40,  # At least 40 occurrences
        },
    ),
    GoldenTestCase(
        name="event_time_low_2024_rth",
        question="когда обычно формируется минимум дня на NQ в 2024 году в RTH (09:30-16:00)?",
        expected_special_op="event_time",
        expected_data={
            "top_bucket_contains": "09:30",  # 09:30 is also most common for low (49 days)
            "min_count": 40,
        },
    ),

    # ----- FIND_EXTREMUM variations -----
    GoldenTestCase(
        name="find_extremum_high_only",
        question="во сколько был хай на NQ 3 января 2025?",
        expected_special_op="find_extremum",
        expected_data={
            "high_time": "14:39:00",
            "high_value": 21559.25,
        },
    ),

    # ----- Natural language variations -----
    GoldenTestCase(
        name="find_extremum_natural_language",
        question="NQ пятого августа 2024 - когда был максимум?",
        expected_special_op="find_extremum",
        expected_data={
            "high_time": "21:13:00",
            "high_value": 18437.0,
        },
    ),
]


# =============================================================================
# Test Runner
# =============================================================================

def run_pipeline(question: str) -> dict:
    """
    Run full pipeline and return structured result.

    Returns:
        {
            "query_spec": {...},
            "special_op": str,
            "sql": str,
            "rows": [...],
            "row_count": int,
            "error": str | None,
        }
    """
    from agent.graph import TradingGraph

    graph = TradingGraph()
    result = {
        "query_spec": None,
        "special_op": None,
        "sql": None,
        "rows": [],
        "row_count": 0,
        "error": None,
    }

    try:
        for event in graph.stream_sse(
            question=question,
            user_id="test_integration",
            session_id=f"test_{int(time.time())}",
            chat_history=[],
        ):
            event_type = event.get("type")

            if event_type == "step_end":
                agent = event.get("agent")
                output = event.get("output", {})

                if agent == "understander":
                    intent = output.get("intent", {})
                    result["query_spec"] = intent.get("query_spec")
                    if result["query_spec"]:
                        result["special_op"] = result["query_spec"].get("special_op")

                elif agent == "query_builder":
                    result["sql"] = output.get("sql_query")

                elif agent == "data_fetcher":
                    result["rows"] = output.get("rows", [])
                    result["row_count"] = output.get("row_count", 0)

            elif event_type == "error":
                result["error"] = event.get("message")

    except Exception as e:
        result["error"] = str(e)

    return result


def verify_data(result: dict, expected: dict, tolerance: float = 0.01) -> list[str]:
    """
    Verify result data against expected values.

    Returns list of error messages (empty if all passed).
    """
    errors = []
    rows = result.get("rows", [])

    if not rows:
        errors.append("No rows returned")
        return errors

    # For single-row results (FIND_EXTREMUM)
    row = rows[0] if len(rows) == 1 else None

    for key, expected_value in expected.items():
        if key == "high_time" and row:
            actual = str(row.get("high_time", ""))
            if expected_value not in actual:
                errors.append(f"high_time: expected {expected_value}, got {actual}")

        elif key == "high_value" and row:
            actual = row.get("high_value")
            if actual is not None and abs(actual - expected_value) > tolerance:
                errors.append(f"high_value: expected {expected_value}, got {actual}")

        elif key == "low_time" and row:
            actual = str(row.get("low_time", ""))
            if expected_value not in actual:
                errors.append(f"low_time: expected {expected_value}, got {actual}")

        elif key == "low_value" and row:
            actual = row.get("low_value")
            if actual is not None and abs(actual - expected_value) > tolerance:
                errors.append(f"low_value: expected {expected_value}, got {actual}")

        elif key == "top_date" and row:
            actual = str(row.get("date", ""))
            if expected_value not in actual:
                errors.append(f"top_date: expected {expected_value}, got {actual}")

        elif key == "top_range_approx" and row:
            actual = row.get("range")
            if actual is not None and abs(actual - expected_value) > 50:  # Allow 50 point variance
                errors.append(f"range: expected ~{expected_value}, got {actual}")

        elif key == "top_bucket_contains":
            # For EVENT_TIME: check if top bucket contains expected time
            found = False
            for r in rows[:3]:  # Check top 3 buckets
                bucket = str(r.get("time_bucket", ""))
                if expected_value in bucket:
                    found = True
                    break
            if not found:
                errors.append(f"top_bucket: expected to contain {expected_value} in top 3")

        elif key == "min_count":
            # For EVENT_TIME: check minimum count in top bucket
            if rows:
                top_count = rows[0].get("frequency", rows[0].get("count", rows[0].get("cnt", 0)))
                if top_count < expected_value:
                    errors.append(f"min_count: expected >= {expected_value}, got {top_count}")

    return errors


# =============================================================================
# Pytest Tests
# =============================================================================

import pytest


@pytest.fixture
def run_test():
    """Fixture to run pipeline and verify results."""
    def _run(test_case: GoldenTestCase) -> tuple[bool, list[str]]:
        print(f"\n{'='*60}")
        print(f"Test: {test_case.name}")
        print(f"Question: {test_case.question}")
        print(f"{'='*60}")

        result = run_pipeline(test_case.question)

        errors = []

        # Check for pipeline errors
        if result["error"]:
            errors.append(f"Pipeline error: {result['error']}")
            return False, errors

        # Check special_op
        actual_op = result["special_op"]
        if actual_op != test_case.expected_special_op:
            errors.append(f"special_op: expected {test_case.expected_special_op}, got {actual_op}")

        # Verify data
        data_errors = verify_data(result, test_case.expected_data, test_case.tolerance)
        errors.extend(data_errors)

        # Print results
        print(f"Special Op: {actual_op}")
        print(f"Rows: {result['row_count']}")
        if result['rows']:
            print(f"First row: {result['rows'][0]}")

        if errors:
            print(f"\nERRORS:")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"\n OK")

        return len(errors) == 0, errors

    return _run


# ----- FIND_EXTREMUM Tests -----

def test_find_extremum_jan_10_2025(run_test):
    """Test FIND_EXTREMUM for Jan 10, 2025 - known high/low times."""
    test_case = GOLDEN_DATASET[0]
    passed, errors = run_test(test_case)
    assert passed, f"Failed: {errors}"


def test_find_extremum_aug_5_2024(run_test):
    """Test FIND_EXTREMUM for Aug 5, 2024 - most volatile day."""
    test_case = GOLDEN_DATASET[1]
    passed, errors = run_test(test_case)
    assert passed, f"Failed: {errors}"


# ----- TOP_N Tests -----

def test_top_n_max_range_2024(run_test):
    """Test TOP_N - find most volatile day in 2024."""
    test_case = GOLDEN_DATASET[2]
    passed, errors = run_test(test_case)
    assert passed, f"Failed: {errors}"


# ----- EVENT_TIME Tests -----

def test_event_time_high_2024_rth(run_test):
    """Test EVENT_TIME - high time distribution for 2024 RTH."""
    test_case = GOLDEN_DATASET[3]
    passed, errors = run_test(test_case)
    assert passed, f"Failed: {errors}"


def test_event_time_low_2024_rth(run_test):
    """Test EVENT_TIME - low time distribution for 2024 RTH."""
    test_case = GOLDEN_DATASET[4]
    passed, errors = run_test(test_case)
    assert passed, f"Failed: {errors}"


# ----- Additional FIND_EXTREMUM Tests -----

def test_find_extremum_high_only(run_test):
    """Test FIND_EXTREMUM - only high (not both)."""
    test_case = GOLDEN_DATASET[5]
    passed, errors = run_test(test_case)
    assert passed, f"Failed: {errors}"


def test_find_extremum_natural_language(run_test):
    """Test FIND_EXTREMUM - natural language variation."""
    test_case = GOLDEN_DATASET[6]
    passed, errors = run_test(test_case)
    assert passed, f"Failed: {errors}"


# =============================================================================
# Direct Run
# =============================================================================

def run_all_tests():
    """Run all golden dataset tests without pytest."""
    print("\n" + "="*70)
    print("INTEGRATION TESTS - Golden Dataset")
    print("="*70)

    passed = 0
    failed = 0

    for test_case in GOLDEN_DATASET:
        print(f"\n{'='*60}")
        print(f"Test: {test_case.name}")
        print(f"Question: {test_case.question}")
        print(f"Expected: {test_case.expected_special_op}")
        print(f"{'='*60}")

        result = run_pipeline(test_case.question)

        errors = []

        if result["error"]:
            errors.append(f"Pipeline error: {result['error']}")
        else:
            if result["special_op"] != test_case.expected_special_op:
                errors.append(f"special_op: expected {test_case.expected_special_op}, got {result['special_op']}")

            data_errors = verify_data(result, test_case.expected_data, test_case.tolerance)
            errors.extend(data_errors)

        print(f"Special Op: {result['special_op']}")
        print(f"Rows: {result['row_count']}")
        if result['rows']:
            print(f"First row: {result['rows'][0]}")

        if errors:
            failed += 1
            print(f"\n FAILED:")
            for e in errors:
                print(f"  - {e}")
        else:
            passed += 1
            print(f"\n PASSED")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Passed: {passed}/{len(GOLDEN_DATASET)}")
    print(f"Failed: {failed}/{len(GOLDEN_DATASET)}")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
