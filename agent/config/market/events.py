"""
Regular market events.

Usage:
    from agent.config.market import get_event_types_for_instrument, is_high_impact_day
"""

from datetime import date, timedelta
from enum import Enum
from dataclasses import dataclass


class EventCategory(Enum):
    MACRO = "macro"
    OIL = "oil"
    CRYPTO = "crypto"
    STOCKS = "stocks"
    OPTIONS = "options"


class EventImpact(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class MarketEvent:
    """Definition of a market event (NFP, FOMC, OPEX, etc.)."""
    id: str
    name: str
    category: EventCategory
    impact: EventImpact
    schedule: str
    typical_time: str | None = None


# =============================================================================
# Event Definitions
# =============================================================================

MACRO_EVENTS = {
    "fomc": MarketEvent("fomc", "FOMC Rate Decision", EventCategory.MACRO, EventImpact.HIGH, "8x/year", "14:00"),
    "nfp": MarketEvent("nfp", "Non-Farm Payrolls", EventCategory.MACRO, EventImpact.HIGH, "1st Friday", "08:30"),
    "cpi": MarketEvent("cpi", "CPI", EventCategory.MACRO, EventImpact.HIGH, "monthly", "08:30"),
    "ppi": MarketEvent("ppi", "PPI", EventCategory.MACRO, EventImpact.MEDIUM, "monthly", "08:30"),
    "gdp": MarketEvent("gdp", "GDP", EventCategory.MACRO, EventImpact.MEDIUM, "quarterly", "08:30"),
    "pce": MarketEvent("pce", "PCE", EventCategory.MACRO, EventImpact.HIGH, "monthly", "08:30"),
    "retail_sales": MarketEvent("retail_sales", "Retail Sales", EventCategory.MACRO, EventImpact.MEDIUM, "monthly", "08:30"),
    "jobless_claims": MarketEvent("jobless_claims", "Initial Jobless Claims", EventCategory.MACRO, EventImpact.LOW, "Thursday", "08:30"),
    "ism_manufacturing": MarketEvent("ism_manufacturing", "ISM Manufacturing", EventCategory.MACRO, EventImpact.MEDIUM, "1st biz day", "10:00"),
    "ism_services": MarketEvent("ism_services", "ISM Services", EventCategory.MACRO, EventImpact.MEDIUM, "3rd biz day", "10:00"),
    "consumer_confidence": MarketEvent("consumer_confidence", "Consumer Confidence", EventCategory.MACRO, EventImpact.MEDIUM, "monthly", "10:00"),
    "michigan_sentiment": MarketEvent("michigan_sentiment", "Michigan Sentiment", EventCategory.MACRO, EventImpact.MEDIUM, "monthly", "10:00"),
    "durable_goods": MarketEvent("durable_goods", "Durable Goods Orders", EventCategory.MACRO, EventImpact.MEDIUM, "monthly", "08:30"),
    "industrial_production": MarketEvent("industrial_production", "Industrial Production", EventCategory.MACRO, EventImpact.LOW, "monthly", "09:15"),
}

OIL_EVENTS = {
    "eia_crude": MarketEvent("eia_crude", "EIA Crude Inventories", EventCategory.OIL, EventImpact.HIGH, "Wednesday", "10:30"),
    "api_crude": MarketEvent("api_crude", "API Crude Stock", EventCategory.OIL, EventImpact.MEDIUM, "Tuesday", "16:30"),
    "opec": MarketEvent("opec", "OPEC Meeting", EventCategory.OIL, EventImpact.HIGH, "~6x/year", None),
    "baker_hughes": MarketEvent("baker_hughes", "Baker Hughes Rig Count", EventCategory.OIL, EventImpact.LOW, "Friday", "13:00"),
}

CRYPTO_EVENTS = {
    "btc_halving": MarketEvent("btc_halving", "BTC Halving", EventCategory.CRYPTO, EventImpact.HIGH, "~4 years", None),
    "etf_flows": MarketEvent("etf_flows", "ETF Flows", EventCategory.CRYPTO, EventImpact.MEDIUM, "daily", "16:00"),
    "token_unlocks": MarketEvent("token_unlocks", "Major Token Unlocks", EventCategory.CRYPTO, EventImpact.MEDIUM, "varies", None),
    "exchange_listing": MarketEvent("exchange_listing", "Exchange Listings", EventCategory.CRYPTO, EventImpact.MEDIUM, "varies", None),
}

STOCKS_EVENTS = {
    "earnings": MarketEvent("earnings", "Earnings", EventCategory.STOCKS, EventImpact.HIGH, "quarterly", None),
    "dividends_ex": MarketEvent("dividends_ex", "Dividends Ex-Date", EventCategory.STOCKS, EventImpact.MEDIUM, "quarterly", None),
    "stock_splits": MarketEvent("stock_splits", "Stock Splits", EventCategory.STOCKS, EventImpact.MEDIUM, "varies", None),
    "index_rebalance": MarketEvent("index_rebalance", "Index Rebalance", EventCategory.STOCKS, EventImpact.MEDIUM, "quarterly", None),
    "fda_decisions": MarketEvent("fda_decisions", "FDA Decisions", EventCategory.STOCKS, EventImpact.HIGH, "varies", None),
    "product_launches": MarketEvent("product_launches", "Product Launches", EventCategory.STOCKS, EventImpact.MEDIUM, "varies", None),
}

OPTIONS_EVENTS = {
    "opex": MarketEvent("opex", "Options Expiration", EventCategory.OPTIONS, EventImpact.MEDIUM, "3rd Friday", "16:00"),
    "quad_witching": MarketEvent("quad_witching", "Quad Witching", EventCategory.OPTIONS, EventImpact.HIGH, "3rd Fri Mar/Jun/Sep/Dec", "16:00"),
    "vix_expiration": MarketEvent("vix_expiration", "VIX Expiration", EventCategory.OPTIONS, EventImpact.MEDIUM, "Wed before 3rd Fri", "09:00"),
}

EVENT_GROUPS = {
    "macro": MACRO_EVENTS,
    "oil": OIL_EVENTS,
    "crypto": CRYPTO_EVENTS,
    "stocks": STOCKS_EVENTS,
    "options": OPTIONS_EVENTS,
}


# =============================================================================
# Date Calculations
# =============================================================================

# Import shared date utility from holidays
from agent.config.market.holidays import _nth_weekday_of_month as _nth_weekday


def get_opex_date(year: int, month: int) -> date:
    """Third Friday of month."""
    return _nth_weekday(year, month, 4, 3)


def get_nfp_date(year: int, month: int) -> date:
    """First Friday of month."""
    return _nth_weekday(year, month, 4, 1)


def get_vix_expiration(year: int, month: int) -> date:
    """Wednesday before third Friday."""
    return get_opex_date(year, month) - timedelta(days=2)


def get_event_dates(
    event_id: str,
    start_date: date,
    end_date: date,
) -> list[date]:
    """Get all dates for a calculable event within a period.

    Supported event_ids (calculable):
    - opex: ALL options expiration (3rd Friday every month, includes Quad Witching)
    - quad_witching: Quad Witching only (3rd Friday of Mar/Jun/Sep/Dec)
    - nfp: Non-Farm Payrolls (1st Friday)
    - vix_exp: VIX Expiration (Wednesday before 3rd Friday)

    Returns empty list for non-calculable events (fomc, cpi, etc.)
    These require historical data files.
    """
    dates = []
    event_id = event_id.lower()

    # Iterate through all months in range
    current = date(start_date.year, start_date.month, 1)
    while current <= end_date:
        year, month = current.year, current.month

        if event_id == "opex":
            # ALL 3rd Fridays (including Quad Witching months)
            d = get_opex_date(year, month)
            if start_date <= d <= end_date:
                dates.append(d)

        elif event_id == "quad_witching":
            # Quad Witching ONLY - 3rd Friday of Mar, Jun, Sep, Dec
            if month in (3, 6, 9, 12):
                d = get_opex_date(year, month)
                if start_date <= d <= end_date:
                    dates.append(d)

        elif event_id == "nfp":
            d = get_nfp_date(year, month)
            if start_date <= d <= end_date:
                dates.append(d)

        elif event_id == "vix_exp":
            d = get_vix_expiration(year, month)
            if start_date <= d <= end_date:
                dates.append(d)

        # Move to next month
        if month == 12:
            current = date(year + 1, 1, 1)
        else:
            current = date(year, month + 1, 1)

    return dates


# =============================================================================
# Public API
# =============================================================================

def get_event_types_for_instrument(symbol: str) -> list[MarketEvent]:
    """Get event types affecting instrument (reads from instruments.py)."""
    from agent.config.market.instruments import get_instrument

    instrument = get_instrument(symbol)
    groups = instrument.get("events", ["macro"]) if instrument else ["macro"]

    events = []
    for g in groups:
        if g in EVENT_GROUPS:
            events.extend(EVENT_GROUPS[g].values())
    return events


def get_event_type(event_id: str) -> MarketEvent | None:
    """Get event type by ID."""
    for group in EVENT_GROUPS.values():
        if event_id in group:
            return group[event_id]
    return None


def is_high_impact_day(symbol: str, d: date) -> bool:
    """Check if date has high-impact events (calculable only: OPEX, NFP)."""
    if d == get_opex_date(d.year, d.month):
        return True
    if d == get_nfp_date(d.year, d.month):
        return True
    return False


def get_events_for_date(d: date) -> list[MarketEvent]:
    """Get calculable events for a specific date.

    Checks: OPEX, Quad Witching, NFP, VIX Expiration.
    """
    events = []

    opex_date = get_opex_date(d.year, d.month)
    nfp_date = get_nfp_date(d.year, d.month)
    vix_date = get_vix_expiration(d.year, d.month)

    if d == opex_date:
        if d.month in (3, 6, 9, 12):
            events.append(OPTIONS_EVENTS["quad_witching"])
        else:
            events.append(OPTIONS_EVENTS["opex"])

    if d == nfp_date:
        events.append(MACRO_EVENTS["nfp"])

    if d == vix_date:
        events.append(OPTIONS_EVENTS["vix_expiration"])

    return events


def check_dates_for_events(
    dates: list[str],
    symbol: str = "NQ",
) -> dict | None:
    """
    Check if any requested dates have known events.

    Returns None if no events, or dict with event info for Analyst.
    Similar to check_dates_for_holidays().
    """
    from datetime import datetime
    from agent.config.market.instruments import get_instrument

    if not dates:
        return None

    instrument = get_instrument(symbol)
    if not instrument:
        return None

    # Get relevant event categories for this instrument
    relevant_categories = set(instrument.get("events", ["macro"]))

    event_dates = []  # dates with events
    event_map = {}    # date_str -> list of event names
    high_impact = 0

    for date_str in dates:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        events = get_events_for_date(d)

        # Filter by relevant categories
        relevant = [e for e in events if e.category.value in relevant_categories]

        if relevant:
            event_dates.append(date_str)
            event_map[date_str] = [e.name for e in relevant]
            high_impact += sum(1 for e in relevant if e.impact == EventImpact.HIGH)

    if not event_dates:
        return None

    return {
        "dates": event_dates,
        "events": event_map,  # {"2024-03-15": ["Quad Witching"], ...}
        "high_impact_count": high_impact,
    }
