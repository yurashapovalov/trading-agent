"""
Unit tests for date_resolver.py

Run: pytest agent/tests/test_date_resolver.py -v
"""

import pytest
from datetime import date

from agent.date_resolver import resolve_period, _prev_trading_day, _n_trading_days_ago
from agent.types import Period


class TestResolveYear:
    """Test year period resolution."""

    def test_year_2024(self):
        period = Period(type="year", value="2024")
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2024-01-01", "2024-12-31")

    def test_year_2023(self):
        period = Period(type="year", value="2023")
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2023-01-01", "2023-12-31")


class TestResolveMonth:
    """Test month period resolution."""

    def test_january_2024(self):
        period = Period(type="month", value="2024-01")
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2024-01-01", "2024-01-31")

    def test_february_2024_leap_year(self):
        period = Period(type="month", value="2024-02")
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2024-02-01", "2024-02-29")  # 2024 is leap year

    def test_december_2024(self):
        period = Period(type="month", value="2024-12")
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2024-12-01", "2024-12-31")


class TestResolveQuarter:
    """Test quarter period resolution."""

    def test_q1_2024(self):
        period = Period(type="quarter", year=2024, q=1)
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2024-01-01", "2024-03-31")

    def test_q2_2024(self):
        period = Period(type="quarter", year=2024, q=2)
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2024-04-01", "2024-06-30")

    def test_q3_2024(self):
        period = Period(type="quarter", year=2024, q=3)
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2024-07-01", "2024-09-30")

    def test_q4_2024(self):
        period = Period(type="quarter", year=2024, q=4)
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2024-10-01", "2024-12-31")


class TestResolveDate:
    """Test single date resolution."""

    def test_single_date(self):
        period = Period(type="date", value="2024-06-15")
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2024-06-15", "2024-06-15")


class TestResolveDateRange:
    """Test date range resolution."""

    def test_date_range(self):
        period = Period(type="range", start="2024-01-01", end="2024-06-30")
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result == ("2024-01-01", "2024-06-30")


class TestResolveRelative:
    """Test relative period resolution."""

    def test_today(self):
        today = date(2025, 1, 15)  # Wednesday
        period = Period(type="relative", value="today")
        result = resolve_period(period, today, "NQ")
        assert result == ("2025-01-15", "2025-01-15")

    def test_yesterday_weekday(self):
        today = date(2025, 1, 15)  # Wednesday
        period = Period(type="relative", value="yesterday")
        result = resolve_period(period, today, "NQ")
        assert result == ("2025-01-14", "2025-01-14")  # Tuesday

    def test_yesterday_after_weekend(self):
        today = date(2025, 1, 13)  # Monday
        period = Period(type="relative", value="yesterday")
        result = resolve_period(period, today, "NQ")
        assert result == ("2025-01-10", "2025-01-10")  # Friday (skip weekend)

    def test_last_week(self):
        today = date(2025, 1, 15)  # Wednesday
        period = Period(type="relative", value="last_week")
        result = resolve_period(period, today, "NQ")
        assert result == ("2025-01-06", "2025-01-10")  # Mon-Fri of prev week

    def test_this_week(self):
        today = date(2025, 1, 15)  # Wednesday
        period = Period(type="relative", value="this_week")
        result = resolve_period(period, today, "NQ")
        assert result == ("2025-01-13", "2025-01-15")  # Monday to today

    def test_last_month(self):
        today = date(2025, 1, 15)
        period = Period(type="relative", value="last_month")
        result = resolve_period(period, today, "NQ")
        assert result == ("2024-12-01", "2024-12-31")

    def test_this_month(self):
        today = date(2025, 1, 15)
        period = Period(type="relative", value="this_month")
        result = resolve_period(period, today, "NQ")
        assert result == ("2025-01-01", "2025-01-15")

    def test_ytd(self):
        today = date(2025, 3, 15)
        period = Period(type="relative", value="ytd")
        result = resolve_period(period, today, "NQ")
        assert result == ("2025-01-01", "2025-03-15")

    def test_last_year(self):
        today = date(2025, 3, 15)
        period = Period(type="relative", value="last_year")
        result = resolve_period(period, today, "NQ")
        assert result == ("2024-01-01", "2024-12-31")

    def test_last_n_days(self):
        today = date(2025, 1, 15)  # Wednesday
        period = Period(type="relative", value="last_n_days", n=5)
        result = resolve_period(period, today, "NQ")
        # 5 trading days before yesterday (Jan 14)
        # Jan 14, 13, 10, 9, 8 → start Jan 8
        assert result[1] == "2025-01-14"  # ends yesterday


class TestNoPeriod:
    """Test None/empty period handling."""

    def test_none_period(self):
        result = resolve_period(None, date(2025, 1, 15), "NQ")
        assert result is None

    def test_empty_period(self):
        period = Period(type=None)
        result = resolve_period(period, date(2025, 1, 15), "NQ")
        assert result is None


class TestTradingDayHelpers:
    """Test trading day helper functions."""

    def test_prev_trading_day_weekday(self):
        # Thursday → Wednesday
        result = _prev_trading_day(date(2025, 1, 16), "NQ")
        assert result == date(2025, 1, 15)

    def test_prev_trading_day_monday(self):
        # Monday → Friday
        result = _prev_trading_day(date(2025, 1, 13), "NQ")
        assert result == date(2025, 1, 10)

    def test_n_trading_days_ago(self):
        today = date(2025, 1, 15)  # Wednesday
        result = _n_trading_days_ago(today, 3, "NQ")
        # 3 days ago: Tue Jan 14, Mon Jan 13, Fri Jan 10
        assert result == date(2025, 1, 10)
