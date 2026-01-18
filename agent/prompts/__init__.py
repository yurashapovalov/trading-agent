"""Prompt templates for agents."""

from agent.prompts.analyst import get_analyst_prompt
from agent.prompts.parser import get_parser_prompt

__all__ = [
    "get_analyst_prompt",
    "get_parser_prompt",
]
