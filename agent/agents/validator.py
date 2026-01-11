"""Validator agent - checks responses against data for hallucinations."""

import json
import re
from google import genai
from google.genai import types

import config
from agent.state import AgentState, ValidationResult, UsageStats
from agent.prompts import get_prompt
from agent.pricing import calculate_cost


def extract_json(text: str) -> dict | None:
    """Extract JSON from text that may contain markdown code blocks or other text."""
    text = text.strip()

    # Try to find JSON in code blocks first
    code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Last resort: try parsing the whole text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


class Validator:
    """
    Validates responses against the source data.

    This agent:
    1. Compares the response to the actual data
    2. Checks for hallucinated facts, dates, percentages
    3. Returns validation status and feedback

    NOT based on BaseOutputAgent because it has special return type.
    """

    name = "validator"
    agent_type = "validator"

    # Maximum validation attempts before forcing approval
    max_attempts = 3

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        # Use same model as analyst for consistent validation
        self.model = config.GEMINI_MODEL
        self._last_usage = UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def _format_data(self, state: AgentState) -> str:
        """Format data for validation prompt."""
        sql_queries = state.get("sql_queries", [])

        parts = []
        for query in sql_queries:
            if query.get("rows"):
                parts.append(json.dumps(query["rows"][:50], indent=2, default=str))

        return "\n".join(parts) if parts else "{}"

    def validate(self, state: AgentState) -> ValidationResult:
        """
        Validate the response against the data.

        Returns:
            ValidationResult with status, issues, and feedback
        """
        response = state.get("response", "")
        data_str = self._format_data(state)
        attempts = state.get("validation_attempts", 0)

        # If max attempts reached, force approval
        if attempts >= self.max_attempts:
            return ValidationResult(
                status="ok",
                issues=["Max validation attempts reached, auto-approved"],
                feedback=""
            )

        # For concept/hypothetical routes, skip detailed validation
        route = state.get("route")
        if route in ["concept", "hypothetical"]:
            return ValidationResult(
                status="ok",
                issues=[],
                feedback=""
            )

        prompt = get_prompt("validator", data=data_str, response=response)

        try:
            result = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=500,
                )
            )

            # Track usage
            if result.usage_metadata:
                input_tokens = result.usage_metadata.prompt_token_count or 0
                output_tokens = result.usage_metadata.candidates_token_count or 0
                thinking_tokens = getattr(result.usage_metadata, 'thoughts_token_count', 0) or 0
                cost = calculate_cost(input_tokens, output_tokens, thinking_tokens)

                self._last_usage = UsageStats(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    thinking_tokens=thinking_tokens,
                    cost_usd=cost
                )

            # Parse JSON response using robust extraction
            validation = extract_json(result.text)

            if validation is None:
                # If can't parse, assume ok
                return ValidationResult(
                    status="ok",
                    issues=["Validation response not parseable"],
                    feedback=""
                )

            return ValidationResult(
                status=validation.get("status", "ok"),
                issues=validation.get("issues", []),
                feedback=validation.get("feedback", "")
            )
        except Exception as e:
            # On error, don't block - approve with warning
            return ValidationResult(
                status="ok",
                issues=[f"Validation error: {str(e)}"],
                feedback=""
            )

    def __call__(self, state: AgentState) -> dict:
        """
        Process state and return updates.

        This is called by LangGraph when the node executes.
        """
        import time
        start_time = time.time()

        validation = self.validate(state)
        duration_ms = int((time.time() - start_time) * 1000)

        # Merge usage stats
        current_usage = state.get("usage", {})
        merged_usage = UsageStats(
            input_tokens=current_usage.get("input_tokens", 0) + self._last_usage.get("input_tokens", 0),
            output_tokens=current_usage.get("output_tokens", 0) + self._last_usage.get("output_tokens", 0),
            thinking_tokens=current_usage.get("thinking_tokens", 0) + self._last_usage.get("thinking_tokens", 0),
            cost_usd=current_usage.get("cost_usd", 0.0) + self._last_usage.get("cost_usd", 0.0),
        )

        return {
            "validation": validation,
            "validation_attempts": state.get("validation_attempts", 0) + 1,
            "usage": merged_usage,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
        }

    def get_usage(self) -> UsageStats:
        """Return usage from last validation."""
        return self._last_usage

    def get_trace_data(
        self,
        state: AgentState,
        validation: ValidationResult,
        duration_ms: int
    ) -> dict:
        """Return data for request_traces logging."""
        return {
            "agent_name": self.name,
            "agent_type": self.agent_type,
            "input_data": {
                "response_length": len(state.get("response", "")),
                "data_rows": sum(q.get("row_count", 0) for q in state.get("sql_queries", []))
            },
            "output_data": {"validation": dict(validation)},
            "validation_status": validation.get("status"),
            "validation_issues": validation.get("issues"),
            "validation_feedback": validation.get("feedback"),
            "input_tokens": self._last_usage.get("input_tokens", 0),
            "output_tokens": self._last_usage.get("output_tokens", 0),
            "cost_usd": self._last_usage.get("cost_usd", 0.0),
            "duration_ms": duration_ms,
        }
