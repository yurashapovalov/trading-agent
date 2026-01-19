"""
Source scenarios — which data source is used.

- DAILY: aggregated daily bars
- MINUTES: raw minute bars (for hourly analysis, event_time)
- DAILY_WITH_PREV: daily + LAG data (for gap analysis)
"""

SOURCE_DAILY = [
    {"q": "Statistics for 2024", "expect": {"source": "DAILY", "grouping": "TOTAL"}},
    {"q": "Статистика за 2024", "expect": {"source": "DAILY"}},
    {"q": "Average range for Fridays 2020-2025", "expect": {"source": "DAILY"}},
]

SOURCE_MINUTES = [
    {"q": "Volatility by hour", "expect": {"source": "MINUTES", "grouping": "HOUR"}},
    {"q": "Какая волатильность по часам?", "expect": {"source": "MINUTES"}},
    {"q": "Range by hour for 2024", "expect": {"source": "MINUTES"}},
    {"q": "Volume distribution by hour", "expect": {"source": "MINUTES"}},
]

SOURCE_DAILY_WITH_PREV = [
    {"q": "Days with gap up > 1%", "expect": {"source": "DAILY_WITH_PREV"}},
    {"q": "Statistics for gap down days", "expect": {"source": "DAILY_WITH_PREV"}},
]
