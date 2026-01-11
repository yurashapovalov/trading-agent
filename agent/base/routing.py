"""Base class for routing agents (no validation needed)."""

from abc import ABC, abstractmethod
from typing import Any
import time

from agent.state import AgentState


class BaseRoutingAgent(ABC):
    """
    Base class for agents that make routing decisions.

    These agents decide where the graph should go next.
    No validation needed - their output is a simple choice.
    """

    name: str = "routing_agent"
    agent_type: str = "routing"

    @abstractmethod
    def decide(self, state: AgentState) -> str:
        """
        Make a routing decision.

        Args:
            state: Current graph state

        Returns:
            Route name (e.g., "data", "concept", "hypothetical")
        """
        pass

    def __call__(self, state: AgentState) -> dict:
        """
        Process state and return updates.

        This is called by LangGraph when the node executes.
        """
        start_time = time.time()

        route = self.decide(state)

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "route": route,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
        }

    def get_trace_data(self, state: AgentState, output: dict, duration_ms: int) -> dict:
        """Return data for request_traces logging."""
        return {
            "agent_name": self.name,
            "agent_type": self.agent_type,
            "input_data": {"question": state.get("question")},
            "output_data": {"route": output.get("route")},
            "duration_ms": duration_ms,
        }
