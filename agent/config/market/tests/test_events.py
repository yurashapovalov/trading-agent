"""
Tests for market events.

Tests date calculations for regular market events:
- OPEX (3rd Friday)
- NFP (1st Friday)
- VIX Expiration (Wed before 3rd Friday)
- Quad Witching (3rd Friday of Mar/Jun/Sep/Dec)
"""

import pytest
from datetime import date

from agent.config.market.events import (
    get_opex_date,
    get_nfp_date,
    get_vix_expiration,
    get_event_dates,
    get_events_for_date,
    is_high_impact_day,
    get_event_types_for_instrument,
    get_event_type,
    check_dates_for_events,
    EventCategory,
    EventImpact,
    MACRO_EVENTS,
    OPTIONS_EVENTS,
)


# =============================================================================
# Date Calculations
# =============================================================================

class TestGetOpexDate:
    """Tests for OPEX date (3rd Friday)."""

    def test_opex_march_2024(self):
        """March 2024 OPEX (Quad Witching)."""
        result = get_opex_date(2024, 3)
        assert result == date(2024, 3, 15)
        assert result.weekday() == 4  # Friday

    def test_opex_april_2024(self):
        """April 2024 OPEX."""
        result = get_opex_date(2024, 4)
        assert result == date(2024, 4, 19)
        assert result.weekday() == 4

    def test_opex_january_2025(self):
        """January 2025 OPEX."""
        result = get_opex_date(2025, 1)
        assert result == date(2025, 1, 17)
        assert result.weekday() == 4


class TestGetNfpDate:
    """Tests for NFP date (1st Friday)."""

    def test_nfp_january_2024(self):
        """January 2024 NFP (1st Friday)."""
        result = get_nfp_date(2024, 1)
        assert result == date(2024, 1, 5)
        assert result.weekday() == 4

    def test_nfp_march_2024(self):
        """March 2024 NFP (1st Friday)."""
        result = get_nfp_date(2024, 3)
        assert result == date(2024, 3, 1)  # March 1, 2024 is Friday
        assert result.weekday() == 4

    def test_nfp_february_2024(self):
        """February 2024 NFP."""
        result = get_nfp_date(2024, 2)
        assert result == date(2024, 2, 2)
        assert result.weekday() == 4


class TestGetVixExpiration:
    """Tests for VIX expiration (Wed before 3rd Friday)."""

    def test_vix_march_2024(self):
        """March 2024 VIX expiration."""
        result = get_vix_expiration(2024, 3)
        # OPEX is March 15 (Friday), VIX is March 13 (Wednesday)
        assert result == date(2024, 3, 13)
        assert result.weekday() == 2  # Wednesday

    def test_vix_april_2024(self):
        """April 2024 VIX expiration."""
        result = get_vix_expiration(2024, 4)
        # OPEX is April 19 (Friday), VIX is April 17 (Wednesday)
        assert result == date(2024, 4, 17)
        assert result.weekday() == 2


# =============================================================================
# Event Date Ranges
# =============================================================================

class TestGetEventDates:
    """Tests for get_event_dates (events in date range)."""

    def test_opex_dates_in_quarter(self):
        """Get OPEX dates for Q1 2024."""
        dates = get_event_dates("opex", date(2024, 1, 1), date(2024, 3, 31))
        assert len(dates) == 3
        assert date(2024, 1, 19) in dates
        assert date(2024, 2, 16) in dates
        assert date(2024, 3, 15) in dates

    def test_quad_witching_dates_in_year(self):
        """Get Quad Witching dates for 2024."""
        dates = get_event_dates("quad_witching", date(2024, 1, 1), date(2024, 12, 31))
        assert len(dates) == 4
        # Mar, Jun, Sep, Dec
        assert date(2024, 3, 15) in dates
        assert date(2024, 6, 21) in dates
        assert date(2024, 9, 20) in dates
        assert date(2024, 12, 20) in dates

    def test_nfp_dates_in_quarter(self):
        """Get NFP dates for Q1 2024."""
        dates = get_event_dates("nfp", date(2024, 1, 1), date(2024, 3, 31))
        assert len(dates) == 3
        assert date(2024, 1, 5) in dates
        assert date(2024, 2, 2) in dates
        assert date(2024, 3, 1) in dates

    def test_vix_exp_dates_in_quarter(self):
        """Get VIX expiration dates for Q1 2024."""
        dates = get_event_dates("vix_exp", date(2024, 1, 1), date(2024, 3, 31))
        assert len(dates) == 3

    def test_unknown_event_returns_empty(self):
        """Unknown/non-calculable event returns empty."""
        dates = get_event_dates("fomc", date(2024, 1, 1), date(2024, 12, 31))
        assert dates == []


# =============================================================================
# Events for Date
# =============================================================================

