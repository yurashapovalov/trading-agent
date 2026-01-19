"""
Non-data scenarios — don't require QueryBuilder.

- Concepts: explanations of trading terms
- Greetings: hello, thanks, etc.
- Not supported: queries we can't handle
- Holidays: market closed days
"""

CONCEPTS = [
    {"q": "What is gap?", "expect": {"type": "concept"}},
    {"q": "Explain RTH session", "expect": {"type": "concept"}},
    {"q": "What is ETH?", "expect": {"type": "concept"}},
    {"q": "Что такое гэп?", "expect": {"type": "concept"}},
]

GREETINGS = [
    {"q": "Hello", "expect": {"type": "greeting"}},
    {"q": "Hi there", "expect": {"type": "greeting"}},
    {"q": "Привет", "expect": {"type": "greeting"}},
    {"q": "Thanks", "expect": {"type": "greeting"}},
    {"q": "Спасибо", "expect": {"type": "greeting"}},
]

NOT_SUPPORTED = [
    {"q": "What happens the day after a gap up > 1%?", "expect": {"type": "not_supported"}},
    {"q": "Win rate for gap down strategy", "expect": {"type": "not_supported"}},
    {"q": "Days after 3+ days of growth in a row", "expect": {"type": "not_supported"}},
]

HOLIDAYS = [
    {"q": "What happened on December 25, 2024?", "expect": {"holiday": True}},
    {"q": "Statistics for July 4, 2024", "expect": {"holiday": True}},
]
