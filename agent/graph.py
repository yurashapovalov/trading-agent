"""
LangGraph v2 — Fast Intent Classification

Flow:
    Question → IntentClassifier (fast, no thinking)
                 ├── chitchat → Responder → END
                 ├── concept → Responder → END
                 └── data → Parser (with thinking) → Router
                                                       ├── unclear → Clarifier → END (or loop)
                                                       └── Executor → END
"""

from typing import Literal
from datetime import date
import uuid

import config

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage

from agent.state import AgentState, get_current_question
from agent.types import ParsedQuery, Usage
from agent.agents.intent import IntentClassifier
from agent.agents.parser import Parser
from agent.agents.clarifier import Clarifier
from agent.agents.responder import Responder
from agent.executor import execute
from agent.memory import get_memory_manager
from agent.agents.presenter import Presenter


# =============================================================================
# Node Functions
# =============================================================================

def load_memory(state: AgentState) -> dict:
    """
    Load conversation memory and add current user message.

    Runs at the start of each invoke to:
    1. Get/create memory for session (loads from Supabase if exists)
    2. Add user message to memory
    3. Put memory context into state for downstream nodes
    """
    # session_id is actually chat_id from API
    chat_id = state.get("session_id") or str(uuid.uuid4())
    user_id = state.get("user_id")
    question = get_current_question(state)

    # Get memory for chat (auto-loads from Supabase)
    manager = get_memory_manager()
    memory = manager.get_or_create(chat_id=chat_id, user_id=user_id)

    # Add user message to memory (not saved to DB here - API does that via chat_logs)
    if question:
        memory.add_message("user", question)

    # Get context for downstream nodes
    memory_context = memory.get_context()

    return {
        "session_id": chat_id,
        "memory_context": memory_context,
    }


def classify_intent(state: AgentState) -> dict:
    """
    Fast intent classification (no thinking).

    Quickly determines: chitchat, concept, or data.
    Also detects user's language and translates to English.
    ~200-400ms instead of ~3500ms with full Parser.

    If clarified_query is present (from Clarifier), use that instead of current message.
    """
    # Use clarified_query if present (from Clarifier), otherwise current question
    clarified = state.get("clarified_query")
    if clarified:
        question = clarified
    else:
        question = get_current_question(state)

    classifier = IntentClassifier()
    result = classifier.classify(question)

    # Aggregate usage
    prev_usage_dict = state.get("usage") or {}
    prev_usage = Usage.model_validate(prev_usage_dict) if prev_usage_dict else Usage()
    total_usage = prev_usage + result.usage

    update = {
        "intent": result.intent,
        "lang": result.lang,  # User's language (ISO 639-1)
        "question_en": result.question_en,  # Translated to English
        "parsed_query": {"intent": result.intent},
        "agents_used": ["intent"],
        "step_number": state.get("step_number", 0) + 1,
        "usage": total_usage.model_dump(),
    }

    # Clear clarified_query after processing
    if clarified:
        update["clarified_query"] = None

    return update


def route_after_intent(state: AgentState) -> Literal["chitchat", "concept", "parser"]:
    """
    Route based on fast intent classification.

    chitchat/concept → go directly to responder (skip Parser)
    data → go to full Parser with thinking
    """
    intent = state.get("intent", "data")

    if intent == "chitchat":
        return "chitchat"
    if intent == "concept":
        return "concept"
    return "parser"


def parse_question(state: AgentState) -> dict:
    """
    Parser node — stateless entity extraction.

    Just takes a question and parses it.
    Uses memory_context for conversation history.
    If there's a clarified_query from Clarifier, parse that instead.
    """
    # Use clarified_query if available (from Clarifier), otherwise question_en from IntentClassifier
    clarified = state.get("clarified_query")
    question = clarified if clarified else state.get("question_en", get_current_question(state))

    # Get memory context for Parser (conversation history)
    memory_context = state.get("memory_context", "")

    parser = Parser()
    result = parser.parse(question, today=date.today(), context=memory_context)

    # Aggregate usage (stored as dict in state)
    prev_usage_dict = state.get("usage") or {}
    prev_usage = Usage.model_validate(prev_usage_dict) if prev_usage_dict else Usage()
    total_usage = prev_usage + result.usage

    return {
        "parsed_query": result.query.model_dump(),
        "parser_thoughts": result.thoughts,
        "parser_chunks_used": result.chunks_used,  # RAP chunks
        "parser_cached": result.cached,  # Explicit cache hit
        "agents_used": state.get("agents_used", []) + ["parser"],
        "step_number": state.get("step_number", 0) + 1,
        "usage": total_usage.model_dump(),
        # Clear clarified_query after using it
        "clarified_query": None,
    }


