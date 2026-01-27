"""
TradingGraph wrapper for SSE streaming.

Wraps LangGraph execution with SSE events for API consumption.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Generator, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage

from agent.graph import get_graph
from agent.state import AgentState
from agent.types import Usage
from agent.logging.supabase import init_chat_log_sync, complete_chat_log_sync
from agent.memory.conversation import ConversationMemory


@dataclass
class AgentUsage:
    """Usage tracking per agent."""
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "thinking_tokens": self.thinking_tokens,
            "cached_tokens": self.cached_tokens,
            "cost_usd": self.cost_usd,
        }


@dataclass
class StreamContext:
    """Context for streaming execution."""
    question: str
    user_id: str
    session_id: str
    request_id: str
    chat_id: str | None = None
    start_time: float = field(default_factory=time.time)
    step_number: int = 0
    current_agent: str | None = None
    agent_start_time: float = 0

    # Per-agent usage
    usage_by_agent: dict[str, AgentUsage] = field(default_factory=dict)

    # State for clarification flow
    awaiting_clarification: bool = False
    original_question: str | None = None
    clarification_history: list[dict] | None = None

    # Conversation memory (for context and saving)
    memory: Any = None


class TradingGraph:
    """
    Wrapper around LangGraph for SSE streaming.

    Yields SSE events:
    - step_start: agent starting work
    - step_end: agent finished with output
    - text_delta: streaming text (for response)
    - usage: token usage summary
    - done: completion with total duration
    """

    def __init__(self):
        self._graph = None

    @property
    def graph(self):
        """Lazy load graph."""
        if self._graph is None:
            self._graph = get_graph()
        return self._graph

    def stream_sse(
        self,
        question: str,
        user_id: str,
        session_id: str,
        chat_id: str | None = None,
        request_id: str | None = None,
        awaiting_clarification: bool = False,
        original_question: str | None = None,
        clarification_history: list[dict] | None = None,
        needs_title: bool = False,
    ) -> Generator[dict, None, None]:
        """
        Stream SSE events for question processing.

        Args:
            question: User's question
            user_id: User ID for logging
            session_id: Session ID for memory
            chat_id: Chat session ID for logging
            request_id: Request ID for traces (generated if None)
            awaiting_clarification: True if continuing clarification flow
            original_question: Original question (for clarification)
            clarification_history: Previous clarification turns
            needs_title: True if chat session needs a title (first message)

        Yields:
            SSE events: step_start, step_end, text_delta, usage, done
        """
        ctx = StreamContext(
            question=question,
            user_id=user_id,
            session_id=session_id,
            chat_id=chat_id,
            request_id=request_id or str(uuid4()),
            awaiting_clarification=awaiting_clarification,
            original_question=original_question,
            clarification_history=clarification_history,
        )

        # Load conversation memory (for context)
        memory_context = None
        context_compacted = False

        if chat_id:
            try:
                memory = ConversationMemory(chat_id=chat_id, user_id=user_id)
                if memory.load_sync():
                    memory_context = memory.get_context() if (memory.recent or memory.summaries or memory.key_facts) else None
                    context_compacted = len(memory.summaries) > 0
                    ctx.memory = memory
            except Exception as e:
                # Memory load failed - continue without context
                import logging
                logging.getLogger(__name__).warning(f"Failed to load memory: {e}")

        # Initialize chat log at the START of request
        init_chat_log_sync(
            request_id=ctx.request_id,
            user_id=user_id,
            chat_id=chat_id,
            question=question,
        )

        # Build initial state with request_id for node logging
        state: AgentState = {
            "messages": [HumanMessage(content=question)],
            "session_id": session_id,
            "user_id": user_id,
            "request_id": ctx.request_id,
            "awaiting_clarification": awaiting_clarification,
            "original_question": original_question,
            "clarification_history": clarification_history or [],
            "needs_title": needs_title,
            "step_number": 0,
            "memory_context": memory_context,
            "context_compacted": context_compacted,
        }

        # Run graph and yield events
        yield from self._run_graph(state, ctx)

    def _run_graph(
        self,
        state: AgentState,
        ctx: StreamContext,
    ) -> Generator[dict, None, None]:
        """Run graph and yield SSE events."""

        # Track which agents ran
        agents_seen = set()
        last_state = state

        # Use stream to get node-by-node updates
        for event in self.graph.stream(state, stream_mode="updates"):
            # event is dict: {node_name: node_output}
            for node_name, output in event.items():
                # Skip if we've already processed this agent in this run
                if node_name in agents_seen:
                    continue
                agents_seen.add(node_name)

                ctx.step_number += 1
                ctx.current_agent = node_name
                agent_start = time.time()

                # Yield step_start
                yield {
                    "type": "step_start",
                    "agent": node_name,
                    "step": ctx.step_number,
                    "request_id": ctx.request_id,
                }

                # Calculate duration
                duration_ms = int((time.time() - agent_start) * 1000)

                # Extract usage from output if present
                usage_dict = output.get("usage") if isinstance(output, dict) else None
                if usage_dict:
                    agent_usage = AgentUsage(
                        input_tokens=usage_dict.get("input_tokens", 0),
                        output_tokens=usage_dict.get("output_tokens", 0),
                        thinking_tokens=usage_dict.get("thinking_tokens", 0),
                        cached_tokens=usage_dict.get("cached_tokens", 0),
                        cost_usd=usage_dict.get("cost_usd", 0.0),
                    )
                    ctx.usage_by_agent[node_name] = agent_usage

                # Build input for logging (from previous state)
                input_data = self._build_input_data(node_name, last_state)

                # Yield step_end
                yield {
                    "type": "step_end",
                    "agent": node_name,
                    "step": ctx.step_number,
                    "duration_ms": duration_ms,
                    "input": input_data,
                    "output": output if isinstance(output, dict) else {},
                    "request_id": ctx.request_id,
                }

                # Stream text_delta for response
                if isinstance(output, dict):
                    response = output.get("response")
                    if response and node_name in ("presenter", "clarify", "responder", "end"):
                        yield {
                            "type": "text_delta",
                            "content": response,
                            "agent": node_name,
                        }

                # Update last_state with output
                if isinstance(output, dict):
                    last_state = {**last_state, **output}

        # Calculate totals
        total_duration_ms = int((time.time() - ctx.start_time) * 1000)
        total_usage = self._calculate_total_usage(ctx.usage_by_agent)

        # Extract response and route from final state
        response = last_state.get("response", "")
        route = self._determine_route(agents_seen, last_state)

        # Yield usage summary
        yield {
            "type": "usage",
            "by_agent": {
                name: usage.to_dict()
                for name, usage in ctx.usage_by_agent.items()
            },
            "total": total_usage.to_dict(),
            "input_tokens": total_usage.input_tokens,
            "output_tokens": total_usage.output_tokens,
            "thinking_tokens": total_usage.thinking_tokens,
            "cached_tokens": total_usage.cached_tokens,
            "cost": total_usage.cost_usd,
        }

        # Yield done
        yield {
            "type": "done",
            "request_id": ctx.request_id,
            "total_duration_ms": total_duration_ms,
            "agents_used": list(agents_seen),
        }

        # Complete chat log at END of request
        usage_for_log = {
            name: usage.to_dict()
            for name, usage in ctx.usage_by_agent.items()
        }
        usage_for_log["total"] = total_usage.to_dict()

        complete_chat_log_sync(
            request_id=ctx.request_id,
            chat_id=ctx.chat_id,
            response=response,
            route=route,
            agents_used=list(agents_seen),
            duration_ms=total_duration_ms,
            usage=usage_for_log,
        )

        # Update conversation memory with this exchange
        if ctx.memory and response:
            try:
                ctx.memory.add_message("user", ctx.question)
                ctx.memory.add_message("assistant", response)
                # Note: compaction and save happen automatically in add_message if needed
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to update memory: {e}")

    def _build_input_data(self, agent_name: str, state: dict) -> dict:
        """Build input_data for logging based on agent type."""
        if agent_name == "intent":
            return {"question": state.get("messages", [{}])[-1].content if state.get("messages") else ""}

        elif agent_name == "understander":
            return {
                "internal_query": state.get("internal_query"),
                "lang": state.get("lang"),
                "awaiting_clarification": state.get("awaiting_clarification"),
                "original_question": state.get("original_question"),
                "clarification_history": state.get("clarification_history"),
            }

        elif agent_name == "clarifier":
            return {
                "need_clarification": state.get("need_clarification"),
                "question": state.get("original_question"),
                "lang": state.get("lang"),
                "memory_context": state.get("memory_context"),
            }

        elif agent_name == "parser":
            return {
                "expanded_query": state.get("expanded_query"),
            }

        elif agent_name == "planner":
            return {
                "steps": state.get("parsed_query"),
            }

        elif agent_name == "executor":
            return {
                "plans": state.get("execution_plan"),
            }

        elif agent_name == "presenter":
            return {
                "data": state.get("data"),
                "question": state.get("internal_query"),
                "lang": state.get("lang"),
            }

        elif agent_name == "responder":
            return {
                "question": state.get("internal_query"),
                "intent": state.get("intent"),
                "lang": state.get("lang"),
            }

        return {}

    def _calculate_total_usage(self, usage_by_agent: dict[str, AgentUsage]) -> AgentUsage:
        """Sum usage across all agents."""
        total = AgentUsage()
        for usage in usage_by_agent.values():
            total.input_tokens += usage.input_tokens
            total.output_tokens += usage.output_tokens
            total.thinking_tokens += usage.thinking_tokens
            total.cached_tokens += usage.cached_tokens
            total.cost_usd += usage.cost_usd
        return total

    def _determine_route(self, agents_seen: set, last_state: dict) -> str:
        """Determine route from agents used and final state."""
        # Check if clarification flow
        if "clarify" in agents_seen or last_state.get("awaiting_clarification"):
            return "clarify"

        # Check if data flow completed
        if "presenter" in agents_seen:
            return "data"

        # Check if responder handled it (chitchat/concept)
        if "responder" in agents_seen:
            intent = last_state.get("intent", "chitchat")
            return intent if intent in ("chitchat", "concept") else "chitchat"

        # Fallback
        return "data"


# Singleton instance
trading_graph = TradingGraph()
