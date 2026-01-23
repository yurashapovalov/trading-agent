"""
Resolve date strings to absolute date ranges.

Converts Parser 'when' strings to (start_date, end_date) tuples.
Used by Planner to create ExecutionPlan with concrete dates.
"""

import re
from datetime import date, timedelta


def resolve_date(when: str, today: date | None = None) -> tuple[str, str]:
    """
    Resolve 'when' string to (start_date, end_date).

    Supports:
    - Year: "2024"
    - Month: "2024-01", "January", "January 2024"
    - Quarter: "Q1 2024", "Q1"
    - Range: "2020-2024"
    - Relative: "yesterday", "today", "last week", "last 5 days"
    - All: "all"

    Args:
        when: Date string from Parser atom (e.g., "Q1 2024", "yesterday")
        today: Reference date (defaults to date.today())

    Returns:
        Tuple of (start_date, end_date) as YYYY-MM-DD strings
    """
    today = today or date.today()
    when_lower = when.lower().strip()

    if when_lower == "all":
        return "2008-01-01", today.isoformat()

    # Year: 2024
    if re.match(r"^\d{4}$", when):
        year = int(when)
        end = date(year, 12, 31) if year < today.year else today
        return f"{year}-01-01", end.isoformat()

    # Month: 2024-01
    if m := re.match(r"^(\d{4})-(\d{2})$", when):
        year, month = int(m.group(1)), int(m.group(2))
        return date(year, month, 1).isoformat(), _last_day_of_month(year, month).isoformat()

    # Month name: January, January 2024
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for name, num in months.items():
        if name in when_lower:
            year = int(m.group()) if (m := re.search(r"\d{4}", when)) else today.year
            return date(year, num, 1).isoformat(), _last_day_of_month(year, num).isoformat()

    # Quarter: Q1 2024
    if m := re.match(r"Q([1-4])\s*(\d{4})?", when, re.I):
        q = int(m.group(1))
        year = int(m.group(2)) if m.group(2) else today.year
        start_month = (q - 1) * 3 + 1
        end_month = start_month + 2
        return date(year, start_month, 1).isoformat(), _last_day_of_month(year, end_month).isoformat()

    # Relative
    if when_lower == "yesterday":
        d = today - timedelta(days=1)
        return d.isoformat(), d.isoformat()

    if when_lower == "today":
        return today.isoformat(), today.isoformat()

    if when_lower == "last week":
        start = today - timedelta(days=today.weekday() + 7)
        return start.isoformat(), (start + timedelta(days=6)).isoformat()

    # Last N days/weeks/months
    if m := re.match(r"last\s+(\d+)\s+(days?|weeks?|months?)", when_lower):
        n = int(m.group(1))
        unit = m.group(2)
        if "day" in unit:
            delta = timedelta(days=n)
        elif "week" in unit:
            delta = timedelta(weeks=n)
        else:
            delta = timedelta(days=n * 30)
        return (today - delta).isoformat(), today.isoformat()

    # Year range: 2020-2024
    if m := re.match(r"(\d{4})\s*[-–]\s*(\d{4})", when):
        start_year, end_year = int(m.group(1)), int(m.group(2))
        end = date(end_year, 12, 31) if end_year < today.year else today
        return f"{start_year}-01-01", end.isoformat()

    # Default: current year
    return f"{today.year}-01-01", today.isoformat()


def _last_day_of_month(year: int, month: int) -> date:
    """Last day of month."""
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)
