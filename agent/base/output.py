"""Base class for output agents (LLM validation on final output)."""

from abc import ABC, abstractmethod
from typing import Generator, Any
import time

from agent.state import AgentState, UsageStats


class BaseOutputAgent(ABC):
    """
    Base class for agents that generate final user-facing output.

    These agents produce text responses.
    Validation is done by a separate Validator agent (LLM-based).
    """

    name: str = "output_agent"
    agent_type: str = "output"

    @abstractmethod
    def generate(self, state: AgentState) -> str:
        """
        Generate response text.

        Args:
            state: Current graph state (includes data if available)

        Returns:
            Response text
        """
        pass

    def generate_stream(self, state: AgentState) -> Generator[str, None, str]:
        """
        Generate response with streaming.

        Override this for streaming support.
        Default implementation calls generate() and yields the full response.

        Yields:
            Text chunks

        Returns:
            Full response text
        """
        response = self.generate(state)
        yield response
        return response

    def get_usage(self) -> UsageStats:
        """
        Return token usage from last generation.

        Override to provide actual usage stats.
        """
        return UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def __call__(self, state: AgentState) -> dict:
        """
        Process state and return updates.

        This is called by LangGraph when the node executes.
        """
        start_time = time.time()

        response = self.generate(state)
        usage = self.get_usage()

        duration_ms = int((time.time() - start_time) * 1000)

        # Merge usage stats
        current_usage = state.get("usage", {})
        merged_usage = UsageStats(
            input_tokens=current_usage.get("input_tokens", 0) + usage.get("input_tokens", 0),
            output_tokens=current_usage.get("output_tokens", 0) + usage.get("output_tokens", 0),
            thinking_tokens=current_usage.get("thinking_tokens", 0) + usage.get("thinking_tokens", 0),
            cost_usd=current_usage.get("cost_usd", 0.0) + usage.get("cost_usd", 0.0),
        )

        return {
            "response": response,
            "usage": merged_usage,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
        }

    def get_trace_data(
        self,
        state: AgentState,
        response: str,
        usage: UsageStats,
        duration_ms: int
    ) -> dict:
        """Return data for request_traces logging."""
        return {
            "agent_name": self.name,
            "agent_type": self.agent_type,
            "input_data": {
                "question": state.get("question"),
                "data_summary": {
                    "total_rows": state.get("data", {}).get("total_rows", 0),
                    "has_errors": state.get("data", {}).get("has_errors", False),
                }
            },
            "output_data": {"response_length": len(response)},
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "thinking_tokens": usage.get("thinking_tokens", 0),
            "cost_usd": usage.get("cost_usd", 0.0),
            "duration_ms": duration_ms,
        }
