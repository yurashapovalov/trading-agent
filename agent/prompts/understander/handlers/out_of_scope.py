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
Question: "Покажи RSI для NQ"
```json
{
  "type": "out_of_scope",
  "response_text": "Технические индикаторы (RSI, MACD и др.) пока недоступны. Могу помочь с анализом OHLCV данных: статистика по периодам, время формирования high/low, анализ гэпов, сравнение сессий."
}
```

Question: "Какая будет цена завтра?"
```json
{
  "type": "out_of_scope",
  "response_text": "Прогнозы цен не делаю. Могу показать исторические данные: статистику, паттерны, распределения. Например, когда обычно формируется high дня или какая средняя волатильность по месяцам."
}
```
"""
