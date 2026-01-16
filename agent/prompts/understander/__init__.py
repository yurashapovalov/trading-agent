"""
Understander RAP (Retrieval-Augmented Prompting) prompts.

Instead of one 800-token monolithic prompt, we use:
1. Classifier (~50 tokens) - determines query type
2. Handler (~50-200 tokens) - specialized prompt for that type

Usage:
    from agent.prompts.understander import get_classifier_prompt, get_handler_prompt

    # Step 1: Classify
    classifier_prompt = get_classifier_prompt(question, chat_history)
    query_type = llm(classifier_prompt)  # → "data.event_time"

    # Step 2: Get handler
    handler_prompt = get_handler_prompt(query_type, context)
    intent = llm(handler_prompt)  # → {"type": "data", "query_spec": {...}}
"""

from agent.prompts.understander.classifier import (
    CLASSIFIER_PROMPT,
    get_classifier_prompt,
)
from agent.prompts.understander.base import (
    BASE_ROLE,
    BASE_SCHEMA,
    BASE_DEFAULTS,
)
from agent.prompts.understander.loader import (
    get_handler_prompt,
    QueryType,
)

__all__ = [
    "CLASSIFIER_PROMPT",
    "get_classifier_prompt",
    "get_handler_prompt",
    "QueryType",
    "BASE_ROLE",
    "BASE_SCHEMA",
    "BASE_DEFAULTS",
]
