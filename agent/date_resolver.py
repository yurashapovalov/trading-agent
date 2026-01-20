"""
Resolve parsed period to absolute dates.

Converts Parser output to start/end dates with trading day logic.
"""

from datetime import date, timedelta
from agent.types import Period
from agent.config.market.holidays import is_trading_day


def resolve_period(
    period: Period | None,
    today: date,
    symbol: str = "NQ",
) -> tuple[str, str] | None:
    """
    Convert Period to absolute start/end dates.

    Args:
        period: Period from Parser (type, value, n, start, end, year, q)
        today: Today's date
        symbol: Instrument for trading day calculation

    Returns:
        Tuple of (start_date, end_date) as YYYY-MM-DD strings
        or None if no period specified
    """
    if not period or not period.type:
        return None

    if period.type == "relative":
        return _resolve_relative(period, today, symbol)

    if period.type == "year":
        year = int(period.value)
        return f"{year}-01-01", f"{year}-12-31"

    if period.type == "month":
        # value like "2024-01"
        year, month = period.value.split("-")
        year, month = int(year), int(month)
        # Last day of month
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        return f"{year}-{month:02d}-01", last_day.isoformat()

    if period.type == "date":
        # Single date
        return period.value, period.value

    if period.type == "range":
        return period.start, period.end

    if period.type == "quarter":
        year = period.year
        q = period.q
        quarter_starts = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}
        quarter_ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
        return f"{year}-{quarter_starts[q]}", f"{year}-{quarter_ends[q]}"

    return None


def _resolve_relative(
    period: Period,
    today: date,
    symbol: str,
) -> tuple[str, str]:
    """Resolve relative period to absolute dates."""
    value = period.value

    if value == "today":
        return today.isoformat(), today.isoformat()

    if value == "yesterday":
        yesterday = _prev_trading_day(today, symbol)
        return yesterday.isoformat(), yesterday.isoformat()

    if value == "day_before_yesterday":
        day1 = _prev_trading_day(today, symbol)
        day2 = _prev_trading_day(day1, symbol)
        return day2.isoformat(), day2.isoformat()

    if value == "last_week":
        # Mon-Fri of previous week
        # Find last Friday
        days_since_friday = (today.weekday() - 4) % 7
        if days_since_friday == 0:
            days_since_friday = 7  # If today is Friday, go to last Friday
        last_friday = today - timedelta(days=days_since_friday)
        last_monday = last_friday - timedelta(days=4)
        return last_monday.isoformat(), last_friday.isoformat()

    if value == "this_week":
        # Mon of this week to today
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        return monday.isoformat(), today.isoformat()

    if value == "last_n_days":
        n = period.n or 5
        start = _n_trading_days_ago(today, n, symbol)
        end = _prev_trading_day(today, symbol)
        return start.isoformat(), end.isoformat()

    if value == "last_n_weeks":
        n = period.n or 1
        # n weeks * 5 trading days
        trading_days = n * 5
        start = _n_trading_days_ago(today, trading_days, symbol)
        end = _prev_trading_day(today, symbol)
        return start.isoformat(), end.isoformat()

    if value == "last_month":
        # Previous calendar month
        first_of_this_month = date(today.year, today.month, 1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = date(last_of_prev_month.year, last_of_prev_month.month, 1)
        return first_of_prev_month.isoformat(), last_of_prev_month.isoformat()

    if value == "last_n_months":
        n = period.n or 1
        # Go back n months
        month = today.month - n
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        start = date(year, month, 1)
        end = _prev_trading_day(today, symbol)
        return start.isoformat(), end.isoformat()

    if value == "this_month":
        first_of_month = date(today.year, today.month, 1)
        return first_of_month.isoformat(), today.isoformat()

    if value == "ytd":
        first_of_year = date(today.year, 1, 1)
        return first_of_year.isoformat(), today.isoformat()

    if value == "mtd":
        first_of_month = date(today.year, today.month, 1)
        return first_of_month.isoformat(), today.isoformat()

    if value == "last_year":
        prev_year = today.year - 1
        return f"{prev_year}-01-01", f"{prev_year}-12-31"

    if value == "this_year":
        return f"{today.year}-01-01", today.isoformat()

    # Fallback
    return today.isoformat(), today.isoformat()


def _prev_trading_day(d: date, symbol: str) -> date:
    """Find previous trading day (skip weekends and holidays)."""
    d = d - timedelta(days=1)
    while not is_trading_day(symbol, d):
        d = d - timedelta(days=1)
    return d


def _n_trading_days_ago(d: date, n: int, symbol: str) -> date:
    """Find date that is N trading days before d."""
    count = 0
    current = d
    while count < n:
        current = current - timedelta(days=1)
        if is_trading_day(symbol, current):
            count += 1
    return current
