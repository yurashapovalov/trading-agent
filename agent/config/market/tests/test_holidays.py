"""
Tests for holiday calculations.

Tests date calculations for US market holidays:
- Fixed holidays (New Year, Christmas, etc.)
- Nth weekday holidays (MLK Day, Presidents Day, etc.)
- Easter-based holidays (Good Friday)
- Observed date adjustments (weekend → Friday/Monday)
"""

import pytest
from datetime import date

from agent.config.market.holidays import (
    _nth_weekday_of_month,
    _easter_sunday,
    _observed_date,
    get_holiday_date,
    get_holidays_for_year,
    get_day_type,
    get_close_time,
    is_trading_day,
    check_dates_for_holidays,
)


# =============================================================================
# Date Calculation Helpers
# =============================================================================

class TestNthWeekdayOfMonth:
    """Tests for _nth_weekday_of_month."""

    def test_first_monday(self):
        """First Monday of January 2024."""
        result = _nth_weekday_of_month(2024, 1, 0, 1)  # weekday=0=Monday, n=1=first
        assert result == date(2024, 1, 1)  # Jan 1, 2024 is Monday

    def test_third_monday(self):
        """Third Monday of January 2024 (MLK Day)."""
        result = _nth_weekday_of_month(2024, 1, 0, 3)
        assert result == date(2024, 1, 15)

    def test_last_monday(self):
        """Last Monday of May 2024 (Memorial Day)."""
        result = _nth_weekday_of_month(2024, 5, 0, -1)
        assert result == date(2024, 5, 27)

    def test_fourth_thursday(self):
        """Fourth Thursday of November 2024 (Thanksgiving)."""
        result = _nth_weekday_of_month(2024, 11, 3, 4)  # weekday=3=Thursday
        assert result == date(2024, 11, 28)

    def test_third_friday(self):
        """Third Friday of March 2024 (OPEX)."""
        result = _nth_weekday_of_month(2024, 3, 4, 3)  # weekday=4=Friday
        assert result == date(2024, 3, 15)


class TestEasterSunday:
    """Tests for Easter calculation."""

    def test_easter_2024(self):
        """Easter Sunday 2024."""
        result = _easter_sunday(2024)
        assert result == date(2024, 3, 31)

    def test_easter_2025(self):
        """Easter Sunday 2025."""
        result = _easter_sunday(2025)
        assert result == date(2025, 4, 20)

    def test_easter_2026(self):
        """Easter Sunday 2026."""
        result = _easter_sunday(2026)
        assert result == date(2026, 4, 5)


class TestObservedDate:
    """Tests for weekend observed date adjustment."""

    def test_saturday_observed_friday(self):
        """Holiday on Saturday observed on Friday."""
        # July 4, 2026 is Saturday
        result = _observed_date(date(2026, 7, 4))
        assert result == date(2026, 7, 3)  # Friday

    def test_sunday_observed_monday(self):
        """Holiday on Sunday observed on Monday."""
        # July 4, 2021 is Sunday
        result = _observed_date(date(2021, 7, 4))
        assert result == date(2021, 7, 5)  # Monday

    def test_weekday_unchanged(self):
        """Holiday on weekday stays the same."""
        # July 4, 2024 is Thursday
        result = _observed_date(date(2024, 7, 4))
        assert result == date(2024, 7, 4)


# =============================================================================
# Holiday Date Calculations
# =============================================================================

class TestGetHolidayDate:
    """Tests for get_holiday_date."""

    def test_new_year(self):
        """New Year's Day 2024."""
        result = get_holiday_date("new_year", 2024)
        assert result == date(2024, 1, 1)

    def test_mlk_day(self):
        """MLK Day 2024 (3rd Monday of January)."""
        result = get_holiday_date("mlk_day", 2024)
        assert result == date(2024, 1, 15)

    def test_presidents_day(self):
        """Presidents Day 2024 (3rd Monday of February)."""
        result = get_holiday_date("presidents_day", 2024)
        assert result == date(2024, 2, 19)

    def test_good_friday(self):
        """Good Friday 2024 (2 days before Easter)."""
        result = get_holiday_date("good_friday", 2024)
        assert result == date(2024, 3, 29)

    def test_memorial_day(self):
        """Memorial Day 2024 (last Monday of May)."""
        result = get_holiday_date("memorial_day", 2024)
        assert result == date(2024, 5, 27)

    def test_juneteenth(self):
        """Juneteenth 2024."""
        result = get_holiday_date("juneteenth", 2024)
        assert result == date(2024, 6, 19)

    def test_independence_day(self):
        """Independence Day 2024."""
        result = get_holiday_date("independence_day", 2024)
        assert result == date(2024, 7, 4)

    def test_labor_day(self):
        """Labor Day 2024 (1st Monday of September)."""
        result = get_holiday_date("labor_day", 2024)
        assert result == date(2024, 9, 2)

    def test_thanksgiving(self):
        """Thanksgiving 2024 (4th Thursday of November)."""
        result = get_holiday_date("thanksgiving", 2024)
        assert result == date(2024, 11, 28)

    def test_christmas(self):
        """Christmas 2024."""
        result = get_holiday_date("christmas", 2024)
        assert result == date(2024, 12, 25)

    def test_black_friday(self):
        """Black Friday 2024 (day after Thanksgiving)."""
        result = get_holiday_date("black_friday", 2024)
        assert result == date(2024, 11, 29)

    def test_christmas_eve(self):
        """Christmas Eve 2024."""
        result = get_holiday_date("christmas_eve", 2024)
        assert result == date(2024, 12, 24)

    def test_unknown_rule_returns_none(self):
        """Unknown holiday rule returns None."""
        result = get_holiday_date("unknown_holiday", 2024)
        assert result is None


