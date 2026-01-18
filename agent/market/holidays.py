"""
Holiday calculations for trading instruments.

Calculates actual dates from holiday rules (e.g., "3rd Monday of January").
Determines if a date is a regular trading day, early close, or full closure.

Usage:
    from agent.market import get_day_type, get_close_time

    day_type = get_day_type("NQ", "2024-12-25")  # "closed"
    day_type = get_day_type("NQ", "2024-12-24")  # "early_close"

    close_time = get_close_time("NQ", "2024-12-24")  # "13:15"
"""

from datetime import date, timedelta
from typing import Literal

from agent.market.instruments import get_instrument


# =============================================================================
# Holiday Date Calculations
# =============================================================================

def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """
    Find nth occurrence of weekday in month.

    Args:
        year: Year
        month: Month (1-12)
        weekday: Day of week (0=Monday, 6=Sunday)
        n: Which occurrence (1=first, 2=second, -1=last)

    Returns:
        Date of nth weekday
    """
    if n > 0:
        # Find first day of month
        first_day = date(year, month, 1)
        # Find first occurrence of weekday
        days_until = (weekday - first_day.weekday()) % 7
        first_occurrence = first_day + timedelta(days=days_until)
        # Add (n-1) weeks
        return first_occurrence + timedelta(weeks=n - 1)
    else:
        # Last occurrence: start from next month and go back
        if month == 12:
            first_of_next = date(year + 1, 1, 1)
        else:
            first_of_next = date(year, month + 1, 1)
        last_day = first_of_next - timedelta(days=1)
        # Find last occurrence of weekday
        days_back = (last_day.weekday() - weekday) % 7
        return last_day - timedelta(days=days_back)


