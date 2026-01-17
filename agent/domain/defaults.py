"""
Instrument-aware defaults and assumption tracking.

Centralized defaults system for Understander. All defaults are applied
in one place and tracked as assumptions for transparency in Analyst responses.

Supported defaults:
    1. Session: "_default_" marker → resolves to RTH (if instrument has it)
    2. Period: "all" or null → resolves to full data range from DB

Markers:
    - "_default_": User implied concept but didn't specify value
    - "all": Use all available data (for period)
    - null: Concept not mentioned → no filtering applied

Usage:
    from agent.domain import apply_defaults

    intent = apply_defaults(intent, symbol="NQ")
    # intent["assumptions"] contains list of applied defaults for Analyst
"""

from dataclasses import dataclass
from typing import TypedDict

# Marker that LLM uses when user implies but doesn't specify
DEFAULT_MARKER = "_default_"


# =============================================================================
# Assumption Tracking
# =============================================================================

class Assumption(TypedDict):
    """Tracked assumption for transparency in response."""
    field: str
    value: str
    display_ru: str
    display_en: str


def create_assumption(field: str, value: str, display_ru: str, display_en: str) -> Assumption:
    """Create assumption record."""
    return {
        "field": field,
        "value": value,
        "display_ru": display_ru,
        "display_en": display_en,
    }


# =============================================================================
# Session Defaults
# =============================================================================

def get_session_default(symbol: str) -> tuple[str, str, str] | None:
    """
    Get default session for symbol.

    Returns:
        (value, display_ru, display_en) or None if clarification needed

    Logic:
        - If instrument has RTH → default to RTH
        - If instrument has only one session → use it
        - Otherwise → None (needs clarification)
    """
    from agent.query_builder.instruments import get_instrument, list_sessions

    sessions = list_sessions(symbol)

    if not sessions:
        return None  # Unknown instrument

    # Rule: if RTH exists, it's the default
    if "RTH" in sessions:
        instrument = get_instrument(symbol)
        times = instrument["sessions"]["RTH"]
        return (
            "RTH",
            f"RTH сессия ({times[0]}-{times[1]} ET)",
            f"RTH session ({times[0]}-{times[1]} ET)",
        )

    # Rule: if only one session, use it
    if len(sessions) == 1:
        session = sessions[0]
        instrument = get_instrument(symbol)
        times = instrument["sessions"][session]
        return (
            session,
            f"{session} ({times[0]}-{times[1]} ET)",
            f"{session} ({times[0]}-{times[1]} ET)",
        )

    # Multiple sessions, no RTH → clarification needed
    return None


# =============================================================================
# Period Defaults
# =============================================================================

def get_period_default(symbol: str) -> tuple[str, str, str, str] | None:
    """
    Get default period (full data range) for symbol.

    Returns:
        (start, end, display_ru, display_en) or None if not available
    """
    from agent.modules.sql import get_data_range

    data_range = get_data_range(symbol)
    if data_range:
        start = data_range['start_date']
        end = data_range['end_date']
        return (
            start,
            end,
            f"все данные ({start} — {end})",
            f"all data ({start} — {end})",
        )

    # Fallback
    from datetime import datetime
    start = "2008-01-01"
    end = datetime.now().strftime("%Y-%m-%d")
    return (
        start,
        end,
        f"все данные ({start} — {end})",
        f"all data ({start} — {end})",
    )


# =============================================================================
# Apply Defaults
# =============================================================================

def apply_defaults(intent: dict, symbol: str = "NQ") -> dict:
    """
    Apply instrument-aware defaults to intent and track assumptions.

    Processes "_default_" markers from LLM:
    - Resolves to actual values based on instrument config
    - Creates assumption records for transparency in Analyst response

    Args:
        intent: Intent dict from Understander
        symbol: Instrument symbol

    Returns:
        Modified intent with:
        - Resolved values (no more "_default_" markers)
        - "assumptions" list for Analyst to mention
        - "needs_clarification" dict if defaults couldn't be resolved
    """
    if intent.get("type") != "data":
        return intent

    query_spec = intent.get("query_spec", {})
    filters = query_spec.get("filters", {})
    assumptions: list[Assumption] = []
    needs_clarification: dict[str, list[str]] = {}

    # --- Session ---
    session = filters.get("session")

    # Check if this is a specific-date query that needs clarification
    # (trading day vs session is ambiguous for single-date queries)
    has_specific_date = _has_specific_date_query(filters)

    # Extract date for holiday-aware options
    specific_date = _get_specific_date(filters)

    if session == DEFAULT_MARKER:
        # If specific date query with _default_ session → clarify instead of assuming
        if has_specific_date:
            filters["session"] = None
            needs_clarification["trading_day_or_session"] = get_trading_day_options(
                symbol, specific_date
            )
        else:
            # Multi-day range query → safe to use default session
            default = get_session_default(symbol)
            if default:
                value, display_ru, display_en = default
                filters["session"] = value
                assumptions.append(create_assumption(
                    field="session",
                    value=value,
                    display_ru=display_ru,
                    display_en=display_en,
                ))
            else:
                # Can't default → needs clarification
                filters["session"] = None
                sessions = list_sessions_for_clarification(symbol)
                needs_clarification["session"] = sessions

    # --- Ambiguous date without session ---
    # If user specified a single date (or specific_dates) but no session,
    # we need clarification: trading day vs session
    elif session is None:
        if has_specific_date:
            needs_clarification["trading_day_or_session"] = get_trading_day_options(
                symbol, specific_date
            )

    # --- Period ---
    period_start = filters.get("period_start")
    period_end = filters.get("period_end")

    if not period_start or period_start == "all" or not period_end or period_end == "all":
        default = get_period_default(symbol)
        if default:
            start, end, display_ru, display_en = default
            filters["period_start"] = start
            filters["period_end"] = end
            assumptions.append(create_assumption(
                field="period",
                value=f"{start} — {end}",
                display_ru=display_ru,
                display_en=display_en,
            ))

    # --- Add more fields here as needed ---

    # Update intent
    if filters:
        query_spec["filters"] = filters
    intent["query_spec"] = query_spec
    intent["assumptions"] = assumptions

    # Update top-level period for compatibility
    intent["period_start"] = filters.get("period_start")
    intent["period_end"] = filters.get("period_end")

    if needs_clarification:
        intent["needs_clarification"] = needs_clarification

    return intent


