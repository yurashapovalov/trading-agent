"""
Filter scenarios — how data is filtered.

- Period: date range
- Weekday: day of week filter
- Session: trading session filter
- Conditions: price/range conditions
- Events: market events (OPEX, NFP)
- Clarification: triggers for missing info
"""

FILTER_PERIOD = [
    {"q": "Statistics for 2024", "expect": {"period_start": "2024-01-01", "period_end": "2024-12-31"}},
    {"q": "Range for 2020-2025", "expect": {"period_start": "2020-01-01", "period_end": "2025-12-31"}},
    {"q": "Data for January 2024", "expect": {"period_start": "2024-01-01", "period_end": "2024-01-31"}},
]

FILTER_WEEKDAY = [
    {"q": "Statistics for Fridays 2024", "expect": {"filter_weekdays": ["Friday"]}},
    {"q": "Monday statistics", "expect": {"filter_weekdays": ["Monday"]}},
    {"q": "Статистика по пятницам", "expect": {"filter_weekdays": ["Friday"]}},
]

FILTER_SESSION = [
    {"q": "RTH statistics for 2024", "expect": {"filter_session": "RTH"}},
    {"q": "ETH range", "expect": {"filter_session": "ETH"}},
    {"q": "Overnight volatility", "expect": {"filter_session": "OVERNIGHT"}},
]

FILTER_CONDITIONS = [
    {"q": "Days where range > 300", "expect": {"conditions": ["range > 300"]}},
    {"q": "Statistics for Fridays where close - low >= 200", "expect": {"conditions": ["close - low >= 200"]}},
    {"q": "Days where change_pct < -2", "expect": {"conditions": ["change_pct < -2"]}},
]

FILTER_EVENTS = [
    {"q": "Statistics for OPEX days", "expect": {"event_filter": "opex"}},
    {"q": "Volatility on expiration days", "expect": {"event_filter": "opex"}},
    {"q": "How does NQ behave on NFP?", "expect": {"event_filter": "nfp"}},
    {"q": "Статистика по дням экспирации", "expect": {"event_filter": "opex"}},
]

# Clarification triggers
FILTER_SPECIFIC_DATE = [
    {"q": "What happened on May 16, 2024?", "expect": {"clarification": "session"}},
    {"q": "Show me January 10, 2024", "expect": {"clarification": "session"}},
    {"q": "Что было 16 мая 2024?", "expect": {"clarification": "session"}},
]

FILTER_DATE_NO_YEAR = [
    {"q": "What was jan 10", "expect": {"clarification": "year"}},
    {"q": "Show me May 16", "expect": {"clarification": "year"}},
    {"q": "Что было 16 мая?", "expect": {"clarification": "year"}},
]
