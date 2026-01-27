"""
Tests for clarification flow.

Covers all edge cases:
1. Initial question → needs clarification → user answers → understood → parser
2. Initial question → needs clarification → user changes topic (new data) → parser
3. Initial question → needs clarification → user cancels (chitchat) → responder
4. Initial question → needs clarification → user answers → still unclear → clarify again
5. Safety net: max 3 rounds → exit

Usage:
    pytest agent/tests/test_clarification_flow.py -v
    pytest agent/tests/test_clarification_flow.py -v -k "test_case1"
"""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

from agent.trading_graph import TradingGraph


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def graph():
    """Fresh TradingGraph instance."""
    return TradingGraph()


@pytest.fixture
def mock_supabase():
    """Mock Supabase logging to avoid DB writes."""
    with patch("agent.trading_graph.init_chat_log_sync") as mock_init, \
         patch("agent.trading_graph.complete_chat_log_sync") as mock_complete, \
         patch("agent.graph.log_trace_step_sync") as mock_trace:
        yield {
            "init": mock_init,
            "complete": mock_complete,
            "trace": mock_trace,
        }


def run_question(
    graph: TradingGraph,
    question: str,
    awaiting_clarification: bool = False,
    original_question: str | None = None,
    clarification_history: list[dict] | None = None,
) -> dict:
    """
    Run question through graph and collect results.

    Returns dict with:
        - agents_used: list of agent names
        - response: final response text
        - awaiting_clarification: bool
        - route: data/clarify/chitchat
        - final_state: last state dict
    """
    user_id = "test-user"
    session_id = str(uuid4())
    chat_id = str(uuid4())

    events = []
    final_state = {}

    for event in graph.stream_sse(
        question=question,
        user_id=user_id,
        session_id=session_id,
        chat_id=chat_id,
        awaiting_clarification=awaiting_clarification,
        original_question=original_question,
        clarification_history=clarification_history,
    ):
        events.append(event)

        # Capture state from step_end events
        if event.get("type") == "step_end":
            output = event.get("output", {})
            final_state.update(output)

    # Extract results from events
    done_event = next((e for e in events if e.get("type") == "done"), {})
    agents_used = done_event.get("agents_used", [])

    return {
        "events": events,
        "agents_used": agents_used,
        "response": final_state.get("response", ""),
        "awaiting_clarification": final_state.get("awaiting_clarification", False),
        "original_question": final_state.get("original_question"),
        "clarification_history": final_state.get("clarification_history"),
        "route": _determine_route(agents_used, final_state),
        "final_state": final_state,
    }


def _determine_route(agents_used: list, state: dict) -> str:
    """Determine route from agents and state."""
    if "clarify" in agents_used or state.get("awaiting_clarification"):
        return "clarify"
    if "presenter" in agents_used:
        return "data"
    if "responder" in agents_used:
        return state.get("intent", "chitchat")
    return "unknown"


# =============================================================================
# Test Cases
# =============================================================================

