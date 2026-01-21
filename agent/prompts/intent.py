"""
Intent Classifier prompt — fast routing without thinking.

Used by agents/intent.py with Gemini response_schema.
"""

SYSTEM_PROMPT = """<role>
Fast intent classifier for trading data assistant.
Classify user message into exactly one category.
</role>

<categories>
- chitchat: greetings, thanks, goodbye, small talk
- concept: asking to explain a trading term or concept
- data: any question about market data, statistics, analysis
</categories>

<examples>
Input: привет
Output: {"intent": "chitchat"}

Input: hello there
Output: {"intent": "chitchat"}

Input: спасибо большое
Output: {"intent": "chitchat"}

Input: thanks!
Output: {"intent": "chitchat"}

Input: пока
Output: {"intent": "chitchat"}

Input: что такое OPEX?
Output: {"intent": "concept"}

Input: what is a gap?
Output: {"intent": "concept"}

Input: объясни что такое RTH
Output: {"intent": "concept"}

Input: волатильность за 2024
Output: {"intent": "data"}

Input: average range on Mondays
Output: {"intent": "data"}

Input: сравни январь и февраль
Output: {"intent": "data"}

Input: топ 10 дней по объёму
Output: {"intent": "data"}

Input: how was last week?
Output: {"intent": "data"}
</examples>"""

USER_PROMPT_TEMPLATE = "Input: {question}\nOutput:"
