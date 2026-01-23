"""
Prompt templates for agents.

Each file contains only constants (SYSTEM_PROMPT, USER_PROMPT, etc.)
Agent logic is in agent/agents/*.py
"""

# Export prompt constants for convenience
from agent.prompts.clarification import SYSTEM_PROMPT as CLARIFICATION_SYSTEM_PROMPT
from agent.prompts.responder import SYSTEM_PROMPT as RESPONDER_SYSTEM_PROMPT

__all__ = [
    "CLARIFICATION_SYSTEM_PROMPT",
    "RESPONDER_SYSTEM_PROMPT",
]
