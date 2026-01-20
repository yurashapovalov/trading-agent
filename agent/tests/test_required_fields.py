"""
Test which field combinations lead to dead ends in executor.

Run: python -m agent.tests.test_required_fields
"""

from datetime import date
from agent.types import ParsedQuery, Period
from agent.executor import execute


def test_combination(name: str, **kwargs) -> dict:
    """Test a specific combination of fields."""
    # Defaults
    defaults = {
        "intent": "data",
        "what": name,
    }
    defaults.update(kwargs)

    try:
        parsed = ParsedQuery(**defaults)
        result = execute(parsed, symbol="NQ", today=date(2024, 12, 15))

        rows = result.get("row_count", 0)

        # Check if result is useful
        problems = []
        if rows > 1000:
            problems.append(f"too_many_rows({rows})")
        if rows == 0:
            problems.append("no_data")

        # Check if operation makes sense
        op = result.get("operation", "stats")
        res = result.get("result", {})

        if op == "stats" and not res:
            problems.append("empty_stats")
        if op == "top_n" and "rows" in res and len(res.get("rows", [])) == 0:
            problems.append("empty_top")

        return {
            "name": name,
            "status": result.get("intent"),
            "rows": rows,
            "operation": op,
            "problems": problems,
            "error": None,
        }
    except Exception as e:
        return {
            "name": name,
            "status": "error",
            "rows": 0,
            "problems": ["exception"],
            "error": str(e),
        }


def main():
    """Test all combinations."""

    period_2024 = Period(type="year", value="2024")
    period_q1 = Period(type="quarter", year=2024, q=1)

    period_all = Period(type="range", start="2008-01-01", end="2024-12-31")  # All data
    period_month = Period(type="month", value="2024-06")

    tests = [
        # === No period (defaults to current year) ===
        ("no period, no metric", {}),
        ("no period, metric=range", {"metric": "range"}),
        ("no period, operation=stats", {"operation": "stats"}),
        ("no period, operation=list", {"operation": "list"}),

        # === ALL data (huge range) ===
        ("ALL data, no metric", {"period": period_all}),
        ("ALL data, metric=range", {"period": period_all, "metric": "range"}),
        ("ALL data, operation=list", {"period": period_all, "operation": "list"}),
        ("ALL data, top_n=5", {"period": period_all, "operation": "top_n", "top_n": 5}),
        ("ALL data, seasonality", {"period": period_all, "operation": "seasonality", "group_by": "weekday"}),

        # === Year period ===
        ("period=2024, no metric", {"period": period_2024}),
        ("period=2024, operation=stats", {"period": period_2024, "operation": "stats"}),
        ("period=2024, operation=list", {"period": period_2024, "operation": "list"}),
        ("period=2024, operation=top_n", {"period": period_2024, "operation": "top_n", "top_n": 5}),
        ("period=2024, operation=seasonality", {"period": period_2024, "operation": "seasonality", "group_by": "weekday"}),

        # === Month period ===
        ("period=month, no metric", {"period": period_month}),
        ("period=month, operation=stats", {"period": period_month, "operation": "stats"}),

        # === With period and metric ===
        ("period=2024, metric=range", {"period": period_2024, "metric": "range"}),
        ("period=2024, metric=range, op=stats", {"period": period_2024, "metric": "range", "operation": "stats"}),
        ("period=2024, metric=range, op=top_n", {"period": period_2024, "metric": "range", "operation": "top_n", "top_n": 5}),

        # === Seasonality ===
        ("seasonality, no group_by", {"period": period_2024, "operation": "seasonality"}),
        ("seasonality, group_by=weekday", {"period": period_2024, "operation": "seasonality", "group_by": "weekday"}),
        ("seasonality, group_by=month", {"period": period_2024, "operation": "seasonality", "group_by": "month"}),

        # === Compare ===
        ("compare, no targets", {"operation": "compare"}),
        ("compare, targets=[2023,2024]", {"operation": "compare", "compare": ["2023", "2024"]}),

        # === Top N ===
        ("top_n, no n", {"period": period_2024, "operation": "top_n"}),
        ("top_n, n=5, no sort_by", {"period": period_2024, "operation": "top_n", "top_n": 5}),
        ("top_n, n=5, sort_by=range", {"period": period_2024, "operation": "top_n", "top_n": 5, "sort_by": "range"}),

        # === Filters without period ===
        ("weekday_filter only", {"weekday_filter": ["Monday", "Tuesday"]}),
        ("weekday_filter + period", {"period": period_2024, "weekday_filter": ["Monday"]}),
        ("weekday_filter + period + metric", {"period": period_2024, "weekday_filter": ["Monday"], "metric": "range"}),

        # === Edge cases ===
        ("condition only", {"condition": "range > 300"}),
        ("condition + period", {"period": period_2024, "condition": "range > 300"}),

        # === Potentially problematic ===
        ("just 'list' operation", {"operation": "list"}),
        ("just 'filter' operation", {"operation": "filter"}),
    ]

    print("=" * 80)
    print("TESTING FIELD COMBINATIONS")
    print("=" * 80)
    print()

    results = []
    for name, kwargs in tests:
        r = test_combination(name, **kwargs)
        results.append(r)

        has_problems = bool(r.get("problems"))
        status_icon = "⚠" if has_problems else "✓"
        if r["status"] == "error":
            status_icon = "✗"

        print(f"{status_icon} {name}")
        print(f"    → rows={r['rows']}, op={r.get('operation', '?')}")
        if r.get("problems"):
            print(f"    → PROBLEMS: {r['problems']}")
        if r["error"]:
            print(f"    → error: {r['error'][:60]}")
        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    ok = [r for r in results if not r.get("problems") and r["status"] == "data"]
    problematic = [r for r in results if r.get("problems")]
    errors = [r for r in results if r["status"] == "error"]

    print(f"\n✓ OK ({len(ok)}):")
    for r in ok:
        print(f"    {r['name']} → {r['rows']} rows")

    print(f"\n⚠ PROBLEMATIC ({len(problematic)}):")
    for r in problematic:
        print(f"    {r['name']} → {r['problems']}")

    print(f"\n✗ ERRORS ({len(errors)}):")
    for r in errors:
        print(f"    {r['name']} → {r['error'][:50]}")


if __name__ == "__main__":
    main()