# =============================================================================
# Day Type Detection
# =============================================================================

class TestGetDayType:
    """Tests for get_day_type."""

    def test_regular_day(self):
        """Regular trading day."""
        result = get_day_type("NQ", "2024-01-02")
        assert result == "regular"

    def test_closed_day(self):
        """Market closed on Christmas."""
        result = get_day_type("NQ", "2024-12-25")
        assert result == "closed"

    def test_early_close_day(self):
        """Early close on Christmas Eve."""
        result = get_day_type("NQ", "2024-12-24")
        assert result == "early_close"

    def test_unknown_symbol_returns_regular(self):
        """Unknown symbol defaults to regular."""
        result = get_day_type("UNKNOWN", "2024-12-25")
        assert result == "regular"

    def test_date_object_input(self):
        """Accepts date object as input."""
        result = get_day_type("NQ", date(2024, 12, 25))
        assert result == "closed"


class TestGetCloseTime:
    """Tests for get_close_time."""

    def test_regular_day_close(self):
        """Regular day close time."""
        result = get_close_time("NQ", "2024-01-02")
        assert result == "17:00"

    def test_early_close_day(self):
        """Early close time on Christmas Eve."""
        result = get_close_time("NQ", "2024-12-24")
        assert result == "13:15"

    def test_closed_day_returns_none(self):
        """Closed day returns None."""
        result = get_close_time("NQ", "2024-12-25")
        assert result is None


class TestIsTradingDay:
    """Tests for is_trading_day."""

    def test_regular_weekday(self):
        """Regular weekday is trading day."""
        result = is_trading_day("NQ", "2024-01-02")  # Tuesday
        assert result is True

    def test_saturday_not_trading(self):
        """Saturday is not trading day."""
        result = is_trading_day("NQ", "2024-01-06")  # Saturday
        assert result is False

    def test_sunday_not_trading(self):
        """Sunday is not trading day."""
        result = is_trading_day("NQ", "2024-01-07")  # Sunday
        assert result is False

    def test_holiday_not_trading(self):
        """Holiday is not trading day."""
        result = is_trading_day("NQ", "2024-12-25")  # Christmas
        assert result is False

    def test_early_close_is_trading(self):
        """Early close day is still a trading day."""
        result = is_trading_day("NQ", "2024-12-24")  # Christmas Eve
        assert result is True


# =============================================================================
# Bulk Holiday Checking
# =============================================================================

class TestCheckDatesForHolidays:
    """Tests for check_dates_for_holidays."""

    def test_no_holidays(self):
        """Regular dates return None."""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
        result = check_dates_for_holidays(dates, "NQ")
        assert result is None

    def test_finds_holidays(self):
        """Finds holidays in date list."""
        dates = ["2024-12-24", "2024-12-25", "2024-12-26"]
        result = check_dates_for_holidays(dates, "NQ")

        assert result is not None
        assert "2024-12-25" in result["holiday_dates"]
        assert "2024-12-24" in result["early_close_dates"]
        assert "Christmas Day" in result["holiday_names"]["2024-12-25"]

    def test_empty_dates(self):
        """Empty dates list returns None."""
        result = check_dates_for_holidays([], "NQ")
        assert result is None

    def test_unknown_symbol(self):
        """Unknown symbol returns None."""
        result = check_dates_for_holidays(["2024-12-25"], "UNKNOWN")
        assert result is None


class TestGetHolidaysForYear:
    """Tests for get_holidays_for_year."""

    def test_returns_full_and_early_close(self):
        """Returns both full close and early close dates."""
        result = get_holidays_for_year("NQ", 2024)

        assert "full_close" in result
        assert "early_close" in result
        assert len(result["full_close"]) > 0
        assert len(result["early_close"]) > 0

    def test_full_close_includes_christmas(self):
        """Full close includes Christmas."""
        result = get_holidays_for_year("NQ", 2024)
        assert date(2024, 12, 25) in result["full_close"]

    def test_early_close_includes_christmas_eve(self):
        """Early close includes Christmas Eve."""
        result = get_holidays_for_year("NQ", 2024)
        assert date(2024, 12, 24) in result["early_close"]

    def test_unknown_symbol_returns_empty(self):
        """Unknown symbol returns empty lists."""
        result = get_holidays_for_year("UNKNOWN", 2024)
        assert result == {"full_close": [], "early_close": []}
