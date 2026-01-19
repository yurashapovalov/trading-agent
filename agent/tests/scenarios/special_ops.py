"""
Special operations scenarios — complex query types.

- TOP_N: top N records by metric
- EVENT_TIME: distribution of when high/low forms
- FIND_EXTREMUM: exact time of high/low for specific day
- COMPARE: compare categories (RTH vs ETH, Monday vs Friday)
"""

SPECIAL_TOP_N = [
    {"q": "Top 10 volatile days in 2024", "expect": {"special_op": "TOP_N", "top_n": 10}},
    {"q": "5 biggest range days", "expect": {"special_op": "TOP_N", "top_n": 5}},
    {"q": "When was the market craziest in 2023?", "expect": {"special_op": "TOP_N"}},
    {"q": "Find me days with huge moves last year", "expect": {"special_op": "TOP_N"}},
    {"q": "Топ 10 волатильных дней за 2024", "expect": {"special_op": "TOP_N"}},
]

SPECIAL_EVENT_TIME = [
    {"q": "When is high usually formed?", "expect": {"special_op": "EVENT_TIME", "find": "high"}},
    {"q": "When is low usually formed?", "expect": {"special_op": "EVENT_TIME", "find": "low"}},
    {"q": "В какое время обычно формируется хай?", "expect": {"special_op": "EVENT_TIME"}},
    {"q": "What time does the high form on Fridays?", "expect": {"special_op": "EVENT_TIME"}},
]

SPECIAL_FIND_EXTREMUM = [
    {"q": "When was the high on May 16, 2024?", "expect": {"special_op": "FIND_EXTREMUM"}},
    {"q": "What time was the low on January 10, 2024?", "expect": {"special_op": "FIND_EXTREMUM"}},
    {"q": "Во сколько был хай 16 мая 2024?", "expect": {"special_op": "FIND_EXTREMUM"}},
]

SPECIAL_COMPARE = [
    {"q": "RTH vs ETH range", "expect": {"special_op": "COMPARE", "compare": ["RTH", "ETH"]}},
    {"q": "Compare Monday and Friday volatility", "expect": {"special_op": "COMPARE"}},
    {"q": "Сравни RTH и ETH по range", "expect": {"special_op": "COMPARE"}},
    {"q": "Monday vs Friday statistics", "expect": {"special_op": "COMPARE"}},
]
