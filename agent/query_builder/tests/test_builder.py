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
from agent.query_builder.types import HolidayFilter


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

    assert "WITH daily_raw AS" in sql
    assert "daily AS" in sql
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


def test_calendar_filter_years():
    """Тест: фильтрация по годам."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2008-01-01",
            period_end="2025-01-01",
            years=[2012, 2016, 2020, 2024],  # Високосные годы
        ),
        grouping=Grouping.YEAR,
        metrics=[
            MetricSpec(Metric.AVG, "range", "avg_range"),
            MetricSpec(Metric.COUNT, alias="trading_days"),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_calendar_filter_years ===")
    print(sql)

    assert "YEAR(date) IN (2012, 2016, 2020, 2024)" in sql


def test_calendar_filter_months():
    """Тест: фильтрация по месяцам."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2020-01-01",
            period_end="2025-01-01",
            months=[6, 7, 8],  # Лето
        ),
        grouping=Grouping.TOTAL,
        metrics=[
            MetricSpec(Metric.AVG, "range", "avg_range"),
            MetricSpec(Metric.COUNT, alias="summer_days"),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_calendar_filter_months ===")
    print(sql)

    assert "MONTH(date) IN (6, 7, 8)" in sql


def test_calendar_filter_weekdays():
    """Тест: фильтрация по дням недели."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2020-01-01",
            period_end="2025-01-01",
            weekdays=["Monday", "Friday"],
        ),
        grouping=Grouping.WEEKDAY,
        metrics=[
            MetricSpec(Metric.AVG, "range", "avg_range"),
            MetricSpec(Metric.COUNT, alias="days"),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_calendar_filter_weekdays ===")
    print(sql)

    assert "DAYNAME(date) IN ('Monday', 'Friday')" in sql


def test_calendar_filter_combined():
    """Тест: комбинация нескольких календарных фильтров."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2020-01-01",
            period_end="2025-01-01",
            years=[2020, 2022, 2024],
            months=[1, 12],
            weekdays=["Friday"],
        ),
        grouping=Grouping.TOTAL,
        metrics=[
            MetricSpec(Metric.AVG, "range", "avg_range"),
            MetricSpec(Metric.COUNT, alias="days"),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_calendar_filter_combined ===")
    print(sql)

    assert "YEAR(date) IN (2020, 2022, 2024)" in sql
    assert "MONTH(date) IN (1, 12)" in sql
    assert "DAYNAME(date) IN ('Friday')" in sql


def test_event_time_with_calendar_filters():
    """Тест: EVENT_TIME с календарными фильтрами."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.MINUTES,
        filters=Filters(
            period_start="2020-01-01",
            period_end="2025-01-01",
            session="RTH",
            weekdays=["Tuesday"],
        ),
        grouping=Grouping.MINUTE_15,
        special_op=SpecialOp.EVENT_TIME,
        event_time_spec=EventTimeSpec(find="high"),
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_event_time_with_calendar_filters ===")
    print(sql)

    assert "DAYNAME(timestamp::date) IN ('Tuesday')" in sql
    assert "BETWEEN '09:30:00' AND '17:00:00'" in sql  # RTH ends at 17:00 ET (16:00 CT)


def test_event_time_both():
    """Тест: EVENT_TIME с find='both' для high и low."""
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
        event_time_spec=EventTimeSpec(find="both"),
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_event_time_both ===")
    print(sql)

    assert "daily_highs" in sql
    assert "daily_lows" in sql
    assert "event_type" in sql
    assert "UNION ALL" in sql


def test_holiday_filter_exclude_holidays():
    """Тест: исключение праздников (дни полного закрытия)."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2024-01-01",
            period_end="2024-12-31",
            market_holidays=HolidayFilter.EXCLUDE,
        ),
        grouping=Grouping.TOTAL,
        metrics=[
            MetricSpec(Metric.AVG, "range", "avg_range"),
            MetricSpec(Metric.COUNT, alias="trading_days"),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_holiday_filter_exclude_holidays ===")
    print(sql)

    # Должен исключить основные праздники 2024 года
    assert "NOT IN" in sql
    assert "2024-12-25" in sql  # Christmas
    assert "2024-01-01" in sql  # New Year


def test_holiday_filter_exclude_early_close():
    """Тест: исключение дней раннего закрытия."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2024-01-01",
            period_end="2024-12-31",
            early_close_days=HolidayFilter.EXCLUDE,
        ),
        grouping=Grouping.TOTAL,
        metrics=[
            MetricSpec(Metric.AVG, "range", "avg_range"),
            MetricSpec(Metric.COUNT, alias="trading_days"),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_holiday_filter_exclude_early_close ===")
    print(sql)

    # Должен исключить early close дни 2024 года
    assert "NOT IN" in sql
    assert "2024-12-24" in sql  # Christmas Eve
    assert "2024-11-29" in sql  # Black Friday


def test_holiday_filter_both():
    """Тест: исключение и праздников и early close."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2024-01-01",
            period_end="2024-12-31",
            market_holidays=HolidayFilter.EXCLUDE,
            early_close_days=HolidayFilter.EXCLUDE,
        ),
        grouping=Grouping.TOTAL,
        metrics=[
            MetricSpec(Metric.AVG, "range", "avg_range"),
            MetricSpec(Metric.COUNT, alias="trading_days"),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_holiday_filter_both ===")
    print(sql)

    # Должен исключить и праздники и early close
    assert "NOT IN" in sql
    assert "2024-12-25" in sql  # Christmas (full close)
    assert "2024-12-24" in sql  # Christmas Eve (early close)


def test_holiday_filter_only_early_close():
    """Тест: показать ТОЛЬКО дни раннего закрытия."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2024-01-01",
            period_end="2024-12-31",
            early_close_days=HolidayFilter.ONLY,
        ),
        grouping=Grouping.NONE,
        metrics=[
            MetricSpec(Metric.RANGE),
            MetricSpec(Metric.VOLUME),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_holiday_filter_only_early_close ===")
    print(sql)

    # Должен показать ТОЛЬКО early close дни
    assert "date IN (" in sql  # IN вместо NOT IN
    assert "2024-12-24" in sql  # Christmas Eve
    assert "2024-11-29" in sql  # Black Friday


def test_computed_columns():
    """Тест: вычисляемые колонки в daily CTE."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2024-01-01",
            period_end="2024-12-31",
        ),
        grouping=Grouping.NONE,
        metrics=[
            MetricSpec(Metric.RANGE),
            MetricSpec(Metric.CHANGE_PCT),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_computed_columns ===")
    print(sql)

    # Проверяем наличие вычисляемых колонок в daily_raw CTE
    assert "as close_to_low" in sql
    assert "as close_to_high" in sql
    assert "as open_to_high" in sql
    assert "as open_to_low" in sql
    assert "as body" in sql
    assert "as upper_wick" in sql
    assert "as lower_wick" in sql


def test_filter_by_close_to_low():
    """Тест: фильтрация по close_to_low (пример запроса про пятницы)."""
    spec = QuerySpec(
        symbol="NQ",
        source=Source.DAILY,
        filters=Filters(
            period_start="2020-01-01",
            period_end="2025-01-01",
            weekdays=["Friday"],
            conditions=[
                Condition("close_to_low", ">=", 200),
            ],
        ),
        grouping=Grouping.NONE,
        metrics=[
            MetricSpec(Metric.OPEN),
            MetricSpec(Metric.CLOSE),
            MetricSpec(Metric.LOW),
            MetricSpec(Metric.RANGE),
        ],
    )

    builder = QueryBuilder()
    sql = builder.build(spec)

    print("\n=== test_filter_by_close_to_low ===")
    print(sql)

    # Проверяем условие фильтрации
    assert "WHERE close_to_low >= 200" in sql
    assert "DAYNAME(date) IN ('Friday')" in sql


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
        # Новые тесты для календарных фильтров
        test_calendar_filter_years,
        test_calendar_filter_months,
        test_calendar_filter_weekdays,
        test_calendar_filter_combined,
        test_event_time_with_calendar_filters,
        test_event_time_both,
        # Тесты для holiday filter
        test_holiday_filter_exclude_holidays,
        test_holiday_filter_exclude_early_close,
        test_holiday_filter_both,
        test_holiday_filter_only_early_close,
        # Тесты для computed columns
        test_computed_columns,
        test_filter_by_close_to_low,
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