def route_after_parser(state: AgentState) -> Literal["clarification", "executor"]:
    """
    Router — decide next step based on Parser output.

    Only handles data queries (chitchat/concept already routed by intent classifier).
    """
    parsed = state.get("parsed_query", {})
    unclear = parsed.get("unclear", [])

    if unclear:
        return "clarification"

    return "executor"


def handle_chitchat(state: AgentState) -> dict:
    """
    Chitchat node — greetings, thanks, goodbye using Responder.
    Uses detected language from IntentClassifier.
    """
    question = get_current_question(state)
    lang = state.get("lang", "en")  # Default to English

    responder = Responder()
    result = responder.respond(question, intent="chitchat", subtype="greeting", lang=lang)

    # Aggregate usage (stored as dict in state)
    prev_usage_dict = state.get("usage") or {}
    prev_usage = Usage.model_validate(prev_usage_dict) if prev_usage_dict else Usage()
    total_usage = prev_usage + result.usage

    return {
        "response": result.text,
        "messages": [AIMessage(content=result.text)],
        "agents_used": state.get("agents_used", []) + ["responder"],
        "usage": total_usage.model_dump(),
    }


def handle_concept(state: AgentState) -> dict:
    """
    Concept node — explain trading concept using Responder.
    Uses detected language from IntentClassifier.
    """
    parsed = state.get("parsed_query", {})
    what = parsed.get("what", "")
    question = get_current_question(state)
    lang = state.get("lang", "en")  # Default to English

    responder = Responder()
    result = responder.respond(question, intent="concept", topic=what, lang=lang)

    # Aggregate usage (stored as dict in state)
    prev_usage_dict = state.get("usage") or {}
    prev_usage = Usage.model_validate(prev_usage_dict) if prev_usage_dict else Usage()
    total_usage = prev_usage + result.usage

    return {
        "response": result.text,
        "messages": [AIMessage(content=result.text)],
        "agents_used": state.get("agents_used", []) + ["responder"],
        "usage": total_usage.model_dump(),
    }


def handle_clarification(state: AgentState) -> dict:
    """
    Clarification node — ask user for missing info OR confirm clarified query.

    Two modes:
    1. First time (from Parser): ask clarifying question, store context
    2. User answered: combine original + answer → generate clarified_query

    Uses question_en (translated by IntentClassifier) and responds in user's lang.
    """
    # Use translated question when evaluating user's answer
    question_en = state.get("question_en", get_current_question(state))
    lang = state.get("lang", "en")
    parsed = state.get("parsed_query", {})
    parser_thoughts = state.get("parser_thoughts", "")
    clarifier_question = state.get("clarifier_question", "")

    # Build previous_context from clarification history
    history = state.get("clarification_history", [])
    original = state.get("original_question", "")

    if history:
        # Format history for Clarifier
        lines = [f"Original question: {original}"]
        for turn in history:
            if turn["role"] == "assistant":
                lines.append(f"Assistant: {turn['content']}")
            else:
                lines.append(f"User: {turn['content']}")
        previous_context = "\n".join(lines)
    else:
        previous_context = ""

    clarifier = Clarifier()
    result = clarifier.clarify(
        question=question_en,
        parsed=parsed,
        previous_context=previous_context,
        parser_thoughts=parser_thoughts,
        clarifier_question=clarifier_question,
        lang=lang,
    )

    # Aggregate usage (stored as dict in state)
    prev_usage_dict = state.get("usage") or {}
    prev_usage = Usage.model_validate(prev_usage_dict) if prev_usage_dict else Usage()
    total_usage = prev_usage + result.usage

    # Get raw question for history (in user's language)
    raw_question = get_current_question(state)

    update = {
        "response": result.response,
        "messages": [AIMessage(content=result.response)],
        "agents_used": state.get("agents_used", []) + ["clarifier"],
        "usage": total_usage.model_dump(),
        "clarifier_thoughts": result.thoughts,  # For logging
    }

    if result.clarified_query:
        # Clarifier formed complete query — route to IntentClassifier
        update["clarified_query"] = result.clarified_query
        update["awaiting_clarification"] = False
        update["clarification_history"] = None
        update["original_question"] = None
        update["clarifier_question"] = None
    else:
        # Still need more info — store state and wait
        update["awaiting_clarification"] = True
        # Save Clarifier's question for relevance check next time
        update["clarifier_question"] = result.response

        # Store original question on first clarification
        if not original:
            update["original_question"] = raw_question

        # Add to history
        new_history = list(history) if history else []
        if history:  # User responded, add their message
            new_history.append({"role": "user", "content": raw_question})
        new_history.append({"role": "assistant", "content": result.response})
        update["clarification_history"] = new_history

    return update


