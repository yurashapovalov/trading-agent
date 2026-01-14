#!/usr/bin/env python3
"""
Run all agent tests.

Usage:
    python agent/scripts/run_tests.py              # Run all tests
    python agent/scripts/run_tests.py --unit       # Only unit tests
    python agent/scripts/run_tests.py --integration # Only integration tests
    python agent/scripts/run_tests.py --quick      # Skip slow integration tests
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n{YELLOW}{'='*60}{RESET}")
    print(f"{YELLOW}{description}{RESET}")
    print(f"{YELLOW}{'='*60}{RESET}")
    print(f"Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd)
    success = result.returncode == 0

    if success:
        print(f"\n{GREEN}✓ {description} PASSED{RESET}")
    else:
        print(f"\n{RED}✗ {description} FAILED{RESET}")

    return success


def main():
    parser = argparse.ArgumentParser(description="Run agent tests")
    parser.add_argument("--unit", action="store_true", help="Only run unit tests")
    parser.add_argument("--integration", action="store_true", help="Only run integration tests")
    parser.add_argument("--quick", action="store_true", help="Skip slow tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Default: run all tests
    run_unit = not args.integration
    run_integration = not args.unit

    results = []
    verbose_flag = ["-v"] if args.verbose else []

    # Unit tests (fast)
    if run_unit:
        success = run_command(
            ["python", "-m", "pytest", "agent/query_builder/tests/", *verbose_flag],
            "QueryBuilder Unit Tests"
        )
        results.append(("Unit Tests", success))

    # Integration tests (slower, requires LLM calls)
    if run_integration:
        if args.quick:
            # Run only 2 quick integration tests
            success = run_command(
                ["python", "-m", "pytest", "agent/tests/test_integration.py",
                 "-k", "find_extremum_jan_10_2025 or top_n_max_range",
                 *verbose_flag],
                "Integration Tests (Quick)"
            )
        else:
            success = run_command(
                ["python", "agent/tests/test_integration.py"],
                "Integration Tests (Golden Dataset)"
            )
        results.append(("Integration Tests", success))

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")

    all_passed = True
    for name, passed in results:
        status = f"{GREEN}PASSED{RESET}" if passed else f"{RED}FAILED{RESET}"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print(f"{'='*60}")
    if all_passed:
        print(f"{GREEN}ALL TESTS PASSED{RESET}")
        return 0
    else:
        print(f"{RED}SOME TESTS FAILED{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
