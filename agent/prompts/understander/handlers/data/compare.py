"""
Compare handler.

Handles comparison requests (sessions, periods, weekdays).
"""

HANDLER_PROMPT = """<task>
User wants to compare different categories.

Types of comparisons:
1. **Sessions**: RTH vs ETH, RTH vs OVERNIGHT
2. **Weekdays**: Monday vs Friday, all weekdays
3. **Periods**: Year over year, month over month
4. **Custom**: Any grouping comparison

Key decisions:
1. **source**: "minutes" for session comparison, "daily" for others
2. **grouping**: What to compare by
   - "session" → compare RTH vs ETH
   - "weekday" → compare Monday through Friday
   - "month" → compare by month
   - "year" → compare by year
3. **metrics**: What to compare (avg range, volume, etc.)

Return JSON with type: "data" and query_spec.
</task>"""

EXAMPLES = """
Question: "Сравни волатильность RTH и ETH"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "minutes",
    "filters": {
      "period_start": "all",
      "period_end": "all"
    },
    "grouping": "session",
    "metrics": [
      {"metric": "sum", "column": "volume", "alias": "total_volume"},
      {"metric": "avg", "column": "range", "alias": "avg_bar_range"},
      {"metric": "count", "alias": "bar_count"}
    ],
    "special_op": "none"
  }
}
```

Question: "Сравни волатильность по дням недели"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "all",
      "period_end": "all"
    },
    "grouping": "weekday",
    "metrics": [
      {"metric": "avg", "column": "range", "alias": "avg_range"},
      {"metric": "avg", "column": "volume", "alias": "avg_volume"},
      {"metric": "stddev", "column": "change_pct", "alias": "volatility"},
      {"metric": "count", "alias": "days"}
    ],
    "special_op": "none"
  }
}
```

Question: "Сравни 2023 и 2024 по волатильности"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "all",
      "period_end": "all",
      "years": [2023, 2024]
    },
    "grouping": "year",
    "metrics": [
      {"metric": "avg", "column": "range", "alias": "avg_range"},
      {"metric": "stddev", "column": "change_pct", "alias": "volatility"},
      {"metric": "count", "alias": "trading_days"}
    ],
    "special_op": "none"
  }
}
```

Question: "Понедельник vs Пятница — где больше волатильность?"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "all",
      "period_end": "all",
      "weekdays": ["Monday", "Friday"]
    },
    "grouping": "weekday",
    "metrics": [
      {"metric": "avg", "column": "range", "alias": "avg_range"},
      {"metric": "stddev", "column": "change_pct", "alias": "volatility"},
      {"metric": "count", "alias": "days"}
    ],
    "special_op": "none"
  }
}
```
"""