def route_entry(state: AgentState) -> Literal["intent", "clarifier"]:
    """
    Entry router — check if we're in clarification flow.

    If awaiting_clarification, user's message is an answer → go to Clarifier.
    Otherwise, it's a new question → go to fast IntentClassifier.
    """
    if state.get("awaiting_clarification"):
        return "clarifier"
    return "intent"


def route_after_clarification(state: AgentState) -> Literal["intent", "respond"]:
    """
    Router after Clarifier — check if we have clarified_query.

    If yes → go to IntentClassifier to translate and route.
    If no → respond to user and wait for more input.
    """
    if state.get("clarified_query"):
        return "intent"
    return "respond"


def save_memory(state: AgentState) -> dict:
    """
    Save assistant response to memory.

    Runs before END to persist the conversation turn.
    Note: Actual persistence to chat_logs is done by API layer.
    This updates in-memory state and may trigger compaction → summary save.
    """
    chat_id = state.get("session_id")
    user_id = state.get("user_id")
    response = state.get("response")

    if chat_id and response:
        manager = get_memory_manager()
        memory = manager.get_or_create(chat_id=chat_id, user_id=user_id)
        memory.add_message("assistant", response)

    return {}


def handle_executor(state: AgentState) -> dict:
    """
    Executor node — get data and compute result.

    Uses Presenter to format response based on data size and context.
    """
    parsed_dict = state.get("parsed_query", {})
    parsed = ParsedQuery.model_validate(parsed_dict)

    # Get original question for Presenter (in user's language)
    question = get_current_question(state)
    lang = state.get("lang", "en")

    result = execute(parsed, symbol="NQ", today=date.today())

    # Use Presenter to format response
    presenter = Presenter(symbol="NQ")
    presentation = presenter.present(data=result, question=question, lang=lang)

    return {
        "response": presentation.text,
        "messages": [AIMessage(content=presentation.text)],
        "data": result,
        "agents_used": state.get("agents_used", []) + ["executor", "presenter"],
    }


# =============================================================================
# Build Graph
# =============================================================================

