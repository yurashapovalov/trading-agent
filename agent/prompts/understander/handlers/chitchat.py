"""
Chitchat handler.

Handles greetings, thanks, and small talk.
"""

HANDLER_PROMPT = """<task>
User is engaging in small talk (greeting, thanks, goodbye).

Respond naturally and briefly. Mention that you can help with trading data analysis.

Return JSON:
{
  "type": "chitchat",
  "response_text": "Your friendly response here"
}
</task>"""

EXAMPLES = """
Question: "Привет!"
```json
{
  "type": "chitchat",
  "response_text": "Привет! Готов помочь с анализом торговых данных. Что хочешь узнать?"
}
```

Question: "Спасибо за помощь"
```json
{
  "type": "chitchat",
  "response_text": "Пожалуйста! Обращайся, если будут ещё вопросы по данным."
}
```
"""
