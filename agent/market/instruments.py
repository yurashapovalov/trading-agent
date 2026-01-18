"""
Instrument configurations.

All times in ET (data timezone). CME native times are CT (+1h to get ET).
"""

INSTRUMENTS = {
    "NQ": {
        "name": "Nasdaq 100 E-mini",
        "exchange": "CME",
        "tick_size": 0.25,
        "tick_value": 5.0,
        "native_timezone": "CT",
        "data_timezone": "ET",

        # Available data (update when loading new data)
        "data_start": "2008-01-02",
        "data_end": "2026-01-07",

        # Trading day: 18:00 prev → 17:00 current (CME: 17:00-16:00 CT)
        "trading_day_start": "18:00",
        "trading_day_end": "17:00",

        "default_session": "RTH",
        "sessions": {  # All times in ET
            "RTH": ("09:30", "17:00"),
            "ETH": ("18:00", "17:00"),
            "OVERNIGHT": ("18:00", "09:30"),
            "ASIAN": ("18:00", "03:00"),
            "EUROPEAN": ("03:00", "09:30"),
            "MORNING": ("09:30", "12:30"),
            "AFTERNOON": ("12:30", "17:00"),
            "RTH_OPEN": ("09:30", "10:30"),
            "RTH_CLOSE": ("16:00", "17:00"),
        },

        "maintenance": ("17:00", "18:00"),

        "holidays": {
            "full_close": [
                "new_year", "mlk_day", "presidents_day", "good_friday",
                "memorial_day", "juneteenth", "independence_day",
                "labor_day", "thanksgiving", "christmas",
            ],
            "early_close": {
                "independence_day_eve": "13:15",
                "black_friday": "13:15",
                "christmas_eve": "13:15",
                "new_year_eve": "13:15",
            },
        },

        "events": ["macro", "options"],
    },
}


def get_instrument(symbol: str) -> dict | None:
    """Get instrument configuration."""
    return INSTRUMENTS.get(symbol.upper())


def get_session_times(symbol: str, session: str) -> tuple[str, str] | None:
    """Get session (start, end) times in ET."""
    instrument = get_instrument(symbol)
    if not instrument:
        return None
    return instrument.get("sessions", {}).get(session.upper())


def get_trading_day_boundaries(symbol: str) -> tuple[str, str] | None:
    """Get trading day (start, end) times."""
    instrument = get_instrument(symbol)
    if not instrument:
        return None
    start = instrument.get("trading_day_start")
    end = instrument.get("trading_day_end")
    return (start, end) if start and end else None


def get_maintenance_window(symbol: str) -> tuple[str, str] | None:
    """Get maintenance break window."""
    instrument = get_instrument(symbol)
    if not instrument:
        return None
    return instrument.get("maintenance")


def list_sessions(symbol: str) -> list[str]:
    """List available sessions for instrument."""
    instrument = get_instrument(symbol)
    if not instrument:
        return []
    return list(instrument.get("sessions", {}).keys())


def get_default_session(symbol: str) -> str:
    """Get default session for instrument."""
    instrument = get_instrument(symbol)
    if not instrument:
        return "RTH"
    return instrument.get("default_session", "RTH")


def get_trading_day_options(symbol: str, date_str: str = "") -> list[str]:
    """
    Get session options for clarification with holiday awareness.

    Returns user-facing strings like "RTH (09:30-17:00 ET)".
    Adjusts times for early close days.

    Args:
        symbol: Instrument symbol
        date_str: Date in YYYY-MM-DD format (for holiday check)
    """
    from datetime import datetime
    from agent.market.holidays import get_day_type, get_close_time

    # Check if it's a weekend
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            weekday = dt.weekday()
            weekday_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][weekday]
            if weekday >= 5:
                return [f"Market closed on {date_str} ({weekday_name})"]
        except ValueError:
            pass

    # Check if it's a holiday
    if date_str:
        day_type = get_day_type(symbol, date_str)
        if day_type == "closed":
            return [f"Market closed on {date_str}"]
        close_time = get_close_time(symbol, date_str) or "17:00"
    else:
        day_type = "regular"
        close_time = "17:00"

    result = []

    # RTH option
    rth = get_session_times(symbol, "RTH")
    if rth:
        rth_start = rth[0]
        rth_end = min(rth[1], close_time) if day_type == "early_close" else rth[1]
        suffix = " — early close" if day_type == "early_close" else ""
        result.append(f"RTH ({rth_start}-{rth_end} ET){suffix}")

    # ETH option (full trading day)
    eth = get_session_times(symbol, "ETH")
    if eth:
        eth_start = eth[0]
        eth_end = close_time
        suffix = " — early close" if day_type == "early_close" else ""
        result.append(f"ETH ({eth_start} prev - {eth_end} ET){suffix}")

    # Calendar day option
    result.append("Calendar day (00:00-23:59 ET)")

    return result or ["RTH", "ETH", "Calendar day"]