def build_graph() -> StateGraph:
    """
    Build the graph with fast intent classification.

    Flow:
        START → load_memory → route_entry
                               ├── awaiting_clarification → clarifier → route_after_clarification
                               │                                          ├── has clarified_query → intent → parser
                               │                                          └── need more info → save_memory → END
                               └── new question → intent → route_after_intent
                                                            ├── chitchat → save_memory → END
                                                            ├── concept → save_memory → END
                                                            └── data → parser → route_after_parser
                                                                                  ├── unclear → clarifier
                                                                                  └── executor → save_memory → END
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("load_memory", load_memory)
    graph.add_node("intent", classify_intent)  # Fast intent classifier
    graph.add_node("parser", parse_question)   # Full parser with thinking
    graph.add_node("chitchat", handle_chitchat)
    graph.add_node("concept", handle_concept)
    graph.add_node("clarifier", handle_clarification)
    graph.add_node("executor", handle_executor)
    graph.add_node("save_memory", save_memory)

    # Start with loading memory
    graph.add_edge(START, "load_memory")

    # After loading memory — check if we're in clarification flow
    graph.add_conditional_edges(
        "load_memory",
        route_entry,
        {
            "intent": "intent",
            "clarifier": "clarifier",
        }
    )

    # After IntentClassifier — route to responder or parser
    graph.add_conditional_edges(
        "intent",
        route_after_intent,
        {
            "chitchat": "chitchat",
            "concept": "concept",
            "parser": "parser",  # Only data queries go to full Parser
        }
    )

    # After Parser — route based on unclear (data queries only)
    graph.add_conditional_edges(
        "parser",
        route_after_parser,
        {
            "clarification": "clarifier",
            "executor": "executor",
        }
    )

    # After Clarifier — check if we have clarified_query (LOOP back to parser!)
    graph.add_conditional_edges(
        "clarifier",
        route_after_clarification,
        {
            "intent": "intent",  # clarified_query → IntentClassifier → Parser
            "respond": "save_memory",  # No clarified_query → save and wait for user
        }
    )

    # All response nodes go to save_memory before END
    graph.add_edge("chitchat", "save_memory")
    graph.add_edge("concept", "save_memory")
    graph.add_edge("executor", "save_memory")

    # save_memory goes to END
    graph.add_edge("save_memory", END)

    return graph


def compile_graph():
    """Compile graph for execution."""
    graph = build_graph()
    return graph.compile()


# =============================================================================
# Barb — SSE Streaming Wrapper
# =============================================================================

import time


class Barb:
    """
    AskBar assistant wrapper with SSE streaming.

    Wraps LangGraph and generates events for API:
    - step_start: agent starting
    - step_end: agent finished with input/output data
    - text_delta: streaming text chunks
    - usage: token counts
    - done: completion
    """

    def __init__(self):
        self._graph = None

    @property
    def graph(self):
        """Lazy compile graph."""
        if self._graph is None:
            self._graph = compile_graph()
        return self._graph

    def stream_sse(
        self,
        question: str,
        user_id: str,
        session_id: str,
        request_id: str | None = None,
    ):
        """
        Stream SSE events for the question.

        Yields dicts with event data for API to serialize.
        Uses stream_mode="updates" to get node-by-node updates with proper timing.
        """
        start_time = time.time()

        # Initial state
        initial_state = {
            "messages": [HumanMessage(content=question)],
            "session_id": session_id,
            "user_id": user_id,
            "agents_used": [],
            "step_number": 0,
        }

        # Track state and timing
        current_state = dict(initial_state)
        prev_usage = Usage()
        node_start_time = time.time()  # First node starts now
        current_agent = None

        # Map LangGraph node names to our agent names
        NODE_TO_AGENT = {
            "intent": "intent",      # Fast intent classifier
            "parser": "parser",      # Full parser with thinking
            "executor": "executor",
            "clarifier": "clarifier",
            "chitchat": "responder",
            "concept": "responder",
        }

        try:
            # Stream through graph with updates mode
            for update in self.graph.stream(initial_state, stream_mode="updates"):
                # update is dict like {"node_name": {state_updates}}
                for node_name, node_updates in update.items():
                    # Skip empty updates (LangGraph returns None for empty dict returns)
                    if node_updates is None:
                        continue

                    # Skip internal nodes
                    if node_name in ("load_memory", "save_memory", "__start__"):
                        # Merge updates into current state
                        current_state.update(node_updates)
                        continue

                    agent = NODE_TO_AGENT.get(node_name)
                    if not agent:
                        current_state.update(node_updates)
                        continue

                    # Emit step_start for this agent
                    yield {
                        "type": "step_start",
                        "agent": agent,
                    }

                    # Merge updates into current state
                    current_state.update(node_updates)

                    # Calculate duration (time since node started)
                    duration_ms = int((time.time() - node_start_time) * 1000)

                    # Calculate per-agent usage (delta)
                    current_usage_dict = current_state.get("usage") or {}
                    current_usage = Usage.model_validate(current_usage_dict) if current_usage_dict else Usage()
                    agent_usage = Usage(
                        input_tokens=current_usage.input_tokens - prev_usage.input_tokens,
                        output_tokens=current_usage.output_tokens - prev_usage.output_tokens,
                        thinking_tokens=current_usage.thinking_tokens - prev_usage.thinking_tokens,
                        cached_tokens=current_usage.cached_tokens - prev_usage.cached_tokens,
                    )
                    prev_usage = current_usage

                    # Build output with usage
                    output = self._get_agent_output(agent, current_state)
                    output["usage"] = {
                        "input_tokens": agent_usage.input_tokens,
                        "output_tokens": agent_usage.output_tokens,
                        "thinking_tokens": agent_usage.thinking_tokens,
                        "cached_tokens": agent_usage.cached_tokens,
                        "cost_usd": agent_usage.cost(config.GEMINI_LITE_MODEL),
                    }

                    # Emit step_end with timing and data
                    yield {
                        "type": "step_end",
                        "agent": agent,
                        "duration_ms": duration_ms,
                        "input": self._get_agent_input(agent, current_state),
                        "output": output,
                    }

                    # Stream response text if available
                    response = current_state.get("response")
                    if response:
                        yield {
                            "type": "text_delta",
                            "content": response,
                        }

                    # Next node starts now
                    node_start_time = time.time()
                    current_agent = agent

            # Final state
            total_duration_ms = int((time.time() - start_time) * 1000)

            # Usage from aggregated state
            usage_dict = current_state.get("usage") or {}
            usage = Usage.model_validate(usage_dict) if usage_dict else Usage()
            yield {
                "type": "usage",
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "thinking_tokens": usage.thinking_tokens,
                "cached_tokens": usage.cached_tokens,
                "cost": usage.cost(config.GEMINI_LITE_MODEL),
            }

            yield {
                "type": "done",
                "total_duration_ms": total_duration_ms,
                "response": current_state.get("response", ""),
            }

        except Exception as e:
            yield {
                "type": "error",
                "message": str(e),
            }

    def _get_agent_input(self, agent: str, state: dict) -> dict:
        """Get input data for agent (for logging)."""
        if agent == "intent":
            return {
                "question": get_current_question(state),
            }
        elif agent == "parser":
            return {
                "question": get_current_question(state),
                "memory_context": state.get("memory_context", "")[:500] if state.get("memory_context") else None,
                "clarified_query": state.get("clarified_query"),
            }
        elif agent == "executor":
            return {
                "parsed_query": state.get("parsed_query"),
            }
        elif agent == "clarifier":
            return {
                "question": get_current_question(state),
                "parsed_query": state.get("parsed_query"),
                "parser_thoughts": state.get("parser_thoughts"),
                "original_question": state.get("original_question"),
                "clarification_history": state.get("clarification_history"),
            }
        elif agent == "responder":
            return {
                "question": get_current_question(state),
                "parsed_query": state.get("parsed_query"),
            }
        return {}

    def _get_agent_output(self, agent: str, state: dict) -> dict:
        """Get output data for agent (for logging)."""
        if agent == "intent":
            return {
                "intent": state.get("intent"),
                "lang": state.get("lang"),
                "question_en": state.get("question_en"),
            }
        elif agent == "parser":
            return {
                "parsed_query": state.get("parsed_query"),
                "thoughts": state.get("parser_thoughts"),
                "chunks_used": state.get("parser_chunks_used"),
                "cached": state.get("parser_cached"),
            }
        elif agent == "executor":
            data = state.get("data") or {}
            output = {
                "row_count": data.get("row_count"),
                "operation": data.get("operation"),
                "result": data.get("result"),
            }
            # Convert DataFrame to rows/columns for UI
            df = data.get("data")
            if df is not None and hasattr(df, "to_dict"):
                output["full_data"] = self._df_to_dict(df)
            return output
        elif agent == "clarifier":
            return {
                "response": state.get("response"),
                "clarified_query": state.get("clarified_query"),
                "thoughts": state.get("clarifier_thoughts"),
            }
        elif agent == "responder":
            return {
                "response": state.get("response"),
            }
        return {}

    def _df_to_dict(self, df, max_rows: int = 100) -> dict:
        """Convert DataFrame to dict for JSON serialization."""
        import math

        total = len(df)
        df_limited = df.head(max_rows)

        rows = []
        for _, row in df_limited.iterrows():
            record = {}
            for col, val in row.items():
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    record[col] = None
                elif hasattr(val, "isoformat"):
                    record[col] = val.isoformat()
                elif isinstance(val, float):
                    record[col] = round(val, 4)
                else:
                    record[col] = val
            rows.append(record)

        return {
            "columns": list(df.columns),
            "rows": rows,
            "row_count": total,
            "truncated": total > max_rows,
        }

    def invoke(self, question: str, **kwargs) -> dict:
        """Simple invoke without streaming."""
        state = {
            "messages": [HumanMessage(content=question)],
            **kwargs,
        }
        return self.graph.invoke(state)


# Singleton instance
barb = Barb()

# Alias for api.py compatibility
trading_graph = barb


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    tests = [
        "привет",
        "что такое OPEX",
        "статистика за 2024",
    ]

    for q in tests:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        for event in barb.stream_sse(q, user_id="test", session_id="test"):
            print(f"  {event['type']}: ", end="")
            if event["type"] == "step_end":
                print(f"{event['agent']} ({event['duration_ms']}ms)")
            elif event["type"] == "text_delta":
                print(f"{event['content'][:50]}...")
            elif event["type"] == "done":
                print(f"total {event['total_duration_ms']}ms")
            else:
                print()
