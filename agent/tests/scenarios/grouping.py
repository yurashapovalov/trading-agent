"""
Grouping scenarios — how results are grouped.

- TOTAL: single row aggregation
- NONE: list of individual days
- HOUR: by hour (requires MINUTES source)
- WEEKDAY: by day of week
- MONTH: by month
- YEAR: by year
- SESSION: by trading session
"""

GROUPING_TOTAL = [
    {"q": "Statistics for 2024", "expect": {"grouping": "TOTAL"}},
    {"q": "Average range for Fridays", "expect": {"grouping": "TOTAL"}},
    {"q": "Общая статистика за 2023-2024", "expect": {"grouping": "TOTAL"}},
]

GROUPING_NONE = [
    {"q": "Show me all Fridays in 2024", "expect": {"grouping": "NONE"}},
    {"q": "Days where range > 300 in 2024", "expect": {"grouping": "NONE"}},
]

GROUPING_HOUR = [
    {"q": "Volatility by hour", "expect": {"grouping": "HOUR"}},
    {"q": "Range by hour for RTH", "expect": {"grouping": "HOUR"}},
    {"q": "Волатильность по часам", "expect": {"grouping": "HOUR"}},
]

GROUPING_WEEKDAY = [
    {"q": "Statistics by weekday", "expect": {"grouping": "WEEKDAY"}},
    {"q": "Volatility by day of week", "expect": {"grouping": "WEEKDAY"}},
    {"q": "Статистика по дням недели", "expect": {"grouping": "WEEKDAY"}},
]

GROUPING_MONTH = [
    {"q": "Average range by month for 2024", "expect": {"grouping": "MONTH"}},
    {"q": "Volatility by month", "expect": {"grouping": "MONTH"}},
    {"q": "Статистика по месяцам за 2024", "expect": {"grouping": "MONTH"}},
]

GROUPING_YEAR = [
    {"q": "Statistics by year 2020-2024", "expect": {"grouping": "YEAR"}},
    {"q": "Average range by year", "expect": {"grouping": "YEAR"}},
]

GROUPING_SESSION = [
    {"q": "Compare RTH and ETH volume", "expect": {"grouping": "SESSION"}},
    {"q": "Statistics by session", "expect": {"grouping": "SESSION"}},
]
