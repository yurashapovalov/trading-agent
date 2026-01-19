"""
Responder agent — user-facing communication.

Handles ALL user communication:
- Expert preview before data arrives
- Concept explanations
- Clarification requests
- Greetings
- Not supported explanations

Generates data card title for query results.
"""

import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

import config
from agent.state import AgentState, UsageStats, get_current_question
from agent.prompts.responder import get_responder_prompt
from agent.pricing import calculate_cost
from langchain_core.messages import AIMessage


class ResponderOutput(BaseModel):
    """Structured output schema for Responder.

    Gemini will always return JSON matching this schema.
    """
    title: str | None = Field(
        default=None,
        description="Short title for data card (3-6 words). Only for offer_analysis type."
    )
    response: str = Field(
        description="Response text to show the user."
    )

# LangGraph streaming support
try:
    from langgraph.config import get_stream_writer
    HAS_STREAM_WRITER = True
except ImportError:
    HAS_STREAM_WRITER = False
    get_stream_writer = None


class Responder:
    """
    Responder — the voice of askbar.ai.

    Handles all user-facing communication with expert context.
    Streams responses in real-time.

    Usage:
        responder = Responder()
        result = responder(state)
        # result["response"] = text response
        # result["data_title"] = title for data card (if query type)
    """

    name = "responder"
    agent_type = "communication"

    def __init__(self):
        """Initialize Gemini client."""
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_LITE_MODEL  # Fast and cheap
        self._last_usage = UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def __call__(self, state: AgentState) -> dict:
        """
        Generate response based on composer result.

        Reads from state:
        - question (from messages)
        - intent.type (composer result type)
        - intent.parser_output (parsed entities)
        - intent.symbol
        - intent.holiday_info
        - intent.event_info
        - composer_result (QuerySpec for query type, etc.)

        Returns:
        - response: text to show user
        - data_title: title for data card (if query type)
        - messages: AIMessage for checkpointer
        """
        question = get_current_question(state)
        intent = state.get("intent") or {}

        result_type = intent.get("type", "greeting")
        parser_output = intent.get("parser_output", {})
        symbol = intent.get("symbol", "NQ")
        holiday_info = intent.get("holiday_info")
        event_info = intent.get("event_info")

        # Get type-specific info from intent
        query_spec = None
        clarification_field = None
        clarification_options = None
        concept = None
        not_supported_reason = None
        data_preview = None
        row_count = None

        if result_type == "query" or result_type == "data":
            query_spec = intent.get("query_spec", {})
        elif result_type == "clarification":
            clarification_field = intent.get("field")
            clarification_options = intent.get("suggestions", [])
        elif result_type == "concept":
            concept = intent.get("concept")
        elif result_type == "out_of_scope" or result_type == "not_supported":
            not_supported_reason = intent.get("response_text", "")
            result_type = "not_supported"
        elif result_type == "chitchat":
            # Map chitchat subtypes based on parser's "what" field
            what = parser_output.get("what", "greeting").lower()
            if "insult" in what or "негатив" in what:
                result_type = "insult"
            elif "feedback" in what or "correction" in what or "error" in what:
                result_type = "feedback"
            elif "thank" in what or "спасибо" in what:
                result_type = "thanks"
            elif "bye" in what or "goodbye" in what or "пока" in what:
                result_type = "goodbye"
            else:
                result_type = "greeting"
        elif result_type == "no_data":
            row_count = 0
        elif result_type == "data_summary":
            data_preview = intent.get("data_preview", "")
            row_count = intent.get("row_count", 0)
        elif result_type == "offer_analysis":
            row_count = intent.get("row_count", 0)

        # Build prompt
        system_prompt, user_prompt = get_responder_prompt(
            question=question,
            result_type=result_type,
            parsed_entities=parser_output,
            symbol=symbol,
            query_spec=query_spec,
            clarification_field=clarification_field,
            clarification_options=clarification_options,
            concept=concept,
            not_supported_reason=not_supported_reason,
            event_info=event_info,
            holiday_info=holiday_info,
            data_preview=data_preview,
            row_count=row_count,
        )

        # Try streaming
        writer = None
        if HAS_STREAM_WRITER:
            try:
                writer = get_stream_writer()
            except Exception:
                pass

        if writer:
            return self._generate_with_streaming(system_prompt, user_prompt, writer, state, result_type)
        else:
            return self._generate_batch(system_prompt, user_prompt, state, result_type)

    def _generate_with_streaming(
        self,
        system_prompt: str,
        user_prompt: str,
        writer,
        state: AgentState,
        result_type: str,
    ) -> dict:
        """Generate with real-time streaming and structured output schema."""
        full_text = ""
        total_input = 0
        total_output = 0

        try:
            for chunk in self.client.models.generate_content_stream(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=1.0,
                    response_mime_type="application/json",
                    response_schema=ResponderOutput,  # Enforce JSON schema
                )
            ):
                if chunk.usage_metadata:
                    total_input = chunk.usage_metadata.prompt_token_count or 0
                    total_output = chunk.usage_metadata.candidates_token_count or 0

                if chunk.text:
                    full_text += chunk.text

            # Parse JSON response
            response_text, data_title = self._parse_response(full_text, result_type)

            # Send data_title first (even if response is empty)
            if data_title:
                writer({"type": "data_title", "title": data_title})

            # Stream the response text (only if not empty)
            if response_text:
                writer({"type": "text_delta", "agent": self.name, "content": response_text})

            # Update usage
            cost = calculate_cost(
                input_tokens=total_input,
                output_tokens=total_output,
                model=self.model,
            )
            self._last_usage = UsageStats(
                input_tokens=total_input,
                output_tokens=total_output,
                thinking_tokens=0,
                cost_usd=cost
            )

        except Exception as e:
            response_text = f"Error: {e}"
            data_title = None

        return self._build_result(response_text, data_title, state, result_type)

    def _generate_batch(
        self,
        system_prompt: str,
        user_prompt: str,
        state: AgentState,
        result_type: str,
    ) -> dict:
        """Generate in batch mode with structured output schema."""
        try:
            response_obj = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=1.0,
                    response_mime_type="application/json",
                    response_schema=ResponderOutput,  # Enforce JSON schema
                )
            )

            self._track_usage(response_obj)
            response_text, data_title = self._parse_response(response_obj.text, result_type)

        except Exception as e:
            response_text = f"Error: {e}"
            data_title = None

        return self._build_result(response_text, data_title, state, result_type)

    def _parse_response(self, text: str, result_type: str) -> tuple[str, str | None]:
        """Parse JSON response from LLM."""
        try:
            # Strip markdown fences if present
            cleaned = text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # Try to parse as JSON
            data = json.loads(cleaned)
            response_text = data.get("response", text)
            # Title only for offer_analysis (>5 rows with DataCard)
            data_title = data.get("title") if result_type == "offer_analysis" else None
            return response_text, data_title
        except json.JSONDecodeError:
            # If not JSON, use raw text
            return text, None

    def _build_result(
        self,
        response_text: str,
        data_title: str | None,
        state: AgentState,
        result_type: str,
    ) -> dict:
        """Build result dict."""
        result = {
            "response": response_text,
            "usage": self._last_usage,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
            "messages": [AIMessage(content=response_text)],
        }

        if data_title:
            result["data_title"] = data_title

        # Pass through intent for routing
        intent = state.get("intent") or {}
        result["intent"] = intent

        return result

    def _track_usage(self, response) -> None:
        """Track token usage."""
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0
            cached_tokens = getattr(response.usage_metadata, 'cached_content_token_count', 0) or 0
            cost = calculate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                model=self.model,
            )

            self._last_usage = UsageStats(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=0,
                cost_usd=cost
            )

    def get_usage(self) -> UsageStats:
        """Return usage from last generation."""
        return self._last_usage


# Singleton
responder = Responder()
