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
Question: "Hello!"
```json
{
  "type": "chitchat",
  "response_text": "Hello! Ready to help with trading data analysis. What would you like to know?"
}
```

Question: "Thanks for the help"
```json
{
  "type": "chitchat",
  "response_text": "You're welcome! Feel free to ask if you have more questions about the data."
}
```
"""
