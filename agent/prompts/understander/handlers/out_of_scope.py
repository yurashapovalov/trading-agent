"""
Out of scope handler.

Handles requests for features we don't support.
"""

HANDLER_PROMPT = """<task>
User is asking for something we don't support.

Out of scope features:
- Technical indicators (RSI, MACD, Bollinger Bands, moving averages)
- Price predictions ("what will price be tomorrow")
- Backtesting strategies
- Real-time data
- Order execution / trading

Politely explain what we CAN do:
- OHLCV data analysis
- Statistics by period (daily, monthly, yearly)
- Session comparisons (RTH vs ETH)
- Time of high/low analysis
- Gap analysis
- Volatility statistics
- Day filtering by conditions

Return JSON:
{
  "type": "out_of_scope",
  "response_text": "Explanation of what we can't do and what we CAN do"
}
</task>"""

EXAMPLES = """
Question: "Show RSI for NQ"
```json
{
  "type": "out_of_scope",
  "response_text": "Technical indicators (RSI, MACD, etc.) are not available yet. I can help with OHLCV data analysis: statistics by period, time of high/low formation, gap analysis, session comparisons."
}
```

Question: "What will the price be tomorrow?"
```json
{
  "type": "out_of_scope",
  "response_text": "I don't make price predictions. I can show historical data: statistics, patterns, distributions. For example, when the daily high typically forms or average volatility by month."
}
```
"""
