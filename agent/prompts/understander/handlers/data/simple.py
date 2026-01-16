"""
Simple statistics handler.

Handles basic statistics requests for a period.
"""

HANDLER_PROMPT = """<task>
User wants basic statistics for a period.

Key decisions:
1. **source**: Usually "daily" for daily stats
2. **period**: Extract from question or use "all"
3. **grouping**: "total" for summary, or "month"/"year"/"weekday" for breakdown
4. **metrics**: avg range, avg change, stddev (volatility), count

Return JSON with type: "data" and query_spec.
</task>"""

EXAMPLES = """
Question: "Покажи статистику NQ за январь 2024"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "2024-01-01",
      "period_end": "2024-02-01"
    },
    "grouping": "total",
    "metrics": [
      {"metric": "avg", "column": "range", "alias": "avg_range"},
      {"metric": "avg", "column": "change_pct", "alias": "avg_change"},
      {"metric": "stddev", "column": "change_pct", "alias": "volatility"},
      {"metric": "count", "alias": "trading_days"}
    ],
    "special_op": "none"
  }
}
```

Question: "Волатильность по месяцам за 2024"
```json
{
  "type": "data",
  "query_spec": {
    "symbol": "NQ",
    "source": "daily",
    "filters": {
      "period_start": "2024-01-01",
      "period_end": "2025-01-01"
    },
    "grouping": "month",
    "metrics": [
      {"metric": "avg", "column": "range", "alias": "avg_range"},
      {"metric": "stddev", "column": "change_pct", "alias": "volatility"},
      {"metric": "count", "alias": "trading_days"}
    ],
    "special_op": "none"
  }
}
```

Question: "Средняя волатильность NQ"
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
    "grouping": "total",
    "metrics": [
      {"metric": "avg", "column": "range", "alias": "avg_range"},
      {"metric": "stddev", "column": "change_pct", "alias": "volatility"},
      {"metric": "count", "alias": "trading_days"}
    ],
    "special_op": "none"
  }
}
```
"""
