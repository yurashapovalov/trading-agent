"""
Filter handler.

Handles requests to find days matching conditions.
"""

HANDLER_PROMPT = """<task>
User wants to find days matching a condition.

Key decisions:
1. **source**: "daily" or "daily_with_prev" (if gap_pct needed)
2. **filters**:
   - period_start/period_end: date range or "all" (see Period rule above)
   - weekdays: ["Monday", "Friday"] — day names in English
   - months: [1, 6] — month numbers
   - years: [2020, 2024] — year numbers
3. **conditions**: Extract the condition from question
   - "упал больше 2%" → {"column": "change_pct", "operator": "<", "value": -2.0}
   - "вырос больше 1%" → {"column": "change_pct", "operator": ">", "value": 1.0}
   - "гэп вверх больше 0.5%" → {"column": "gap_pct", "operator": ">", "value": 0.5}
   - "range больше 200" → {"column": "range", "operator": ">", "value": 200}
   - "low ниже close на 200" → {"column": "close_to_low", "operator": ">=", "value": 200}
   - "high выше close на 100" → {"column": "close_to_high", "operator": ">=", "value": 100}
4. **grouping**: "none" (return individual days)
5. **metrics**: Include relevant columns

Available columns: open, high, low, close, volume, range, change_pct, gap_pct,
                  close_to_low, close_to_high, open_to_high, open_to_low, body

Operators: ">", "<", ">=", "<=", "=", "!="

Return JSON with type: "data" and query_spec.
</task>"""

EXAMPLES = """
Question: "Найди дни когда NQ упал больше 2%"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "all",
      "period_end": "all",
      "conditions": [
        {"column": "change_pct", "operator": "<", "value": -2.0}
      ]
    },
    "grouping": "none",
    "metrics": [
      {"metric": "open"},
      {"metric": "close"},
      {"metric": "change_pct"},
      {"metric": "range"},
      {"metric": "volume"}
    ],
    "special_op": "none"
  }
}
```

Question: "Дни с гэпом вверх больше 1%"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily_with_prev",
    "filters": {
      "period_start": "all",
      "period_end": "all",
      "conditions": [
        {"column": "gap_pct", "operator": ">", "value": 1.0}
      ]
    },
    "grouping": "none",
    "metrics": [
      {"metric": "gap_pct"},
      {"metric": "change_pct"},
      {"metric": "range"}
    ],
    "special_op": "none"
  }
}
```

Question: "Волатильные дни с range больше 300 пунктов за 2024"
Note: "за 2024" means include all of 2024, so period_end = 2025-01-01 (first day AFTER 2024)
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "2024-01-01",
      "period_end": "2025-01-01",
      "conditions": [
        {"column": "range", "operator": ">", "value": 300}
      ]
    },
    "grouping": "none",
    "metrics": [
      {"metric": "range"},
      {"metric": "change_pct"},
      {"metric": "volume"}
    ],
    "special_op": "none"
  }
}
```

Question: "Пятницы за 2020-2025 у которых low был ниже close на 200 и более пунктов"
Note: "2020-2025" means include all of 2025, so period_end = 2026-01-01 (first day AFTER the range)
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "2020-01-01",
      "period_end": "2026-01-01",
      "weekdays": ["Friday"],
      "conditions": [
        {"column": "close_to_low", "operator": ">=", "value": 200}
      ]
    },
    "grouping": "none",
    "metrics": [
      {"metric": "open"},
      {"metric": "high"},
      {"metric": "low"},
      {"metric": "close"},
      {"metric": "range"},
      {"metric": "close_to_low"}
    ],
    "special_op": "none"
  }
}
```
"""
