"""Tests for date_resolver module."""

import pytest
from datetime import date

from agent.date_resolver import resolve_date, _last_day_of_month


class TestResolveDateYear:
    """Test year resolution."""

    def test_full_year(self):
        """Year 2024 resolves to full year."""
        today = date(2026, 1, 23)
        start, end = resolve_date("2024", today)
        assert start == "2024-01-01"
        assert end == "2024-12-31"

    def test_current_year(self):
        """Current year resolves to today."""
        today = date(2026, 1, 23)
        start, end = resolve_date("2026", today)
        assert start == "2026-01-01"
        assert end == "2026-01-23"

    def test_future_year(self):
        """Future year still resolves (uses today as end)."""
        today = date(2026, 1, 23)
        start, end = resolve_date("2027", today)
        assert start == "2027-01-01"
        # Future year uses today as end
        assert end == "2026-01-23"


class TestResolveDateMonth:
    """Test month resolution."""

    def test_month_iso_format(self):
        """Month in ISO format (2024-01)."""
        today = date(2026, 1, 23)
        start, end = resolve_date("2024-01", today)
        assert start == "2024-01-01"
        assert end == "2024-01-31"

    def test_month_february_leap_year(self):
        """February in leap year."""
        today = date(2026, 1, 23)
        start, end = resolve_date("2024-02", today)
        assert start == "2024-02-01"
        assert end == "2024-02-29"  # 2024 is leap year

    def test_month_february_non_leap(self):
        """February in non-leap year."""
        today = date(2026, 1, 23)
        start, end = resolve_date("2023-02", today)
        assert start == "2023-02-01"
        assert end == "2023-02-28"

    def test_month_name_only(self):
        """Month name without year uses current year."""
        today = date(2026, 1, 23)
        start, end = resolve_date("january", today)
        assert start == "2026-01-01"
        assert end == "2026-01-31"

    def test_month_name_with_year(self):
        """Month name with year."""
        today = date(2026, 1, 23)
        start, end = resolve_date("January 2024", today)
        assert start == "2024-01-01"
        assert end == "2024-01-31"

    def test_month_december(self):
        """December month."""
        today = date(2026, 1, 23)
        start, end = resolve_date("2024-12", today)
        assert start == "2024-12-01"
        assert end == "2024-12-31"


class TestResolveDateQuarter:
    """Test quarter resolution."""

    def test_q1(self):
        """Q1 resolution."""
        today = date(2026, 1, 23)
        start, end = resolve_date("Q1 2024", today)
        assert start == "2024-01-01"
        assert end == "2024-03-31"

    def test_q2(self):
        """Q2 resolution."""
        today = date(2026, 1, 23)
        start, end = resolve_date("Q2 2024", today)
        assert start == "2024-04-01"
        assert end == "2024-06-30"

    def test_q3(self):
        """Q3 resolution."""
        today = date(2026, 1, 23)
        start, end = resolve_date("Q3 2024", today)
        assert start == "2024-07-01"
        assert end == "2024-09-30"

    def test_q4(self):
        """Q4 resolution."""
        today = date(2026, 1, 23)
        start, end = resolve_date("Q4 2024", today)
        assert start == "2024-10-01"
        assert end == "2024-12-31"

    def test_quarter_no_year(self):
        """Quarter without year uses current year."""
        today = date(2026, 1, 23)
        start, end = resolve_date("Q1", today)
        assert start == "2026-01-01"
        assert end == "2026-03-31"

    def test_quarter_lowercase(self):
        """Quarter lowercase."""
        today = date(2026, 1, 23)
        start, end = resolve_date("q1 2024", today)
        assert start == "2024-01-01"
        assert end == "2024-03-31"


class TestResolveDateRelative:
    """Test relative date resolution."""

    def test_yesterday(self):
        """Yesterday."""
        today = date(2026, 1, 23)
        start, end = resolve_date("yesterday", today)
        assert start == "2026-01-22"
        assert end == "2026-01-22"

    def test_today(self):
        """Today."""
        today = date(2026, 1, 23)
        start, end = resolve_date("today", today)
        assert start == "2026-01-23"
        assert end == "2026-01-23"

    def test_last_week(self):
        """Last week (Mon-Sun)."""
        today = date(2026, 1, 23)  # Thursday
        start, end = resolve_date("last week", today)
        # Last week: Mon Jan 12 - Sun Jan 18
        assert start == "2026-01-12"
        assert end == "2026-01-18"

    def test_last_5_days(self):
        """Last 5 days."""
        today = date(2026, 1, 23)
        start, end = resolve_date("last 5 days", today)
        assert start == "2026-01-18"
        assert end == "2026-01-23"

    def test_last_2_weeks(self):
        """Last 2 weeks."""
        today = date(2026, 1, 23)
        start, end = resolve_date("last 2 weeks", today)
        assert start == "2026-01-09"
        assert end == "2026-01-23"

    def test_last_3_months(self):
        """Last 3 months."""
        today = date(2026, 1, 23)
        start, end = resolve_date("last 3 months", today)
        # 3 * 30 = 90 days back
        assert start == "2025-10-25"
        assert end == "2026-01-23"


class TestResolveDateRange:
    """Test year range resolution."""

    def test_year_range(self):
        """Year range 2020-2024."""
        today = date(2026, 1, 23)
        start, end = resolve_date("2020-2024", today)
        assert start == "2020-01-01"
        assert end == "2024-12-31"

    def test_year_range_with_dash(self):
        """Year range with en-dash."""
        today = date(2026, 1, 23)
        start, end = resolve_date("2020–2024", today)  # en-dash
        assert start == "2020-01-01"
        assert end == "2024-12-31"


class TestResolveDateAll:
    """Test 'all' resolution."""

    def test_all(self):
        """All data from 2008."""
        today = date(2026, 1, 23)
        start, end = resolve_date("all", today)
        assert start == "2008-01-01"
        assert end == "2026-01-23"


class TestResolveDateDefault:
    """Test default resolution."""

    def test_unknown_string(self):
        """Unknown string defaults to current year."""
        today = date(2026, 1, 23)
        start, end = resolve_date("something random", today)
        assert start == "2026-01-01"
        assert end == "2026-01-23"


class TestLastDayOfMonth:
    """Test _last_day_of_month helper."""

    def test_january(self):
        assert _last_day_of_month(2024, 1) == date(2024, 1, 31)

    def test_february_leap(self):
        assert _last_day_of_month(2024, 2) == date(2024, 2, 29)

    def test_february_non_leap(self):
        assert _last_day_of_month(2023, 2) == date(2023, 2, 28)

    def test_april(self):
        assert _last_day_of_month(2024, 4) == date(2024, 4, 30)

    def test_december(self):
        assert _last_day_of_month(2024, 12) == date(2024, 12, 31)
