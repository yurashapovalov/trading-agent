"""
Top N handler.

Handles requests for top N days by some metric.
"""

HANDLER_PROMPT = """<task>
User wants top N days ranked by some metric.

Key decisions:
1. **source**: Usually "daily" or "daily_with_prev" (if gap needed)
2. **special_op**: "top_n"
3. **top_n_spec**:
   - n: number of results (default 10)
   - order_by: column to rank by (range, change_pct, gap_pct, volume)
   - direction: "DESC" (largest first) or "ASC" (smallest first)
4. **grouping**: "none" (return individual days)

Common patterns:
- "самые волатильные" → order_by: "range", direction: "DESC"
- "самые большие падения" → order_by: "change_pct", direction: "ASC"
- "самые большие гэпы вверх" → order_by: "gap_pct", direction: "DESC"

Return JSON with type: "data" and query_spec.
</task>"""

EXAMPLES = """
Question: "Топ 10 самых волатильных дней"
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
    "grouping": "none",
    "metrics": [
      {"metric": "range"},
      {"metric": "change_pct"},
      {"metric": "volume"}
    ],
    "special_op": "top_n",
    "top_n_spec": {"n": 10, "order_by": "range", "direction": "DESC"}
  }
}
```

Question: "5 самых больших падений за 2024"
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
    "grouping": "none",
    "metrics": [
      {"metric": "change_pct"},
      {"metric": "range"},
      {"metric": "open"},
      {"metric": "close"}
    ],
    "special_op": "top_n",
    "top_n_spec": {"n": 5, "order_by": "change_pct", "direction": "ASC"}
  }
}
```

Question: "Топ 10 гэпов вверх"
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
        {"column": "gap_pct", "operator": ">", "value": 0}
      ]
    },
    "grouping": "none",
    "metrics": [
      {"metric": "gap_pct"},
      {"metric": "change_pct"},
      {"metric": "range"}
    ],
    "special_op": "top_n",
    "top_n_spec": {"n": 10, "order_by": "gap_pct", "direction": "DESC"}
  }
}
```
"""