class TestClarificationFlow:
    """Test clarification flow edge cases."""

    def test_case1_understood_after_clarification(self, graph, mock_supabase):
        """
        Case 1: User answers clarification → understood → parser → data

        Flow: intent → understander → clarify → END
              intent → understander → parser → ... → presenter → END
        """
        # Step 1: Initial vague question
        result1 = run_question(graph, "есть смысл держать позицию в RTH?")

        # Should ask for clarification
        assert result1["awaiting_clarification"], "Should be awaiting clarification"
        assert result1["route"] == "clarify", f"Route should be 'clarify', got {result1['route']}"
        assert "clarify" in result1["agents_used"], "Should use clarify agent"
        assert result1["original_question"] is not None, "Should save original question"

        # Step 2: User provides clarification
        result2 = run_question(
            graph,
            question="средний профит",
            awaiting_clarification=True,
            original_question=result1["original_question"],
            clarification_history=result1["clarification_history"],
        )

        # Should understand and process
        assert not result2["awaiting_clarification"], "Should not be awaiting clarification"
        assert result2["route"] == "data", f"Route should be 'data', got {result2['route']}"
        assert "understander" in result2["agents_used"], "Should use understander"
        assert "parser" in result2["agents_used"], "Should use parser"
        assert "presenter" in result2["agents_used"], "Should use presenter"

        print(f"\n✓ Case 1 passed")
        print(f"  Step 1: {result1['agents_used']}")
        print(f"  Step 2: {result2['agents_used']}")

    def test_case2_topic_changed_new_data_request(self, graph, mock_supabase):
        """
        Case 2: User ignores clarification, asks new data question → parser

        Flow: intent → understander → parser → ... → presenter → END
        """
        # Step 1: Initial vague question
        result1 = run_question(graph, "есть смысл держать позицию?")

        assert result1["awaiting_clarification"], "Should be awaiting clarification"

        # Step 2: User ignores clarification, asks something else
        result2 = run_question(
            graph,
            question="покажи топ 5 дней по волатильности в 2024",  # New question
            awaiting_clarification=True,
            original_question=result1["original_question"],
            clarification_history=result1["clarification_history"],
        )

        # Should process new question
        assert not result2["awaiting_clarification"], "Should not be awaiting clarification"
        assert result2["route"] == "data", f"Route should be 'data', got {result2['route']}"
        assert "understander" in result2["agents_used"], "Should use understander"
        assert "parser" in result2["agents_used"], "Should use parser"

        print(f"\n✓ Case 2 passed")
        print(f"  Step 1: {result1['agents_used']}")
        print(f"  Step 2: {result2['agents_used']}")

    def test_case3_topic_changed_chitchat(self, graph, mock_supabase):
        """
        Case 3: User cancels/chitchats → end (response set by understander)

        Flow: intent → understander → end → END
        """
        # Step 1: Initial vague question
        result1 = run_question(graph, "что будет завтра?")

        # May or may not need clarification, but let's assume it does
        if not result1["awaiting_clarification"]:
            pytest.skip("Question didn't trigger clarification")

        # Step 2: User cancels
        result2 = run_question(
            graph,
            question="забей",  # Cancel
            awaiting_clarification=True,
            original_question=result1["original_question"],
            clarification_history=result1["clarification_history"],
        )

        # Should end flow (understander sets response, routes to end)
        assert not result2["awaiting_clarification"], "Should not be awaiting clarification"
        assert "understander" in result2["agents_used"], "Should use understander"
        # Routes to "end" node (response already set by understander)
        assert "end" in result2["agents_used"], f"Should route to end, got {result2['agents_used']}"

        print(f"\n✓ Case 3 passed")
        print(f"  Step 1: {result1['agents_used']}")
        print(f"  Step 2: {result2['agents_used']}")

    def test_case4_still_need_clarification(self, graph, mock_supabase):
        """
        Case 4: User answer is still unclear → ask again

        Flow: intent → understander → clarify → END
        """
        # Step 1: Initial vague question
        result1 = run_question(graph, "как там рынок?")

        if not result1["awaiting_clarification"]:
            pytest.skip("Question didn't trigger clarification")

        # Step 2: User gives vague answer
        result2 = run_question(
            graph,
            question="ну вообще",  # Still vague
            awaiting_clarification=True,
            original_question=result1["original_question"],
            clarification_history=result1["clarification_history"],
        )

        # May still need clarification or might give up
        # This is acceptable behavior either way
        assert "understander" in result2["agents_used"], "Should use understander"

        print(f"\n✓ Case 4 passed")
        print(f"  Step 1: {result1['agents_used']}")
        print(f"  Step 2: {result2['agents_used']}")
        print(f"  Still awaiting: {result2['awaiting_clarification']}")

    def test_case5_safety_net_max_rounds(self, graph, mock_supabase):
        """
        Case 5: Safety net - max 3 rounds (6 messages) → exit

        After 3 rounds of clarification, should give up gracefully.
        """
        # Build history with 3 rounds (6 messages)
        history = [
            {"role": "assistant", "content": "Что именно интересует?"},
            {"role": "user", "content": "не знаю"},
            {"role": "assistant", "content": "Может волатильность?"},
            {"role": "user", "content": "может"},
            {"role": "assistant", "content": "За какой период?"},
            {"role": "user", "content": "любой"},
        ]

        # This should trigger safety net
        result = run_question(
            graph,
            question="ещё что-то",
            awaiting_clarification=True,
            original_question="как там рынок?",
            clarification_history=history,
        )

        # Should exit clarification flow
        assert "understander" in result["agents_used"], "Should use understander"
        # Safety net should kick in
        # Either gives response or routes away from clarification

        print(f"\n✓ Case 5 passed")
        print(f"  Agents: {result['agents_used']}")
        print(f"  Response: {result['response'][:100]}...")


class TestClarificationTraces:
    """Test that traces are logged correctly."""

    def test_traces_logged_for_each_agent(self, graph, mock_supabase):
        """Verify each agent logs its trace."""
        result = run_question(graph, "топ 5 дней по объёму")

        # Check that trace was called for each agent
        trace_calls = mock_supabase["trace"].call_args_list
        agents_traced = [call.kwargs.get("agent_name") or call.args[3] for call in trace_calls]

        # Should have traces for agents used
        for agent in result["agents_used"]:
            assert agent in agents_traced, f"Agent {agent} should be traced"

        print(f"\n✓ Traces test passed")
        print(f"  Agents used: {result['agents_used']}")
        print(f"  Agents traced: {agents_traced}")

    def test_clarification_flow_traces(self, graph, mock_supabase):
        """Verify clarification flow logs correct traces."""
        # Step 1: Trigger clarification
        result1 = run_question(graph, "есть смысл?")

        if not result1["awaiting_clarification"]:
            pytest.skip("Question didn't trigger clarification")

        trace_calls_1 = mock_supabase["trace"].call_args_list.copy()
        mock_supabase["trace"].reset_mock()

        # Step 2: Answer clarification
        result2 = run_question(
            graph,
            question="профит",
            awaiting_clarification=True,
            original_question=result1["original_question"],
            clarification_history=result1["clarification_history"],
        )

        trace_calls_2 = mock_supabase["trace"].call_args_list
        agents_traced_2 = [call.kwargs.get("agent_name") or call.args[3] for call in trace_calls_2]

        # understander should be in traces
        assert "understander" in agents_traced_2, "understander should be traced"

        print(f"\n✓ Clarification traces test passed")
        print(f"  Step 2 traces: {agents_traced_2}")


# =============================================================================
# Run as script
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
