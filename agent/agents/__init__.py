"""Agent implementations for new architecture."""

# v2: Only import responders (other agents use old query_builder)
from agent.agents.responders.data import DataResponder, respond

__all__ = [
    "DataResponder",
    "respond",
]
