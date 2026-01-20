"""
Market data — источники правды о торговых инструментах.

Содержит:
- instruments: Инструменты (NQ, ES, CL) и их параметры
- holidays: Праздники и торговое расписание
- events: Регулярные события (FOMC, NFP, OPEX, EIA...)

Используется:
- QueryBuilder для построения SQL
- Barb для валидации дат
- Analyst для контекста ответов
"""

from agent.config.market.instruments import (
    get_instrument,
    get_trading_day_boundaries,
    get_session_times,
    get_default_session,
    list_sessions,
)

from agent.config.market.holidays import (
    get_holiday_date,
    get_holidays_for_year,
    get_day_type,
    get_close_time,
    is_trading_day,
    check_dates_for_holidays,
)

from agent.config.market.events import (
    MarketEvent,
    EventCategory,
    EventImpact,
    get_event_types_for_instrument,
    get_event_type,
    get_opex_date,
    get_nfp_date,
    get_vix_expiration,
    is_high_impact_day,
    get_events_for_date,
    get_event_dates,
    check_dates_for_events,
)

__all__ = [
    # Instruments
    "get_instrument",
    "get_trading_day_boundaries",
    "get_session_times",
    "get_default_session",
    "list_sessions",
    # Holidays
    "get_holiday_date",
    "get_holidays_for_year",
    "get_day_type",
    "get_close_time",
    "is_trading_day",
    "check_dates_for_holidays",
    # Events
    "MarketEvent",
    "EventCategory",
    "EventImpact",
    "get_event_types_for_instrument",
    "get_event_type",
    "get_opex_date",
    "get_nfp_date",
    "get_vix_expiration",
    "is_high_impact_day",
    "get_events_for_date",
    "get_event_dates",
    "check_dates_for_events",
]
