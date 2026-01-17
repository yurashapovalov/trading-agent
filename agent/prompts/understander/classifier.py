"""
Classifier prompt for RAP.

Fast, cheap classification of user question into query type.
Uses lite model (gemini-flash-lite) for speed and cost efficiency.
"""

from enum import Enum


class QueryType(Enum):
    """All possible query types."""

    # Simple - no query_spec needed
    CHITCHAT = "chitchat"
    CONCEPT = "concept"
    OUT_OF_SCOPE = "out_of_scope"

    # Needs clarification
    CLARIFICATION = "clarification"

    # Data queries - need query_spec
    DATA_SIMPLE = "data.simple"
    DATA_FILTER = "data.filter"
    DATA_EVENT_TIME = "data.event_time"
    DATA_TOP_N = "data.top_n"
    DATA_COMPARE = "data.compare"
    DATA_FIND_EXTREMUM = "data.find_extremum"


CLASSIFIER_PROMPT = """<task>
Classify the trading data question into exactly one type.
Return JSON: {{"type": "<type>"}}
</task>

<domain>
Trading futures data (NQ) with OHLCV minute bars.
Columns: open, high, low, close, volume, range, change_pct, gap_pct,
close_to_low, close_to_high, open_to_high, open_to_low, body.
</domain>

<types>
| Type | Description | Examples |
|------|-------------|----------|
| chitchat | greetings, thanks, small talk | "hello", "thanks" |
| concept | asking what term means | "what is a gap?", "what is RTH?" |
| out_of_scope | indicators, predictions | "show RSI", "price tomorrow" |
| clarification | unclear request | "show data", "high low" |
| data.simple | basic statistics | "stats for January", "average volatility" |
| data.filter | days matching condition | "days when dropped > 2%", "days with gap" |
| data.event_time | PATTERN distribution | "when is high usually?", "what time is low typically?" |
| data.find_extremum | EXACT time on date | "what time was high yesterday?", "when did session open?" |
| data.top_n | top N by metric | "top 10 volatile days", "5 biggest gaps" |
| data.compare | compare categories | "RTH vs ETH", "Monday vs Friday" |
</types>

<key_distinction>
event_time vs find_extremum:
- event_time = PATTERN ("usually", "typically", "distribution")
- find_extremum = EXACT time ("yesterday", "Jan 10", "when did session open")
</key_distinction>

Question: {question}
"""


CLASSIFIER_PROMPT_WITH_HISTORY = """<task>
Classify the trading data question into exactly one type.
Consider chat history for context (follow-up questions).
Return JSON: {{"type": "<type>"}}
</task>

<domain>
Trading futures data (NQ) with OHLCV minute bars.
Columns: open, high, low, close, volume, range, change_pct, gap_pct,
close_to_low, close_to_high, open_to_high, open_to_low, body.
</domain>

<types>
| Type | Description | Examples |
|------|-------------|----------|
| chitchat | greetings, thanks, small talk | "hello", "thanks" |
| concept | asking what term means | "what is a gap?", "what is RTH?" |
| out_of_scope | indicators, predictions | "show RSI", "price tomorrow" |
| clarification | unclear request | "show data", "high low" |
| data.simple | basic statistics | "stats for January", "average volatility" |
| data.filter | days matching condition | "days when dropped > 2%", "days with gap" |
| data.event_time | PATTERN distribution | "when is high usually?", "what time is low typically?" |
| data.find_extremum | EXACT time on date | "what time was high yesterday?", "when did session open?" |
| data.top_n | top N by metric | "top 10 volatile days", "5 biggest gaps" |
| data.compare | compare categories | "RTH vs ETH", "Monday vs Friday" |
</types>

<key_distinction>
event_time vs find_extremum:
- event_time = PATTERN ("usually", "typically", "distribution")
- find_extremum = EXACT time ("yesterday", "Jan 10", "when did session open")
</key_distinction>

<chat_history>
{chat_history}
</chat_history>

Question: {question}
"""


def get_classifier_prompt(question: str, chat_history: str = "") -> str:
    """
    Build classifier prompt.

    Args:
        question: User's question
        chat_history: Optional chat history for context

    Returns:
        Formatted classifier prompt
    """
    if chat_history:
        return CLASSIFIER_PROMPT_WITH_HISTORY.format(
            question=question,
            chat_history=chat_history,
        )
    return CLASSIFIER_PROMPT.format(question=question)
