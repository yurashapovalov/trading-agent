# Edge Cases

Handle requests that should be refused or need special handling.

<rules>
REFUSE (intent="unsupported"):
- predictions, forecasts → cannot predict future
- different instruments without context → wrong instrument
- real-time data requests → no live data

CLARIFY instrument:
- "what about ES" → different instrument, clarify
- other tickers → need to switch context

LIMITATIONS:
- minute data requests → may not have granular data
- very old data → limited history
</rules>

<examples>
Input: make a prediction for tomorrow
Output: {"intent": "unsupported", "reason": "cannot_predict", "what": "future prediction"}

Input: what will happen tomorrow
Output: {"intent": "unsupported", "reason": "cannot_predict", "what": "future prediction"}

Input: forecast for next week
Output: {"intent": "unsupported", "reason": "cannot_predict", "what": "future prediction"}

Input: what about ES
Output: {"intent": "clarify_instrument", "what": "ES", "unclear": ["confirm_instrument_switch"]}

Input: show me SPY data
Output: {"intent": "clarify_instrument", "what": "SPY", "unclear": ["confirm_instrument_switch"]}

Input: what is the current price
Output: {"intent": "unsupported", "reason": "no_realtime", "what": "current price"}

Input: live volume right now
Output: {"intent": "unsupported", "reason": "no_realtime", "what": "live data"}
</examples>
