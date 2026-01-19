"""
Follow-up chain scenarios — Parser context preservation.

Tests how Parser handles follow-up questions when it has previous_parsed context.

Categories:
- A: Modification (keep previous, add/change something)
- B: New Query (ignore previous, start fresh)
- C: Non-data (greeting/concept after data query)
- M: Multi-step chains (3+ questions)
"""

FOLLOW_UP_CHAINS = [
    # =========================================================================
    # Category A: Modification (keep previous, add/change)
    # =========================================================================
    {
        "name": "A1_add_top_n",
        "description": "Add top_n to existing hourly query",
        "chain": [
            {"q": "волатильность по часам", "expect": {"grouping": "HOUR"}},
            {"q": "топ 5", "expect": {"grouping": "HOUR", "top_n": 5}},
        ],
    },
    {
        "name": "A2_find_max",
        "description": "Find extremum from grouped data",
        "chain": [
            {"q": "волатильность по часам", "expect": {"grouping": "HOUR"}},
            {"q": "какой час самый волатильный?", "expect": {"grouping": "HOUR", "top_n": 1}},
        ],
    },
    {
        "name": "A3_change_grouping",
        "description": "Change grouping from hour to weekday",
        "chain": [
            {"q": "волатильность по часам", "expect": {"grouping": "HOUR"}},
            {"q": "а по дням недели?", "expect": {"grouping": "WEEKDAY"}},
        ],
    },
    {
        "name": "A4_add_weekday_filter",
        "description": "Add weekday filter to existing query",
        "chain": [
            {"q": "волатильность по часам", "expect": {"grouping": "HOUR"}},
            {"q": "только пятницы", "expect": {"grouping": "HOUR", "filter_weekdays": ["Friday"]}},
        ],
    },
    {
        "name": "A5_add_period",
        "description": "Add period to existing query",
        "chain": [
            {"q": "волатильность по часам"},
            {"q": "за 2023", "expect": {"grouping": "HOUR", "period_start": "2023-01-01"}},
        ],
    },
    {
        "name": "A6_add_session_filter",
        "description": "Add session filter after period",
        "chain": [
            {"q": "статистика за 2024", "expect": {"period_start": "2024-01-01"}},
            {"q": "только RTH", "expect": {"period_start": "2024-01-01", "filter_session": "RTH"}},
        ],
    },

    # =========================================================================
    # Category B: New Query (ignore previous)
    # =========================================================================
    {
        "name": "B1_new_unrelated_query",
        "description": "Completely different query should ignore previous",
        "chain": [
            {"q": "волатильность по часам", "expect": {"grouping": "HOUR"}},
            {"q": "статистика за 2024", "expect": {"grouping": "TOTAL"}, "expect_no": ["grouping:HOUR"]},
        ],
    },
    {
        "name": "B2_new_event_time",
        "description": "Event time query is independent",
        "chain": [
            {"q": "волатильность по часам"},
            {"q": "когда обычно формируется хай?", "expect": {"special_op": "EVENT_TIME"}},
        ],
    },
    {
        "name": "B3_new_compare",
        "description": "Compare is a new query type",
        "chain": [
            {"q": "статистика за 2024"},
            {"q": "сравни RTH и ETH", "expect": {"special_op": "COMPARE"}},
        ],
    },

    # =========================================================================
    # Category C: Non-data (ignore previous)
    # =========================================================================
    {
        "name": "C1_greeting_after_data",
        "description": "Greeting should ignore previous data context",
        "chain": [
            {"q": "волатильность по часам"},
            {"q": "спасибо", "expect": {"type": "greeting"}},
        ],
    },
    {
        "name": "C2_concept_after_data",
        "description": "Concept explanation ignores previous",
        "chain": [
            {"q": "волатильность по часам"},
            {"q": "что такое RTH?", "expect": {"type": "concept"}},
        ],
    },

    # =========================================================================
    # Category M: Multi-step chains
    # =========================================================================
    {
        "name": "M1_three_step_refinement",
        "description": "Progressive refinement over 3 steps",
        "chain": [
            {"q": "статистика"},
            {"q": "за 2024", "expect": {"period_start": "2024-01-01"}},
            {"q": "только пятницы", "expect": {"period_start": "2024-01-01", "filter_weekdays": ["Friday"]}},
        ],
    },
    {
        "name": "M2_modify_then_new",
        "description": "Modify existing, then start fresh query",
        "chain": [
            {"q": "волатильность по часам"},
            {"q": "топ 5", "expect": {"top_n": 5, "grouping": "HOUR"}},
            {"q": "что такое RTH?", "expect": {"type": "concept"}},
        ],
    },
    {
        "name": "M3_new_then_modify",
        "description": "New query, then modify it",
        "chain": [
            {"q": "волатильность по часам", "expect": {"grouping": "HOUR"}},
            {"q": "статистика за 2024", "expect": {"grouping": "TOTAL"}},
            {"q": "только RTH", "expect": {"filter_session": "RTH"}},
        ],
    },
    {
        "name": "M4_modify_modify_then_unrelated",
        "description": "Build up query, then ask something completely unrelated",
        "chain": [
            {"q": "волатильность по часам", "expect": {"grouping": "HOUR"}},
            {"q": "топ 5", "expect": {"grouping": "HOUR", "top_n": 5}},
            {"q": "только пятницы", "expect": {"grouping": "HOUR", "top_n": 5, "filter_weekdays": ["Friday"]}},
            {"q": "когда был хай 10 января 2024?", "expect": {"special_op": "FIND_EXTREMUM"}},
        ],
    },
    {
        "name": "M5_long_chain_then_reset",
        "description": "Long modification chain, then completely new topic",
        "chain": [
            {"q": "статистика"},
            {"q": "за 2024", "expect": {"period_start": "2024-01-01"}},
            {"q": "только RTH", "expect": {"period_start": "2024-01-01", "filter_session": "RTH"}},
            {"q": "по месяцам", "expect": {"grouping": "MONTH", "filter_session": "RTH"}},
            {"q": "сравни понедельник и пятницу", "expect": {"special_op": "COMPARE"}},
        ],
    },

    # =========================================================================
    # Category F: Find extremum follow-ups (ambiguous "which is most X")
    # =========================================================================
    {
        "name": "F1_find_most_volatile_implicit",
        "description": "Find most volatile from hourly data — implicit grouping from context",
        "chain": [
            {"q": "волатильность по часам", "expect": {"grouping": "HOUR"}},
            # "какой самый волатильный" без указания "час" — Parser должен понять из контекста
            {"q": "какой самый волатильный", "expect": {"grouping": "HOUR", "top_n": 1}},
            # Благодарность — должен быть greeting, не query
            {"q": "спасибо", "expect": {"type": "greeting"}},
        ],
    },
    {
        "name": "F2_find_most_volatile_with_clarification",
        "description": "Ambiguous question then user clarifies they meant hour",
        "chain": [
            {"q": "волатильность по часам", "expect": {"grouping": "HOUR"}},
            {"q": "какой самый волатильный", "expect": {"grouping": "HOUR", "top_n": 1}},
            {"q": "я имею в виду час", "expect": {"grouping": "HOUR", "top_n": 1}},
        ],
    },
]
