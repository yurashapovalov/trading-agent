"""Analyst agent - interprets data and generates user-facing responses.

Analyzes data from DataFetcher and generates markdown responses with Stats
for validation. Stats are structured numbers that Validator checks against
actual data to ensure accuracy.

Supports two modes:
- Streaming: Real-time text output via LangGraph's get_stream_writer()
- Batch: JSON response with stats for validation

Example:
    analyst = Analyst()
    result = analyst({"question": "...", "data": {...}})
    # result["response"] = markdown text
    # result["stats"] = {"change_pct": 2.5, ...} for validation
"""

import json
from typing import Generator
from google import genai
from google.genai import types

import config
from agent.state import AgentState, Stats, UsageStats, get_current_question, get_chat_history
from agent.prompts.analyst import get_analyst_prompt, get_analyst_prompt_streaming
from agent.pricing import calculate_cost
from langchain_core.messages import AIMessage

# LangGraph streaming support
try:
    from langgraph.config import get_stream_writer
    HAS_STREAM_WRITER = True
except ImportError:
    HAS_STREAM_WRITER = False
    get_stream_writer = None


class Analyst:
    """Analyzes trading data and generates user-facing responses with Stats.

    Uses Gemini LLM to interpret data and write insights. Returns structured
    Stats that Validator checks against actual data for accuracy.

    Attributes:
        name: Agent name for logging.
        agent_type: Agent type ("output" - generates final response).
        model: Gemini model name from config.
    """

    name = "analyst"
    agent_type = "output"

    def __init__(self):
        """Initialize Gemini client and usage tracking."""
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_MODEL
        self._last_usage = UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def __call__(self, state: AgentState) -> dict:
        """Generate analysis response with stats for validation.

        Uses real-time streaming when running inside LangGraph graph.
        Falls back to batch JSON generation otherwise.

        Args:
            state: Agent state with messages (MessagesState), data, intent.

        Returns:
            Dict with response, stats, usage, agents_used, step_number, and messages.
        """
        # Get question and history from messages
        question = get_current_question(state)
        chat_history = get_chat_history(state)

        data = state.get("data") or {}
        intent = state.get("intent") or {}
        intent_type = intent.get("type", "data")
        holiday_info = intent.get("holiday_info")  # From Understander if dates are holidays
        assumptions = intent.get("assumptions")  # From Understander if defaults were used

        # Check if rewrite needed
        validation = state.get("validation") or {}
        previous_response = ""
        issues = []
        if validation.get("status") == "rewrite":
            previous_response = state.get("response", "")
            issues = validation.get("issues", [])

        # Try to get stream writer (only works inside LangGraph execution)
        writer = None
        if HAS_STREAM_WRITER:
            try:
                writer = get_stream_writer()
            except Exception:
                pass  # Not in streaming context

        if writer:
            # Real-time streaming mode - use simpler prompt without JSON requirement
            prompt = get_analyst_prompt_streaming(
                question=question,
                data=data,
                chat_history=chat_history,
                holiday_info=holiday_info,
                assumptions=assumptions,
            )
            return self._generate_with_streaming(prompt, writer, state)
        else:
            # Batch mode - use full prompt with JSON/stats
            prompt = get_analyst_prompt(
                question=question,
                data=data,
                intent_type=intent_type,
                previous_response=previous_response,
                issues=issues,
                chat_history=chat_history,
                holiday_info=holiday_info,
                assumptions=assumptions,
            )
            return self._generate_batch(prompt, state)

    def _generate_with_streaming(self, prompt: str, writer, state: AgentState) -> dict:
        """Generate response with real-time streaming via LangGraph."""
        full_text = ""
        total_input = 0
        total_output = 0

        try:
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                )
            ):
                # Track usage from last chunk
                if chunk.usage_metadata:
                    total_input = chunk.usage_metadata.prompt_token_count or 0
                    total_output = chunk.usage_metadata.candidates_token_count or 0

                # Emit text chunk in real-time
                if chunk.text:
                    writer({"type": "text_delta", "agent": self.name, "content": chunk.text})
                    full_text += chunk.text

            # Update usage stats
            cost = calculate_cost(total_input, total_output, 0)
            self._last_usage = UsageStats(
                input_tokens=total_input,
                output_tokens=total_output,
                thinking_tokens=0,
                cost_usd=cost
            )

            # Try to extract stats from streamed text
            stats = self._extract_stats_from_text(full_text)

        except Exception as e:
            full_text = f"Error generating response: {e}"
            stats = None

        return {
            "response": full_text,
            "stats": stats,
            "usage": self._last_usage,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
            "validation_attempts": state.get("validation_attempts", 0) + 1,
            # Add AIMessage to messages for checkpointer accumulation
            "messages": [AIMessage(content=full_text)],
        }

    def _generate_batch(self, prompt: str, state: AgentState) -> dict:
        """Generate response in batch mode (no streaming)."""
        try:
            response_obj = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    response_mime_type="application/json",
                )
            )

            # Track usage
            self._track_usage(response_obj)

            # Parse JSON response
            result = json.loads(response_obj.text)
            response_text = result.get("response", "")
            stats = result.get("stats") or {}

        except json.JSONDecodeError:
            response_text = response_obj.text if response_obj else ""
            stats = {}
        except Exception as e:
            response_text = f"Error generating response: {e}"
            stats = {}

        return {
            "response": response_text,
            "stats": Stats(**stats) if stats else None,
            "usage": self._last_usage,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
            "validation_attempts": state.get("validation_attempts", 0) + 1,
            # Add AIMessage to messages for checkpointer accumulation
            "messages": [AIMessage(content=response_text)],
        }

    def generate_stream(self, state: AgentState) -> Generator[str, None, dict]:
        """
        Generate response with streaming.

        Note: Streaming doesn't support JSON mode well,
        so we collect full response and parse at the end.
        """
        question = state.get("question", "")
        data = state.get("data") or {}
        intent = state.get("intent") or {}
        intent_type = intent.get("type", "data")

        # Check if rewrite needed
        validation = state.get("validation") or {}
        previous_response = ""
        issues = []
        if validation.get("status") == "rewrite":
            previous_response = state.get("response", "")
            issues = validation.get("issues", [])

        # Build prompt
        prompt = get_analyst_prompt(
            question=question,
            data=data,
            intent_type=intent_type,
            previous_response=previous_response,
            issues=issues,
        )

        full_text = ""
        total_input = 0
        total_output = 0

        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
            )
        ):
            if chunk.usage_metadata:
                total_input = chunk.usage_metadata.prompt_token_count or 0
                total_output = chunk.usage_metadata.candidates_token_count or 0

            if chunk.text:
                yield chunk.text
                full_text += chunk.text

        # Update usage
        cost = calculate_cost(total_input, total_output, 0)
        self._last_usage = UsageStats(
            input_tokens=total_input,
            output_tokens=total_output,
            thinking_tokens=0,
            cost_usd=cost
        )

        # Try to parse stats from streamed response
        stats = self._extract_stats_from_text(full_text)

        return {
            "response": full_text,
            "stats": stats,
            "agents_used": [self.name],
            "validation_attempts": state.get("validation_attempts", 0) + 1,
        }

    def _track_usage(self, response) -> None:
        """Track token usage from response."""
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0
            thinking_tokens = getattr(response.usage_metadata, 'thoughts_token_count', 0) or 0
            cost = calculate_cost(input_tokens, output_tokens, thinking_tokens)

            self._last_usage = UsageStats(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                cost_usd=cost
            )

    def _extract_stats_from_text(self, text: str) -> Stats | None:
        """Try to extract stats from text response (for streaming)."""
        try:
            if "{" in text and "}" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                json_str = text[start:end]
                data = json.loads(json_str)
                if "stats" in data:
                    return Stats(**data["stats"])
        except:
            pass
        return None

    def get_usage(self) -> UsageStats:
        """Return usage from last generation."""
        return self._last_usage
