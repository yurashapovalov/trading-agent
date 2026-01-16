"""Prompt templates for agents."""

# RAP prompts (modular approach)
from agent.prompts.understander import (
    get_classifier_prompt,
    get_handler_prompt,
    QueryType,
)

from agent.prompts.analyst import get_analyst_prompt

__all__ = [
    # RAP
    "get_classifier_prompt",
    "get_handler_prompt",
    "QueryType",
    # Other
    "get_analyst_prompt",
]
