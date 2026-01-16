"""
Handler loader for RAP.

Loads the appropriate handler prompt based on query type classification.
"""

from agent.prompts.understander.classifier import QueryType
from agent.prompts.understander.base import get_base_prompt

# Import handlers
from agent.prompts.understander.handlers import chitchat
from agent.prompts.understander.handlers import concept
from agent.prompts.understander.handlers import out_of_scope
from agent.prompts.understander.handlers import clarification
from agent.prompts.understander.handlers.data import base as data_base
from agent.prompts.understander.handlers.data import simple as data_simple
from agent.prompts.understander.handlers.data import filter as data_filter
from agent.prompts.understander.handlers.data import event_time as data_event_time
from agent.prompts.understander.handlers.data import top_n as data_top_n
from agent.prompts.understander.handlers.data import compare as data_compare
from agent.prompts.understander.handlers.data import find_extremum as data_find_extremum


# Handler registry
HANDLERS = {
    QueryType.CHITCHAT: chitchat,
    QueryType.CONCEPT: concept,
    QueryType.OUT_OF_SCOPE: out_of_scope,
    QueryType.CLARIFICATION: clarification,
    QueryType.DATA_SIMPLE: data_simple,
    QueryType.DATA_FILTER: data_filter,
    QueryType.DATA_EVENT_TIME: data_event_time,
    QueryType.DATA_TOP_N: data_top_n,
    QueryType.DATA_COMPARE: data_compare,
    QueryType.DATA_FIND_EXTREMUM: data_find_extremum,
}


def get_handler_prompt(
    query_type: str | QueryType,
    question: str,
    chat_history: str = "",
    data_info: str = "",
    today: str = "",
) -> str:
    """
    Build complete handler prompt for query type.

    Args:
        query_type: Classified query type (string or QueryType enum)
        question: User's question
        chat_history: Optional chat history
        data_info: Available data info (symbols, date range)
        today: Current date string

    Returns:
        Complete prompt for the handler
    """
    # Convert string to enum if needed
    if isinstance(query_type, str):
        query_type = QueryType(query_type)

    # Get handler module
    handler = HANDLERS.get(query_type)
    if not handler:
        raise ValueError(f"No handler for query type: {query_type}")

    # Build prompt parts
    parts = []

    # Base prompt (role, domain, schema for data types)
    is_data_type = query_type.value.startswith("data.")
    parts.append(get_base_prompt(
        include_schema=is_data_type,
        include_defaults=is_data_type,
    ))

    # Data info and date (for data types)
    if is_data_type and data_info:
        parts.append(f"<available_data>\n{data_info}\n</available_data>")
    if is_data_type and today:
        parts.append(f"<current_date>{today}</current_date>")

    # Data base prompt (common for all data handlers)
    if is_data_type:
        parts.append(data_base.HANDLER_PROMPT)

    # Specific handler prompt
    parts.append(handler.HANDLER_PROMPT)

    # Examples from handler
    if hasattr(handler, "EXAMPLES") and handler.EXAMPLES:
        parts.append(f"<examples>\n{handler.EXAMPLES}\n</examples>")

    # User question with context
    context_part = f"<context>\n{chat_history}\n</context>\n\n" if chat_history else ""
    parts.append(f"{context_part}<question>\n{question}\n</question>")

    return "\n\n".join(parts)


def get_query_type_from_string(type_str: str) -> QueryType:
    """Convert string to QueryType enum."""
    return QueryType(type_str)