def list_sessions_for_clarification(symbol: str) -> list[str]:
    """Get list of available sessions for clarification question."""
    from agent.query_builder.instruments import list_sessions, get_instrument

    sessions = list_sessions(symbol)
    instrument = get_instrument(symbol)

    result = []
    for s in sessions:
        times = instrument["sessions"].get(s, ("?", "?"))
        result.append(f"{s} ({times[0]}-{times[1]} ET)")

    return result


def _has_specific_date_query(filters: dict) -> bool:
    """
    Check if query targets specific date(s) vs date range.

    Returns True if:
    - specific_dates is set
    - period is exactly 1 day (period_end = period_start + 1 day)

    This indicates user asked about a specific day, not a range,
    so we need to clarify: trading day vs session.
    """
    # Has explicit specific_dates
    if filters.get("specific_dates"):
        return True

    # Check if period is single day
    period_start = filters.get("period_start")
    period_end = filters.get("period_end")

    if not period_start or not period_end:
        return False

    if period_start == "all" or period_end == "all":
        return False

    # Check if it's a 1-day period (YYYY-MM-DD format)
    try:
        from datetime import datetime, timedelta
        start = datetime.strptime(period_start, "%Y-%m-%d")
        end = datetime.strptime(period_end, "%Y-%m-%d")
        return (end - start) == timedelta(days=1)
    except (ValueError, TypeError):
        return False


def _get_specific_date(filters: dict) -> str:
    """
    Extract specific date from filters for holiday checking.

    Returns date string (YYYY-MM-DD) or empty string.
    """
    # Try specific_dates first
    specific_dates = filters.get("specific_dates")
    if specific_dates and len(specific_dates) > 0:
        return specific_dates[0]

    # Try period_start for single-day queries
    period_start = filters.get("period_start")
    if period_start and period_start != "all":
        return period_start

    return ""


def get_trading_day_options(symbol: str, date_str: str = "") -> list[str]:
    """
    Get session options for clarification with holiday awareness.

    Uses times from instruments.py + holidays.py (single source of truth).
    Adjusts times for early close days.

    Args:
        symbol: Instrument symbol
        date_str: Date in YYYY-MM-DD format (for holiday check)
    """
    from agent.query_builder.instruments import get_session_times
    from agent.query_builder.holidays import get_day_type, get_close_time

    # Check if it's a holiday
    if date_str:
        day_type = get_day_type(symbol, date_str)
        if day_type == "closed":
            return [f"Market closed on {date_str}"]

        # Get actual close time (may be early close)
        close_time = get_close_time(symbol, date_str) or "17:00"
    else:
        day_type = "regular"
        close_time = "17:00"

    result = []

    # RTH - regular trading hours
    rth = get_session_times(symbol, "RTH")
    if rth:
        rth_start = rth[0]
        # RTH end is min of session end and actual close time
        rth_end = min(rth[1], close_time) if day_type == "early_close" else rth[1]
        suffix = " — early close" if day_type == "early_close" else ""
        result.append(f"RTH ({rth_start}-{rth_end} ET){suffix}")

    # ETH = full trading day (prev day evening to current day close)
    eth = get_session_times(symbol, "ETH")
    if eth:
        eth_start = eth[0]
        eth_end = close_time  # actual close time for this date
        suffix = " — early close" if day_type == "early_close" else ""
        result.append(f"ETH ({eth_start} prev - {eth_end} ET){suffix}")

    # Calendar day (00:00-23:59 of that date)
    result.append("Calendar day (00:00-23:59 ET)")

    return result or ["RTH", "ETH", "Calendar day"]
