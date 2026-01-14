"""
Тесты для QueryBuilder.

Запуск:
    python -m pytest agent/query_builder/tests/test_builder.py -v
    или
    python agent/query_builder/tests/test_builder.py
"""

import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from agent.query_builder import (
    QueryBuilder,
    QuerySpec,
    Source,
    Filters,
    Condition,
    Grouping,
    Metric,
    MetricSpec,
    SpecialOp,
    EventTimeSpec,
    TopNSpec,
)


def test_daily_simple():
    """Тест: простая статистика за период."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2024-01-01",
            period_end="2024-02-01",
        ),
        grouping=Grouping.TOTAL,
        metrics=[
            MetricSpec(Metric.AVG, "range", "avg_range"),
            MetricSpec(Metric.COUNT, alias="trading_days"),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_daily_simple ===")
    print(sql)

    assert "WITH daily AS" in sql
    assert "AVG(range)" in sql
    assert "COUNT(*)" in sql
    assert "'NQ'" in sql
    assert "'2024-01-01'" in sql


def test_daily_filter():
    """Тест: фильтрация дней по условию."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2020-01-01",
            period_end="2025-01-01",
            conditions=[
                Condition("change_pct", "<", -2.0),
            ],
        ),
        grouping=Grouping.NONE,
        metrics=[
            MetricSpec(Metric.OPEN),
            MetricSpec(Metric.CLOSE),
            MetricSpec(Metric.CHANGE_PCT),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_daily_filter ===")
    print(sql)

    assert "WHERE change_pct < -2.0" in sql
    assert "ORDER BY date" in sql


def test_daily_by_month():
    """Тест: группировка по месяцам."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2024-01-01",
            period_end="2025-01-01",
        ),
        grouping=Grouping.MONTH,
        metrics=[
            MetricSpec(Metric.AVG, "range", "avg_range"),
            MetricSpec(Metric.COUNT, alias="trading_days"),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_daily_by_month ===")
    print(sql)

    assert "STRFTIME(date, '%Y-%m')" in sql
    assert "GROUP BY" in sql


def test_daily_by_weekday():
    """Тест: группировка по дням недели."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2024-01-01",
            period_end="2025-01-01",
        ),
        grouping=Grouping.WEEKDAY,
        metrics=[
            MetricSpec(Metric.AVG, "volume", "avg_volume"),
            MetricSpec(Metric.COUNT, alias="days"),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_daily_by_weekday ===")
    print(sql)

    assert "DAYNAME(date)" in sql
    assert "DAYOFWEEK(date)" in sql


def test_event_time_high():
    """Тест: время формирования high дня."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.MINUTES,
        filters=Filters(
            period_start="2020-01-01",
            period_end="2025-01-01",
            session="RTH",
        ),
        grouping=Grouping.MINUTE_15,
        special_op=SpecialOp.EVENT_TIME,
        event_time_spec=EventTimeSpec(find="high"),
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_event_time_high ===")
    print(sql)

    assert "filtered_data" in sql
    assert "daily_extremes" in sql
    assert "distribution" in sql
    assert "ORDER BY high DESC" in sql
    assert "TIME_BUCKET" in sql
    assert "09:30:00" in sql  # RTH filter


def test_event_time_low():
    """Тест: время формирования low дня."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.MINUTES,
        filters=Filters(
            period_start="2021-01-01",
            period_end="2024-01-01",
            session="RTH",
        ),
        grouping=Grouping.MINUTE_15,
        special_op=SpecialOp.EVENT_TIME,
        event_time_spec=EventTimeSpec(find="low"),
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_event_time_low ===")
    print(sql)

    assert "ORDER BY low ASC" in sql


def test_top_n():
    """Тест: топ N записей."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2020-01-01",
            period_end="2025-01-01",
        ),
        grouping=Grouping.NONE,
        special_op=SpecialOp.TOP_N,
        top_n_spec=TopNSpec(n=10, order_by="range", direction="DESC"),
        metrics=[
            MetricSpec(Metric.RANGE),
            MetricSpec(Metric.CHANGE_PCT),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_top_n ===")
    print(sql)

    assert "ORDER BY range DESC" in sql
    assert "LIMIT 10" in sql


def test_daily_with_prev():
    """Тест: дневные данные с gap_pct."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY_WITH_PREV,
        filters=Filters(
            period_start="2024-01-01",
            period_end="2024-02-01",
            conditions=[
                Condition("gap_pct", ">", 1.0),
            ],
        ),
        grouping=Grouping.NONE,
        metrics=[
            MetricSpec(Metric.GAP_PCT),
            MetricSpec(Metric.CHANGE_PCT),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_daily_with_prev ===")
    print(sql)

    assert "daily_with_prev" in sql
    assert "LAG(close)" in sql
    assert "gap_pct" in sql
    assert "WHERE gap_pct > 1.0" in sql


def run_all_tests():
    """Запускает все тесты."""
    tests = [
        test_daily_simple,
        test_daily_filter,
        test_daily_by_month,
        test_daily_by_weekday,
        test_event_time_high,
        test_event_time_low,
        test_top_n,
        test_daily_with_prev,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
