"""
Understander v2 - senior trading data analyst.

Deeply understands user questions and formulates detailed specifications
for SQL Agent. Uses thinking for complex analysis type detection.

Supports human-in-the-loop via LangGraph interrupt() for clarifications.
"""

import json
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from langgraph.types import interrupt

import config
from agent.state import AgentState, Intent, UsageStats
from agent.pricing import calculate_cost
from agent.capabilities import (
    get_capabilities_prompt,
    DEFAULT_SYMBOL,
    DEFAULT_GRANULARITY,
)
from agent.modules.sql import get_data_range
from agent.prompts.understander import get_understander_prompt


# =============================================================================
# Understander Agent v2
# =============================================================================

class Understander:
    """
    Senior trading data analyst that understands user intent.

    Uses Gemini with thinking to:
    - Deeply understand what trader wants to know
    - Detect analysis type (FILTER, EVENT, DISTRIBUTION, etc.)
    - Generate detailed_spec for SQL Agent
    """

    name = "understander"
    agent_type = "routing"

    def __init__(self):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.model = config.GEMINI_MODEL  # Smart model with thinking
        self._last_usage = UsageStats(
            input_tokens=0,
            output_tokens=0,
            thinking_tokens=0,
            cost_usd=0.0
        )

    def __call__(self, state: AgentState) -> dict:
        """Parse question and return Intent.

        Uses interrupt() for human-in-the-loop clarifications.
        When clarification is needed:
        1. Graph pauses and returns question to user
        2. User responds
        3. Graph resumes, response is added to context
        4. LLM re-analyzes with full context
        """
        question = state.get("question", "")
        chat_history = list(state.get("chat_history", []))  # Copy to avoid mutation

        # Call LLM with JSON mode
        intent = self._parse_with_llm(question, chat_history)

        # If clarification needed, interrupt and wait for user response
        if intent.get("needs_clarification"):
            clarification_question = intent.get("clarification_question", "Уточните ваш запрос")
            suggestions = intent.get("suggestions", [])

            # Interrupt graph - pauses here until resume
            user_response = interrupt({
                "type": "clarification",
                "question": clarification_question,
                "suggestions": suggestions,
            })

            # After resume - user_response contains user's answer
            # Add exchange to chat history and re-parse
            chat_history.append({"role": "assistant", "content": clarification_question})
            chat_history.append({"role": "user", "content": user_response})

            # Re-call LLM with updated context
            intent = self._parse_with_llm(question, chat_history)

        return {
            "intent": intent,
            "usage": self._last_usage,
            "agents_used": [self.name],
            "step_number": state.get("step_number", 0) + 1,
        }

    def _get_data_info(self) -> str:
        """Get available data info."""
        data_range = get_data_range("NQ")
        if data_range:
            return (
                f"Символ: NQ\n"
                f"Период данных: {data_range['start_date']} — {data_range['end_date']}\n"
                f"Торговых дней: {data_range['trading_days']}"
            )
        return "Данные: NQ"

    def _build_prompt(self, question: str, chat_history: list) -> str:
        """Build full prompt for LLM using external template."""
        # Format chat history
        history_str = ""
        if chat_history:
            for msg in chat_history[-config.CHAT_HISTORY_LIMIT:]:
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_str += f"{role}: {msg.get('content', '')}\n"

        return get_understander_prompt(
            capabilities=get_capabilities_prompt(),
            data_info=self._get_data_info(),
            today=datetime.now().strftime("%Y-%m-%d"),
            question=question,
            chat_history=history_str,
        )

    def _parse_with_llm(self, question: str, chat_history: list) -> Intent:
        """Call LLM with thinking and parse response into Intent."""
        try:
            prompt = self._build_prompt(question, chat_history)

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=1.0,  # Recommended for thinking models
                    thinking_config=types.ThinkingConfig(include_thoughts=True),
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["data", "concept", "chitchat", "out_of_scope"]
                            },
                            "symbol": {"type": "string"},
                            "period_start": {"type": "string"},
                            "period_end": {"type": "string"},
                            "granularity": {
                                "type": "string",
                                "enum": ["period", "daily", "weekly", "monthly", "quarterly", "yearly", "hourly", "weekday"]
                            },
                            "detailed_spec": {"type": "string"},  # Detailed specification for SQL Agent
                            "search_condition": {"type": "string"},  # DEPRECATED
                            "concept": {"type": "string"},
                            "response_text": {"type": "string"},
                            "needs_clarification": {"type": "boolean"},
                            "clarification_question": {"type": "string"},
                            "suggestions": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["type"]
                    }
                )
            )

            # Track usage including thinking tokens
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

            # Parse JSON response
            data = json.loads(response.text)
            return self._build_intent(data)

        except Exception as e:
            # Fallback to default intent on error
            print(f"Understander error: {e}")
            return self._default_intent()

    def _build_intent(self, data: dict) -> Intent:
        """Build Intent from parsed data."""
        intent_type = data.get("type", "data")

        intent: Intent = {
            "type": intent_type,
            "symbol": data.get("symbol") or DEFAULT_SYMBOL,
            # needs_clarification is handled via interrupt(), not stored in final intent
            "needs_clarification": data.get("needs_clarification", False),
            "clarification_question": data.get("clarification_question"),
            "suggestions": data.get("suggestions", []),
        }

        # Add type-specific fields
        if intent_type == "data":
            intent["period_start"] = data.get("period_start")
            intent["period_end"] = data.get("period_end")
            intent["granularity"] = data.get("granularity") or DEFAULT_GRANULARITY
            intent["detailed_spec"] = data.get("detailed_spec")
            intent["search_condition"] = data.get("search_condition")  # DEPRECATED

            # Default period: ALL available data (more data = better analytics)
            if not intent["period_start"] or not intent["period_end"]:
                intent["period_start"], intent["period_end"] = self._full_data_range()

        if intent_type == "concept":
            intent["concept"] = data.get("concept", "")

        if intent_type in ("chitchat", "out_of_scope"):
            intent["response_text"] = data.get("response_text", "")

        return intent

    def _default_intent(self) -> Intent:
        """Return default intent for fallback."""
        start, end = self._full_data_range()
        return Intent(
            type="data",
            symbol=DEFAULT_SYMBOL,
            period_start=start,
            period_end=end,
            granularity=DEFAULT_GRANULARITY,
            needs_clarification=False,
        )

    def _full_data_range(self) -> tuple[str, str]:
        """Get full available data range (default for all queries)."""
        data_range = get_data_range("NQ")
        if data_range:
            return data_range['start_date'], data_range['end_date']

        # Fallback - wide range
        return "2008-01-01", datetime.now().strftime("%Y-%m-%d")
