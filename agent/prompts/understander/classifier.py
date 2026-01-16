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


CLASSIFIER_PROMPT = """Classify the trading data question into exactly one type.

Domain: Trading futures data (NQ, ES, CL) with OHLCV bars.
Available columns: open, high, low, close, volume, range, change_pct, gap_pct,
close_to_low, close_to_high, open_to_high, open_to_low, body.
Any question about filtering by these columns or their relationships = data.filter

Types:
- chitchat: greetings, thanks, small talk ("привет", "спасибо", "пока")
- concept: asking what something means ("что такое гэп?", "что такое RTH?")
- out_of_scope: technical indicators, backtesting, predictions ("покажи RSI", "какой будет цена завтра")
- clarification: unclear or ambiguous request ("покажи данные", "high low")
- data.simple: basic statistics for a period ("статистика за январь", "средняя волатильность 2024")
- data.filter: find days matching condition ("дни когда упало > 2%", "дни с гэпом", "пятницы где low ниже close")
- data.event_time: when does high/low USUALLY form - distribution ("когда обычно формируется high?")
- data.find_extremum: when WAS high/low on specific date ("во сколько был high вчера?")
- data.top_n: top N days by metric ("топ 10 волатильных дней", "5 самых больших гэпов")
- data.compare: compare sessions, periods, weekdays ("сравни RTH vs ETH", "понедельник vs пятница")

Key distinction:
- data.event_time = PATTERN over many days ("обычно", "как правило", "распределение")
- data.find_extremum = EXACT time for specific date(s) ("вчера", "10 января", "на прошлой неделе")

Return JSON: {{"type": "<type>"}}

Question: {question}
"""


CLASSIFIER_PROMPT_WITH_HISTORY = """Classify the trading data question into exactly one type.
Consider the chat history for context.

Domain: Trading futures data (NQ, ES, CL) with OHLCV bars.
Available columns: open, high, low, close, volume, range, change_pct, gap_pct,
close_to_low, close_to_high, open_to_high, open_to_low, body.
Any question about filtering by these columns or their relationships = data.filter

Types:
- chitchat: greetings, thanks, small talk ("привет", "спасибо", "пока")
- concept: asking what something means ("что такое гэп?", "что такое RTH?")
- out_of_scope: technical indicators, backtesting, predictions ("покажи RSI", "какой будет цена завтра")
- clarification: unclear or ambiguous request ("покажи данные", "high low")
- data.simple: basic statistics for a period ("статистика за январь", "средняя волатильность 2024")
- data.filter: find days matching condition ("дни когда упало > 2%", "дни с гэпом", "пятницы где low ниже close")
- data.event_time: when does high/low USUALLY form - distribution ("когда обычно формируется high?")
- data.find_extremum: when WAS high/low on specific date ("во сколько был high вчера?")
- data.top_n: top N days by metric ("топ 10 волатильных дней", "5 самых больших гэпов")
- data.compare: compare sessions, periods, weekdays ("сравни RTH vs ETH", "понедельник vs пятница")

Key distinction:
- data.event_time = PATTERN over many days ("обычно", "как правило", "распределение")
- data.find_extremum = EXACT time for specific date(s) ("вчера", "10 января", "на прошлой неделе")

Chat history:
{chat_history}

Return JSON: {{"type": "<type>"}}

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
