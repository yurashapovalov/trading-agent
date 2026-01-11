"""Educator agent - explains trading concepts without data."""

from typing import Generator
from google import genai
from google.genai import types

import config
from agent.base import BaseOutputAgent
from agent.state import AgentState, UsageStats
from agent.prompts import get_prompt
from agent.pricing import calculate_cost


class Educator(BaseOutputAgent):
    """
    Explains trading concepts and theory.

    This agent:
    1. Explains what terms mean (RSI, MACD, etc.)
    2. Describes general principles
    3. Does NOT reference specific data or statistics
    """

    name = "educator"
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

    def generate(self, state: AgentState) -> str:
        """Generate concept explanation."""
        question = state.get("question", "")

        prompt = get_prompt("educator", question=question)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,  # Slightly more creative for explanations
                max_output_tokens=1500,
            )
        )

        # Track usage
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

        return response.text or ""

    def generate_stream(self, state: AgentState) -> Generator[str, None, str]:
        """Generate explanation with streaming."""
        question = state.get("question", "")

        prompt = get_prompt("educator", question=question)

        full_text = ""
        total_input = 0
        total_output = 0
        total_thinking = 0

        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
                max_output_tokens=1500,
            )
        ):
            if chunk.usage_metadata:
                total_input = chunk.usage_metadata.prompt_token_count or 0
                total_output = chunk.usage_metadata.candidates_token_count or 0
                total_thinking = getattr(chunk.usage_metadata, 'thoughts_token_count', 0) or 0

            if chunk.text:
                yield chunk.text
                full_text += chunk.text

        # Update usage after streaming
        cost = calculate_cost(total_input, total_output, total_thinking)
        self._last_usage = UsageStats(
            input_tokens=total_input,
            output_tokens=total_output,
            thinking_tokens=total_thinking,
            cost_usd=cost
        )

        return full_text

    def get_usage(self) -> UsageStats:
        """Return usage from last generation."""
        return self._last_usage