def _easter_sunday(year: int) -> date:
    """
    Calculate Easter Sunday using Anonymous Gregorian algorithm.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _observed_date(d: date) -> date:
    """
    Get observed date for fixed holidays.

    If holiday falls on Saturday, observed Friday.
    If holiday falls on Sunday, observed Monday.
    """
    if d.weekday() == 5:  # Saturday
        return d - timedelta(days=1)
    elif d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d


def get_holiday_date(rule: str, year: int) -> date | None:
    """
    Calculate actual date for a holiday rule.

    Args:
        rule: Holiday name/rule (e.g., "mlk_day", "thanksgiving")
        year: Year to calculate for

    Returns:
        Date or None if rule unknown
    """
    rule = rule.lower()

    # Fixed date holidays (with observed adjustment)
    if rule == "new_year":
        return _observed_date(date(year, 1, 1))
    elif rule == "juneteenth":
        return _observed_date(date(year, 6, 19))
    elif rule == "independence_day":
        return _observed_date(date(year, 7, 4))
    elif rule == "christmas":
        return _observed_date(date(year, 12, 25))

    # Nth weekday holidays
    elif rule == "mlk_day":
        # 3rd Monday of January
        return _nth_weekday_of_month(year, 1, 0, 3)
    elif rule == "presidents_day":
        # 3rd Monday of February
        return _nth_weekday_of_month(year, 2, 0, 3)
    elif rule == "memorial_day":
        # Last Monday of May
        return _nth_weekday_of_month(year, 5, 0, -1)
    elif rule == "labor_day":
        # 1st Monday of September
        return _nth_weekday_of_month(year, 9, 0, 1)
    elif rule == "thanksgiving":
        # 4th Thursday of November
        return _nth_weekday_of_month(year, 11, 3, 4)

    # Easter-based
    elif rule == "good_friday":
        easter = _easter_sunday(year)
        return easter - timedelta(days=2)

    # Early close days
    elif rule == "independence_day_eve":
        # July 3, or prior trading day if weekend
        july3 = date(year, 7, 3)
        if july3.weekday() == 5:  # Saturday
            return july3 - timedelta(days=1)  # Friday
        elif july3.weekday() == 6:  # Sunday
            return july3 - timedelta(days=2)  # Friday
        return july3

    elif rule == "black_friday":
        # Day after Thanksgiving
        thanksgiving = _nth_weekday_of_month(year, 11, 3, 4)
        return thanksgiving + timedelta(days=1)

    elif rule == "christmas_eve":
        # December 24, or prior trading day if weekend
        dec24 = date(year, 12, 24)
        if dec24.weekday() == 5:  # Saturday
            return dec24 - timedelta(days=1)
        elif dec24.weekday() == 6:  # Sunday
            return dec24 - timedelta(days=2)
        return dec24

    elif rule == "new_year_eve":
        # December 31, or prior trading day if weekend
        dec31 = date(year, 12, 31)
        if dec31.weekday() == 5:  # Saturday
            return dec31 - timedelta(days=1)
        elif dec31.weekday() == 6:  # Sunday
            return dec31 - timedelta(days=2)
        return dec31

    return None


def get_holidays_for_year(symbol: str, year: int) -> dict[str, list[date]]:
    """
    Get all holiday dates for a symbol and year.

    Returns:
        {
            "full_close": [date, date, ...],
            "early_close": [date, date, ...]
        }
    """
    instrument = get_instrument(symbol)
    if not instrument:
        return {"full_close": [], "early_close": []}

    holidays = instrument.get("holidays", {})
    result = {"full_close": [], "early_close": []}

    # Full close dates
    for rule in holidays.get("full_close", []):
        d = get_holiday_date(rule, year)
        if d:
            result["full_close"].append(d)

    # Early close dates
    for rule in holidays.get("early_close", {}).keys():
        d = get_holiday_date(rule, year)
        if d:
            result["early_close"].append(d)

    return result


# =============================================================================
# Day Type Detection
# =============================================================================

DayType = Literal["regular", "early_close", "closed"]


def get_day_type(symbol: str, check_date: str | date) -> DayType:
    """
    Determine if date is regular, early close, or closed.

    Args:
        symbol: Instrument symbol
        check_date: Date to check (string YYYY-MM-DD or date object)

    Returns:
        "regular", "early_close", or "closed"
    """
    if isinstance(check_date, str):
        check_date = date.fromisoformat(check_date)

    instrument = get_instrument(symbol)
    if not instrument:
        return "regular"

    holidays = instrument.get("holidays", {})
    year = check_date.year

    # Check full close
    for rule in holidays.get("full_close", []):
        holiday_date = get_holiday_date(rule, year)
        if holiday_date == check_date:
            return "closed"

    # Check early close
    for rule in holidays.get("early_close", {}).keys():
        holiday_date = get_holiday_date(rule, year)
        if holiday_date == check_date:
            return "early_close"

    return "regular"


def get_close_time(symbol: str, check_date: str | date) -> str | None:
    """
    Get close time for a specific date.

    Args:
        symbol: Instrument symbol
        check_date: Date to check

    Returns:
        Close time string (e.g., "17:00" for regular, "13:15" for early close)
        or None if market is closed
    """
    if isinstance(check_date, str):
        check_date = date.fromisoformat(check_date)

    day_type = get_day_type(symbol, check_date)

    if day_type == "closed":
        return None

    instrument = get_instrument(symbol)
    if not instrument:
        return None

    if day_type == "early_close":
        # Find which early close rule matches
        holidays = instrument.get("holidays", {})
        early_closes = holidays.get("early_close", {})
        year = check_date.year

        for rule, close_time in early_closes.items():
            holiday_date = get_holiday_date(rule, year)
            if holiday_date == check_date:
                return close_time

    # Regular day - return trading day end
    return instrument.get("trading_day_end", "17:00")


def is_trading_day(symbol: str, check_date: str | date) -> bool:
    """Check if date is a trading day (not closed and not weekend)."""
    if isinstance(check_date, str):
        check_date = date.fromisoformat(check_date)

    # Weekend check
    if check_date.weekday() >= 5:
        return False

    return get_day_type(symbol, check_date) != "closed"


# =============================================================================
# Holiday Names (human-readable)
# =============================================================================

HOLIDAY_NAMES = {
    "new_year": "New Year's Day",
    "mlk_day": "Martin Luther King Jr. Day",
    "presidents_day": "Presidents Day",
    "good_friday": "Good Friday",
    "memorial_day": "Memorial Day",
    "juneteenth": "Juneteenth",
    "independence_day": "Independence Day",
    "labor_day": "Labor Day",
    "thanksgiving": "Thanksgiving",
    "christmas": "Christmas Day",
    # Early close days
    "independence_day_eve": "Day before Independence Day",
    "black_friday": "Black Friday",
    "christmas_eve": "Christmas Eve",
    "new_year_eve": "New Year's Eve",
}


def check_dates_for_holidays(
    dates: list[str],
    symbol: str = "NQ",
) -> dict | None:
    """
    Check if any requested dates fall on market holidays or early close.

    Returns None if no issues, or dict with holiday info for Analyst.
    """
    if not dates:
        return None

    instrument = get_instrument(symbol)
    if not instrument:
        return None

    holidays_config = instrument.get("holidays", {})

    # Build date -> name maps for requested years
    years = {int(d[:4]) for d in dates if len(d) >= 4}

    full_close_map = {}  # date_str -> name
    early_close_map = {}  # date_str -> name

    for year in years:
        # Full close holidays
        for rule in holidays_config.get("full_close", []):
            d = get_holiday_date(rule, year)
            if d:
                full_close_map[d.isoformat()] = HOLIDAY_NAMES.get(rule, "Market Holiday")

        # Early close holidays
        for rule in holidays_config.get("early_close", {}).keys():
            d = get_holiday_date(rule, year)
            if d:
                early_close_map[d.isoformat()] = HOLIDAY_NAMES.get(rule, "Early Close")

    # Check requested dates
    holiday_dates = []
    early_close_dates = []
    holiday_names = {}

    for d in dates:
        if d in full_close_map:
            holiday_dates.append(d)
            holiday_names[d] = full_close_map[d]
        elif d in early_close_map:
            early_close_dates.append(d)
            holiday_names[d] = early_close_map[d] + " (early close)"

    if not holiday_dates and not early_close_dates:
        return None

    return {
        "holiday_dates": holiday_dates,
        "early_close_dates": early_close_dates,
        "holiday_names": holiday_names,
        "all_holidays": len(holiday_dates) == len(dates),
    }
