"""
Clarification handler.

Handles ambiguous or unclear requests.
"""

HANDLER_PROMPT = """<task>
User's request is unclear or ambiguous. Ask for clarification.

When to clarify:
1. ACTION unclear - "покажи данные" (what to do with data?)
2. AMBIGUOUS - could mean multiple different things
3. CUSTOM TIME RANGE - user specified non-standard time like "с 6 до 16"
   (need to clarify timezone and whether they mean a session)

Provide helpful suggestions showing what's possible.

Return JSON:
{
  "type": "clarification",
  "clarification_question": "Your question to user",
  "suggestions": ["Option 1", "Option 2", "Option 3", "Option 4"]
}
</task>

<important>
Do NOT ask for clarification when:
- Period not specified → just use "all" (full dataset)
- Symbol not specified → just use NQ
- User explicitly uses session names (RTH, ETH)
</important>"""

EXAMPLES = """
Question: "Покажи high low"
```json
{
  "type": "clarification",
  "clarification_question": "Что именно вас интересует про high/low?",
  "suggestions": [
    "Показать дневные high/low за последний месяц",
    "Найти дни с максимальным диапазоном (high-low)",
    "Узнать в какое время обычно формируется high/low дня",
    "Сравнить high/low по дням недели"
  ]
}
```

Question: "Статистика с 6 утра до 16 дня"
```json
{
  "type": "clarification",
  "clarification_question": "Уточните временной диапазон. Времена должны быть в ET (Eastern Time):",
  "suggestions": [
    "RTH сессия (09:30-16:00 ET) — основная торговая сессия",
    "Премаркет + RTH (04:00-16:00 ET)",
    "Кастомное время 06:00-16:00 ET",
    "Весь торговый день ETH"
  ]
}
```
"""
