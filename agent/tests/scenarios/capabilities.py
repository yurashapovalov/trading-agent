"""
Capability tests — atomic testing of Parser → Composer → QueryBuilder → DataFetcher.

Each capability is tested independently and in combinations.
Focus: correct data output, not conversation flow.

Structure:
- FIND: superlatives (max/min)
- GROUPING: hour, weekday, month, etc. (TODO)
- FILTERS: session, weekday, period (TODO)
- SPECIAL_OPS: top_n, compare, event_time (TODO)
- COMBINATIONS: multiple capabilities together (TODO)
"""

# =============================================================================
# FIND capability — superlatives (max/min)
# =============================================================================

FIND_CAPABILITY = [
    # --- find: max ---
    {
        "name": "find_max_volatility_hour",
        "q": "самый волатильный час",
        "expect": {
            "rows": 1,
            "has_columns": ["time_bucket", "volatility"],
        }
    },
    {
        "name": "find_max_volatility_hour_en",
        "q": "most volatile hour",
        "expect": {
            "rows": 1,
            "has_columns": ["time_bucket", "volatility"],
        }
    },
    {
        "name": "find_max_range_weekday",
        "q": "день недели с наибольшим range",
        "expect": {
            "rows": 1,
            "has_columns": ["weekday", "avg_range"],
        }
    },
    {
        "name": "find_max_range_month",
        "q": "самый волатильный месяц 2024",
        "expect": {
            "rows": 1,
            "has_columns": ["month", "volatility"],
        }
    },

    # --- find: min ---
    {
        "name": "find_min_volatility_hour",
        "q": "наименее волатильный час",
        "expect": {
            "rows": 1,
            "has_columns": ["time_bucket", "volatility"],
        }
    },
    {
        "name": "find_min_volatility_hour_en",
        "q": "quietest hour of the day",
        "expect": {
            "rows": 1,
            "has_columns": ["time_bucket", "volatility"],
        }
    },
    {
        "name": "find_min_range_weekday",
        "q": "день недели с наименьшим range",
        "expect": {
            "rows": 1,
            "has_columns": ["weekday", "avg_range"],
        }
    },

    # --- find: month ---
    {
        "name": "find_min_volatility_month",
        "q": "наименее волатильный месяц 2024",
        "expect": {
            "rows": 1,
            "has_columns": ["month", "volatility"],
        }
    },

    # --- find: year ---
    {
        "name": "find_max_volatility_year",
        "q": "самый волатильный год",
        "expect": {
            "rows": 1,
            "has_columns": ["year", "volatility"],
        }
    },
    {
        "name": "find_min_range_year",
        "q": "год с наименьшим средним range",
        "expect": {
            "rows": 1,
            "has_columns": ["year", "avg_range"],
        }
    },

    # --- find: session ---
    {
        "name": "find_max_volatility_session",
        "q": "какая сессия самая волатильная",
        "expect": {
            "rows": 1,
            "has_columns": ["session", "volatility"],
        }
    },

    # --- find: other metrics ---
    {
        "name": "find_max_volume_hour",
        "q": "час с наибольшим объёмом",
        "expect": {
            "rows": 1,
            "has_columns": ["time_bucket"],
        }
    },
    {
        "name": "find_max_change_weekday",
        "q": "день недели с наибольшим средним изменением",
        "expect": {
            "rows": 1,
            "has_columns": ["weekday"],
        }
    },

    # --- find with filters ---
    {
        "name": "find_max_volatility_hour_rth",
        "q": "самый волатильный час RTH",
        "expect": {
            "rows": 1,
            "has_columns": ["time_bucket", "volatility"],
        }
    },
    {
        "name": "find_max_range_friday",
        "q": "самый большой range по пятницам",
        "expect": {
            "rows": 1,
        }
    },
    {
        "name": "find_min_volatility_2024",
        "q": "наименее волатильный час в 2024",
        "expect": {
            "rows": 1,
            "has_columns": ["time_bucket", "volatility"],
        }
    },
]
