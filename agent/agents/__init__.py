"""
Agent implementations.

Each agent does ONE thing:
- Parser: extracts entities from question → ParsedQuery
- Clarifier: asks for missing info → ClarificationOutput
- Responder: handles chitchat and concepts → str
- Presenter: formats data for user → DataResponse
"""

from agent.agents.parser import Parser, parse
from agent.agents.clarifier import Clarifier, clarify
from agent.agents.responder import Responder
from agent.agents.responder import respond as respond_to
from agent.agents.presenter import Presenter, present

__all__ = [
    "Parser",
    "parse",
    "Clarifier",
    "clarify",
    "Responder",
    "respond_to",
    "Presenter",
    "present",
]
