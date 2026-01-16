"""
Instrument configurations for QueryBuilder.

Contains trading rules for each instrument:
- Timezones (native exchange vs data storage)
- Trading day boundaries
- Session definitions (RTH, ETH, etc.)
- Maintenance windows
- Holiday schedules

⚠️ All times are in DATA TIMEZONE (ET) unless noted otherwise.
   Conversion from native timezone is already applied.
   Example: CME says RTH 08:30-16:00 CT → here 09:30-17:00 ET

Usage:
    from agent.query_builder.instruments import INSTRUMENTS, get_session_times

    config = INSTRUMENTS["NQ"]
    rth_start, rth_end = get_session_times("NQ", "RTH")
"""

# =============================================================================
# Instrument Configurations
# =============================================================================

INSTRUMENTS = {
    "NQ": {
        # ===========================================
        # Basic Info
        # ===========================================
        "name": "Nasdaq 100 E-mini",
        "exchange": "CME",
        "tick_size": 0.25,
        "tick_value": 5.0,

        # ===========================================
        # Timezones
        # ===========================================
        "native_timezone": "CT",   # CME official time (Chicago)
        "data_timezone": "ET",     # Our data storage (New York)
        # CT to ET conversion: +1 hour

        # ===========================================
        # Trading Day (in ET)
        # ===========================================
        # CME: Trading day runs 17:00 CT (Sun-Thu) to 16:00 CT (Mon-Fri)
        # In ET: 18:00 previous day to 17:00 current day
        # Example: Tuesday's trading day = Monday 18:00 ET → Tuesday 17:00 ET
        "trading_day_start": "18:00",  # CME: 17:00 CT (previous calendar day)
        "trading_day_end": "17:00",    # CME: 16:00 CT

        # ===========================================
        # Sessions (in ET)
        # ===========================================
        # All times converted from CT (+1 hour)
        "sessions": {
            # Core sessions
            "RTH": ("09:30", "17:00"),       # CME: 08:30-16:00 CT — Regular Trading Hours
            "ETH": ("18:00", "17:00"),       # CME: 17:00-16:00 CT — Electronic (full 23h)
            "OVERNIGHT": ("18:00", "09:30"), # CME: 17:00-08:30 CT — Before RTH

            # Regional sessions (approximate overlaps)
            "ASIAN": ("18:00", "03:00"),     # CME: 17:00-02:00 CT
            "EUROPEAN": ("03:00", "09:30"),  # CME: 02:00-08:30 CT

            # RTH segments
            "MORNING": ("09:30", "12:30"),   # CME: 08:30-11:30 CT — First half RTH
            "AFTERNOON": ("12:30", "17:00"), # CME: 11:30-16:00 CT — Second half RTH

            # Key hours
            "RTH_OPEN": ("09:30", "10:30"),  # CME: 08:30-09:30 CT — First hour
            "RTH_CLOSE": ("16:00", "17:00"), # CME: 15:00-16:00 CT — Last hour
        },

        # ===========================================
        # Maintenance Break (in ET)
        # ===========================================
        # Daily halt for system maintenance
        "maintenance": ("17:00", "18:00"),  # CME: 16:00-17:00 CT

        # ===========================================
        # Holidays (CME Globex schedule)
        # ===========================================
        # Rules, not dates — calculated for any year
        "holidays": {
            # Full market closure
            "full_close": [
                "new_year",         # January 1 (observed)
                "mlk_day",          # 3rd Monday of January
                "presidents_day",   # 3rd Monday of February
                "good_friday",      # Friday before Easter Sunday
                "memorial_day",     # Last Monday of May
                "juneteenth",       # June 19 (observed)
                "independence_day", # July 4 (observed)
                "labor_day",        # 1st Monday of September
                "thanksgiving",     # 4th Thursday of November
                "christmas",        # December 25 (observed)
            ],
            # Early close at 12:15 CT = 13:15 ET
            "early_close": {
                "independence_day_eve": "13:15",  # July 3 (or prior trading day)
                "black_friday": "13:15",          # Day after Thanksgiving
                "christmas_eve": "13:15",         # December 24 (or prior trading day)
                "new_year_eve": "13:15",          # December 31 (or prior trading day)
            },
        },
    },

    "ES": {
        # S&P 500 E-mini — same rules as NQ (CME Equity Index)
        "name": "S&P 500 E-mini",
        "exchange": "CME",
        "tick_size": 0.25,
        "tick_value": 12.50,
        "native_timezone": "CT",
        "data_timezone": "ET",
        "trading_day_start": "18:00",
        "trading_day_end": "17:00",
        "sessions": {
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
    },

    "CL": {
        # Crude Oil — NYMEX, different schedule (to be expanded)
        "name": "Crude Oil",
        "exchange": "NYMEX",
        "tick_size": 0.01,
        "tick_value": 10.0,
        "native_timezone": "CT",
        "data_timezone": "ET",
        "trading_day_start": "18:00",
        "trading_day_end": "17:00",
        "sessions": {
            "RTH": ("09:00", "14:30"),       # NYMEX pit hours (approximate)
            "ETH": ("18:00", "17:00"),
        },
        "maintenance": ("17:00", "18:00"),
        "holidays": {
            "full_close": [
                "new_year", "mlk_day", "presidents_day", "good_friday",
                "memorial_day", "juneteenth", "independence_day",
                "labor_day", "thanksgiving", "christmas",
            ],
            "early_close": {},
        },
    },
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_instrument(symbol: str) -> dict | None:
    """Get instrument configuration by symbol."""
    return INSTRUMENTS.get(symbol.upper())


def get_session_times(symbol: str, session: str) -> tuple[str, str] | None:
    """
    Get session start/end times for instrument.

    Times are in data timezone (ET), ready for SQL.

    Args:
        symbol: Instrument symbol (NQ, ES, CL)
        session: Session name (RTH, ETH, OVERNIGHT, etc.)

    Returns:
        (start_time, end_time) tuple or None if not found

    Example:
        >>> get_session_times("NQ", "RTH")
        ("09:30", "17:00")
    """
    instrument = get_instrument(symbol)
    if not instrument:
        return None

    sessions = instrument.get("sessions", {})
    return sessions.get(session.upper())


def get_trading_day_boundaries(symbol: str) -> tuple[str, str] | None:
    """
    Get trading day start/end times.

    Returns:
        (start_time, end_time) tuple in data timezone

    Example:
        >>> get_trading_day_boundaries("NQ")
        ("18:00", "17:00")  # Previous day 18:00 ET to current day 17:00 ET
    """
    instrument = get_instrument(symbol)
    if not instrument:
        return None

    start = instrument.get("trading_day_start")
    end = instrument.get("trading_day_end")

    if start and end:
        return (start, end)
    return None


def get_maintenance_window(symbol: str) -> tuple[str, str] | None:
    """Get daily maintenance break window."""
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