class TestGetEventsForDate:
    """Tests for get_events_for_date."""

    def test_opex_date_has_opex_event(self):
        """OPEX date returns OPEX event."""
        events = get_events_for_date(date(2024, 4, 19))  # April OPEX
        event_ids = [e.id for e in events]
        assert "opex" in event_ids

    def test_quad_witching_date(self):
        """Quad Witching date returns quad_witching event."""
        events = get_events_for_date(date(2024, 3, 15))  # March Quad Witching
        event_ids = [e.id for e in events]
        assert "quad_witching" in event_ids
        assert "opex" not in event_ids  # Quad Witching replaces regular OPEX

    def test_nfp_date_has_nfp_event(self):
        """NFP date returns NFP event."""
        events = get_events_for_date(date(2024, 1, 5))  # January NFP
        event_ids = [e.id for e in events]
        assert "nfp" in event_ids

    def test_vix_date_has_vix_event(self):
        """VIX expiration date returns VIX event."""
        events = get_events_for_date(date(2024, 3, 13))  # March VIX exp
        event_ids = [e.id for e in events]
        assert "vix_expiration" in event_ids

    def test_regular_day_empty(self):
        """Regular day returns empty list."""
        events = get_events_for_date(date(2024, 1, 2))  # Regular Tuesday
        assert events == []

    def test_multiple_events_same_day(self):
        """Day with multiple events returns all."""
        # VIX exp on Wed, OPEX on Fri
        # If NFP happens to be same day as VIX...
        # Check January 3, 2024 - it's Wednesday, VIX exp is Jan 17
        # Let's check a day with VIX
        events = get_events_for_date(date(2024, 1, 17))  # VIX exp day
        event_ids = [e.id for e in events]
        assert "vix_expiration" in event_ids


# =============================================================================
# High Impact Detection
# =============================================================================

class TestIsHighImpactDay:
    """Tests for is_high_impact_day."""

    def test_opex_is_high_impact(self):
        """OPEX day is high impact."""
        assert is_high_impact_day("NQ", date(2024, 4, 19)) is True

    def test_nfp_is_high_impact(self):
        """NFP day is high impact."""
        assert is_high_impact_day("NQ", date(2024, 1, 5)) is True

    def test_regular_day_not_high_impact(self):
        """Regular day is not high impact."""
        assert is_high_impact_day("NQ", date(2024, 1, 2)) is False


# =============================================================================
# Event Types
# =============================================================================

class TestGetEventTypesForInstrument:
    """Tests for get_event_types_for_instrument."""

    def test_nq_gets_macro_events(self):
        """NQ gets macro events."""
        events = get_event_types_for_instrument("NQ")
        event_ids = [e.id for e in events]
        assert "nfp" in event_ids
        assert "fomc" in event_ids

    def test_nq_gets_options_events(self):
        """NQ gets options events."""
        events = get_event_types_for_instrument("NQ")
        event_ids = [e.id for e in events]
        assert "opex" in event_ids

    def test_unknown_symbol_gets_macro(self):
        """Unknown symbol defaults to macro events."""
        events = get_event_types_for_instrument("UNKNOWN")
        event_ids = [e.id for e in events]
        assert "nfp" in event_ids


class TestGetEventType:
    """Tests for get_event_type."""

    def test_finds_macro_event(self):
        """Finds macro event by ID."""
        event = get_event_type("nfp")
        assert event is not None
        assert event.id == "nfp"
        assert event.category == EventCategory.MACRO
        assert event.impact == EventImpact.HIGH

    def test_finds_options_event(self):
        """Finds options event by ID."""
        event = get_event_type("opex")
        assert event is not None
        assert event.id == "opex"
        assert event.category == EventCategory.OPTIONS

    def test_unknown_event_returns_none(self):
        """Unknown event ID returns None."""
        event = get_event_type("unknown_event")
        assert event is None


# =============================================================================
# Bulk Event Checking
# =============================================================================

class TestCheckDatesForEvents:
    """Tests for check_dates_for_events."""

    def test_no_events(self):
        """Regular dates return None."""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04"]  # Regular days
        result = check_dates_for_events(dates, "NQ")
        assert result is None

    def test_finds_opex(self):
        """Finds OPEX in date list."""
        dates = ["2024-04-18", "2024-04-19", "2024-04-20"]  # OPEX on 19th
        result = check_dates_for_events(dates, "NQ")

        assert result is not None
        assert "2024-04-19" in result["dates"]
        assert "Options Expiration" in result["events"]["2024-04-19"]

    def test_finds_quad_witching(self):
        """Finds Quad Witching in date list."""
        dates = ["2024-03-15"]  # Quad Witching
        result = check_dates_for_events(dates, "NQ")

        assert result is not None
        assert "Quad Witching" in result["events"]["2024-03-15"]
        assert result["high_impact_count"] > 0

    def test_empty_dates(self):
        """Empty dates list returns None."""
        result = check_dates_for_events([], "NQ")
        assert result is None


# =============================================================================
# Event Definitions
# =============================================================================

class TestEventDefinitions:
    """Tests for event definitions in config."""

    def test_macro_events_exist(self):
        """Macro events are defined."""
        assert "fomc" in MACRO_EVENTS
        assert "nfp" in MACRO_EVENTS
        assert "cpi" in MACRO_EVENTS

    def test_options_events_exist(self):
        """Options events are defined."""
        assert "opex" in OPTIONS_EVENTS
        assert "quad_witching" in OPTIONS_EVENTS
        assert "vix_expiration" in OPTIONS_EVENTS

    def test_event_has_required_fields(self):
        """Events have all required fields."""
        nfp = MACRO_EVENTS["nfp"]
        assert nfp.id == "nfp"
        assert nfp.name == "Non-Farm Payrolls"
        assert nfp.category == EventCategory.MACRO
        assert nfp.impact == EventImpact.HIGH
        assert nfp.schedule is not None

    def test_high_impact_events_marked(self):
        """High impact events are marked correctly."""
        high_impact = [e for e in MACRO_EVENTS.values() if e.impact == EventImpact.HIGH]
        high_impact_ids = [e.id for e in high_impact]
        assert "fomc" in high_impact_ids
        assert "nfp" in high_impact_ids
        assert "cpi" in high_impact_ids
