"""Analyst agent - interprets data and generates responses."""

import json
from typing import Generator
from google import genai
from google.genai import types

import config
from agent.base import BaseOutputAgent
from agent.state import AgentState, UsageStats
from agent.prompts import get_prompt
from agent.pricing import calculate_cost


class Analyst(BaseOutputAgent):
    """
    Interprets data and writes user-facing responses.

    This agent:
    1. Receives data from Data Agent
    2. Analyzes and interprets the data
    3. Writes a clear, factual response
    4. ONLY uses facts from the provided data
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

    def _format_data(self, state: AgentState) -> str:
        """Format data for the prompt."""
        data = state.get("data", {})
        sql_queries = state.get("sql_queries", [])

        # Build data summary
        parts = []

        # Add SQL results
        for i, query in enumerate(sql_queries):
            parts.append(f"### Query {i+1}")
            parts.append(f"SQL: {query.get('query', 'N/A')}")
            parts.append(f"Rows: {query.get('row_count', 0)}")
            if query.get("error"):
                parts.append(f"Error: {query['error']}")
            elif query.get("rows"):
                # Show first 20 rows as JSON
                rows = query["rows"][:20]
                parts.append(f"Data:\n```json\n{json.dumps(rows, indent=2, default=str)}\n```")

        # Add validation info if present
        if data.get("validation"):
            parts.append(f"\n### Data Validation")
            parts.append(f"Status: {data['validation'].get('status')}")
            if data['validation'].get('reason'):
                parts.append(f"Note: {data['validation']['reason']}")

        return "\n".join(parts) if parts else "No data available."

    def generate(self, state: AgentState) -> str:
        """Generate analysis response."""
        question = state.get("question", "")
        data_str = self._format_data(state)

        # Check if this is a rewrite request
        feedback = state.get("validation", {}).get("feedback", "")
        if feedback and state.get("validation_attempts", 0) > 0:
            prompt = get_prompt(
                "analyst_rewrite",
                question=question,
                data=data_str,
                previous_response=state.get("response", ""),
                feedback=feedback,
                issues=state.get("validation", {}).get("issues", [])
            )
        else:
            prompt = get_prompt("analyst", question=question, data=data_str)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=2000,
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
        """Generate response with streaming."""
        question = state.get("question", "")
        data_str = self._format_data(state)

        # Check if this is a rewrite request
        feedback = state.get("validation", {}).get("feedback", "")
        if feedback and state.get("validation_attempts", 0) > 0:
            prompt = get_prompt(
                "analyst_rewrite",
                question=question,
                data=data_str,
                previous_response=state.get("response", ""),
                feedback=feedback,
                issues=state.get("validation", {}).get("issues", [])
            )
        else:
            prompt = get_prompt("analyst", question=question, data=data_str)

        full_text = ""
        total_input = 0
        total_output = 0
        total_thinking = 0

        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=2000,
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
