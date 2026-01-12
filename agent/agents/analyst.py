"""
Analyst agent - interprets data and generates responses with Stats.

Returns:
- response: User-facing markdown response
- stats: Structured numbers for validation
"""

import json
from typing import Generator
from google import genai
from google.genai import types

import config
from agent.state import AgentState, Stats, UsageStats
from agent.prompts.analyst import get_analyst_prompt
from agent.pricing import calculate_cost


class Analyst:
    """
    Analyzes data and writes responses with Stats for validation.

    Principle: LLM analyzes data, returns response + stats.
    Validator (code) checks if stats match actual data.
    """

    name = "analyst"
    agent_type = "output"

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_MODEL
        self._last_usage = UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def __call__(self, state: AgentState) -> dict:
        """Generate analysis with stats."""
        question = state.get("question", "")
        data = state.get("data", {})
        intent = state.get("intent") or {}
        intent_type = intent.get("type", "data")
        chat_history = state.get("chat_history", [])

        # Check if rewrite needed
        validation = state.get("validation", {})
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
            chat_history=chat_history,
            search_condition=intent.get("search_condition"),
        )

        # Call LLM with JSON mode
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
            stats = result.get("stats", {})

        except json.JSONDecodeError:
            # Fallback: treat entire response as text
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
        }

    def generate_stream(self, state: AgentState) -> Generator[str, None, dict]:
        """
        Generate response with streaming.

        Note: Streaming doesn't support JSON mode well,
        so we collect full response and parse at the end.
        """
        question = state.get("question", "")
        data = state.get("data", {})
        intent = state.get("intent", {})
        intent_type = intent.get("type", "data")

        # Check if rewrite needed
        validation = state.get("validation", {})
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
            search_condition=intent.get("search_condition"),
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
